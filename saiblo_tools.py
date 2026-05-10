#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, Tuple

try:
    import requests
except Exception:  # pragma: no cover - optional runtime dependency
    requests = None

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


def is_timeout_error(exc: BaseException) -> bool:
    if isinstance(exc, (TimeoutError, socket.timeout)):
        return True
    msg = str(exc).strip().lower()
    return "timed out" in msg or "timeout" in msg


def api_request(method: str, path: str, token: str | None = None, payload: dict | None = None, timeout: float | None = None) -> Any:
    url = f"{API_BASE}{path}"
    if timeout is None:
        timeout = float(os.environ.get("SAIBLO_API_TIMEOUT", "60"))
    data = None
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    attempts = 3 if str(method).upper() == "GET" else 1
    for attempt in range(1, attempts + 1):
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
            if attempt < attempts and is_timeout_error(e.reason if isinstance(e.reason, BaseException) else e):
                time.sleep(0.5 * attempt)
                continue
            raise RuntimeError(f"Request failed: {url} ({e})") from e
        except (TimeoutError, socket.timeout) as e:
            if attempt < attempts:
                time.sleep(0.5 * attempt)
                continue
            raise RuntimeError(f"Request timed out: {url} ({e})") from e


def api_download(path: str, token: str | None = None, timeout: float | None = None) -> Tuple[bytes, Dict[str, str]]:
    url = f"{API_BASE}{path}"
    if timeout is None:
        timeout = float(os.environ.get("SAIBLO_API_TIMEOUT", "60"))
    h = {
        "Accept": "*/*",
        "User-Agent": "antgame-root-tools/1.0",
    }
    if token:
        h["Authorization"] = f"Bearer {token}"
    for attempt in range(1, 4):
        req = urllib.request.Request(url=url, headers=h, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read()
                headers = {k.lower(): v for k, v in resp.headers.items()}
                return body, headers
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"HTTP {e.code} {url}\n{body}") from e
        except urllib.error.URLError as e:
            if attempt < 3 and is_timeout_error(e.reason if isinstance(e.reason, BaseException) else e):
                time.sleep(0.5 * attempt)
                continue
            raise RuntimeError(f"Request failed: {url} ({e})") from e
        except (TimeoutError, socket.timeout) as e:
            if attempt < 3:
                time.sleep(0.5 * attempt)
                continue
            raise RuntimeError(f"Request timed out: {url} ({e})") from e


def api_multipart_post(
    path: str,
    token: str,
    data: Dict[str, str],
    files: Dict[str, tuple[str, bytes, str]],
    timeout: float | None = None,
) -> Any:
    if requests is None:
        raise RuntimeError("python package 'requests' is required for multipart upload")
    url = f"{API_BASE}{path}"
    if timeout is None:
        timeout = float(os.environ.get("SAIBLO_API_TIMEOUT", "60"))
    h = {
        "Accept": "application/json, text/plain, */*",
        "User-Agent": "antgame-root-tools/1.0",
        "Authorization": f"Bearer {token}",
    }
    try:
        resp = requests.post(url, headers=h, data=data, files=files, timeout=timeout)
        raw = resp.text
        if resp.status_code >= 400:
            raise RuntimeError(f"HTTP {resp.status_code} {url}\n{raw}")
        if not raw.strip():
            return {}
        return resp.json()
    except requests.RequestException as e:
        raise RuntimeError(f"Request failed: {url} ({e})") from e


def get_profile(token: str) -> Dict[str, Any]:
    data = api_request("GET", "/api/profile/", token=token)
    if not isinstance(data, dict):
        raise RuntimeError("invalid profile response")
    return data


def get_user_entities(username: str, game_id: int, token: str) -> Dict[str, Any]:
    return api_request("GET", f"/api/users/{username}/games/{int(game_id)}/entities/", token=token)


