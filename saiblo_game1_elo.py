#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import random
import re
import sqlite3
import sys
import time
import traceback
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from config_runtime import load_config  # noqa: E402
from saiblo_tools import api_download, api_request, create_room_match, resolve_token  # noqa: E402


RUNTIME_DIR = ROOT_DIR / "autolab" / "runtime" / "saiblo_game1_elo"
DEFAULT_DB = RUNTIME_DIR / "matches.sqlite3"
DEFAULT_LATEST = RUNTIME_DIR / "latest.json"

PENDING_STATES = {"", "准备中", "评测中", "队列中", "等待中", "Pending", "Running", "Queued", "Queueing"}
SUCCESS_STATES = {"评测成功", "Finished", "Success", "Succeeded"}
HEAVY_DETAIL_KEYS = {"message", "debug"}


@dataclass
class CrawlConfig:
    game_id: int = 48
    contest_id: int = 0
    start_match_id: int = 7981000
    db_path: Path = DEFAULT_DB
    latest_path: Path = DEFAULT_LATEST
    list_limit: int = 100
    max_list_pages: int = 50
    gap_probe_per_cycle: int = 50
    max_detail_per_cycle: int = 30
    pending_state_limit: int = 100
    pending_state_max_pages: int = 20
    request_delay: float = 0.35
    loop_interval: float = 60.0
    detail_poll_min: float = 20.0
    detail_poll_max: float = 300.0
    request_timeout: float = 20.0
    replay_timeout: float = 60.0
    replay_concurrency: int = 3
    token: str = ""
    base_rating: float = 1500.0
    max_k: float = 36.0
    min_k: float = 8.0
    provisional_games: float = 12.0
    reliability_games: float = 30.0
    hp_margin_scale: float = 18.0
    hp_margin_weight: float = 0.35
    supplement_enabled: bool = True
    supplement_interval_min_sec: float = 600.0
    supplement_interval_max_sec: float = 1200.0
    supplement_min_per_cycle: int = 10
    supplement_max_per_cycle: int = 30
    supplement_min_age_sec: float = 7200.0
    supplement_min_games: int = 10
    supplement_candidate_max_games: int = 50
    supplement_max_outstanding: int = 80
    supplement_pair_cap: int = 4
    supplement_request_timeout: float = 60.0
    supplement_excluded_usernames: tuple[str, ...] = ("theend",)


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def read_json_value(raw: str) -> Any:
    decoder = json.JSONDecoder()
    value, _ = decoder.raw_decode(raw.lstrip())
    return value


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def as_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(value)
    except Exception:
        return default


