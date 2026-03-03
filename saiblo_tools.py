#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, Tuple

ROOT_DIR = Path(__file__).resolve().parent

from config_runtime import get_cfg

API_BASE = str(get_cfg("saiblo.api_base", "https://api.saiblo.net"))


def _headers(token: str | None) -> Dict[str, str]:
    h = {
        "Accept": "application/json, text/plain, */*",
        "User-Agent": "antgame-root-tools/1.0",
        "Content-Type": "application/json",
    }
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def load_token_from_zdata() -> str:
    path = ROOT_DIR / "past_AIs" / "zdata.py"
    if not path.is_file():
        return ""
    txt = path.read_text(encoding="utf-8", errors="ignore")
    m = re.search(r"^\s*bearer\s*=\s*['\"]([^'\"]+)['\"]", txt, re.M)
    return m.group(1).strip() if m else ""


def load_token_from_config() -> str:
    return str(get_cfg("saiblo.bearer", "")).strip()


def resolve_token(cli_token: str) -> Tuple[str, str]:
    if cli_token:
        return cli_token, "--token"
    env_token = os.environ.get("SAIBLO_BEARER", "").strip()
    if env_token:
        return env_token, "env:SAIBLO_BEARER"
    cfg_token = load_token_from_config()
    if cfg_token:
        return cfg_token, "config.local.json"
    zdata_token = load_token_from_zdata()
    if zdata_token:
        return zdata_token, "past_AIs/zdata.py"
    return "", ""


def api_request(method: str, path: str, token: str | None = None, payload: dict | None = None, timeout: float = 20.0) -> Any:
    url = f"{API_BASE}{path}"
    data = None
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url=url, data=data, headers=_headers(token), method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            if not raw.strip():
                return {}
            return json.loads(raw)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {e.code} {url}\n{body}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Request failed: {url} ({e})") from e


def require_token(cli_token: str, action: str) -> str:
    token, source = resolve_token(cli_token)
    if not token:
        print(
            f"Bearer token required for {action}. Use --token, SAIBLO_BEARER, config.local.json, or past_AIs/zdata.py",
            file=sys.stderr,
        )
        raise SystemExit(2)
    print(f"[token-source] {source}", file=sys.stderr)
    return token


def cmd_recent(args: argparse.Namespace) -> int:
    token = require_token(args.token, "recent")
    q = urllib.parse.urlencode({"limit": args.limit, "offset": args.offset})
    data = api_request("GET", f"/api/matches/?{q}", token=token)
    results = data.get("results", []) if isinstance(data, dict) else []

    rows = []
    for m in results:
        if not isinstance(m, dict):
            continue
        game = m.get("game", {})
        gid = game.get("id", -1) if isinstance(game, dict) else -1
        if args.game_id is not None and gid != args.game_id:
            continue
        info = m.get("info", [])
        if not isinstance(info, list) or len(info) != 2:
            continue

        p0 = info[0].get("user", {}).get("username", "?") if isinstance(info[0], dict) else "?"
        p1 = info[1].get("user", {}).get("username", "?") if isinstance(info[1], dict) else "?"
        s0 = info[0].get("score", "?") if isinstance(info[0], dict) else "?"
        s1 = info[1].get("score", "?") if isinstance(info[1], dict) else "?"

        rows.append(
            {
                "match_id": m.get("id"),
                "time": m.get("time"),
                "state": m.get("state"),
                "game_id": gid,
                "game": game.get("name", "") if isinstance(game, dict) else "",
                "p0": p0,
                "p1": p1,
                "score": [s0, s1],
            }
        )

    print(json.dumps({"count": len(rows), "rows": rows}, ensure_ascii=False, indent=2))
    return 0


def cmd_match(args: argparse.Namespace) -> int:
    token = require_token(args.token, "match")
    data = api_request("GET", f"/api/matches/{args.match_id}/", token=token)
    print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0


def create_room_match(game_id: int, entity_a: str, entity_b: str, token: str) -> dict:
    room = api_request(
        "POST",
        "/api/rooms/",
        token=token,
        payload={"game_id": int(game_id), "player_number": 2},
    )
    room_id = room["id"]

    join_path = f"/api/rooms/{room_id}/join/"
    api_request(
        "POST",
        join_path,
        token=token,
        payload={"order": 0, "enter": True, "is_user": False, "is_remote": False, "entity": entity_a},
    )
    api_request(
        "POST",
        join_path,
        token=token,
        payload={"order": 1, "enter": True, "is_user": False, "is_remote": False, "entity": entity_b},
    )

    begin = api_request("POST", f"/api/rooms/{room_id}/begin_match/", token=token, payload={})
    return {
        "room_id": room_id,
        "match_id": begin.get("match_id"),
        "entity_a": entity_a,
        "entity_b": entity_b,
    }


def cmd_room_match(args: argparse.Namespace) -> int:
    token = require_token(args.token, "room-match")

    rows = []
    for i in range(args.count):
        if args.swap and i % 2 == 1:
            a, b = args.entity_b, args.entity_a
        else:
            a, b = args.entity_a, args.entity_b
        row = create_room_match(args.game_id, a, b, token)
        rows.append(row)
        if args.interval > 0 and i + 1 < args.count:
            time.sleep(args.interval)

    print(json.dumps({"count": len(rows), "rows": rows}, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Root-level Saiblo helper tools")
    p.add_argument(
        "--token",
        default="",
        help="Bearer token (priority: --token > env > config.local.json > past_AIs/zdata.py)",
    )

    sub = p.add_subparsers(dest="cmd", required=True)

    sp_recent = sub.add_parser("recent", help="list recent matches")
    sp_recent.add_argument("--limit", type=int, default=20)
    sp_recent.add_argument("--offset", type=int, default=0)
    sp_recent.add_argument("--game-id", type=int, default=48)
    sp_recent.set_defaults(func=cmd_recent)

    sp_match = sub.add_parser("match", help="get one match detail")
    sp_match.add_argument("--match-id", type=int, required=True)
    sp_match.set_defaults(func=cmd_match)

    sp_room = sub.add_parser("room-match", help="create room and start match between two entities")
    sp_room.add_argument("--game-id", type=int, default=48)
    sp_room.add_argument("--entity-a", required=True, help="AI token of seat 0")
    sp_room.add_argument("--entity-b", required=True, help="AI token of seat 1")
    sp_room.add_argument("--count", type=int, default=1)
    sp_room.add_argument("--swap", action="store_true", help="alternate seat order between runs")
    sp_room.add_argument("--interval", type=float, default=0.0, help="seconds between room creations")
    sp_room.set_defaults(func=cmd_room_match)

    return p


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return args.func(args)
    except Exception as e:
        print(str(e), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