def create_entity(username: str, game_id: int, name: str, language: str, token: str) -> Dict[str, Any]:
    payload = {"name": name, "language": language}
    return api_request(
        "POST",
        f"/api/users/{username}/games/{int(game_id)}/entities/",
        token=token,
        payload=payload,
    )


def get_entity_codes(entity_id: int, token: str) -> list[Dict[str, Any]]:
    data = api_request("GET", f"/api/entities/{int(entity_id)}/codes/", token=token)
    return data if isinstance(data, list) else []


def upload_entity_code(entity_id: int, source_path: Path, remark: str, token: str) -> Dict[str, Any]:
    if not source_path.is_file():
        raise RuntimeError(f"source file not found: {source_path}")
    file_bytes = source_path.read_bytes()
    files = {
        "file": (source_path.name, file_bytes, "text/plain"),
    }
    data = {"remark": remark}
    return api_multipart_post(
        path=f"/api/entities/{int(entity_id)}/codes/",
        token=token,
        data=data,
        files=files,
    )


def activate_code(entity_id: int, code_id: str, token: str) -> Dict[str, Any]:
    return api_request(
        "PUT",
        f"/api/entities/{int(entity_id)}/codes/{code_id}/",
        token=token,
        payload={"activate": True},
    )


def normalize_code_ref(value: Any) -> str:
    return re.sub(r"[^0-9a-f]", "", str(value or "").strip().lower())


def format_uuidish(code_id: Any) -> str:
    raw = normalize_code_ref(code_id)
    if len(raw) == 32:
        return f"{raw[:8]}-{raw[8:12]}-{raw[12:16]}-{raw[16:20]}-{raw[20:]}"
    return str(code_id or "").strip()


def extract_code_api_id(code: Dict[str, Any]) -> str:
    url = str(code.get("url", "")).strip()
    m = re.search(r"/codes/([0-9a-fA-F-]+)/", url)
    if m:
        return m.group(1).lower()
    return format_uuidish(code.get("id", ""))


def resolve_entity_code(entity_id: int, token: str, code_id: str = "", version: int | None = None) -> Dict[str, Any]:
    codes = get_entity_codes(entity_id, token)
    if version is not None:
        for code in codes:
            if isinstance(code, dict) and int(code.get("version", -1)) == int(version):
                return code
        raise RuntimeError(f"code version not found on entity {entity_id}: version={version}")

    want = normalize_code_ref(code_id)
    if not want:
        raise RuntimeError("either code_id or version is required")
    for code in codes:
        if not isinstance(code, dict):
            continue
        candidates = {
            normalize_code_ref(code.get("id", "")),
            normalize_code_ref(extract_code_api_id(code)),
        }
        if want in candidates:
            return code
    raise RuntimeError(f"code id not found on entity {entity_id}: {code_id}")


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


def cmd_activate_code(args: argparse.Namespace) -> int:
    token = require_token(args.token, "activate-code")
    version = int(args.version) if args.version is not None else None
    code = resolve_entity_code(
        entity_id=int(args.entity_id),
        token=token,
        code_id=args.code_id,
        version=version,
    )
    compile_status = str(code.get("compile_status", "")).strip()
    compact_code_id = str(code.get("id", "")).strip()
    api_code_id = extract_code_api_id(code)
    out = {
        "entity_id": int(args.entity_id),
        "requested_code_id": str(args.code_id or "").strip() or None,
        "requested_version": version,
        "resolved_code_id": compact_code_id or None,
        "resolved_api_code_id": api_code_id or None,
        "resolved_version": int(code.get("version", 0)) if str(code.get("version", "")).strip() else None,
        "compile_status": compile_status,
        "dry_run": bool(args.dry_run),
        "activated": False,
    }
    if args.dry_run:
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0
    if compile_status != "编译成功":
        raise RuntimeError(f"cannot activate code with compile_status={compile_status}")
    out["activate_response"] = activate_code(int(args.entity_id), api_code_id, token)
    out["activated"] = True
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


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


