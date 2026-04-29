#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict
from urllib.parse import urlparse


ROOT_DIR = Path(__file__).resolve().parents[1]
STATIC_DIR = ROOT_DIR / "elo_web" / "static"
PROD_LATEST = ROOT_DIR / "autolab" / "runtime" / "latest.json"
ITER_LATEST = ROOT_DIR / "autolab" / "runtime" / "scopes" / "iter" / "latest.json"
SAIBLO_GAME1_LATEST = ROOT_DIR / "autolab" / "runtime" / "saiblo_game1_elo" / "latest.json"


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def read_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def as_float(v: Any) -> float:
    try:
        return float(v)
    except Exception:
        return 0.0


def as_int(v: Any) -> int:
    try:
        return int(v)
    except Exception:
        return 0


def build_view(path: Path, label: str) -> Dict[str, Any]:
    if not path.exists():
        return {
            "label": label,
            "available": False,
            "path": str(path),
            "error": "missing file",
        }
    try:
        data = read_json(path)
    except Exception as e:
        return {
            "label": label,
            "available": False,
            "path": str(path),
            "error": f"load failed: {e}",
        }

    ratings = data.get("ratings", []) or []
    stats = data.get("stats", {}) or {}
    if not isinstance(stats, dict):
        stats = {}

    rows = []
    for i, item in enumerate(ratings, start=1):
        vid = str(item.get("id", ""))
        elo = as_float(item.get("elo", 0.0))
        s = stats.get(vid, {}) if isinstance(stats.get(vid, {}), dict) else {}
        games = as_int(s.get("games", 0))
        wins = as_float(s.get("wins", 0))
        draws = as_float(s.get("draws", 0))
        losses = as_float(s.get("losses", 0))
        score = as_float(s.get("score", 0))
        win_rate = wins / games if games > 0 else 0.0
        score_rate = score / games if games > 0 else 0.0
        rows.append(
            {
                "rank": i,
                "id": vid,
                "elo": round(elo, 2),
                "games": games,
                "wins": wins,
                "draws": draws,
                "losses": losses,
                "win_rate": round(win_rate, 4),
                "score_rate": round(score_rate, 4),
            }
        )

    mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    config = data.get("config", {}) if isinstance(data.get("config", {}), dict) else {}
    champion = data.get("champion", {}) if isinstance(data.get("champion", {}), dict) else {}
    config_mode = str(config.get("mode", ""))
    rating_mode = str(config.get("rating_mode", "")).strip() or "round"
    display_mode = "cumulative" if rating_mode == "cumulative" else config_mode

    return {
        "label": label,
        "available": True,
        "path": str(path),
        "file_mtime": mtime,
        "tag": str(data.get("tag", "")),
        "matches": as_int(data.get("matches", 0)),
        "games_per_pair": as_int(config.get("games_per_pair", 0)),
        "mode": display_mode,
        "config_mode": config_mode,
        "rating_mode": rating_mode,
        "jobs": as_int(config.get("jobs", 0)),
        "runtime_scope": str(config.get("runtime_scope", "")),
        "champion_old": str(champion.get("old", "")),
        "champion_new": str(champion.get("new", "")),
        "champion_promoted": bool(champion.get("promoted", False)),
        "rows": rows,
    }


