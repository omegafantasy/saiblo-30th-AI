#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import re
import sqlite3
import sys
import time
import traceback
import urllib.parse
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from config_runtime import load_config  # noqa: E402
from saiblo_tools import api_request, resolve_token  # noqa: E402


RUNTIME_DIR = ROOT_DIR / "autolab" / "runtime" / "saiblo_game53_score"
DEFAULT_DB = RUNTIME_DIR / "matches.sqlite3"
DEFAULT_LATEST = RUNTIME_DIR / "latest.json"

PENDING_STATES = {"", "准备中", "评测中", "队列中", "等待中", "Pending", "Running", "Queued", "Queueing"}
SUCCESS_STATES = {"评测成功", "Finished", "Success", "Succeeded"}
HEAVY_DETAIL_KEYS = {"message", "debug"}


@dataclass
class CrawlConfig:
    game_id: int = 53
    start_match_id: int = 0
    db_path: Path = DEFAULT_DB
    latest_path: Path = DEFAULT_LATEST
    list_limit: int = 100
    max_list_pages: int = 50
    max_detail_per_cycle: int = 60
    request_delay: float = 0.25
    loop_interval: float = 60.0
    detail_poll_min: float = 20.0
    detail_poll_max: float = 300.0
    request_timeout: float = 20.0
    token: str = ""
    reliability_samples: int = 10


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


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
            state TEXT NOT NULL DEFAULT '',
            create_time TEXT NOT NULL DEFAULT '',
            error TEXT NOT NULL DEFAULT '',
            ignored INTEGER NOT NULL DEFAULT 0,
            terminal INTEGER NOT NULL DEFAULT 0,
            success INTEGER NOT NULL DEFAULT 0,
            detail_status TEXT NOT NULL DEFAULT '',
            score0 REAL,
            info_count INTEGER NOT NULL DEFAULT 0,
            detail_json TEXT NOT NULL DEFAULT '',
            first_seen_at TEXT NOT NULL DEFAULT '',
            last_seen_at TEXT NOT NULL DEFAULT '',
            detail_fetched_at TEXT NOT NULL DEFAULT '',
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
            source TEXT NOT NULL DEFAULT '',
            first_seen_at TEXT NOT NULL DEFAULT '',
            last_seen_at TEXT NOT NULL DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS crawl_state (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL DEFAULT ''
        );

        CREATE INDEX IF NOT EXISTS idx_matches_poll ON matches(ignored, terminal, next_poll_at);
        CREATE INDEX IF NOT EXISTS idx_matches_state ON matches(ignored, success, terminal);
        CREATE INDEX IF NOT EXISTS idx_players_code ON match_players(code_id);
        CREATE INDEX IF NOT EXISTS idx_players_seat0 ON match_players(seat, code_id, score);
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
            compact_info = []
            for row in value:
                if not isinstance(row, dict):
                    compact_info.append(row)
                    continue
                item = dict(row)
                if isinstance(item.get("stderr"), str) and len(item["stderr"]) > 2000:
                    item["stderr"] = item["stderr"][:2000] + "...<truncated>"
                compact_info.append(item)
            compact[key] = compact_info
        else:
            compact[key] = value
    return compact


def extract_game_id(row: dict[str, Any]) -> int:
    game = row.get("game")
    if isinstance(game, dict):
        return as_int(game.get("id"), 0)
    return as_int(row.get("game_id"), 0)


def extract_entity_fields(code: dict[str, Any]) -> tuple[str, int | None, str]:
    entity = code.get("entity")
    if isinstance(entity, dict):
        return (
            str(entity.get("name") or ""),
            as_int(entity.get("id"), 0) or None,
            str(entity.get("language") or ""),
        )
    return str(entity or ""), None, ""


