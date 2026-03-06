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


def build_payload() -> Dict[str, Any]:
    return {
        "generated_at": now_iso(),
        "hostname": os.uname().nodename,
        "views": {
            "prod": build_view(PROD_LATEST, "production"),
            "iter": build_view(ITER_LATEST, "iteration"),
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