def build_saiblo_view(path: Path, label: str) -> Dict[str, Any]:
    if not path.exists():
        return {
            "label": label,
            "available": False,
            "path": str(path),
            "error": "missing file",
        }
    try:
        data = read_json(path)
    except Exception as e:
        return {
            "label": label,
            "available": False,
            "path": str(path),
            "error": f"load failed: {e}",
        }

    mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    crawl_state = data.get("crawl_state", {}) if isinstance(data.get("crawl_state", {}), dict) else {}
    status = crawl_state.get("status", {}) if isinstance(crawl_state.get("status", {}), dict) else {}
    matches = data.get("matches", {}) if isinstance(data.get("matches", {}), dict) else {}
    elo = data.get("elo", {}) if isinstance(data.get("elo", {}), dict) else {}
    config = data.get("config", {}) if isinstance(data.get("config", {}), dict) else {}

    rows = []
    ratings = elo.get("ratings", []) if isinstance(elo.get("ratings", []), list) else []
    for i, item in enumerate(ratings, start=1):
        if not isinstance(item, dict):
            continue
        games = as_int(item.get("games", 0))
        rows.append(
            {
                "rank": as_int(item.get("rank", i)),
                "code_id": str(item.get("code_id", "")),
                "elo": round(as_float(item.get("elo", 0.0)), 2),
                "raw_elo": round(as_float(item.get("raw_elo", 0.0)), 2),
                "reliability": round(as_float(item.get("reliability", 0.0)), 4),
                "games": games,
                "wins": as_int(item.get("wins", 0)),
                "losses": as_int(item.get("losses", 0)),
                "draws": as_int(item.get("draws", 0)),
                "win_rate": round(as_float(item.get("win_rate", 0.0)), 4),
                "score_rate": round(as_float(item.get("score_rate", 0.0)), 4),
                "avg_hp_diff": round(as_float(item.get("avg_hp_diff", 0.0)), 3),
                "avg_rounds": round(as_float(item.get("avg_rounds", 0.0)), 1),
                "username": str(item.get("username", "")),
                "entity": str(item.get("entity", "")),
                "version": item.get("version"),
                "remark": str(item.get("remark", "")),
                "ladder_rank": item.get("ladder_rank"),
                "ladder_score": item.get("ladder_score"),
                "last_match_id": as_int(item.get("last_match_id", 0)),
                "provisional": bool(item.get("provisional", False)),
            }
        )

    return {
        "label": label,
        "available": True,
        "path": str(path),
        "file_mtime": mtime,
        "generated_at": str(data.get("generated_at", "")),
        "status": str(status.get("state", "")),
        "status_message": str(status.get("message", "")),
        "token_source": str(crawl_state.get("token_source", "")),
        "game_id": as_int(config.get("game_id", 0)),
        "start_match_id": as_int(config.get("start_match_id", 0)),
        "stored": as_int(matches.get("stored", 0)),
        "success": as_int(matches.get("success", 0)),
        "success_with_replay_meta": as_int(matches.get("success_with_replay_meta", 0)),
        "pending": as_int(matches.get("pending", 0)),
        "failed": as_int(matches.get("failed", 0)),
        "min_match_id": as_int(matches.get("min_match_id", 0)),
        "max_match_id": as_int(matches.get("max_match_id", 0)),
        "matches_used": as_int(elo.get("matches_used", 0)),
        "rated_versions": as_int(elo.get("rated_versions", 0)),
        "queue": data.get("queue", []) if isinstance(data.get("queue", []), list) else [],
        "rows": rows,
    }


def build_payload() -> Dict[str, Any]:
    return {
        "generated_at": now_iso(),
        "hostname": os.uname().nodename,
        "views": {
            "prod": build_view(PROD_LATEST, "production"),
            "iter": build_view(ITER_LATEST, "iteration"),
            "saiblo_game1": build_saiblo_view(SAIBLO_GAME1_LATEST, "saiblo-game1"),
        },
    }


class EloHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def _send_json(self, payload: Dict[str, Any], status: int = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/api/elo":
            self._send_json(build_payload())
            return
        if parsed.path == "/healthz":
            self._send_json({"ok": True, "ts": now_iso()})
            return
        if parsed.path == "/":
            self.path = "/index.html"
        return super().do_GET()

    def log_message(self, fmt: str, *args: Any) -> None:
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        print(f"{ts} {self.address_string()} {fmt % args}", flush=True)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Elo dashboard web server")
    p.add_argument("--host", default="0.0.0.0")
    p.add_argument("--port", type=int, default=8000)
    return p.parse_args()


def main() -> None:
    args = parse_args()
    server = ThreadingHTTPServer((args.host, args.port), EloHandler)
    print(f"elo-web serving on http://{args.host}:{args.port}", flush=True)
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