def player_from_info(match_id: int, seat: int, row: dict[str, Any]) -> dict[str, Any]:
    code = row.get("code") if isinstance(row.get("code"), dict) else {}
    user = row.get("user") if isinstance(row.get("user"), dict) else {}
    entity, entity_id, language = extract_entity_fields(code)
    version = (as_int(code.get("version"), 0) or None) if isinstance(code, dict) else None
    return {
        "match_id": int(match_id),
        "seat": int(seat),
        "username": str(user.get("username") or row.get("user") or ""),
        "user_id": as_int(user.get("id"), 0) or None,
        "code_id": normalize_code_id(code.get("id")) if isinstance(code, dict) else "",
        "entity": entity,
        "entity_id": entity_id,
        "language": language,
        "version": version,
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


def upsert_version(conn: sqlite3.Connection, player: dict[str, Any], source: str) -> None:
    code_id = str(player.get("code_id") or "")
    if not code_id:
        return
    ts = now_iso()
    conn.execute(
        """
        INSERT INTO versions(
            code_id, username, user_id, entity, entity_id, language, version, remark, commit_id,
            source, first_seen_at, last_seen_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(code_id) DO UPDATE SET
            username=COALESCE(NULLIF(excluded.username, ''), versions.username),
            user_id=COALESCE(excluded.user_id, versions.user_id),
            entity=COALESCE(NULLIF(excluded.entity, ''), versions.entity),
            entity_id=COALESCE(excluded.entity_id, versions.entity_id),
            language=COALESCE(NULLIF(excluded.language, ''), versions.language),
            version=COALESCE(excluded.version, versions.version),
            remark=COALESCE(NULLIF(excluded.remark, ''), versions.remark),
            commit_id=COALESCE(NULLIF(excluded.commit_id, ''), versions.commit_id),
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


def first_score_from_info(info: Any) -> Any:
    if isinstance(info, list) and info and isinstance(info[0], dict):
        return info[0].get("score") if info[0].get("score") not in ("", None) else None
    return None


def upsert_match_shell(conn: sqlite3.Connection, row: dict[str, Any], cfg: CrawlConfig, detail_status: str = "list") -> int:
    match_id = as_int(row.get("id"), 0)
    if match_id <= 0:
        return 0
    game_id = extract_game_id(row)
    state = str(row.get("state") or "")
    terminal = 1 if is_finished_state(state) else 0
    success = 1 if is_success_state(state) else 0
    ignored = 1 if game_id and game_id != int(cfg.game_id) else 0
    info = row.get("info", [])
    info_count = len(info) if isinstance(info, list) else 0
    score0 = first_score_from_info(info)
    ts = now_iso()
    next_poll = 0.0 if terminal else time.time() + cfg.detail_poll_min
    compact = strip_heavy_detail(row)
    conn.execute(
        """
        INSERT INTO matches(
            match_id, game_id, state, create_time, error, ignored, terminal, success,
            detail_status, score0, info_count, detail_json, first_seen_at, last_seen_at, next_poll_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(match_id) DO UPDATE SET
            game_id=COALESCE(excluded.game_id, matches.game_id),
            state=excluded.state,
            create_time=COALESCE(NULLIF(excluded.create_time, ''), matches.create_time),
            error=COALESCE(NULLIF(excluded.error, ''), matches.error),
            ignored=excluded.ignored,
            terminal=excluded.terminal,
            success=excluded.success,
            detail_status=CASE
                WHEN matches.detail_status = 'ok' THEN matches.detail_status
                ELSE excluded.detail_status
            END,
            score0=COALESCE(excluded.score0, matches.score0),
            info_count=MAX(excluded.info_count, matches.info_count),
            detail_json=CASE
                WHEN matches.detail_status = 'ok' THEN matches.detail_json
                ELSE excluded.detail_json
            END,
            last_seen_at=excluded.last_seen_at,
            next_poll_at=CASE
                WHEN excluded.terminal = 1 THEN 0
                WHEN matches.next_poll_at = 0 THEN excluded.next_poll_at
                ELSE MIN(matches.next_poll_at, excluded.next_poll_at)
            END
        """,
        (
            match_id,
            game_id or None,
            state,
            str(row.get("create_time") or row.get("time") or ""),
            str(row.get("error") or ""),
            ignored,
            terminal,
            success,
            detail_status,
            score0,
            info_count,
            safe_json(compact),
            ts,
            ts,
            next_poll,
        ),
    )
    if ignored == 0 and isinstance(info, list):
        for seat, p in enumerate(info):
            if isinstance(p, dict):
                upsert_player(conn, player_from_info(match_id, seat, p), source=detail_status)
    return match_id


def update_match_detail(conn: sqlite3.Connection, detail: dict[str, Any], cfg: CrawlConfig) -> None:
    match_id = upsert_match_shell(conn, detail, cfg, detail_status="ok")
    if match_id <= 0:
        return
    state = str(detail.get("state") or "")
    terminal = 1 if is_finished_state(state) else 0
    success = 1 if is_success_state(state) else 0
    row = conn.execute("SELECT poll_count FROM matches WHERE match_id=?", (match_id,)).fetchone()
    poll_count = as_int(row["poll_count"], 0) if row else 0
    backoff = min(float(cfg.detail_poll_max), float(cfg.detail_poll_min) * (1.5 ** max(0, poll_count)))
    next_poll = 0.0 if terminal else time.time() + backoff
    info = detail.get("info", [])
    conn.execute(
        """
        UPDATE matches
        SET state=?, game_id=COALESCE(?, game_id), error=?, terminal=?, success=?,
            detail_status='ok', score0=COALESCE(?, score0), info_count=?,
            detail_fetched_at=?, next_poll_at=?, poll_count=poll_count+1, last_error=''
        WHERE match_id=?
        """,
        (
            state,
            extract_game_id(detail) or None,
            str(detail.get("error") or ""),
            terminal,
            success,
            first_score_from_info(info),
            len(info) if isinstance(info, list) else 0,
            now_iso(),
            next_poll,
            match_id,
        ),
    )


def scan_match_list(conn: sqlite3.Connection, cfg: CrawlConfig, token: str) -> dict[str, Any]:
    upserted = 0
    seen = 0
    api_count = None
    stop_reason = "max_pages"
    min_id = None
    max_id = None
    for page in range(max(1, int(cfg.max_list_pages))):
        params = {"game": int(cfg.game_id), "limit": int(cfg.list_limit), "offset": page * int(cfg.list_limit)}
        q = urllib.parse.urlencode(params)
        data = api_request("GET", f"/api/matches/?{q}", token=token, timeout=cfg.request_timeout)
        if isinstance(data, dict) and data.get("count") is not None:
            api_count = data.get("count")
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
                if upsert_match_shell(conn, row, cfg, detail_status="list"):
                    upserted += 1
        conn.commit()
        if page_ids and int(cfg.start_match_id) > 0 and min(page_ids) < int(cfg.start_match_id):
            stop_reason = "reached_start_id"
            break
        if isinstance(data, dict) and not data.get("next"):
            stop_reason = "no_next"
            break
        sleep_delay(cfg)
    out = {
        "ok": True,
        "api_count": api_count,
        "seen": seen,
        "upserted": upserted,
        "min_id": min_id,
        "max_id": max_id,
        "stop_reason": stop_reason,
        "updated_at": now_iso(),
    }
    set_state(conn, "match_list", out)
    return out


def mark_poll_error(conn: sqlite3.Connection, cfg: CrawlConfig, match_id: int, exc: BaseException) -> None:
    backoff = min(float(cfg.detail_poll_max), float(cfg.detail_poll_min) * 4)
    conn.execute(
        """
        UPDATE matches
        SET retry_count=retry_count+1, last_error=?, next_poll_at=?
        WHERE match_id=?
        """,
        (compact_error(exc), time.time() + backoff, match_id),
    )


def select_matches_to_poll(conn: sqlite3.Connection, cfg: CrawlConfig) -> list[int]:
    now = time.time()
    rows = conn.execute(
        """
        SELECT m.match_id
        FROM matches m
        LEFT JOIN match_players p0 ON p0.match_id=m.match_id AND p0.seat=0
        WHERE m.ignored=0
          AND m.match_id >= ?
          AND (
            (m.terminal=0 AND m.next_poll_at <= ?)
            OR (m.success=1 AND (m.score0 IS NULL OR p0.code_id IS NULL OR p0.code_id='') AND m.detail_status != 'ok')
          )
        ORDER BY
          CASE WHEN m.terminal=0 THEN 0 ELSE 1 END,
          m.next_poll_at ASC,
          m.match_id DESC
        LIMIT ?
        """,
        (int(cfg.start_match_id), now, int(cfg.max_detail_per_cycle)),
    ).fetchall()
    return [int(row["match_id"]) for row in rows]


def poll_match_details(conn: sqlite3.Connection, cfg: CrawlConfig, token: str) -> dict[str, Any]:
    ids = select_matches_to_poll(conn, cfg)
    details = 0
    errors = 0
    for match_id in ids:
        try:
            detail = api_request("GET", f"/api/matches/{int(match_id)}/", token=token, timeout=cfg.request_timeout)
            if not isinstance(detail, dict):
                raise RuntimeError("invalid detail response")
            update_match_detail(conn, detail, cfg)
            details += 1
            conn.commit()
        except Exception as exc:
            errors += 1
            mark_poll_error(conn, cfg, match_id, exc)
            conn.commit()
            if is_auth_error(exc):
                raise
        sleep_delay(cfg)
    out = {
        "ok": True,
        "selected": len(ids),
        "details": details,
        "errors": errors,
        "updated_at": now_iso(),
    }
    set_state(conn, "detail_poll", out)
    conn.commit()
    return out


def load_versions(conn: sqlite3.Connection) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in conn.execute("SELECT * FROM versions"):
        code_id = str(row["code_id"] or "")
        if code_id:
            out[code_id] = dict(row)
    return out


def score_rows(conn: sqlite3.Connection, cfg: CrawlConfig) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT
            m.match_id,
            m.create_time,
            p0.code_id AS code_id,
            p0.score AS score,
            p0.username AS username,
            p0.entity AS entity,
            p0.version AS version,
            p0.remark AS remark
        FROM matches m
        JOIN match_players p0 ON p0.match_id=m.match_id AND p0.seat=0
        WHERE m.ignored=0
          AND m.success=1
          AND m.match_id >= ?
          AND p0.code_id != ''
          AND p0.score IS NOT NULL
        ORDER BY COALESCE(NULLIF(m.create_time, ''), printf('%012d', m.match_id)), m.match_id
        """,
        (int(cfg.start_match_id),),
    ).fetchall()

    stats: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "games": 0,
            "score_sum": 0.0,
            "score_sq_sum": 0.0,
            "best_score": None,
            "best_match_id": 0,
            "min_score": None,
            "last_score": None,
            "last_match_id": 0,
            "last_seen_at": "",
        }
    )
    for row in rows:
        code_id = str(row["code_id"] or "")
        if not code_id:
            continue
        score = as_float(row["score"], 0.0)
        match_id = as_int(row["match_id"], 0)
        s = stats[code_id]
        s["games"] += 1
        s["score_sum"] += score
        s["score_sq_sum"] += score * score
        if s["best_score"] is None or score > float(s["best_score"]):
            s["best_score"] = score
            s["best_match_id"] = match_id
        if s["min_score"] is None or score < float(s["min_score"]):
            s["min_score"] = score
        s["last_score"] = score
        s["last_match_id"] = match_id
        s["last_seen_at"] = str(row["create_time"] or "")

    versions = load_versions(conn)
    rating_rows: list[dict[str, Any]] = []
    for code_id, s in stats.items():
        games = int(s["games"])
        if games <= 0:
            continue
        avg = float(s["score_sum"]) / games
        variance = max(0.0, float(s["score_sq_sum"]) / games - avg * avg)
        reliability = min(1.0, math.sqrt(games / max(1.0, float(cfg.reliability_samples))))
        meta = versions.get(code_id, {})
        rating_rows.append(
            {
                "code_id": code_id,
                "avg_score": round(avg, 3),
                "best_score": round(as_float(s["best_score"], 0.0), 3),
                "best_match_id": as_int(s["best_match_id"], 0),
                "min_score": round(as_float(s["min_score"], 0.0), 3),
                "stddev_score": round(math.sqrt(variance), 3),
                "games": games,
                "reliability": round(reliability, 4),
                "last_score": round(as_float(s["last_score"], 0.0), 3),
                "last_match_id": as_int(s["last_match_id"], 0),
                "last_seen_at": str(s["last_seen_at"] or ""),
                "username": str(meta.get("username") or ""),
                "user_id": meta.get("user_id"),
                "entity": str(meta.get("entity") or ""),
                "entity_id": meta.get("entity_id"),
                "version": meta.get("version"),
                "remark": str(meta.get("remark") or ""),
                "language": str(meta.get("language") or ""),
                "provisional": games < int(cfg.reliability_samples),
            }
        )
    rating_rows.sort(
        key=lambda item: (
            float(item["avg_score"]),
            float(item["best_score"]),
            int(item["games"]),
            float(item["last_score"]),
        ),
        reverse=True,
    )
    for rank, item in enumerate(rating_rows, start=1):
        item["rank"] = rank
    return rating_rows, {
        "matches_used": len(rows),
        "scored_versions": len(rating_rows),
        "reliability_samples": int(cfg.reliability_samples),
    }


