#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from saiblo_tools import (  # type: ignore
    api_download,
    create_room_match,
    fetch_match_detail,
    is_match_finished_state,
    pick_filename_from_headers,
    resolve_token,
    save_json,
)


def normalize_code_id(value: str) -> str:
    return str(value or "").replace("-", "").lower().strip()


def parse_opponents(values: list[str]) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for item in values:
        if ":" not in item:
            raise SystemExit(f"invalid opponent spec: {item!r}; expected label:code_id")
        label, code_id = item.split(":", 1)
        label = label.strip()
        code_id = normalize_code_id(code_id)
        if not label or not code_id:
            raise SystemExit(f"invalid opponent spec: {item!r}")
        out.append((label, code_id))
    return out


def load_existing_matches(run_dir: Path, our_code_id: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(run_dir.glob("match_*.json")):
        try:
            detail = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        info = detail.get("info", [])
        our_seat = None
        if isinstance(info, list):
            for idx, row in enumerate(info):
                if not isinstance(row, dict):
                    continue
                code = row.get("code", {})
                if not isinstance(code, dict):
                    continue
                if normalize_code_id(str(code.get("id", ""))) == our_code_id:
                    our_seat = idx
                    break
        match_id = int(detail.get("id", 0) or 0)
        rows.append(
            {
                "match_id": match_id,
                "our_seat": our_seat,
                "state": detail.get("state"),
                "detail": detail,
                "detail_path": str(path),
            }
        )
    return rows


def success_counts(rows: list[dict[str, Any]]) -> tuple[int, int, int]:
    total = 0
    seat0 = 0
    seat1 = 0
    for row in rows:
        if not is_match_success_state(row.get("state")):
            continue
        total += 1
        if row.get("our_seat") == 0:
            seat0 += 1
        elif row.get("our_seat") == 1:
            seat1 += 1
    return total, seat0, seat1


def ensure_target_matches(
    *,
    game_id: int,
    token: str,
    our_code_id: str,
    opp_code_id: str,
    target_count: int,
    target_each_seat: int,
    run_dir: Path,
) -> list[dict[str, Any]]:
    rows = load_existing_matches(run_dir, our_code_id)
    seat0 = sum(1 for row in rows if row.get("our_seat") == 0)
    seat1 = sum(1 for row in rows if row.get("our_seat") == 1)
    while len(rows) < target_count:
        if seat0 < target_each_seat:
            a, b = our_code_id, opp_code_id
            our_seat = 0
            seat0 += 1
        elif seat1 < target_each_seat:
            a, b = opp_code_id, our_code_id
            our_seat = 1
            seat1 += 1
        else:
            break
        started = create_room_match(game_id, a, b, token, request_timeout=60.0)
        match_id = int(started.get("match_id", 0) or 0)
        rows.append(
            {
                "match_id": match_id,
                "our_seat": our_seat,
                "state": "准备中",
                "detail": {},
                "detail_path": str(run_dir / f"match_{match_id}.json"),
            }
        )
    return rows


def append_replacement_matches(
    *,
    game_id: int,
    token: str,
    rows: list[dict[str, Any]],
    our_code_id: str,
    opp_code_id: str,
    target_count: int,
    target_each_seat: int,
    run_dir: Path,
) -> list[dict[str, Any]]:
    success_total, success_seat0, success_seat1 = success_counts(rows)
    while success_total < target_count or success_seat0 < target_each_seat or success_seat1 < target_each_seat:
        if success_seat0 < target_each_seat:
            a, b = our_code_id, opp_code_id
            our_seat = 0
            success_seat0 += 1
        elif success_seat1 < target_each_seat:
            a, b = opp_code_id, our_code_id
            our_seat = 1
            success_seat1 += 1
        else:
            if success_seat0 <= success_seat1:
                a, b = our_code_id, opp_code_id
                our_seat = 0
                success_seat0 += 1
            else:
                a, b = opp_code_id, our_code_id
                our_seat = 1
                success_seat1 += 1
        started = create_room_match(game_id, a, b, token, request_timeout=60.0)
        match_id = int(started.get("match_id", 0) or 0)
        rows.append(
            {
                "match_id": match_id,
                "our_seat": our_seat,
                "state": "准备中",
                "detail": {},
                "detail_path": str(run_dir / f"match_{match_id}.json"),
            }
        )
        success_total += 1
    return rows


def download_replay_if_ready(token: str, match_id: int, run_dir: Path) -> str:
    current = list(run_dir.glob(f"{match_id}.*"))
    if current:
        return str(current[0])
    data, headers = api_download(f"/api/matches/{match_id}/download/", token=token)
    name = pick_filename_from_headers(headers, f"match_{match_id}.bin")
    replay_path = run_dir / name
    replay_path.write_bytes(data)
    return str(replay_path)


def is_match_success_state(value: Any) -> bool:
    return str(value or "").strip() == "评测成功"


def poll_until_done(
    *,
    token: str,
    rows: list[dict[str, Any]],
    run_dir: Path,
    timeout_sec: float,
    poll_interval: float,
) -> list[dict[str, Any]]:
    deadline = time.time() + timeout_sec
    done: set[int] = set()
    while len(done) < len(rows):
        if time.time() >= deadline:
            break
        progressed = False
        for row in rows:
            match_id = int(row["match_id"])
            if match_id in done:
                continue
            detail = fetch_match_detail(match_id, token)
            row["detail"] = detail
            row["state"] = detail.get("state")
            save_json(run_dir / f"match_{match_id}.json", detail)
            if is_match_finished_state(detail.get("state")):
                if is_match_success_state(detail.get("state")):
                    row["replay_path"] = download_replay_if_ready(token, match_id, run_dir)
                done.add(match_id)
                progressed = True
        if len(done) >= len(rows):
            break
        if not progressed:
            time.sleep(poll_interval)
    return rows


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create/poll/download batches of Saiblo room matches by code id")
    parser.add_argument("--game-id", type=int, default=48)
    parser.add_argument("--our-code-id", required=True)
    parser.add_argument("--opponent", action="append", required=True, help="label:code_id")
    parser.add_argument("--count", type=int, default=10)
    parser.add_argument("--each-seat", type=int, default=5)
    parser.add_argument("--save-root", required=True)
    parser.add_argument("--timeout-sec", type=float, default=14400.0)
    parser.add_argument("--poll-interval", type=float, default=10.0)
    parser.add_argument("--token", default="")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    token, source = resolve_token(args.token)
    if not token:
        raise SystemExit("missing bearer token")
    save_root = Path(args.save_root).resolve()
    save_root.mkdir(parents=True, exist_ok=True)
    our_code_id = normalize_code_id(args.our_code_id)
    opponents = parse_opponents(args.opponent)
    output: dict[str, Any] = {
        "game_id": int(args.game_id),
        "our_code_id": our_code_id,
        "token_source": source,
        "groups": {},
    }
    for label, opp_code_id in opponents:
        run_dir = save_root / label
        run_dir.mkdir(parents=True, exist_ok=True)
        rows = ensure_target_matches(
            game_id=int(args.game_id),
            token=token,
            our_code_id=our_code_id,
            opp_code_id=opp_code_id,
            target_count=int(args.count),
            target_each_seat=int(args.each_seat),
            run_dir=run_dir,
        )
        deadline = time.time() + float(args.timeout_sec)
        while True:
            remaining = max(0.0, deadline - time.time())
            if remaining <= 0:
                break
            rows = poll_until_done(
                token=token,
                rows=rows,
                run_dir=run_dir,
                timeout_sec=remaining,
                poll_interval=float(args.poll_interval),
            )
            success_total, success_seat0, success_seat1 = success_counts(rows)
            if success_total >= int(args.count) and success_seat0 >= int(args.each_seat) and success_seat1 >= int(args.each_seat):
                break
            if any(not is_match_finished_state(row.get("state")) for row in rows):
                break
            rows = append_replacement_matches(
                game_id=int(args.game_id),
                token=token,
                rows=rows,
                our_code_id=our_code_id,
                opp_code_id=opp_code_id,
                target_count=int(args.count),
                target_each_seat=int(args.each_seat),
                run_dir=run_dir,
            )
        output["groups"][label] = {
            "opponent_code_id": opp_code_id,
            "count": len(rows),
            "finished": sum(1 for row in rows if is_match_finished_state(row.get("state"))),
            "success": sum(1 for row in rows if is_match_success_state(row.get("state"))),
            "rows": rows,
        }
        save_json(run_dir / "_batch_manifest.json", output["groups"][label])
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
