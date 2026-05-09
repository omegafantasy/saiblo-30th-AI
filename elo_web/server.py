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
SAIBLO_GAME1_LATEST = ROOT_DIR / "autolab" / "runtime" / "saiblo_game1_elo" / "latest.json"
SAIBLO_GAME53_LATEST = ROOT_DIR / "autolab" / "runtime" / "saiblo_game53_score" / "latest.json"


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
                "rating_source": str(item.get("rating_source", "")),
                "games": games,
                "self_play_games": as_int(item.get("self_play_games", 0)),
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
        "local_pending": as_int(matches.get("local_pending", 0)),
        "remote_pending": matches.get("remote_pending"),
        "pending_source": str(matches.get("pending_source", "")),
        "failed": as_int(matches.get("failed", 0)),
        "min_match_id": as_int(matches.get("min_match_id", 0)),
        "max_match_id": as_int(matches.get("max_match_id", 0)),
        "matches_used": as_int(elo.get("matches_used", 0)),
        "rated_versions": as_int(elo.get("rated_versions", 0)),
        "cross_rated_versions": as_int(elo.get("cross_rated_versions", 0)),
        "default_versions": as_int(elo.get("default_versions", 0)),
        "self_play_versions": as_int(elo.get("self_play_versions", 0)),
        "queue": data.get("queue", []) if isinstance(data.get("queue", []), list) else [],
        "rows": rows,
    }


def build_game53_view(path: Path, label: str) -> Dict[str, Any]:
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
    score = data.get("score", {}) if isinstance(data.get("score", {}), dict) else {}
    config = data.get("config", {}) if isinstance(data.get("config", {}), dict) else {}

    rows = []
    ratings = score.get("ratings", []) if isinstance(score.get("ratings", []), list) else []
    for i, item in enumerate(ratings, start=1):
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "rank": as_int(item.get("rank", i)),
                "code_id": str(item.get("code_id", "")),
                "avg_score": round(as_float(item.get("avg_score", 0.0)), 3),
                "best_score": round(as_float(item.get("best_score", 0.0)), 3),
                "best_match_id": as_int(item.get("best_match_id", 0)),
                "min_score": round(as_float(item.get("min_score", 0.0)), 3),
                "stddev_score": round(as_float(item.get("stddev_score", 0.0)), 3),
                "games": as_int(item.get("games", 0)),
                "reliability": round(as_float(item.get("reliability", 0.0)), 4),
                "last_score": round(as_float(item.get("last_score", 0.0)), 3),
                "last_match_id": as_int(item.get("last_match_id", 0)),
                "username": str(item.get("username", "")),
                "entity": str(item.get("entity", "")),
                "version": item.get("version"),
                "remark": str(item.get("remark", "")),
                "language": str(item.get("language", "")),
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
        "ignored": as_int(matches.get("ignored", 0)),
        "success": as_int(matches.get("success", 0)),
        "success_with_score": as_int(matches.get("success_with_score", 0)),
        "success_missing_score": as_int(matches.get("success_missing_score", 0)),
        "pending": as_int(matches.get("pending", 0)),
        "failed": as_int(matches.get("failed", 0)),
        "min_match_id": as_int(matches.get("min_match_id", 0)),
        "max_match_id": as_int(matches.get("max_match_id", 0)),
        "matches_used": as_int(score.get("matches_used", 0)),
        "scored_versions": as_int(score.get("scored_versions", 0)),
        "reliability_samples": as_int(score.get("reliability_samples", 0)),
        "queue": data.get("queue", []) if isinstance(data.get("queue", []), list) else [],
        "rows": rows,
    }


def build_payload() -> Dict[str, Any]:
    return {
        "generated_at": now_iso(),
        "hostname": os.uname().nodename,
        "views": {
            "saiblo_game1": build_saiblo_view(SAIBLO_GAME1_LATEST, "saiblo-game1"),
            "saiblo_game53": build_game53_view(SAIBLO_GAME53_LATEST, "saiblo-game53"),
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

    def end_headers(self) -> None:
        if not self.path.startswith("/api/"):
            self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, fmt: str, *args: Any) -> None:
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        print(f"{ts} {self.address_string()} {fmt % args}", flush=True)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Saiblo dashboard web server")
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