def create_room_match(game_id: int, entity_a: str, entity_b: str, token: str, request_timeout: float = 60.0) -> dict:
    room = api_request(
        "POST",
        "/api/rooms/",
        token=token,
        payload={"game_id": int(game_id), "player_number": 2},
        timeout=float(request_timeout),
    )
    room_id = room["id"]

    join_path = f"/api/rooms/{room_id}/join/"
    api_request(
        "POST",
        join_path,
        token=token,
        payload={"order": 0, "enter": True, "is_user": False, "is_remote": False, "entity": entity_a},
        timeout=float(request_timeout),
    )
    api_request(
        "POST",
        join_path,
        token=token,
        payload={"order": 1, "enter": True, "is_user": False, "is_remote": False, "entity": entity_b},
        timeout=float(request_timeout),
    )

    begin = api_request(
        "POST",
        f"/api/rooms/{room_id}/begin_match/",
        token=token,
        payload={},
        timeout=float(request_timeout),
    )
    return {
        "room_id": room_id,
        "match_id": begin.get("match_id"),
        "entity_a": entity_a,
        "entity_b": entity_b,
        "request_timeout": float(request_timeout),
    }


def fetch_ladders(game_id: int, limit: int, offset: int, token: str) -> Dict[str, Any]:
    q = urllib.parse.urlencode({"limit": int(limit), "offset": int(offset)})
    data = api_request("GET", f"/api/games/{int(game_id)}/ladders/?{q}", token=token)
    return data if isinstance(data, dict) else {}


def fetch_match_detail(match_id: int, token: str) -> Dict[str, Any]:
    data = api_request("GET", f"/api/matches/{int(match_id)}/", token=token)
    return data if isinstance(data, dict) else {}


def wait_match_finished(match_id: int, token: str, timeout_sec: float, poll_interval: float) -> Dict[str, Any]:
    deadline = time.time() + max(1.0, float(timeout_sec))
    last = {}
    while True:
        last = fetch_match_detail(match_id, token)
        state = str(last.get("state", "")).strip()
        if state and state not in ("准备中", "评测中"):
            return last
        if time.time() >= deadline:
            return last
        time.sleep(max(0.1, float(poll_interval)))


def is_match_finished_state(state: Any) -> bool:
    value = str(state or "").strip()
    return bool(value) and value not in ("准备中", "评测中")


def pick_filename_from_headers(headers: Dict[str, str], fallback: str) -> str:
    cd = headers.get("content-disposition", "")
    if cd:
        m = re.search(r"filename[^;=\n]*=((['\"]).*?\2|[^;\n]*)", cd)
        if m:
            name = m.group(1).strip().strip("\"'")
            if name:
                return name
    return fallback


def save_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def summarize_match_info(detail: Dict[str, Any]) -> list[Dict[str, Any]]:
    info = detail.get("info", [])
    out: list[Dict[str, Any]] = []
    if not isinstance(info, list):
        return out
    for i, p in enumerate(info):
        if not isinstance(p, dict):
            continue
        user = p.get("user", {}) if isinstance(p.get("user"), dict) else {}
        code = p.get("code", {}) if isinstance(p.get("code"), dict) else {}
        out.append(
            {
                "info_index": i,
                "username": user.get("username"),
                "rank": p.get("rank"),
                "score": p.get("score"),
                "end_state": p.get("end_state"),
                "code_id": code.get("id"),
                "entity": code.get("entity"),
                "version": code.get("version"),
            }
        )
    return out


def cmd_room_match(args: argparse.Namespace) -> int:
    token = require_token(args.token, "room-match")

    rows = []
    for i in range(args.count):
        if args.swap and i % 2 == 1:
            a, b = args.entity_b, args.entity_a
        else:
            a, b = args.entity_a, args.entity_b
        row = create_room_match(args.game_id, a, b, token, request_timeout=float(args.request_timeout))
        rows.append(row)
        if args.interval > 0 and i + 1 < args.count:
            time.sleep(args.interval)

    print(json.dumps({"count": len(rows), "rows": rows}, ensure_ascii=False, indent=2))
    return 0