def as_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def parse_time_to_epoch(value: Any) -> float:
    text = str(value or "").strip()
    if not text:
        return 0.0
    for candidate in (text, text.replace("Z", "+00:00")):
        try:
            dt = datetime.fromisoformat(candidate)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.timestamp()
        except Exception:
            pass
    try:
        from email.utils import parsedate_to_datetime

        dt = parsedate_to_datetime(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except Exception:
        return 0.0


def normalize_code_id(value: Any) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return ""
    compact = re.sub(r"[^0-9a-f]", "", text)
    return compact or text.replace("-", "")


def is_auth_error(exc: BaseException) -> bool:
    text = str(exc)
    return "HTTP 401" in text or "Authentication credentials" in text or "token not valid" in text


def is_finished_state(state: Any) -> bool:
    return str(state or "").strip() not in PENDING_STATES


def is_success_state(state: Any) -> bool:
    return str(state or "").strip() in SUCCESS_STATES


def compact_error(exc: BaseException) -> str:
    text = str(exc).strip().replace("\n", " | ")
    return text[:1000]


def normalize_username(value: Any) -> str:
    return str(value or "").strip().lower()


def excluded_supplement_usernames(cfg: CrawlConfig) -> set[str]:
    return {normalize_username(item) for item in cfg.supplement_excluded_usernames if normalize_username(item)}


def is_supplement_excluded(row: dict[str, Any], cfg: CrawlConfig) -> bool:
    return normalize_username(row.get("username")) in excluded_supplement_usernames(cfg)


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS matches (
            match_id INTEGER PRIMARY KEY,
            game_id INTEGER,
            contest_id INTEGER,
            state TEXT NOT NULL DEFAULT '',
            create_time TEXT NOT NULL DEFAULT '',
            logic_version INTEGER,
            judger_address TEXT NOT NULL DEFAULT '',
            error TEXT NOT NULL DEFAULT '',
            ignored INTEGER NOT NULL DEFAULT 0,
            terminal INTEGER NOT NULL DEFAULT 0,
            success INTEGER NOT NULL DEFAULT 0,
            detail_status TEXT NOT NULL DEFAULT '',
            replay_status TEXT NOT NULL DEFAULT '',
            rounds INTEGER,
            final_hp0 INTEGER,
            final_hp1 INTEGER,
            winner_seat INTEGER,
            score0 REAL,
            score1 REAL,
            detail_json TEXT NOT NULL DEFAULT '',
            first_seen_at TEXT NOT NULL DEFAULT '',
            last_seen_at TEXT NOT NULL DEFAULT '',
            detail_fetched_at TEXT NOT NULL DEFAULT '',
            replay_parsed_at TEXT NOT NULL DEFAULT '',
            next_poll_at REAL NOT NULL DEFAULT 0,
            poll_count INTEGER NOT NULL DEFAULT 0,
            retry_count INTEGER NOT NULL DEFAULT 0,
            last_error TEXT NOT NULL DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS match_players (
            match_id INTEGER NOT NULL,
            seat INTEGER NOT NULL,
            username TEXT NOT NULL DEFAULT '',
            user_id INTEGER,
            code_id TEXT NOT NULL DEFAULT '',
            entity TEXT NOT NULL DEFAULT '',
            entity_id INTEGER,
            language TEXT NOT NULL DEFAULT '',
            version INTEGER,
            remark TEXT NOT NULL DEFAULT '',
            commit_id TEXT NOT NULL DEFAULT '',
            rank INTEGER,
            score REAL,
            end_state TEXT NOT NULL DEFAULT '',
            exit_code INTEGER,
            stderr TEXT NOT NULL DEFAULT '',
            is_remote INTEGER NOT NULL DEFAULT 0,
            raw_json TEXT NOT NULL DEFAULT '',
            first_seen_at TEXT NOT NULL DEFAULT '',
            last_seen_at TEXT NOT NULL DEFAULT '',
            PRIMARY KEY (match_id, seat)
        );

        CREATE TABLE IF NOT EXISTS versions (
            code_id TEXT PRIMARY KEY,
            username TEXT NOT NULL DEFAULT '',
            user_id INTEGER,
            entity TEXT NOT NULL DEFAULT '',
            entity_id INTEGER,
            language TEXT NOT NULL DEFAULT '',
            version INTEGER,
            remark TEXT NOT NULL DEFAULT '',
            commit_id TEXT NOT NULL DEFAULT '',
            compile_status TEXT NOT NULL DEFAULT '',
            ladder_score REAL,
            ladder_rank INTEGER,
            contest_id INTEGER,
            source TEXT NOT NULL DEFAULT '',
            first_seen_at TEXT NOT NULL DEFAULT '',
            last_seen_at TEXT NOT NULL DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS crawl_state (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS supplement_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL DEFAULT '',
            match_id INTEGER UNIQUE,
            room_id INTEGER,
            target_code_id TEXT NOT NULL DEFAULT '',
            opponent_code_id TEXT NOT NULL DEFAULT '',
            target_seat INTEGER NOT NULL DEFAULT 0,
            reason TEXT NOT NULL DEFAULT '',
            opponent_reason TEXT NOT NULL DEFAULT '',
            target_games_before INTEGER NOT NULL DEFAULT 0,
            target_active_before INTEGER NOT NULL DEFAULT 0,
            opponent_games_before INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT '',
            error TEXT NOT NULL DEFAULT ''
        );

        CREATE INDEX IF NOT EXISTS idx_matches_poll ON matches(ignored, terminal, next_poll_at);
        CREATE INDEX IF NOT EXISTS idx_matches_create ON matches(create_time, match_id);
        CREATE INDEX IF NOT EXISTS idx_players_code ON match_players(code_id);
        CREATE INDEX IF NOT EXISTS idx_supplement_target ON supplement_requests(target_code_id, created_at);
        CREATE INDEX IF NOT EXISTS idx_supplement_match ON supplement_requests(match_id);
        """
    )
    conn.commit()


def set_state(conn: sqlite3.Connection, key: str, value: Any) -> None:
    conn.execute(
        """
        INSERT INTO crawl_state(key, value, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at
        """,
        (key, json.dumps(value, ensure_ascii=False), now_iso()),
    )


def get_state_map(conn: sqlite3.Connection) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for row in conn.execute("SELECT key, value FROM crawl_state"):
        try:
            out[str(row["key"])] = json.loads(str(row["value"]))
        except Exception:
            out[str(row["key"])] = row["value"]
    return out


def sleep_delay(cfg: CrawlConfig) -> None:
    if cfg.request_delay > 0:
        time.sleep(float(cfg.request_delay))


def safe_json(obj: Any, *, limit: int = 12000) -> str:
    try:
        text = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
    except Exception:
        text = ""
    if len(text) > limit:
        return text[:limit] + "...<truncated>"
    return text


def strip_heavy_detail(detail: dict[str, Any]) -> dict[str, Any]:
    compact: dict[str, Any] = {}
    for key, value in detail.items():
        if key in HEAVY_DETAIL_KEYS:
            continue
        if key == "info" and isinstance(value, list):
            compact[key] = []
            for row in value:
                if not isinstance(row, dict):
                    compact[key].append(row)
                    continue
                item = dict(row)
                if isinstance(item.get("stderr"), str) and len(item["stderr"]) > 2000:
                    item["stderr"] = item["stderr"][:2000] + "...<truncated>"
                compact[key].append(item)
        else:
            compact[key] = value
    return compact


def extract_game_id(row: dict[str, Any]) -> int:
    game = row.get("game")
    if isinstance(game, dict):
        return as_int(game.get("id"), 0)
    return as_int(row.get("game_id"), 0)


def extract_contest_id(row: dict[str, Any]) -> int:
    contest = row.get("contest")
    if isinstance(contest, dict):
        return as_int(contest.get("id"), 0)
    return as_int(contest, 0)


def extract_entity_fields(code: dict[str, Any]) -> tuple[str, int, str]:
    entity = code.get("entity")
    if isinstance(entity, dict):
        return (
            str(entity.get("name") or ""),
            as_int(entity.get("id"), 0) or None,  # type: ignore[return-value]
            str(entity.get("language") or ""),
        )
    return str(entity or ""), None, ""  # type: ignore[return-value]


def player_from_info(match_id: int, seat: int, row: dict[str, Any]) -> dict[str, Any]:
    code = row.get("code") if isinstance(row.get("code"), dict) else {}
    user = row.get("user") if isinstance(row.get("user"), dict) else {}
    entity, entity_id, language = extract_entity_fields(code)
    return {
        "match_id": int(match_id),
        "seat": int(seat),
        "username": str(user.get("username") or row.get("user") or ""),
        "user_id": as_int(user.get("id"), 0) or None,
        "code_id": normalize_code_id(code.get("id")) if isinstance(code, dict) else "",
        "entity": entity,
        "entity_id": entity_id,
        "language": language,
        "version": as_int(code.get("version"), 0) or None if isinstance(code, dict) else None,
        "remark": str(code.get("remark") or "") if isinstance(code, dict) else "",
        "commit_id": str(code.get("commit_id") or "") if isinstance(code, dict) else "",
        "rank": as_int(row.get("rank"), 0) or None,
        "score": row.get("score") if row.get("score") not in ("", None) else None,
        "end_state": str(row.get("end_state") or ""),
        "exit_code": as_int(row.get("exit_code"), 0) if row.get("exit_code") not in ("", None) else None,
        "stderr": str(row.get("stderr") or "")[:2000],
        "is_remote": 1 if bool(row.get("is_remote", False)) else 0,
        "raw_json": safe_json(row, limit=5000),
    }


def upsert_version(conn: sqlite3.Connection, player: dict[str, Any], source: str, ladder_rank: int | None = None, ladder_score: Any = None, contest_id: int | None = None, compile_status: str = "") -> None:
    code_id = str(player.get("code_id") or "")
    if not code_id:
        return
    ts = now_iso()
    conn.execute(
        """
        INSERT INTO versions(
            code_id, username, user_id, entity, entity_id, language, version, remark, commit_id,
            compile_status, ladder_score, ladder_rank, contest_id, source, first_seen_at, last_seen_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(code_id) DO UPDATE SET
            username=COALESCE(NULLIF(excluded.username, ''), versions.username),
            user_id=COALESCE(excluded.user_id, versions.user_id),
            entity=COALESCE(NULLIF(excluded.entity, ''), versions.entity),
            entity_id=COALESCE(excluded.entity_id, versions.entity_id),
            language=COALESCE(NULLIF(excluded.language, ''), versions.language),
            version=COALESCE(excluded.version, versions.version),
            remark=COALESCE(NULLIF(excluded.remark, ''), versions.remark),
            commit_id=COALESCE(NULLIF(excluded.commit_id, ''), versions.commit_id),
            compile_status=COALESCE(NULLIF(excluded.compile_status, ''), versions.compile_status),
            ladder_score=COALESCE(excluded.ladder_score, versions.ladder_score),
            ladder_rank=COALESCE(excluded.ladder_rank, versions.ladder_rank),
            contest_id=COALESCE(excluded.contest_id, versions.contest_id),
            source=excluded.source,
            last_seen_at=excluded.last_seen_at
        """,
        (
            code_id,
            player.get("username") or "",
            player.get("user_id"),
            player.get("entity") or "",
            player.get("entity_id"),
            player.get("language") or "",
            player.get("version"),
            player.get("remark") or "",
            player.get("commit_id") or "",
            compile_status,
            ladder_score,
            ladder_rank,
            contest_id,
            source,
            ts,
            ts,
        ),
    )


def upsert_player(conn: sqlite3.Connection, player: dict[str, Any], source: str = "match") -> None:
    ts = now_iso()
    conn.execute(
        """
        INSERT INTO match_players(
            match_id, seat, username, user_id, code_id, entity, entity_id, language, version, remark,
            commit_id, rank, score, end_state, exit_code, stderr, is_remote, raw_json, first_seen_at, last_seen_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(match_id, seat) DO UPDATE SET
            username=excluded.username,
            user_id=excluded.user_id,
            code_id=excluded.code_id,
            entity=excluded.entity,
            entity_id=excluded.entity_id,
            language=COALESCE(NULLIF(excluded.language, ''), match_players.language),
            version=excluded.version,
            remark=excluded.remark,
            commit_id=excluded.commit_id,
            rank=excluded.rank,
            score=excluded.score,
            end_state=excluded.end_state,
            exit_code=excluded.exit_code,
            stderr=excluded.stderr,
            is_remote=excluded.is_remote,
            raw_json=excluded.raw_json,
            last_seen_at=excluded.last_seen_at
        """,
        (
            player["match_id"],
            player["seat"],
            player.get("username") or "",
            player.get("user_id"),
            player.get("code_id") or "",
            player.get("entity") or "",
            player.get("entity_id"),
            player.get("language") or "",
            player.get("version"),
            player.get("remark") or "",
            player.get("commit_id") or "",
            player.get("rank"),
            player.get("score"),
            player.get("end_state") or "",
            player.get("exit_code"),
            player.get("stderr") or "",
            int(player.get("is_remote") or 0),
            player.get("raw_json") or "",
            ts,
            ts,
        ),
    )
    upsert_version(conn, player, source=source)


def upsert_match_shell(conn: sqlite3.Connection, row: dict[str, Any], cfg: CrawlConfig, detail_status: str = "list") -> int:
    match_id = as_int(row.get("id"), 0)
    if match_id <= 0:
        return 0
    game_id = extract_game_id(row)
    contest_id = extract_contest_id(row)
    state = str(row.get("state") or "")
    terminal = 1 if is_finished_state(state) else 0
    success = 1 if is_success_state(state) else 0
    ignored = 1 if game_id and game_id != int(cfg.game_id) else 0
    compact = strip_heavy_detail(row)
    ts = now_iso()
    next_poll = 0.0 if terminal else time.time() + cfg.detail_poll_min
    info = row.get("info", [])
    score0 = score1 = None
    if isinstance(info, list):
        if len(info) > 0 and isinstance(info[0], dict):
            score0 = info[0].get("score")
        if len(info) > 1 and isinstance(info[1], dict):
            score1 = info[1].get("score")
    conn.execute(
        """
        INSERT INTO matches(
            match_id, game_id, contest_id, state, create_time, logic_version, judger_address, error,
            ignored, terminal, success, detail_status, score0, score1, detail_json,
            first_seen_at, last_seen_at, next_poll_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(match_id) DO UPDATE SET
            game_id=COALESCE(excluded.game_id, matches.game_id),
            contest_id=COALESCE(excluded.contest_id, matches.contest_id),
            state=excluded.state,
            create_time=COALESCE(NULLIF(excluded.create_time, ''), matches.create_time),
            logic_version=COALESCE(excluded.logic_version, matches.logic_version),
            judger_address=COALESCE(NULLIF(excluded.judger_address, ''), matches.judger_address),
            error=COALESCE(NULLIF(excluded.error, ''), matches.error),
            ignored=excluded.ignored,
            terminal=excluded.terminal,
            success=excluded.success,
            detail_status=CASE
                WHEN matches.detail_status = 'ok' THEN matches.detail_status
                ELSE excluded.detail_status
            END,
            score0=COALESCE(excluded.score0, matches.score0),
            score1=COALESCE(excluded.score1, matches.score1),
            detail_json=CASE
                WHEN matches.detail_status = 'ok' THEN matches.detail_json
                ELSE excluded.detail_json
            END,
            last_seen_at=excluded.last_seen_at,
            next_poll_at=CASE
                WHEN excluded.terminal = 1 THEN matches.next_poll_at
                ELSE MIN(matches.next_poll_at, excluded.next_poll_at)
            END
        """,
        (
            match_id,
            game_id or None,
            contest_id or None,
            state,
            str(row.get("create_time") or row.get("time") or ""),
            as_int(row.get("logic_version"), 0) or None,
            str(row.get("judger_address") or ""),
            str(row.get("error") or ""),
            ignored,
            terminal,
            success,
            detail_status,
            score0,
            score1,
            safe_json(compact),
            ts,
            ts,
            next_poll,
        ),
    )
    if ignored == 0 and isinstance(info, list):
        for seat, p in enumerate(info[:2]):
            if isinstance(p, dict):
                upsert_player(conn, player_from_info(match_id, seat, p), source=detail_status)
    return match_id


def cleanup_ignored_game_rows(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM match_players WHERE match_id IN (SELECT match_id FROM matches WHERE ignored=1)")
    conn.execute(
        """
        DELETE FROM versions
        WHERE source != 'ladder'
          AND code_id NOT IN (
              SELECT DISTINCT p.code_id
              FROM match_players p
              JOIN matches m ON m.match_id=p.match_id
              WHERE m.ignored=0 AND p.code_id != ''
          )
        """
    )


def update_match_detail(conn: sqlite3.Connection, detail: dict[str, Any], cfg: CrawlConfig) -> None:
    match_id = upsert_match_shell(conn, detail, cfg, detail_status="ok")
    if match_id <= 0:
        return
    state = str(detail.get("state") or "")
    terminal = 1 if is_finished_state(state) else 0
    success = 1 if is_success_state(state) else 0
    info = detail.get("info", [])
    score0 = score1 = None
    if isinstance(info, list):
        if len(info) > 0 and isinstance(info[0], dict):
            score0 = info[0].get("score")
        if len(info) > 1 and isinstance(info[1], dict):
            score1 = info[1].get("score")
    poll_count = as_int(conn.execute("SELECT poll_count FROM matches WHERE match_id=?", (match_id,)).fetchone()["poll_count"], 0)
    backoff = min(float(cfg.detail_poll_max), float(cfg.detail_poll_min) * (1.5 ** max(0, poll_count)))
    next_poll = 0.0 if terminal else time.time() + backoff
    conn.execute(
        """
        UPDATE matches
        SET state=?, game_id=COALESCE(?, game_id), contest_id=COALESCE(?, contest_id),
            logic_version=COALESCE(?, logic_version), judger_address=?, error=?,
            terminal=?, success=?, detail_status='ok', score0=COALESCE(?, score0), score1=COALESCE(?, score1),
            detail_fetched_at=?, next_poll_at=?, poll_count=poll_count+1, last_error=''
        WHERE match_id=?
        """,
        (
            state,
            extract_game_id(detail) or None,
            extract_contest_id(detail) or None,
            as_int(detail.get("logic_version"), 0) or None,
            str(detail.get("judger_address") or ""),
            str(detail.get("error") or ""),
            terminal,
            success,
            score0,
            score1,
            now_iso(),
            next_poll,
            match_id,
        ),
    )


def fetch_ladder(conn: sqlite3.Connection, cfg: CrawlConfig) -> dict[str, Any]:
    offset = 0
    limit = 500
    total_rows = 0
    current_codes: set[str] = set()
    while True:
        q = urllib.parse.urlencode({"limit": limit, "offset": offset})
        data = api_request("GET", f"/api/games/{int(cfg.game_id)}/ladders/?{q}", token="", timeout=cfg.request_timeout)
        rows = data.get("results", []) if isinstance(data, dict) else []
        if not isinstance(rows, list):
            rows = []
        for rank, row in enumerate(rows, start=offset + 1):
            if not isinstance(row, dict):
                continue
            code = row.get("code") if isinstance(row.get("code"), dict) else {}
            user = code.get("user") if isinstance(code.get("user"), dict) else {}
            entity, entity_id, language = extract_entity_fields(code)
            player = {
                "code_id": normalize_code_id(code.get("id")),
                "username": str(row.get("user") or user.get("username") or ""),
                "user_id": as_int(user.get("id"), 0) or None,
                "entity": entity,
                "entity_id": entity_id,
                "language": language,
                "version": as_int(code.get("version"), 0) or None,
                "remark": str(code.get("remark") or ""),
                "commit_id": str(code.get("commit_id") or ""),
            }
            if player["code_id"]:
                current_codes.add(str(player["code_id"]))
            upsert_version(
                conn,
                player,
                source="ladder",
                ladder_rank=rank,
                ladder_score=row.get("score"),
                contest_id=extract_contest_id(row) or None,
                compile_status=str(code.get("compile_status") or ""),
            )
            total_rows += 1
        if not isinstance(data, dict) or not data.get("next") or not rows:
            break
        offset += limit
        sleep_delay(cfg)
    if current_codes:
        placeholders = ",".join("?" for _ in current_codes)
        conn.execute(
            f"UPDATE versions SET ladder_rank=NULL, ladder_score=NULL WHERE code_id != '' AND code_id NOT IN ({placeholders})",
            tuple(sorted(current_codes)),
        )
    else:
        conn.execute("UPDATE versions SET ladder_rank=NULL, ladder_score=NULL WHERE code_id != ''")
    set_state(conn, "ladder", {"ok": True, "rows": total_rows, "current_codes": len(current_codes), "updated_at": now_iso()})
    return {"rows": total_rows, "current_codes": len(current_codes)}


def scan_match_list(conn: sqlite3.Connection, cfg: CrawlConfig, token: str) -> dict[str, Any]:
    inserted = 0
    seen = 0
    stop_reason = "max_pages"
    min_id = None
    max_id = None
    for page in range(max(1, int(cfg.max_list_pages))):
        params = {"limit": int(cfg.list_limit), "offset": page * int(cfg.list_limit)}
        if cfg.contest_id > 0:
            params["contest"] = int(cfg.contest_id)
        else:
            params["game"] = int(cfg.game_id)
        q = urllib.parse.urlencode(params)
        data = api_request("GET", f"/api/matches/?{q}", token=token, timeout=cfg.request_timeout)
        rows = data.get("results", []) if isinstance(data, dict) else []
        if not isinstance(rows, list) or not rows:
            stop_reason = "empty_page"
            break
        page_ids: list[int] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            match_id = as_int(row.get("id"), 0)
            if match_id <= 0:
                continue
            seen += 1
            page_ids.append(match_id)
            min_id = match_id if min_id is None else min(min_id, match_id)
            max_id = match_id if max_id is None else max(max_id, match_id)
            if match_id >= int(cfg.start_match_id):
                if upsert_match_shell(conn, row, cfg):
                    inserted += 1
        conn.commit()
        if page_ids and min(page_ids) < int(cfg.start_match_id):
            stop_reason = "reached_start_id"
            break
        if isinstance(data, dict) and not data.get("next"):
            stop_reason = "no_next"
            break
        sleep_delay(cfg)
    out = {
        "ok": True,
        "seen": seen,
        "upserted": inserted,
        "min_id": min_id,
        "max_id": max_id,
        "stop_reason": stop_reason,
        "updated_at": now_iso(),
    }
    set_state(conn, "match_list", out)
    return out


def scan_remote_pending_states(conn: sqlite3.Connection, cfg: CrawlConfig, token: str) -> dict[str, Any]:
    states = ["准备中", "评测中", "队列中", "等待中"]
    active_ids: set[int] = set()
    counts: dict[str, int] = {}
    fetched_by_state: dict[str, int] = {}
    pages_by_state: dict[str, int] = {}
    complete_by_state: dict[str, bool] = {}
    errors: list[dict[str, Any]] = []
    total_count = 0
    limit = max(1, int(cfg.pending_state_limit))
    max_pages = max(1, int(cfg.pending_state_max_pages))

    for state in states:
        fetched = 0
        complete = False
        pages = 0
        try:
            for page in range(max_pages):
                params = {
                    "game": int(cfg.game_id),
                    "state": state,
                    "limit": limit,
                    "offset": page * limit,
                }
                q = urllib.parse.urlencode(params)
                data = api_request("GET", f"/api/matches/?{q}", token=token, timeout=cfg.request_timeout)
                if isinstance(data, dict) and data.get("count") is not None:
                    counts[state] = as_int(data.get("count"), 0)
                rows = data.get("results", []) if isinstance(data, dict) else []
                if not isinstance(rows, list) or not rows:
                    complete = True
                    break
                pages += 1
                for row in rows:
                    if not isinstance(row, dict):
                        continue
                    match_id = as_int(row.get("id"), 0)
                    if match_id <= 0:
                        continue
                    active_ids.add(match_id)
                    fetched += 1
                    if match_id >= int(cfg.start_match_id):
                        upsert_match_shell(conn, row, cfg, detail_status="list")
                conn.commit()
                if isinstance(data, dict) and not data.get("next"):
                    complete = True
                    break
                sleep_delay(cfg)
        except Exception as exc:
            if is_auth_error(exc):
                raise
            errors.append({"state": state, "error": compact_error(exc)})
        fetched_by_state[state] = fetched
        pages_by_state[state] = pages
        if state not in counts:
            counts[state] = fetched
        total_count += int(counts[state])
        complete_by_state[state] = complete

    complete_all = all(complete_by_state.values()) and not errors
    stale_queued = 0
    if complete_all:
        active_list = sorted(active_ids)
        if active_list:
            placeholders = ",".join("?" for _ in active_list)
            params: list[Any] = [int(cfg.start_match_id), *active_list]
            stale_queued = conn.execute(
                f"""
                UPDATE matches
                SET next_poll_at=0
                WHERE ignored=0
                  AND terminal=0
                  AND match_id >= ?
                  AND match_id NOT IN ({placeholders})
                """,
                params,
            ).rowcount
        else:
            stale_queued = conn.execute(
                """
                UPDATE matches
                SET next_poll_at=0
                WHERE ignored=0 AND terminal=0 AND match_id >= ?
                """,
                (int(cfg.start_match_id),),
            ).rowcount
        conn.commit()

    out = {
        "ok": not errors,
        "complete": complete_all,
        "states": counts,
        "fetched_by_state": fetched_by_state,
        "pages_by_state": pages_by_state,
        "complete_by_state": complete_by_state,
        "active_ids_seen": len(active_ids),
        "total": total_count,
        "stale_queued": stale_queued,
        "errors": errors,
        "updated_at": now_iso(),
    }
    set_state(conn, "remote_pending", out)
    return out


def row_exists(conn: sqlite3.Connection, match_id: int) -> bool:
    return conn.execute("SELECT 1 FROM matches WHERE match_id=?", (int(match_id),)).fetchone() is not None


def gap_probe_matches(conn: sqlite3.Connection, cfg: CrawlConfig, token: str, observed_max_id: int | None = None) -> dict[str, Any]:
    max_id = int(observed_max_id or 0)
    if max_id <= 0:
        max_id = db_scalar(conn, "SELECT MAX(match_id) FROM matches WHERE match_id >= ?", (cfg.start_match_id,))
    if max_id < int(cfg.start_match_id):
        out = {"ok": True, "checked": 0, "fetched": 0, "game_matches": 0, "missing_or_forbidden": 0, "errors": 0, "next_id": int(cfg.start_match_id), "updated_at": now_iso()}
        set_state(conn, "gap_probe", out)
        return out

    state = get_state_map(conn)
    next_id = as_int(state.get("gap_probe_next_id"), int(cfg.start_match_id))
    next_id = max(int(cfg.start_match_id), next_id)
    if next_id > max_id:
        out = {"ok": True, "checked": 0, "fetched": 0, "game_matches": 0, "missing_or_forbidden": 0, "errors": 0, "next_id": next_id, "observed_max_id": max_id, "updated_at": now_iso()}
        set_state(conn, "gap_probe", out)
        return out

    checked = 0
    fetched = 0
    game_matches = 0
    missing_or_forbidden = 0
    errors = 0
    limit = max(0, int(cfg.gap_probe_per_cycle))
    stop_id = min(max_id, next_id + max(0, limit - 1))
    cursor_after = stop_id + 1

    for match_id in range(next_id, stop_id + 1):
        checked += 1
        if row_exists(conn, match_id):
            continue
        try:
            detail = api_request("GET", f"/api/matches/{int(match_id)}/", token=token, timeout=cfg.request_timeout)
            if not isinstance(detail, dict):
                raise RuntimeError("invalid detail response")
            fetched += 1
            if extract_game_id(detail) == int(cfg.game_id):
                game_matches += 1
            upsert_match_shell(conn, detail, cfg, detail_status="ok")
            conn.commit()
            sleep_delay(cfg)
        except Exception as exc:
            if is_auth_error(exc):
                raise
            text = str(exc)
            if "HTTP 404" in text or "HTTP 403" in text:
                missing_or_forbidden += 1
                sleep_delay(cfg)
                continue
            errors += 1
            cursor_after = match_id
            break

    set_state(conn, "gap_probe_next_id", cursor_after)
    out = {
        "ok": errors == 0,
        "checked": checked,
        "fetched": fetched,
        "game_matches": game_matches,
        "missing_or_forbidden": missing_or_forbidden,
        "errors": errors,
        "next_id": cursor_after,
        "observed_max_id": max_id,
        "updated_at": now_iso(),
    }
    set_state(conn, "gap_probe", out)
    return out


def parse_replay_metadata(body: bytes) -> dict[str, Any]:
    raw = body.decode("utf-8", errors="replace")
    payload = read_json_value(raw)
    frames: list[Any]
    if isinstance(payload, list):
        frames = payload
    elif isinstance(payload, dict) and isinstance(payload.get("record"), list):
        frames = payload["record"]
    elif isinstance(payload, dict) and isinstance(payload.get("replay"), list):
        frames = payload["replay"]
    else:
        raise RuntimeError(f"unsupported replay root type: {type(payload).__name__}")

    final_state: dict[str, Any] = {}
    for frame in reversed(frames):
        if isinstance(frame, dict) and isinstance(frame.get("round_state"), dict):
            final_state = frame["round_state"]
            break
    if not final_state:
        raise RuntimeError("no round_state found in replay")

    camps = final_state.get("camps", [])
    if not isinstance(camps, list) or len(camps) < 2:
        raise RuntimeError("final round_state.camps missing")
    hp0 = as_int(camps[0], 0)
    hp1 = as_int(camps[1], 0)
    winner = None
    try:
        raw_winner = int(final_state.get("winner", -1))
        if raw_winner in (0, 1):
            winner = raw_winner
    except Exception:
        winner = None
    if winner is None and hp0 != hp1:
        winner = 0 if hp0 > hp1 else 1
    return {
        "rounds": len(frames),
        "final_hp0": hp0,
        "final_hp1": hp1,
        "winner_seat": winner,
        "bytes": len(body),
    }


def infer_winner_from_players(conn: sqlite3.Connection, match_id: int, current: int | None = None) -> int | None:
    if current in (0, 1):
        return current
    rows = list(conn.execute("SELECT seat, rank, score FROM match_players WHERE match_id=? ORDER BY seat", (match_id,)))
    if len(rows) < 2:
        return None
    score0 = rows[0]["score"]
    score1 = rows[1]["score"]
    if score0 is not None and score1 is not None:
        a = as_float(score0, 0.5)
        b = as_float(score1, 0.5)
        if a != b:
            return 0 if a > b else 1
    rank0 = rows[0]["rank"]
    rank1 = rows[1]["rank"]
    if rank0 is not None and rank1 is not None and rank0 != rank1:
        return 0 if as_int(rank0, 999) < as_int(rank1, 999) else 1
    return None


def download_replay_metadata(cfg: CrawlConfig, token: str, match_id: int) -> dict[str, Any]:
    body, _headers = api_download(f"/api/matches/{int(match_id)}/download/", token=token, timeout=cfg.replay_timeout)
    return parse_replay_metadata(body)


def store_replay_metadata(conn: sqlite3.Connection, match_id: int, meta: dict[str, Any]) -> None:
    winner = infer_winner_from_players(conn, match_id, meta.get("winner_seat"))
    conn.execute(
        """
        UPDATE matches
        SET rounds=?, final_hp0=?, final_hp1=?, winner_seat=?, replay_status=?, replay_parsed_at=?, last_error=''
        WHERE match_id=?
        """,
        (
            meta.get("rounds"),
            meta.get("final_hp0"),
            meta.get("final_hp1"),
            winner,
            f"ok:{meta.get('bytes', 0)}",
            now_iso(),
            match_id,
        ),
    )


def parse_and_store_replay(conn: sqlite3.Connection, cfg: CrawlConfig, token: str, match_id: int) -> None:
    store_replay_metadata(conn, match_id, download_replay_metadata(cfg, token, match_id))


def mark_poll_error(conn: sqlite3.Connection, cfg: CrawlConfig, match_id: int, exc: BaseException) -> None:
    backoff = min(float(cfg.detail_poll_max), float(cfg.detail_poll_min) * 4)
    conn.execute(
        """
        UPDATE matches
        SET retry_count=retry_count+1, last_error=?, next_poll_at=?, replay_status=CASE
            WHEN success=1 AND (rounds IS NULL OR final_hp0 IS NULL OR final_hp1 IS NULL) THEN 'error'
            ELSE replay_status
        END
        WHERE match_id=?
        """,
        (compact_error(exc), time.time() + backoff, match_id),
    )


def mark_missing_or_forbidden(conn: sqlite3.Connection, match_id: int, exc: BaseException) -> None:
    conn.execute(
        """
        UPDATE matches
        SET state='missing_or_forbidden', terminal=1, success=0, detail_status='missing',
            last_error=?, next_poll_at=0, retry_count=retry_count+1
        WHERE match_id=?
        """,
        (compact_error(exc), int(match_id)),
    )


def select_matches_to_poll(conn: sqlite3.Connection, cfg: CrawlConfig) -> list[int]:
    now = time.time()
    rows = conn.execute(
        """
        SELECT match_id
        FROM matches
        WHERE ignored=0
          AND match_id >= ?
          AND (
            detail_status != 'ok'
            OR (terminal=0 AND next_poll_at <= ?)
            OR (success=1 AND (rounds IS NULL OR final_hp0 IS NULL OR final_hp1 IS NULL) AND next_poll_at <= ?)
          )
        ORDER BY
          CASE
            WHEN terminal=0 AND next_poll_at <= ? THEN 0
            WHEN detail_status != 'ok' THEN 1
            WHEN success=1 AND (rounds IS NULL OR final_hp0 IS NULL OR final_hp1 IS NULL) THEN 2
            ELSE 3
          END,
          CASE WHEN detail_status='ok' THEN 1 ELSE 0 END,
          match_id DESC
        LIMIT ?
        """,
        (int(cfg.start_match_id), now, now, now, int(cfg.max_detail_per_cycle)),
    ).fetchall()
    return [int(row["match_id"]) for row in rows]


def poll_match_details_for_ids(
    conn: sqlite3.Connection,
    cfg: CrawlConfig,
    token: str,
    ids: list[int],
    fetch_detail_always: bool = True,
) -> dict[str, Any]:
    details = 0
    detail_skipped = 0
    replays = 0
    replay_errors = 0
    errors = 0
    replay_ids: list[int] = []
    for match_id in ids:
        try:
            if not fetch_detail_always:
                row = conn.execute("SELECT detail_status, success, rounds, final_hp0, final_hp1 FROM matches WHERE match_id=?", (match_id,)).fetchone()
                if row and str(row["detail_status"] or "") == "ok":
                    detail_skipped += 1
                    if int(row["success"] or 0) == 1 and (row["rounds"] is None or row["final_hp0"] is None or row["final_hp1"] is None):
                        replay_ids.append(match_id)
                    continue
            detail = api_request("GET", f"/api/matches/{int(match_id)}/", token=token, timeout=cfg.request_timeout)
            if not isinstance(detail, dict):
                raise RuntimeError("invalid detail response")
            update_match_detail(conn, detail, cfg)
            details += 1
            row = conn.execute("SELECT success, rounds, final_hp0, final_hp1 FROM matches WHERE match_id=?", (match_id,)).fetchone()
            if row and int(row["success"] or 0) == 1 and (row["rounds"] is None or row["final_hp0"] is None or row["final_hp1"] is None):
                replay_ids.append(match_id)
            conn.commit()
        except Exception as exc:
            errors += 1
            text = str(exc)
            if "HTTP 404" in text or "HTTP 403" in text:
                mark_missing_or_forbidden(conn, match_id, exc)
            else:
                mark_poll_error(conn, cfg, match_id, exc)
            conn.commit()
            if is_auth_error(exc):
                raise
        sleep_delay(cfg)

    workers = max(1, int(cfg.replay_concurrency))
    workers = min(workers, len(replay_ids)) if replay_ids else 0
    if replay_ids and workers <= 1:
        for match_id in replay_ids:
            try:
                parse_and_store_replay(conn, cfg, token, match_id)
                replays += 1
                conn.commit()
            except Exception as exc:
                errors += 1
                replay_errors += 1
                mark_poll_error(conn, cfg, match_id, exc)
                conn.commit()
                if is_auth_error(exc):
                    raise
            sleep_delay(cfg)
    elif replay_ids:
        auth_error: BaseException | None = None
        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="saiblo-replay") as pool:
            future_map = {pool.submit(download_replay_metadata, cfg, token, match_id): match_id for match_id in replay_ids}
            for future in as_completed(future_map):
                match_id = future_map[future]
                try:
                    meta = future.result()
                    store_replay_metadata(conn, match_id, meta)
                    replays += 1
                except Exception as exc:
                    errors += 1
                    replay_errors += 1
                    mark_poll_error(conn, cfg, match_id, exc)
                    if is_auth_error(exc):
                        auth_error = exc
                conn.commit()
        if auth_error is not None:
            raise auth_error

    out = {
        "ok": True,
        "selected": len(ids),
        "details": details,
        "detail_skipped": detail_skipped,
        "replay_selected": len(replay_ids),
        "replay_concurrency": workers,
        "replays": replays,
        "replay_errors": replay_errors,
        "errors": errors,
        "updated_at": now_iso(),
    }
    set_state(conn, "detail_poll", out)
    conn.commit()
    return out


def poll_match_details(conn: sqlite3.Connection, cfg: CrawlConfig, token: str) -> dict[str, Any]:
    return poll_match_details_for_ids(conn, cfg, token, select_matches_to_poll(conn, cfg))


def select_history_backfill_matches(
    conn: sqlite3.Connection,
    cfg: CrawlConfig,
    usernames: list[str],
    code_ids: list[str],
    limit: int,
) -> list[int]:
    filters: list[str] = []
    params: list[Any] = [int(cfg.start_match_id), time.time()]
    if usernames:
        placeholders = ",".join("?" for _ in usernames)
        filters.append(f"lower(p.username) IN ({placeholders})")
        params.extend(sorted(usernames))
    if code_ids:
        placeholders = ",".join("?" for _ in code_ids)
        filters.append(f"p.code_id IN ({placeholders})")
        params.extend(sorted(code_ids))
    if not filters:
        return []
    where_user = " OR ".join(filters)
    rows = conn.execute(
        f"""
        SELECT DISTINCT m.match_id
        FROM matches m
        JOIN match_players p ON p.match_id=m.match_id
        WHERE m.ignored=0
          AND m.match_id >= ?
          AND m.success=1
          AND (m.rounds IS NULL OR m.final_hp0 IS NULL OR m.final_hp1 IS NULL)
          AND m.next_poll_at <= ?
          AND ({where_user})
        ORDER BY m.match_id ASC
        LIMIT ?
        """,
        (*params, int(limit)),
    ).fetchall()
    return [int(row["match_id"]) for row in rows]


def run_history_backfill(
    conn: sqlite3.Connection,
    cfg: CrawlConfig,
    token: str,
    usernames: list[str],
    code_ids: list[str],
    limit: int,
) -> dict[str, Any]:
    usernames = [normalize_username(item) for item in usernames if normalize_username(item)]
    code_ids = [normalize_code_id(item) for item in code_ids if normalize_code_id(item)]
    total = {
        "selected": 0,
        "details": 0,
        "replay_selected": 0,
        "detail_skipped": 0,
        "replays": 0,
        "replay_errors": 0,
        "errors": 0,
        "batches": 0,
    }
    if not usernames and not code_ids:
        total.update({"ok": False, "reason": "no_filter", "updated_at": now_iso()})
        set_state(conn, "backfill", total)
        conn.commit()
        return total

    while True:
        ids = select_history_backfill_matches(conn, cfg, usernames, code_ids, limit)
        if not ids:
            break
        batch = poll_match_details_for_ids(conn, cfg, token, ids, fetch_detail_always=False)
        total["selected"] += int(batch.get("selected", 0))
        total["details"] += int(batch.get("details", 0))
        total["detail_skipped"] += int(batch.get("detail_skipped", 0))
        total["replay_selected"] += int(batch.get("replay_selected", 0))
        total["replays"] += int(batch.get("replays", 0))
        total["replay_errors"] += int(batch.get("replay_errors", 0))
        total["errors"] += int(batch.get("errors", 0))
        total["batches"] += 1
        set_state(
            conn,
            "backfill",
            {
                **total,
                "last_batch": batch,
                "usernames": usernames,
                "code_ids": code_ids,
                "limit": int(limit),
                "updated_at": now_iso(),
            },
        )
        conn.commit()
        sleep_delay(cfg)

    total.update({
        "ok": True,
        "usernames": usernames,
        "code_ids": code_ids,
        "limit": int(limit),
        "updated_at": now_iso(),
    })
    set_state(conn, "backfill", total)
    conn.commit()
    return total


def expected_score(ra: float, rb: float) -> float:
    return 1.0 / (1.0 + 10.0 ** ((rb - ra) / 400.0))


def k_for_games(games: int, cfg: CrawlConfig) -> float:
    return float(cfg.min_k) + (float(cfg.max_k) - float(cfg.min_k)) / math.sqrt(1.0 + max(0, games) / max(1.0, float(cfg.provisional_games)))


def hp_margin_multiplier(hp0: int | None, hp1: int | None, cfg: CrawlConfig) -> float:
    if hp0 is None or hp1 is None:
        return 1.0
    margin = abs(float(hp0) - float(hp1))
    return 1.0 + float(cfg.hp_margin_weight) * abs(math.tanh(margin / max(1.0, float(cfg.hp_margin_scale))))


def outcome_from_row(row: sqlite3.Row) -> float:
    score0 = row["score0"]
    score1 = row["score1"]
    if score0 is not None and score1 is not None:
        a = as_float(score0, 0.5)
        b = as_float(score1, 0.5)
        if a > b:
            return 1.0
        if a < b:
            return 0.0
        return 0.5
    winner = row["winner_seat"]
    if winner in (0, 1):
        return 1.0 if int(winner) == 0 else 0.0
    hp0 = row["final_hp0"]
    hp1 = row["final_hp1"]
    if hp0 is not None and hp1 is not None and int(hp0) != int(hp1):
        return 1.0 if int(hp0) > int(hp1) else 0.0
    return 0.5


def load_versions(conn: sqlite3.Connection) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in conn.execute("SELECT * FROM versions"):
        code_id = str(row["code_id"] or "")
        if code_id:
            out[code_id] = dict(row)
    return out


def load_self_play_stats(conn: sqlite3.Connection, cfg: CrawlConfig) -> dict[str, dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT
            p0.code_id AS code_id,
            COUNT(*) AS self_play_games,
            MAX(m.match_id) AS last_self_play_match_id
        FROM matches m
        JOIN match_players p0 ON p0.match_id=m.match_id AND p0.seat=0
        JOIN match_players p1 ON p1.match_id=m.match_id AND p1.seat=1
        WHERE m.ignored=0
          AND m.success=1
          AND m.rounds IS NOT NULL
          AND m.final_hp0 IS NOT NULL
          AND m.final_hp1 IS NOT NULL
          AND m.match_id >= ?
          AND p0.code_id != ''
          AND p0.code_id = p1.code_id
        GROUP BY p0.code_id
        """,
        (int(cfg.start_match_id),),
    ).fetchall()
    return {
        str(row["code_id"]): {
            "self_play_games": as_int(row["self_play_games"], 0),
            "last_self_play_match_id": as_int(row["last_self_play_match_id"], 0),
        }
        for row in rows
        if str(row["code_id"] or "")
    }


def load_excluded_version_codes(conn: sqlite3.Connection, cfg: CrawlConfig) -> set[str]:
    excluded = excluded_supplement_usernames(cfg)
    if not excluded:
        return set()
    placeholders = ",".join("?" for _ in excluded)
    rows = conn.execute(
        f"""
        SELECT code_id
        FROM versions
        WHERE code_id != ''
          AND lower(username) IN ({placeholders})
        """,
        tuple(sorted(excluded)),
    ).fetchall()
    return {str(row["code_id"]) for row in rows if str(row["code_id"] or "")}


def load_recent_match_stats(conn: sqlite3.Connection, cfg: CrawlConfig) -> dict[str, dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT
            p.code_id AS code_id,
            MAX(m.match_id) AS last_any_match_id,
            MAX(COALESCE(NULLIF(m.create_time, ''), NULLIF(m.last_seen_at, ''), NULLIF(m.first_seen_at, ''))) AS last_any_seen_at
        FROM match_players p
        JOIN matches m ON m.match_id=p.match_id
        WHERE m.ignored=0
          AND m.match_id >= ?
          AND p.code_id != ''
        GROUP BY p.code_id
        """,
        (int(cfg.start_match_id),),
    ).fetchall()
    return {
        str(row["code_id"]): {
            "last_any_match_id": as_int(row["last_any_match_id"], 0),
            "last_any_seen_at": str(row["last_any_seen_at"] or ""),
        }
        for row in rows
        if str(row["code_id"] or "")
    }


def elo_rows(conn: sqlite3.Connection, cfg: CrawlConfig) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT
            m.match_id, m.create_time, m.rounds, m.final_hp0, m.final_hp1, m.winner_seat,
            m.score0, m.score1,
            p0.code_id AS code0, p1.code_id AS code1
        FROM matches m
        JOIN match_players p0 ON p0.match_id=m.match_id AND p0.seat=0
        JOIN match_players p1 ON p1.match_id=m.match_id AND p1.seat=1
        WHERE m.ignored=0
          AND m.success=1
          AND m.rounds IS NOT NULL
          AND m.final_hp0 IS NOT NULL
          AND m.final_hp1 IS NOT NULL
          AND p0.code_id != ''
          AND p1.code_id != ''
          AND p0.code_id != p1.code_id
        ORDER BY COALESCE(NULLIF(m.create_time, ''), printf('%012d', m.match_id)), m.match_id
        """
    ).fetchall()

    ratings: dict[str, float] = defaultdict(lambda: float(cfg.base_rating))
    stats: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "games": 0,
            "wins": 0,
            "losses": 0,
            "draws": 0,
            "score": 0.0,
            "hp_diff_sum": 0.0,
            "rounds_sum": 0.0,
            "last_match_id": 0,
            "last_seen_at": "",
        }
    )

    matches_used = 0
    for row in rows:
        code0 = str(row["code0"])
        code1 = str(row["code1"])
        result0 = outcome_from_row(row)
        result1 = 1.0 - result0
        r0 = ratings[code0]
        r1 = ratings[code1]
        exp0 = expected_score(r0, r1)
        exp1 = 1.0 - exp0
        g0 = int(stats[code0]["games"])
        g1 = int(stats[code1]["games"])
        k0 = k_for_games(g0, cfg)
        k1 = k_for_games(g1, cfg)
        margin = hp_margin_multiplier(row["final_hp0"], row["final_hp1"], cfg)
        ratings[code0] = r0 + k0 * margin * (result0 - exp0)
        ratings[code1] = r1 + k1 * margin * (result1 - exp1)

        hp0 = as_int(row["final_hp0"], 0)
        hp1 = as_int(row["final_hp1"], 0)
        rounds = as_int(row["rounds"], 0)
        for code, result, hp_diff in ((code0, result0, hp0 - hp1), (code1, result1, hp1 - hp0)):
            s = stats[code]
            s["games"] += 1
            s["score"] += result
            if result > 0.5:
                s["wins"] += 1
            elif result < 0.5:
                s["losses"] += 1
            else:
                s["draws"] += 1
            s["hp_diff_sum"] += hp_diff
            s["rounds_sum"] += rounds
            s["last_match_id"] = int(row["match_id"])
            s["last_seen_at"] = str(row["create_time"] or "")
        matches_used += 1

    versions = load_versions(conn)
    self_play_stats = load_self_play_stats(conn, cfg)
    excluded_version_codes = load_excluded_version_codes(conn, cfg)
    recent_match_stats = load_recent_match_stats(conn, cfg)
    rating_rows: list[dict[str, Any]] = []
    code_ids = set(ratings.keys()) | set(stats.keys()) | set(self_play_stats.keys()) | excluded_version_codes
    for code_id in code_ids:
        rating = ratings.get(code_id, float(cfg.base_rating))
        s = stats[code_id]
        games = int(s["games"])
        self_play_games = as_int(self_play_stats.get(code_id, {}).get("self_play_games"), 0)
        last_self_play_match_id = as_int(self_play_stats.get(code_id, {}).get("last_self_play_match_id"), 0)
        last_any_match_id = as_int(recent_match_stats.get(code_id, {}).get("last_any_match_id"), 0)
        last_any_seen_at = str(recent_match_stats.get(code_id, {}).get("last_any_seen_at") or "")
        reliability = min(1.0, math.sqrt(games / max(1.0, float(cfg.reliability_games)))) if games > 0 else 0.0
        stable_elo = float(cfg.base_rating) + (float(rating) - float(cfg.base_rating)) * reliability
        meta = versions.get(code_id, {})
        rating_source = "rated" if games > 0 else ("default_self_play" if self_play_games > 0 else ("default_excluded" if code_id in excluded_version_codes else "default"))
        rating_rows.append(
            {
                "code_id": code_id,
                "elo": round(stable_elo, 2),
                "raw_elo": round(float(rating), 2),
                "reliability": round(reliability, 4),
                "rating_source": rating_source,
                "games": games,
                "self_play_games": self_play_games,
                "wins": int(s["wins"]),
                "losses": int(s["losses"]),
                "draws": int(s["draws"]),
                "score": round(float(s["score"]), 3),
                "win_rate": round(int(s["wins"]) / games, 4) if games else 0.0,
                "score_rate": round(float(s["score"]) / games, 4) if games else 0.0,
                "avg_hp_diff": round(float(s["hp_diff_sum"]) / games, 3) if games else 0.0,
                "avg_rounds": round(float(s["rounds_sum"]) / games, 1) if games else 0.0,
                "last_match_id": int(s["last_match_id"]) or last_self_play_match_id or last_any_match_id,
                "last_seen_at": s["last_seen_at"] or last_any_seen_at,
                "username": str(meta.get("username") or ""),
                "user_id": meta.get("user_id"),
                "entity": str(meta.get("entity") or ""),
                "entity_id": meta.get("entity_id"),
                "version": meta.get("version"),
                "remark": str(meta.get("remark") or ""),
                "compile_status": str(meta.get("compile_status") or ""),
                "ladder_score": meta.get("ladder_score"),
                "ladder_rank": meta.get("ladder_rank"),
                "provisional": games < int(cfg.reliability_games),
            }
        )
    rating_rows.sort(key=lambda item: (float(item["elo"]), float(item["raw_elo"]), int(item["games"])), reverse=True)
    for rank, item in enumerate(rating_rows, start=1):
        item["rank"] = rank
    default_versions = sum(1 for item in rating_rows if int(item["games"]) == 0)
    return rating_rows, {
        "matches_used": matches_used,
        "rated_versions": len(rating_rows),
        "cross_rated_versions": len(rating_rows) - default_versions,
        "default_versions": default_versions,
        "self_play_versions": sum(1 for item in rating_rows if int(item.get("self_play_games") or 0) > 0),
        "self_play_matches": sum(int(item.get("self_play_games") or 0) for item in rating_rows),
        "excluded_default_versions": sum(1 for item in rating_rows if item.get("rating_source") == "default_excluded"),
    }


def load_rating_map(conn: sqlite3.Connection, cfg: CrawlConfig) -> dict[str, dict[str, Any]]:
    rows, _meta = elo_rows(conn, cfg)
    return {str(row["code_id"]): row for row in rows if str(row.get("code_id") or "")}


def version_activity_rows(conn: sqlite3.Connection) -> dict[str, dict[str, Any]]:
    rows = conn.execute(
        """
        WITH code_matches AS (
            SELECT
                p.code_id AS code_id,
                m.match_id AS match_id,
                m.ignored AS ignored,
                m.success AS success,
                m.rounds AS rounds,
                m.terminal AS terminal,
                COALESCE(NULLIF(m.first_seen_at, ''), NULLIF(m.create_time, '')) AS first_seen_at
            FROM match_players p
            JOIN matches m ON m.match_id=p.match_id
            WHERE p.code_id != ''
            GROUP BY p.code_id, m.match_id
        ),
        match_counts AS (
            SELECT
                code_id,
                SUM(CASE WHEN ignored=0 THEN 1 ELSE 0 END) AS total_matches,
                SUM(CASE WHEN ignored=0 AND success=1 AND rounds IS NOT NULL THEN 1 ELSE 0 END) AS rated_matches,
                SUM(CASE WHEN ignored=0 AND terminal=0 THEN 1 ELSE 0 END) AS pending_matches,
                MIN(first_seen_at) AS first_match_seen_at
            FROM code_matches
            GROUP BY code_id
        ),
        req_counts AS (
            SELECT
                code_id,
                SUM(requested) AS requested_matches
            FROM (
                SELECT target_code_id AS code_id, 1 AS requested
                FROM supplement_requests
                WHERE target_code_id != '' AND status IN ('created', 'pending')
                UNION ALL
                SELECT opponent_code_id AS code_id, 1 AS requested
                FROM supplement_requests
                WHERE opponent_code_id != '' AND status IN ('created', 'pending')
            )
            GROUP BY code_id
        )
        SELECT
            v.code_id,
            v.username,
            v.entity,
            v.version,
            v.remark,
            v.first_seen_at,
            v.last_seen_at,
            v.compile_status,
            v.ladder_rank,
            v.ladder_score,
            COALESCE(mc.total_matches, 0) AS total_matches,
            COALESCE(mc.rated_matches, 0) AS rated_matches,
            COALESCE(mc.pending_matches, 0) AS pending_matches,
            COALESCE(rc.requested_matches, 0) AS requested_matches,
            mc.first_match_seen_at AS first_match_seen_at
        FROM versions v
        LEFT JOIN match_counts mc ON mc.code_id=v.code_id
        LEFT JOIN req_counts rc ON rc.code_id=v.code_id
        WHERE v.code_id != ''
        """
    ).fetchall()
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        code_id = str(row["code_id"] or "")
        if not code_id:
            continue
        first_seen = str(row["first_match_seen_at"] or row["first_seen_at"] or row["last_seen_at"] or "")
        total = as_int(row["total_matches"], 0)
        pending = as_int(row["pending_matches"], 0)
        requested = as_int(row["requested_matches"], 0)
        out[code_id] = {
            "code_id": code_id,
            "username": str(row["username"] or ""),
            "entity": str(row["entity"] or ""),
            "version": row["version"],
            "remark": str(row["remark"] or ""),
            "first_seen_at": first_seen,
            "first_seen_epoch": parse_time_to_epoch(first_seen),
            "compile_status": str(row["compile_status"] or ""),
            "ladder_rank": row["ladder_rank"],
            "ladder_score": row["ladder_score"],
            "total_matches": total,
            "rated_matches": as_int(row["rated_matches"], 0),
            "pending_matches": pending,
            "requested_matches": requested,
            "active_matches": total + requested,
        }
    return out


def pair_count(conn: sqlite3.Connection, code_a: str, code_b: str) -> int:
    row = conn.execute(
        """
        SELECT COUNT(*)
        FROM matches m
        JOIN match_players p0 ON p0.match_id=m.match_id AND p0.seat=0
        JOIN match_players p1 ON p1.match_id=m.match_id AND p1.seat=1
        WHERE m.ignored=0
          AND ((p0.code_id=? AND p1.code_id=?) OR (p0.code_id=? AND p1.code_id=?))
        """,
        (code_a, code_b, code_b, code_a),
    ).fetchone()[0]
    req = conn.execute(
        """
        SELECT COUNT(*)
        FROM supplement_requests
        WHERE status IN ('created', 'pending')
          AND ((target_code_id=? AND opponent_code_id=?) OR (target_code_id=? AND opponent_code_id=?))
        """,
        (code_a, code_b, code_b, code_a),
    ).fetchone()[0]
    return as_int(row, 0) + as_int(req, 0)


def choose_opponent(
    conn: sqlite3.Connection,
    target: dict[str, Any],
    versions: dict[str, dict[str, Any]],
    ratings: dict[str, dict[str, Any]],
    cfg: CrawlConfig,
) -> tuple[str, str]:
    target_code = str(target["code_id"])
    if is_supplement_excluded(target, cfg):
        return "", "target_excluded_user"
    target_rating = ratings.get(target_code, {})
    target_elo = as_float(target_rating.get("elo"), float(cfg.base_rating))
    target_games = as_int(target.get("active_matches"), 0)
    target_ladder = target.get("ladder_rank")

    candidates: list[tuple[float, str, str]] = []
    for code_id, row in versions.items():
        if code_id == target_code:
            continue
        if is_supplement_excluded(row, cfg):
            continue
        if as_int(row.get("active_matches"), 0) < 8:
            continue
        if str(row.get("compile_status") or "") and str(row.get("compile_status")) != "编译成功":
            continue
        pc = pair_count(conn, target_code, code_id)
        if pc >= int(cfg.supplement_pair_cap):
            continue
        rating = ratings.get(code_id, {})
        opp_elo = as_float(rating.get("elo"), float(cfg.base_rating))
        opp_games = as_int(row.get("active_matches"), 0)
        opp_ladder = row.get("ladder_rank")
        closeness = abs(opp_elo - target_elo)
        stability_bonus = min(20, opp_games) * 2.0
        pair_penalty = pc * 80.0
        ladder_penalty = 0.0
        if target_ladder and opp_ladder:
            ladder_penalty = min(80.0, abs(as_int(target_ladder, 0) - as_int(opp_ladder, 0)) * 2.0)
        score = closeness + pair_penalty + ladder_penalty - stability_bonus
        reason = "near_elo"
        if target_games < int(cfg.supplement_min_games):
            reason = "cold_start_near_elo"
        candidates.append((score, code_id, reason))

    if candidates:
        candidates.sort(key=lambda item: item[0])
        pool = candidates[: min(4, len(candidates))]
        weights = [1.0 / (1.0 + max(0.0, item[0] - pool[0][0]) / 80.0) for item in pool]
        picked = random.choices(pool, weights=weights, k=1)[0]
        return picked[1], picked[2]

    fallback: list[tuple[float, str, str]] = []
    for code_id, row in versions.items():
        if code_id == target_code:
            continue
        if is_supplement_excluded(row, cfg):
            continue
        if str(row.get("compile_status") or "") and str(row.get("compile_status")) != "编译成功":
            continue
        pc = pair_count(conn, target_code, code_id)
        if pc >= int(cfg.supplement_pair_cap):
            continue
        rating = ratings.get(code_id, {})
        games = as_int(row.get("active_matches"), 0)
        fallback.append((-games, code_id, "fallback_most_observed"))
    if not fallback:
        return "", "no_opponent"
    fallback.sort(key=lambda item: item[0])
    pool = fallback[: min(4, len(fallback))]
    return random.choice(pool)[1], "fallback_most_observed_randomized"


def supplement_candidates(conn: sqlite3.Connection, cfg: CrawlConfig) -> list[dict[str, Any]]:
    versions = version_activity_rows(conn)
    ratings = load_rating_map(conn, cfg)
    now = time.time()
    out: list[dict[str, Any]] = []
    for code_id, row in versions.items():
        if is_supplement_excluded(row, cfg):
            continue
        active = as_int(row.get("active_matches"), 0)
        first_epoch = as_float(row.get("first_seen_epoch"), 0.0)
        age = now - first_epoch if first_epoch > 0 else 0.0
        if active >= int(cfg.supplement_candidate_max_games):
            continue
        if first_epoch <= 0:
            continue
        if active < int(cfg.supplement_min_games):
            if age < float(cfg.supplement_min_age_sec):
                continue
            urgency = 1000.0 + (int(cfg.supplement_min_games) - active) * 20.0 + min(100.0, age / 3600.0)
            reason = "cold_start_under_10_after_2h"
            desired = min(4, int(cfg.supplement_min_games) - active)
        else:
            rating = ratings.get(code_id, {})
            reliability = as_float(rating.get("reliability"), 0.0)
            urgency = (int(cfg.supplement_candidate_max_games) - active) * 1.5 + (1.0 - reliability) * 80.0
            reason = "under_50_refine"
            desired = 1
            if active < 20:
                desired = 2
        row = dict(row)
        row["urgency"] = urgency
        row["reason"] = reason
        row["desired"] = max(1, desired)
        row["elo"] = as_float(ratings.get(code_id, {}).get("elo"), float(cfg.base_rating))
        out.append(row)
    out.sort(key=lambda item: (float(item["urgency"]), -as_int(item.get("active_matches"), 0)), reverse=True)
    return out


def supplement_outstanding(conn: sqlite3.Connection) -> int:
    return db_scalar(conn, "SELECT COUNT(*) FROM supplement_requests WHERE status IN ('created', 'pending')")


def game_pending_count(conn: sqlite3.Connection, cfg: CrawlConfig) -> int:
    return db_scalar(
        conn,
        "SELECT COUNT(*) FROM matches WHERE ignored=0 AND terminal=0 AND match_id >= ?",
        (cfg.start_match_id,),
    )


def next_supplement_delay(cfg: CrawlConfig) -> float:
    lo = max(1.0, float(cfg.supplement_interval_min_sec))
    hi = max(lo, float(cfg.supplement_interval_max_sec))
    return random.uniform(lo, hi)


def dynamic_supplement_budget(conn: sqlite3.Connection, cfg: CrawlConfig, outstanding: int) -> tuple[int, dict[str, Any]]:
    pending = game_pending_count(conn, cfg)
    outstanding = max(0, int(outstanding))
    min_n = max(0, int(cfg.supplement_min_per_cycle))
    max_n = max(min_n, int(cfg.supplement_max_per_cycle))
    span = max_n - min_n
    pressure_load = max(pending, outstanding)
    soft_cap = max(1, int(cfg.supplement_max_outstanding))
    pressure_ratio = pressure_load / soft_cap
    if pressure_ratio >= 1.0:
        base = min_n
        pressure = "very_high"
    elif pressure_ratio >= 0.75:
        base = min_n + max(0, span // 4)
        pressure = "high"
    elif pressure_ratio >= 0.5:
        base = min_n + max(0, span // 2)
        pressure = "medium"
    elif pressure_ratio >= 0.25:
        base = min_n + max(0, span * 3 // 4)
        pressure = "low"
    else:
        base = max_n
        pressure = "idle"
    jitter_radius = max(1, min(5, max(1, span // 5)))
    jitter = random.randint(-jitter_radius, jitter_radius)
    wanted = max(min_n, min(max_n, base + jitter))
    capacity = max(0, int(cfg.supplement_max_outstanding) - int(outstanding))
    budget = min(wanted, capacity) if capacity >= min_n else 0
    return budget, {
        "pending": pending,
        "outstanding": outstanding,
        "pressure_load": pressure_load,
        "pressure_ratio": round(pressure_ratio, 3),
        "pressure": pressure,
        "base": base,
        "jitter": jitter,
        "wanted": wanted,
        "capacity": capacity,
    }


def reconcile_supplement_requests(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        UPDATE supplement_requests
        SET status='finished'
        WHERE status IN ('created', 'pending')
          AND match_id IN (SELECT match_id FROM matches WHERE terminal=1 AND success=1)
        """
    )
    conn.execute(
        """
        UPDATE supplement_requests
        SET status='failed'
        WHERE status IN ('created', 'pending')
          AND match_id IN (SELECT match_id FROM matches WHERE terminal=1 AND success=0)
        """
    )


def run_supplement_scheduler(conn: sqlite3.Connection, cfg: CrawlConfig, token: str) -> dict[str, Any]:
    if not cfg.supplement_enabled:
        out = {"enabled": False, "created": 0, "reason": "disabled", "updated_at": now_iso()}
        set_state(conn, "supplement", out)
        return out
    reconcile_supplement_requests(conn)
    conn.commit()
    state = get_state_map(conn)
    now = time.time()
    next_run = as_float(state.get("supplement_next_run_epoch"), 0.0)
    if next_run <= 0:
        last = as_float(state.get("supplement_last_run_epoch"), 0.0)
        next_run = (last if last > 0 else now) + next_supplement_delay(cfg)
        set_state(conn, "supplement_next_run_epoch", next_run)
        conn.commit()
    if now < next_run:
        out = {
            "enabled": True,
            "created": 0,
            "reason": "interval_wait",
            "next_in_sec": round(next_run - now, 1),
            "next_run_at": datetime.fromtimestamp(next_run, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "updated_at": now_iso(),
        }
        set_state(conn, "supplement", out)
        return out

    outstanding = supplement_outstanding(conn)
    budget, pressure = dynamic_supplement_budget(conn, cfg, outstanding)
    if budget <= 0:
        delay = next_supplement_delay(cfg)
        next_run = now + delay
        out = {
            "enabled": True,
            "created": 0,
            "reason": "no_capacity",
            "outstanding": outstanding,
            "pressure": pressure,
            "next_in_sec": round(delay, 1),
            "next_run_at": datetime.fromtimestamp(next_run, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "updated_at": now_iso(),
        }
        set_state(conn, "supplement", out)
        set_state(conn, "supplement_last_run_epoch", now)
        set_state(conn, "supplement_next_run_epoch", next_run)
        return out

    versions = version_activity_rows(conn)
    ratings = load_rating_map(conn, cfg)
    candidates = supplement_candidates(conn, cfg)
    created = 0
    errors = 0
    created_by_code: defaultdict[str, int] = defaultdict(int)
    rows: list[dict[str, Any]] = []
    for target in candidates:
        if created >= budget:
            break
        target_code = str(target["code_id"])
        target_active = as_int(target.get("active_matches"), 0)
        target_created = created_by_code[target_code]
        remaining_for_target = int(cfg.supplement_candidate_max_games) - target_active - target_created
        if remaining_for_target <= 0:
            continue
        want = min(as_int(target.get("desired"), 1), budget - created, remaining_for_target)
        for _ in range(want):
            target_for_pick = dict(target)
            target_for_pick["active_matches"] = target_active + created_by_code[target_code]
            opponent_code, opponent_reason = choose_opponent(conn, target_for_pick, versions, ratings, cfg)
            if not opponent_code:
                rows.append({"target_code_id": target_code, "skipped": True, "reason": opponent_reason})
                break
            seat = (pair_count(conn, target_code, opponent_code) + created) % 2
            entity_a, entity_b = (target_code, opponent_code) if seat == 0 else (opponent_code, target_code)
            try:
                started = create_room_match(
                    int(cfg.game_id),
                    entity_a,
                    entity_b,
                    token,
                    request_timeout=float(cfg.supplement_request_timeout),
                )
                match_id = as_int(started.get("match_id"), 0) or None
                room_id = as_int(started.get("room_id"), 0) or None
                conn.execute(
                    """
                    INSERT OR IGNORE INTO supplement_requests(
                        created_at, match_id, room_id, target_code_id, opponent_code_id, target_seat,
                        reason, opponent_reason, target_games_before, target_active_before,
                        opponent_games_before, status, error
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '')
                    """,
                    (
                        now_iso(),
                        match_id,
                        room_id,
                        target_code,
                        opponent_code,
                        seat,
                        str(target.get("reason") or ""),
                        opponent_reason,
                        as_int(target.get("rated_matches"), 0),
                        target_active,
                        as_int(versions.get(opponent_code, {}).get("active_matches"), 0),
                        "created",
                    ),
                )
                if match_id:
                    conn.execute(
                        """
                        INSERT INTO matches(match_id, game_id, state, ignored, terminal, success, detail_status, first_seen_at, last_seen_at, next_poll_at)
                        VALUES (?, ?, '准备中', 0, 0, 0, 'supplement_created', ?, ?, ?)
                        ON CONFLICT(match_id) DO UPDATE SET
                            game_id=excluded.game_id,
                            ignored=0,
                            terminal=0,
                            detail_status=CASE WHEN matches.detail_status='ok' THEN matches.detail_status ELSE excluded.detail_status END,
                            last_seen_at=excluded.last_seen_at,
                            next_poll_at=excluded.next_poll_at
                        """,
                        (match_id, int(cfg.game_id), now_iso(), now_iso(), time.time()),
                    )
                conn.commit()
                created += 1
                created_by_code[target_code] += 1
                created_by_code[opponent_code] += 1
                if target_code in versions:
                    versions[target_code]["active_matches"] = as_int(versions[target_code].get("active_matches"), 0) + 1
                if opponent_code in versions:
                    versions[opponent_code]["active_matches"] = as_int(versions[opponent_code].get("active_matches"), 0) + 1
                rows.append({"target_code_id": target_code, "opponent_code_id": opponent_code, "match_id": match_id, "room_id": room_id, "reason": target.get("reason"), "opponent_reason": opponent_reason})
                sleep_delay(cfg)
                if created >= budget:
                    break
            except Exception as exc:
                errors += 1
                rows.append({"target_code_id": target_code, "opponent_code_id": opponent_code, "error": compact_error(exc)})
                if is_auth_error(exc):
                    raise
                break

    delay = next_supplement_delay(cfg)
    next_run = time.time() + delay
    set_state(conn, "supplement_last_run_epoch", now)
    set_state(conn, "supplement_next_run_epoch", next_run)
    out = {
        "enabled": True,
        "created": created,
        "errors": errors,
        "budget": budget,
        "outstanding_before": outstanding,
        "pressure": pressure,
        "next_in_sec": round(delay, 1),
        "next_run_at": datetime.fromtimestamp(next_run, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "candidates_seen": len(candidates),
        "rows": rows[:50],
        "updated_at": now_iso(),
    }
    set_state(conn, "supplement", out)
    return out


def db_scalar(conn: sqlite3.Connection, sql: str, params: Iterable[Any] = ()) -> int:
    row = conn.execute(sql, tuple(params)).fetchone()
    if not row:
        return 0
    return as_int(row[0], 0)


def queue_rows(conn: sqlite3.Connection, limit: int = 20) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT match_id, state, detail_status, replay_status, poll_count, retry_count, last_error, next_poll_at
        FROM matches
        WHERE ignored=0 AND (
            terminal=0
            OR detail_status != 'ok'
            OR (success=1 AND (rounds IS NULL OR final_hp0 IS NULL OR final_hp1 IS NULL))
        )
        ORDER BY next_poll_at ASC, match_id DESC
        LIMIT ?
        """,
        (int(limit),),
    ).fetchall()
    now = time.time()
    out = []
    for row in rows:
        next_poll = float(row["next_poll_at"] or 0.0)
        out.append(
            {
                "match_id": int(row["match_id"]),
                "state": row["state"],
                "detail_status": row["detail_status"],
                "replay_status": row["replay_status"],
                "poll_count": int(row["poll_count"] or 0),
                "retry_count": int(row["retry_count"] or 0),
                "last_error": row["last_error"],
                "next_poll_in_sec": max(0, round(next_poll - now, 1)) if next_poll else 0,
            }
        )
    return out


def build_latest(conn: sqlite3.Connection, cfg: CrawlConfig) -> dict[str, Any]:
    ratings, elo_meta = elo_rows(conn, cfg)
    state = get_state_map(conn)
    local_pending = db_scalar(conn, "SELECT COUNT(*) FROM matches WHERE ignored=0 AND terminal=0 AND match_id >= ?", (cfg.start_match_id,))
    remote_pending = state.get("remote_pending", {}) if isinstance(state.get("remote_pending", {}), dict) else {}
    remote_pending_epoch = parse_time_to_epoch(remote_pending.get("updated_at")) if remote_pending else 0.0
    remote_pending_fresh = remote_pending_epoch > 0 and time.time() - remote_pending_epoch <= 1800.0
    remote_pending_ok = bool(remote_pending.get("ok")) and bool(remote_pending.get("complete")) and remote_pending_fresh
    pending_count = as_int(remote_pending.get("total"), local_pending) if remote_pending_ok else local_pending
    matches_summary = {
        "stored": db_scalar(conn, "SELECT COUNT(*) FROM matches WHERE match_id >= ?", (cfg.start_match_id,)),
        "ignored": db_scalar(conn, "SELECT COUNT(*) FROM matches WHERE ignored=1 AND match_id >= ?", (cfg.start_match_id,)),
        "success": db_scalar(conn, "SELECT COUNT(*) FROM matches WHERE ignored=0 AND success=1 AND match_id >= ?", (cfg.start_match_id,)),
        "success_with_replay_meta": db_scalar(
            conn,
            "SELECT COUNT(*) FROM matches WHERE ignored=0 AND success=1 AND rounds IS NOT NULL AND final_hp0 IS NOT NULL AND final_hp1 IS NOT NULL AND match_id >= ?",
            (cfg.start_match_id,),
        ),
        "pending": pending_count,
        "local_pending": local_pending,
        "remote_pending": as_int(remote_pending.get("total"), 0) if remote_pending else None,
        "pending_source": "remote_state_scan" if remote_pending_ok else "local_db",
        "failed": db_scalar(conn, "SELECT COUNT(*) FROM matches WHERE ignored=0 AND terminal=1 AND success=0 AND match_id >= ?", (cfg.start_match_id,)),
        "min_match_id": db_scalar(conn, "SELECT MIN(match_id) FROM matches WHERE ignored=0 AND match_id >= ?", (cfg.start_match_id,)),
        "max_match_id": db_scalar(conn, "SELECT MAX(match_id) FROM matches WHERE ignored=0 AND match_id >= ?", (cfg.start_match_id,)),
    }
    return {
        "generated_at": now_iso(),
        "runtime_dir": str(RUNTIME_DIR),
        "db_path": str(cfg.db_path),
        "config": {
            "game_id": int(cfg.game_id),
            "contest_id": int(cfg.contest_id),
            "start_match_id": int(cfg.start_match_id),
            "list_limit": int(cfg.list_limit),
            "max_list_pages": int(cfg.max_list_pages),
            "gap_probe_per_cycle": int(cfg.gap_probe_per_cycle),
            "max_detail_per_cycle": int(cfg.max_detail_per_cycle),
            "pending_state_limit": int(cfg.pending_state_limit),
            "pending_state_max_pages": int(cfg.pending_state_max_pages),
            "replay_concurrency": int(cfg.replay_concurrency),
            "base_rating": float(cfg.base_rating),
            "max_k": float(cfg.max_k),
            "min_k": float(cfg.min_k),
            "reliability_games": float(cfg.reliability_games),
            "hp_margin_scale": float(cfg.hp_margin_scale),
            "hp_margin_weight": float(cfg.hp_margin_weight),
            "supplement_enabled": bool(cfg.supplement_enabled),
            "supplement_interval_min_sec": float(cfg.supplement_interval_min_sec),
            "supplement_interval_max_sec": float(cfg.supplement_interval_max_sec),
            "supplement_min_per_cycle": int(cfg.supplement_min_per_cycle),
            "supplement_max_per_cycle": int(cfg.supplement_max_per_cycle),
            "supplement_min_age_sec": float(cfg.supplement_min_age_sec),
            "supplement_min_games": int(cfg.supplement_min_games),
            "supplement_candidate_max_games": int(cfg.supplement_candidate_max_games),
            "supplement_max_outstanding": int(cfg.supplement_max_outstanding),
            "supplement_excluded_usernames": sorted(excluded_supplement_usernames(cfg)),
        },
        "crawl_state": state,
        "matches": matches_summary,
        "queue": queue_rows(conn),
        "elo": {
            **elo_meta,
            "ratings": ratings,
        },
    }


def recompute_latest(cfg: CrawlConfig) -> dict[str, Any]:
    with connect(cfg.db_path) as conn:
        init_db(conn)
        payload = build_latest(conn, cfg)
    write_json(cfg.latest_path, payload)
    return payload


def crawl_once(cfg: CrawlConfig) -> dict[str, Any]:
    with connect(cfg.db_path) as conn:
        init_db(conn)
        set_state(conn, "last_cycle_started_at", now_iso())
        set_state(conn, "status", {"state": "running", "message": ""})
        conn.commit()

        try:
            ladder = fetch_ladder(conn, cfg)
            conn.commit()
        except Exception as exc:
            ladder = {"ok": False, "error": compact_error(exc)}
            set_state(conn, "ladder", ladder)
            conn.commit()

        try:
            load_config.cache_clear()
        except Exception:
            pass
        token, source = resolve_token(cfg.token)
        set_state(conn, "token_source", source or "")
        if not token:
            set_state(conn, "status", {"state": "no_token", "message": "match list/detail requires a valid Saiblo bearer token"})
            set_state(conn, "last_cycle_finished_at", now_iso())
            conn.commit()
            payload = build_latest(conn, cfg)
            payload["last_cycle"] = {"ladder": ladder, "match_list": None, "detail_poll": None}
            write_json(cfg.latest_path, payload)
            return payload

        match_list = None
        remote_pending = None
        gap_probe = None
        detail_poll = None
        supplement = None
        try:
            match_list = scan_match_list(conn, cfg, token)
            remote_pending = scan_remote_pending_states(conn, cfg, token)
            gap_probe = gap_probe_matches(conn, cfg, token, as_int(match_list.get("max_id"), 0) if isinstance(match_list, dict) else None)
            cleanup_ignored_game_rows(conn)
            conn.commit()
            detail_poll = poll_match_details(conn, cfg, token)
            supplement = run_supplement_scheduler(conn, cfg, token)
            set_state(conn, "status", {"state": "ok", "message": ""})
        except Exception as exc:
            state = "auth_error" if is_auth_error(exc) else "error"
            set_state(conn, "status", {"state": state, "message": compact_error(exc)})
            if state != "auth_error":
                set_state(conn, "last_traceback", traceback.format_exc()[-4000:])
            conn.commit()

        set_state(conn, "last_cycle_finished_at", now_iso())
        conn.commit()
        payload = build_latest(conn, cfg)
        payload["last_cycle"] = {"ladder": ladder, "match_list": match_list, "remote_pending": remote_pending, "gap_probe": gap_probe, "detail_poll": detail_poll, "supplement": supplement}
        write_json(cfg.latest_path, payload)
        return payload


def cmd_crawl(args: argparse.Namespace) -> int:
    cfg = config_from_args(args)
    cfg.latest_path.parent.mkdir(parents=True, exist_ok=True)
    if args.loop:
        print(f"saiblo-game1-elo crawler loop started db={cfg.db_path} latest={cfg.latest_path}", flush=True)
        while True:
            started = time.time()
            payload = crawl_once(cfg)
            status = payload.get("crawl_state", {}).get("status", {})
            matches = payload.get("matches", {})
            elo = payload.get("elo", {})
            print(
                f"{now_iso()} status={status.get('state')} stored={matches.get('stored')} "
                f"complete={matches.get('success_with_replay_meta')} rated={elo.get('rated_versions')} "
                f"matches_used={elo.get('matches_used')}",
                flush=True,
            )
            elapsed = time.time() - started
            time.sleep(max(1.0, float(cfg.loop_interval) - elapsed))
    payload = crawl_once(cfg)
    print(json.dumps({"latest": str(cfg.latest_path), "summary": payload.get("matches", {}), "status": payload.get("crawl_state", {}).get("status", {})}, ensure_ascii=False, indent=2))
    return 0


def cmd_recompute(args: argparse.Namespace) -> int:
    cfg = config_from_args(args)
    payload = recompute_latest(cfg)
    print(json.dumps({"latest": str(cfg.latest_path), "summary": payload.get("matches", {}), "elo": {k: payload.get("elo", {}).get(k) for k in ("matches_used", "rated_versions")}}, ensure_ascii=False, indent=2))
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    cfg = config_from_args(args)
    payload = recompute_latest(cfg)
    status = payload.get("crawl_state", {}).get("status", {})
    out = {
        "latest": str(cfg.latest_path),
        "status": status,
        "supplement": payload.get("crawl_state", {}).get("supplement", {}),
        "backfill": payload.get("crawl_state", {}).get("backfill", {}),
        "matches": payload.get("matches", {}),
        "elo": {
            k: payload.get("elo", {}).get(k)
            for k in (
                "matches_used",
                "rated_versions",
                "cross_rated_versions",
                "default_versions",
                "self_play_versions",
                "self_play_matches",
            )
        },
        "top": (payload.get("elo", {}).get("ratings") or [])[:10],
        "queue": payload.get("queue", [])[:10],
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


def cmd_backfill(args: argparse.Namespace) -> int:
    cfg = config_from_args(args)
    usernames = [str(item) for item in (args.username or []) if str(item).strip()]
    code_ids = [str(item) for item in (args.code_id or []) if str(item).strip()]
    limit = max(1, int(args.limit))
    if not usernames and not code_ids:
        print("backfill requires at least one --username or --code-id", file=sys.stderr)
        return 2

    try:
        load_config.cache_clear()
    except Exception:
        pass
    token, source = resolve_token(cfg.token)
    with connect(cfg.db_path) as conn:
        init_db(conn)
        set_state(conn, "token_source", source or "")
        if not token:
            out = {"ok": False, "reason": "no_token", "updated_at": now_iso()}
            set_state(conn, "backfill", out)
            payload = build_latest(conn, cfg)
            write_json(cfg.latest_path, payload)
            print(json.dumps({"latest": str(cfg.latest_path), "backfill": out}, ensure_ascii=False, indent=2))
            return 1
        out = run_history_backfill(conn, cfg, token, usernames, code_ids, limit)
        payload = build_latest(conn, cfg)
        write_json(cfg.latest_path, payload)
    print(
        json.dumps(
            {
                "latest": str(cfg.latest_path),
                "backfill": out,
                "summary": payload.get("matches", {}),
                "elo": {k: payload.get("elo", {}).get(k) for k in ("matches_used", "rated_versions")},
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if out.get("ok") else 1


def add_common_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--game-id", type=int, default=48)
    p.add_argument("--contest-id", type=int, default=0, help="if set, scan /api/matches/?contest=... instead of game=...")
    p.add_argument("--start-match-id", type=int, default=7981000)
    p.add_argument("--db", default=str(DEFAULT_DB))
    p.add_argument("--latest", default=str(DEFAULT_LATEST))
    p.add_argument("--token", default="", help="Bearer token override; otherwise resolves env/config/zdata")
    p.add_argument("--list-limit", type=int, default=100)
    p.add_argument("--max-list-pages", type=int, default=50)
    p.add_argument("--gap-probe-per-cycle", type=int, default=50, help="sequential match-id gap probes per cycle")
    p.add_argument("--max-detail-per-cycle", type=int, default=30)
    p.add_argument("--pending-state-limit", type=int, default=100)
    p.add_argument("--pending-state-max-pages", type=int, default=20)
    p.add_argument("--request-delay", type=float, default=0.35)
    p.add_argument("--request-timeout", type=float, default=20.0)
    p.add_argument("--replay-timeout", type=float, default=60.0)
    p.add_argument("--replay-concurrency", type=int, default=3, help="parallel replay downloads; detail polling remains serial")
    p.add_argument("--detail-poll-min", type=float, default=20.0)
    p.add_argument("--detail-poll-max", type=float, default=300.0)
    p.add_argument("--base-rating", type=float, default=1500.0)
    p.add_argument("--max-k", type=float, default=36.0)
    p.add_argument("--min-k", type=float, default=8.0)
    p.add_argument("--provisional-games", type=float, default=12.0)
    p.add_argument("--reliability-games", type=float, default=30.0)
    p.add_argument("--hp-margin-scale", type=float, default=18.0)
    p.add_argument("--hp-margin-weight", type=float, default=0.35)
    p.add_argument("--supplement-enabled", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--supplement-interval-sec", type=float, default=None, help=argparse.SUPPRESS)
    p.add_argument("--supplement-interval-min-sec", type=float, default=600.0)
    p.add_argument("--supplement-interval-max-sec", type=float, default=1200.0)
    p.add_argument("--supplement-min-per-cycle", type=int, default=10)
    p.add_argument("--supplement-max-per-cycle", type=int, default=30)
    p.add_argument("--supplement-min-age-sec", type=float, default=7200.0)
    p.add_argument("--supplement-min-games", type=int, default=10)
    p.add_argument("--supplement-candidate-max-games", type=int, default=50)
    p.add_argument("--supplement-max-outstanding", type=int, default=80)
    p.add_argument("--supplement-pair-cap", type=int, default=4)
    p.add_argument("--supplement-request-timeout", type=float, default=60.0)
    p.add_argument("--supplement-exclude-user", action="append", default=["theend"], help="username excluded from automatic supplement matches; can be repeated")


def config_from_args(args: argparse.Namespace) -> CrawlConfig:
    interval_min_sec = float(args.supplement_interval_min_sec)
    interval_max_sec = float(args.supplement_interval_max_sec)
    legacy_interval_sec = getattr(args, "supplement_interval_sec", None)
    if legacy_interval_sec is not None:
        interval_min_sec = float(legacy_interval_sec)
        interval_max_sec = float(legacy_interval_sec)
    return CrawlConfig(
        game_id=int(args.game_id),
        contest_id=int(args.contest_id),
        start_match_id=int(args.start_match_id),
        db_path=Path(args.db).resolve(),
        latest_path=Path(args.latest).resolve(),
        list_limit=int(args.list_limit),
        max_list_pages=int(args.max_list_pages),
        gap_probe_per_cycle=int(args.gap_probe_per_cycle),
        max_detail_per_cycle=int(args.max_detail_per_cycle),
        pending_state_limit=int(args.pending_state_limit),
        pending_state_max_pages=int(args.pending_state_max_pages),
        request_delay=float(args.request_delay),
        loop_interval=float(getattr(args, "interval", 60.0)),
        detail_poll_min=float(args.detail_poll_min),
        detail_poll_max=float(args.detail_poll_max),
        request_timeout=float(args.request_timeout),
        replay_timeout=float(args.replay_timeout),
        replay_concurrency=max(1, int(args.replay_concurrency)),
        token=str(args.token or ""),
        base_rating=float(args.base_rating),
        max_k=float(args.max_k),
        min_k=float(args.min_k),
        provisional_games=float(args.provisional_games),
        reliability_games=float(args.reliability_games),
        hp_margin_scale=float(args.hp_margin_scale),
        hp_margin_weight=float(args.hp_margin_weight),
        supplement_enabled=bool(args.supplement_enabled),
        supplement_interval_min_sec=interval_min_sec,
        supplement_interval_max_sec=interval_max_sec,
        supplement_min_per_cycle=int(args.supplement_min_per_cycle),
        supplement_max_per_cycle=int(args.supplement_max_per_cycle),
        supplement_min_age_sec=float(args.supplement_min_age_sec),
        supplement_min_games=int(args.supplement_min_games),
        supplement_candidate_max_games=int(args.supplement_candidate_max_games),
        supplement_max_outstanding=int(args.supplement_max_outstanding),
        supplement_pair_cap=int(args.supplement_pair_cap),
        supplement_request_timeout=float(args.supplement_request_timeout),
        supplement_excluded_usernames=tuple(str(item) for item in (args.supplement_exclude_user or []) if str(item).strip()),
    )


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Saiblo Game1 match metadata crawler and AI-version Elo")
    sub = p.add_subparsers(dest="cmd", required=True)

    crawl = sub.add_parser("crawl", help="crawl once or run as a loop")
    add_common_args(crawl)
    crawl.add_argument("--loop", action="store_true")
    crawl.add_argument("--interval", type=float, default=60.0)
    crawl.set_defaults(func=cmd_crawl)

    recompute = sub.add_parser("recompute", help="rebuild latest.json from SQLite")
    add_common_args(recompute)
    recompute.set_defaults(func=cmd_recompute)

    status = sub.add_parser("status", help="print current crawler/Elo status")
    add_common_args(status)
    status.set_defaults(func=cmd_status)

    backfill = sub.add_parser("backfill", help="backfill replay metadata for historical successful matches")
    add_common_args(backfill)
    backfill.add_argument("--username", action="append", default=[], help="username whose historical matches should be backfilled; can be repeated")
    backfill.add_argument("--code-id", action="append", default=[], help="code_id whose historical matches should be backfilled; can be repeated")
    backfill.add_argument("--limit", type=int, default=500, help="maximum candidate matches processed per backfill batch")
    backfill.set_defaults(func=cmd_backfill)
    return p


def main() -> int:
    args = build_parser().parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