def db_scalar(conn: sqlite3.Connection, sql: str, params: Iterable[Any] = ()) -> int:
    row = conn.execute(sql, tuple(params)).fetchone()
    if not row:
        return 0
    return as_int(row[0], 0)


def queue_rows(conn: sqlite3.Connection, limit: int = 20) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT m.match_id, m.state, m.detail_status, m.poll_count, m.retry_count, m.last_error, m.next_poll_at
        FROM matches m
        LEFT JOIN match_players p0 ON p0.match_id=m.match_id AND p0.seat=0
        WHERE m.ignored=0 AND (
            m.terminal=0
            OR (m.success=1 AND (m.score0 IS NULL OR p0.code_id IS NULL OR p0.code_id='') AND m.detail_status != 'ok')
        )
        ORDER BY m.next_poll_at ASC, m.match_id DESC
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
                "poll_count": int(row["poll_count"] or 0),
                "retry_count": int(row["retry_count"] or 0),
                "last_error": row["last_error"],
                "next_poll_in_sec": max(0, round(next_poll - now, 1)) if next_poll else 0,
            }
        )
    return out


def build_latest(conn: sqlite3.Connection, cfg: CrawlConfig) -> dict[str, Any]:
    ratings, score_meta = score_rows(conn, cfg)
    state = get_state_map(conn)
    matches_summary = {
        "stored": db_scalar(conn, "SELECT COUNT(*) FROM matches WHERE match_id >= ?", (cfg.start_match_id,)),
        "ignored": db_scalar(conn, "SELECT COUNT(*) FROM matches WHERE ignored=1 AND match_id >= ?", (cfg.start_match_id,)),
        "success": db_scalar(conn, "SELECT COUNT(*) FROM matches WHERE ignored=0 AND success=1 AND match_id >= ?", (cfg.start_match_id,)),
        "success_with_score": db_scalar(
            conn,
            """
            SELECT COUNT(*)
            FROM matches m
            JOIN match_players p0 ON p0.match_id=m.match_id AND p0.seat=0
            WHERE m.ignored=0 AND m.success=1 AND m.match_id >= ? AND p0.code_id != '' AND p0.score IS NOT NULL
            """,
            (cfg.start_match_id,),
        ),
        "success_missing_score": db_scalar(
            conn,
            """
            SELECT COUNT(*)
            FROM matches m
            LEFT JOIN match_players p0 ON p0.match_id=m.match_id AND p0.seat=0
            WHERE m.ignored=0
              AND m.success=1
              AND m.match_id >= ?
              AND (m.score0 IS NULL OR p0.code_id IS NULL OR p0.code_id='')
            """,
            (cfg.start_match_id,),
        ),
        "pending": db_scalar(conn, "SELECT COUNT(*) FROM matches WHERE ignored=0 AND terminal=0 AND match_id >= ?", (cfg.start_match_id,)),
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
            "start_match_id": int(cfg.start_match_id),
            "list_limit": int(cfg.list_limit),
            "max_list_pages": int(cfg.max_list_pages),
            "max_detail_per_cycle": int(cfg.max_detail_per_cycle),
            "reliability_samples": int(cfg.reliability_samples),
        },
        "crawl_state": state,
        "matches": matches_summary,
        "queue": queue_rows(conn),
        "score": {
            **score_meta,
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
            payload["last_cycle"] = {"match_list": None, "detail_poll": None}
            write_json(cfg.latest_path, payload)
            return payload

        match_list = None
        detail_poll = None
        try:
            match_list = scan_match_list(conn, cfg, token)
            conn.commit()
            detail_poll = poll_match_details(conn, cfg, token)
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
        payload["last_cycle"] = {"match_list": match_list, "detail_poll": detail_poll}
        write_json(cfg.latest_path, payload)
        return payload


def cmd_crawl(args: argparse.Namespace) -> int:
    cfg = config_from_args(args)
    cfg.latest_path.parent.mkdir(parents=True, exist_ok=True)
    if args.loop:
        print(f"saiblo-game53-score crawler loop started db={cfg.db_path} latest={cfg.latest_path}", flush=True)
        while True:
            started = time.time()
            payload = crawl_once(cfg)
            status = payload.get("crawl_state", {}).get("status", {})
            matches = payload.get("matches", {})
            score = payload.get("score", {})
            print(
                f"{now_iso()} status={status.get('state')} stored={matches.get('stored')} "
                f"scored={matches.get('success_with_score')} versions={score.get('scored_versions')} "
                f"pending={matches.get('pending')}",
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
    print(json.dumps({"latest": str(cfg.latest_path), "summary": payload.get("matches", {}), "score": {k: payload.get("score", {}).get(k) for k in ("matches_used", "scored_versions")}}, ensure_ascii=False, indent=2))
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    cfg = config_from_args(args)
    payload = recompute_latest(cfg)
    out = {
        "latest": str(cfg.latest_path),
        "status": payload.get("crawl_state", {}).get("status", {}),
        "matches": payload.get("matches", {}),
        "score": {k: payload.get("score", {}).get(k) for k in ("matches_used", "scored_versions", "reliability_samples")},
        "top": (payload.get("score", {}).get("ratings") or [])[:10],
        "queue": payload.get("queue", [])[:10],
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


def add_common_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--game-id", type=int, default=53)
    p.add_argument("--start-match-id", type=int, default=0)
    p.add_argument("--db", default=str(DEFAULT_DB))
    p.add_argument("--latest", default=str(DEFAULT_LATEST))
    p.add_argument("--token", default="", help="Bearer token override; otherwise resolves env/config/zdata")
    p.add_argument("--list-limit", type=int, default=100)
    p.add_argument("--max-list-pages", type=int, default=50)
    p.add_argument("--max-detail-per-cycle", type=int, default=60)
    p.add_argument("--request-delay", type=float, default=0.25)
    p.add_argument("--request-timeout", type=float, default=20.0)
    p.add_argument("--detail-poll-min", type=float, default=20.0)
    p.add_argument("--detail-poll-max", type=float, default=300.0)
    p.add_argument("--reliability-samples", type=int, default=10)


def config_from_args(args: argparse.Namespace) -> CrawlConfig:
    return CrawlConfig(
        game_id=int(args.game_id),
        start_match_id=int(args.start_match_id),
        db_path=Path(args.db).resolve(),
        latest_path=Path(args.latest).resolve(),
        list_limit=int(args.list_limit),
        max_list_pages=int(args.max_list_pages),
        max_detail_per_cycle=int(args.max_detail_per_cycle),
        request_delay=float(args.request_delay),
        loop_interval=float(getattr(args, "interval", 60.0)),
        detail_poll_min=float(args.detail_poll_min),
        detail_poll_max=float(args.detail_poll_max),
        request_timeout=float(args.request_timeout),
        token=str(args.token or ""),
        reliability_samples=max(1, int(args.reliability_samples)),
    )


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Saiblo Game53 DeepClue match crawler and score table")
    sub = p.add_subparsers(dest="cmd", required=True)

    crawl = sub.add_parser("crawl", help="crawl once or run as a loop")
    add_common_args(crawl)
    crawl.add_argument("--loop", action="store_true")
    crawl.add_argument("--interval", type=float, default=60.0)
    crawl.set_defaults(func=cmd_crawl)

    recompute = sub.add_parser("recompute", help="rebuild latest.json from SQLite")
    add_common_args(recompute)
    recompute.set_defaults(func=cmd_recompute)

    status = sub.add_parser("status", help="print current crawler/score status")
    add_common_args(status)
    status.set_defaults(func=cmd_status)
    return p


def main() -> int:
    args = build_parser().parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