def cmd_ladders(args: argparse.Namespace) -> int:
    token = require_token(args.token, "ladders")
    data = fetch_ladders(args.game_id, args.limit, args.offset, token)
    rows = data.get("results", []) if isinstance(data, dict) else []
    compact = []
    if isinstance(rows, list):
        for i, r in enumerate(rows):
            if not isinstance(r, dict):
                continue
            code = r.get("code", {}) if isinstance(r.get("code"), dict) else {}
            entity = code.get("entity", {}) if isinstance(code.get("entity"), dict) else {}
            compact.append(
                {
                    "idx": i + int(args.offset),
                    "user": r.get("user"),
                    "score": r.get("score"),
                    "code_id": code.get("id"),
                    "entity_id": entity.get("id"),
                    "entity_name": entity.get("name"),
                    "version": code.get("version"),
                }
            )
    out = {
        "game_id": int(args.game_id),
        "count": data.get("count") if isinstance(data, dict) else None,
        "next": data.get("next") if isinstance(data, dict) else None,
        "previous": data.get("previous") if isinstance(data, dict) else None,
        "rows": compact,
    }
    if args.raw:
        out["raw"] = data
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


def cmd_download_replay(args: argparse.Namespace) -> int:
    token = require_token(args.token, "download-replay")
    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    detail = fetch_match_detail(args.match_id, token)
    if args.wait_finish and not is_match_finished_state(detail.get("state") if detail else None):
        detail = wait_match_finished(
            match_id=int(args.match_id),
            token=token,
            timeout_sec=float(args.wait_timeout),
            poll_interval=float(args.poll_interval),
        )

    detail_path = out_dir / f"match_{int(args.match_id)}.json"
    save_json(detail_path, detail)
    if not is_match_finished_state(detail.get("state") if detail else None):
        raise RuntimeError(
            f"match {int(args.match_id)} not finished after waiting; "
            f"state={detail.get('state') if detail else None}; detail_path={detail_path}"
        )

    data, headers = api_download(f"/api/matches/{int(args.match_id)}/download/", token=token)
    fallback = f"match_{int(args.match_id)}.bin"
    filename = pick_filename_from_headers(headers, fallback)
    replay_path = out_dir / filename
    replay_path.write_bytes(data)
    out = {
        "match_id": int(args.match_id),
        "state": detail.get("state"),
        "logic_version": detail.get("logic_version"),
        "replay_path": str(replay_path),
        "detail_path": str(detail_path),
        "size": len(data),
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


def cmd_run_matches(args: argparse.Namespace) -> int:
    token = require_token(args.token, "run-matches")
    save_dir = Path(args.save_dir).resolve()
    save_dir.mkdir(parents=True, exist_ok=True)

    rows: list[Dict[str, Any]] = []
    for i in range(int(args.count)):
        if args.swap and i % 2 == 1:
            a, b = args.entity_b, args.entity_a
        else:
            a, b = args.entity_a, args.entity_b

        started = create_room_match(args.game_id, a, b, token, request_timeout=float(args.request_timeout))
        match_id = int(started.get("match_id", 0) or 0)
        detail: Dict[str, Any] = {}
        if match_id > 0:
            detail = wait_match_finished(
                match_id=match_id,
                token=token,
                timeout_sec=float(args.wait_timeout),
                poll_interval=float(args.poll_interval),
            )

        replay_path = ""
        detail_path = ""
        replay_size = 0
        replay_note = ""
        if match_id > 0:
            detail_path_obj = save_dir / f"match_{match_id}.json"
            save_json(detail_path_obj, detail)
            detail_path = str(detail_path_obj)
            if args.download_replay:
                if is_match_finished_state(detail.get("state") if detail else None):
                    data, headers = api_download(f"/api/matches/{match_id}/download/", token=token)
                    name = pick_filename_from_headers(headers, f"match_{match_id}.bin")
                    replay_obj = save_dir / name
                    replay_obj.write_bytes(data)
                    replay_path = str(replay_obj)
                    replay_size = len(data)
                else:
                    replay_note = f"skip download because state={detail.get('state') if detail else None}"

        rows.append(
            {
                "index": i,
                "room_id": started.get("room_id"),
                "match_id": match_id,
                "entity_a": a,
                "entity_b": b,
                "state": detail.get("state") if detail else None,
                "logic_version": detail.get("logic_version") if detail else None,
                "players": summarize_match_info(detail) if detail else [],
                "detail_path": detail_path,
                "replay_path": replay_path,
                "replay_size": replay_size,
                "replay_note": replay_note,
            }
        )
        if args.interval > 0 and i + 1 < int(args.count):
            time.sleep(float(args.interval))

    print(json.dumps({"count": len(rows), "rows": rows}, ensure_ascii=False, indent=2))
    return 0


def cmd_entities(args: argparse.Namespace) -> int:
    token = require_token(args.token, "entities")
    profile = get_profile(token)
    user = str(profile.get("user", {}).get("username", "")).strip()
    if not user:
        raise RuntimeError("cannot resolve username from /api/profile/")
    data = get_user_entities(user, args.game_id, token)
    entities = data.get("entities", []) if isinstance(data, dict) else []
    active = data.get("active") if isinstance(data, dict) else None
    out = {
        "username": user,
        "game_id": int(args.game_id),
        "active": active,
        "count": len(entities) if isinstance(entities, list) else 0,
        "entities": entities if isinstance(entities, list) else [],
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


def cmd_codes(args: argparse.Namespace) -> int:
    token = require_token(args.token, "codes")
    rows = get_entity_codes(args.entity_id, token)
    print(
        json.dumps(
            {
                "entity_id": int(args.entity_id),
                "count": len(rows),
                "codes": rows,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def cmd_upload_ai(args: argparse.Namespace) -> int:
    token = require_token(args.token, "upload-ai")
    source = Path(args.source).resolve()
    if not source.is_file():
        raise RuntimeError(f"source file not found: {source}")

    user = str(getattr(args, "username", "") or os.environ.get("SAIBLO_USERNAME", "")).strip()
    if not user:
        profile = get_profile(token)
        user = str(profile.get("user", {}).get("username", "")).strip()
    if not user:
        raise RuntimeError("cannot resolve username from /api/profile/")

    entity_id = int(args.entity_id) if int(args.entity_id) > 0 else 0
    entity_name = str(args.entity_name or "").strip()

    listing_error = ""
    skip_entity_list = (
        bool(getattr(args, "skip_entity_list", False))
        or os.environ.get("SAIBLO_SKIP_ENTITY_LIST", "").strip().lower() in {"1", "true", "yes"}
    )
    if skip_entity_list and entity_id > 0:
        listing_error = "skipped by SAIBLO_SKIP_ENTITY_LIST"
        entities = [{"id": entity_id, "name": entity_name or str(entity_id)}]
    elif skip_entity_list and args.create_if_missing and entity_name and entity_id <= 0:
        listing_error = "skipped by SAIBLO_SKIP_ENTITY_LIST"
        entities = []
    else:
        try:
            data = get_user_entities(user, args.game_id, token)
            entities = data.get("entities", []) if isinstance(data, dict) else []
            if not isinstance(entities, list):
                entities = []
        except Exception as exc:
            if not (args.create_if_missing and entity_name and entity_id <= 0):
                raise
            listing_error = str(exc)
            entities = []

    selected_entity: Dict[str, Any] | None = None
    if entity_id > 0:
        for e in entities:
            if isinstance(e, dict) and int(e.get("id", -1)) == entity_id:
                selected_entity = e
                break
    elif entity_name:
        for e in entities:
            if isinstance(e, dict) and str(e.get("name", "")) == entity_name:
                selected_entity = e
                break
    else:
        raise RuntimeError("either --entity-id or --entity-name is required")

    created = False
    if selected_entity is None:
        if not args.create_if_missing:
            raise RuntimeError("target entity not found; use --create-if-missing")
        if not entity_name:
            raise RuntimeError("--entity-name is required when creating entity")
        selected_entity = create_entity(
            username=user,
            game_id=args.game_id,
            name=entity_name,
            language=args.language,
            token=token,
        )
        created = True

    entity_id = int(selected_entity.get("id", 0))
    if entity_id <= 0:
        raise RuntimeError(f"invalid entity selected: {selected_entity}")

    uploaded = upload_entity_code(
        entity_id=entity_id,
        source_path=source,
        remark=args.remark,
        token=token,
    )

    code_id = str(uploaded.get("id", "")).strip()
    version = int(uploaded.get("version", 0)) if str(uploaded.get("version", "")).strip() else None
    compile_status = str(uploaded.get("compile_status", "")).strip()

    waited_polls = 0
    if args.wait_compile and code_id:
        for i in range(max(1, int(args.poll_max))):
            waited_polls = i + 1
            codes = get_entity_codes(entity_id, token)
            cur = None
            for c in codes:
                if isinstance(c, dict) and str(c.get("id", "")).strip() == code_id:
                    cur = c
                    break
            if cur is not None:
                compile_status = str(cur.get("compile_status", "")).strip()
                uploaded = cur
            if compile_status not in ("", "未编译", "编译中", "等待中", "Pending", "Compiling"):
                break
            time.sleep(max(0.1, float(args.poll_interval)))

    activated = False
    activate_resp: Dict[str, Any] | None = None
    if args.activate and code_id:
        if compile_status == "编译成功":
            activate_resp = activate_code(entity_id, extract_code_api_id(uploaded), token)
            activated = True
        else:
            activate_resp = {"skipped": True, "reason": f"compile_status={compile_status}"}

    out = {
        "username": user,
        "game_id": int(args.game_id),
        "source": str(source),
        "entity_created": created,
        "entity_listing_error": listing_error,
        "entity_id": entity_id,
        "entity_name": selected_entity.get("name"),
        "uploaded_code_id": code_id,
        "uploaded_version": version,
        "compile_status": compile_status,
        "waited_polls": waited_polls,
        "activated": activated,
        "activate_response": activate_resp,
        "uploaded": uploaded,
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
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

    sp_room = sub.add_parser("room-match", help="create room and start match between two code ids")
    sp_room.add_argument("--game-id", type=int, default=48)
    sp_room.add_argument("--entity-a", required=True, help="code id of seat 0")
    sp_room.add_argument("--entity-b", required=True, help="code id of seat 1")
    sp_room.add_argument("--count", type=int, default=1)
    sp_room.add_argument("--swap", action="store_true", help="alternate seat order between runs")
    sp_room.add_argument("--interval", type=float, default=0.0, help="seconds between room creations")
    sp_room.add_argument("--request-timeout", type=float, default=60.0, help="timeout seconds for room/join/begin POSTs")
    sp_room.set_defaults(func=cmd_room_match)

    sp_ladder = sub.add_parser("ladders", help="list game ranklist (ladders)")
    sp_ladder.add_argument("--game-id", type=int, default=48)
    sp_ladder.add_argument("--limit", type=int, default=20)
    sp_ladder.add_argument("--offset", type=int, default=0)
    sp_ladder.add_argument("--raw", action="store_true", help="include raw response payload")
    sp_ladder.set_defaults(func=cmd_ladders)

    sp_dl = sub.add_parser("download-replay", help="download replay + detail json for one match")
    sp_dl.add_argument("--match-id", type=int, required=True)
    sp_dl.add_argument("--out-dir", default="replays/saiblo_api")
    sp_dl.add_argument("--wait-finish", action="store_true", help="wait until match finished before download")
    sp_dl.add_argument("--wait-timeout", type=float, default=120.0, help="max seconds waiting for match finish")
    sp_dl.add_argument("--poll-interval", type=float, default=1.5, help="poll interval while waiting")
    sp_dl.set_defaults(func=cmd_download_replay)

    sp_run = sub.add_parser("run-matches", help="create matches from two code ids, wait finish, and save detail/replay")
    sp_run.add_argument("--game-id", type=int, default=48)
    sp_run.add_argument("--entity-a", required=True, help="code id of seat 0")
    sp_run.add_argument("--entity-b", required=True, help="code id of seat 1")
    sp_run.add_argument("--count", type=int, default=2)
    sp_run.add_argument("--swap", action="store_true", help="alternate seat order between runs")
    sp_run.add_argument("--interval", type=float, default=0.0, help="seconds between room creations")
    sp_run.add_argument("--request-timeout", type=float, default=60.0, help="timeout seconds for room/join/begin POSTs")
    sp_run.add_argument("--wait-timeout", type=float, default=120.0, help="max seconds per match waiting")
    sp_run.add_argument("--poll-interval", type=float, default=1.5, help="poll interval while waiting")
    sp_run.add_argument("--save-dir", default="replays/saiblo_api")
    sp_run.add_argument("--download-replay", action="store_true")
    sp_run.set_defaults(func=cmd_run_matches)

    sp_entities = sub.add_parser("entities", help="list my entities for one game")
    sp_entities.add_argument("--game-id", type=int, default=48)
    sp_entities.set_defaults(func=cmd_entities)

    sp_codes = sub.add_parser("codes", help="list uploaded codes for one entity id")
    sp_codes.add_argument("--entity-id", type=int, required=True)
    sp_codes.set_defaults(func=cmd_codes)

    sp_activate = sub.add_parser("activate-code", help="activate one existing code on an entity")
    sp_activate.add_argument("--entity-id", type=int, required=True)
    target = sp_activate.add_mutually_exclusive_group(required=True)
    target.add_argument("--code-id", default="", help="uploaded code id, hyphenated or compact")
    target.add_argument("--version", type=int, help="uploaded version number on the entity")
    sp_activate.add_argument("--dry-run", action="store_true", help="resolve target code without sending activation request")
    sp_activate.set_defaults(func=cmd_activate_code)

    sp_upload = sub.add_parser("upload-ai", help="upload source file to one AI entity (create if needed)")
    sp_upload.add_argument("--game-id", type=int, default=48)
    sp_upload.add_argument("--entity-id", type=int, default=0)
    sp_upload.add_argument("--entity-name", default="", help="entity name; required when creating")
    sp_upload.add_argument("--create-if-missing", action="store_true")
    sp_upload.add_argument("--language", default="cpp", help="language for entity creation, e.g. cpp/python/remote")
    sp_upload.add_argument("--source", required=True, help="source file path to upload")
    sp_upload.add_argument("--remark", default="uploaded via saiblo_tools upload-ai")
    sp_upload.add_argument("--username", default="", help="known Saiblo username; skips /api/profile/ lookup when set")
    sp_upload.add_argument("--skip-entity-list", action="store_true", help="create --entity-name directly instead of listing existing entities first")
    sp_upload.add_argument("--wait-compile", action="store_true", help="poll compile status after upload")
    sp_upload.add_argument("--poll-interval", type=float, default=2.0)
    sp_upload.add_argument("--poll-max", type=int, default=30)
    sp_upload.add_argument("--activate", action="store_true", help="activate uploaded code if compile succeeded")
    sp_upload.set_defaults(func=cmd_upload_ai)

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
