#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from saiblo_tools import get_entity_codes, require_token, resolve_token
from Game2.tools.run_room_eval import GAME_ID, RoomStartError, create_single_player_match


DEFAULT_PROBE_CODE_ID = 'a2b68a7ec9b84a59a8dfd836defd930c'
DEFAULT_STATUS_JSONL = ROOT / 'Game2' / 'runtime' / 'recovery_watch' / 'status.jsonl'
PENDING_STATUSES = {'', '未编译', '编译中', '等待中', 'Pending', 'Compiling'}


def utc_now() -> str:
    return time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())


def log(message: str) -> None:
    print(f'[recovery-watch] {message}', file=sys.stderr, flush=True)


def write_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a', encoding='utf-8') as handle:
        handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + '\n')


def code_statuses(entity_ids: list[int], token: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for entity_id in entity_ids:
        try:
            codes = get_entity_codes(entity_id, token)
        except Exception as exc:
            rows.append({'entity_id': entity_id, 'error': f'{type(exc).__name__}: {exc}'})
            continue
        for code in codes:
            if not isinstance(code, dict):
                continue
            status = str(code.get('compile_status', '')).strip()
            rows.append(
                {
                    'entity_id': entity_id,
                    'version': code.get('version'),
                    'code_id': str(code.get('id', '')).replace('-', ''),
                    'compile_status': status,
                    'pending': status in PENDING_STATUSES,
                }
            )
    return rows


def probe_room(code_id: str, token: str, request_timeout: float) -> dict[str, Any]:
    try:
        started = create_single_player_match(GAME_ID, code_id, token, timeout=request_timeout)
        return {'ok': True, 'room_id': started.get('room_id'), 'match_id': started.get('match_id')}
    except RoomStartError as exc:
        return {'ok': False, 'room_id': exc.room_id, 'error': f'{type(exc).__name__}: {exc}'}
    except Exception as exc:
        return {'ok': False, 'error': f'{type(exc).__name__}: {exc}'}


def run_callback(command: str, cwd: Path) -> int:
    log(f'running callback: {command}')
    completed = subprocess.run(command, cwd=str(cwd), shell=True, check=False)
    return int(completed.returncode)


def main() -> int:
    parser = argparse.ArgumentParser(description='Low-frequency Game53 Saiblo recovery watcher')
    parser.add_argument('--probe-code-id', default=DEFAULT_PROBE_CODE_ID)
    parser.add_argument('--compile-entity-id', type=int, action='append', default=[21072, 21073, 21074])
    parser.add_argument('--interval', type=float, default=900.0, help='seconds between checks; default 15 minutes')
    parser.add_argument('--initial-delay', type=float, default=0.0, help='seconds to wait before the first check')
    parser.add_argument('--max-checks', type=int, default=0, help='0 means run until recovered')
    parser.add_argument('--request-timeout', type=float, default=90.0)
    parser.add_argument('--status-jsonl', default=str(DEFAULT_STATUS_JSONL))
    parser.add_argument('--once', action='store_true')
    parser.add_argument('--skip-room-probe', action='store_true')
    parser.add_argument('--require-compile-clear', action='store_true')
    parser.add_argument('--callback', default='', help='shell command to run once recovery is detected')
    args = parser.parse_args()

    token, _ = resolve_token('')
    token = require_token(token, 'game2-recovery-watch')

    status_path = Path(args.status_jsonl).resolve()
    max_checks = 1 if args.once else int(args.max_checks)
    check_index = 0
    if args.initial_delay > 0:
        sleep_sec = max(0.0, float(args.initial_delay))
        log(f'initial delay {sleep_sec:.0f}s')
        time.sleep(sleep_sec)
    while True:
        check_index += 1
        compile_rows = code_statuses([int(x) for x in args.compile_entity_id], token)
        pending = [row for row in compile_rows if row.get('pending') or row.get('error')]
        room_result = {'ok': False, 'skipped': True} if args.skip_room_probe else probe_room(args.probe_code_id, token, args.request_timeout)
        if args.skip_room_probe:
            recovered = bool(args.require_compile_clear and not pending)
        else:
            recovered = bool(room_result.get('ok')) and (not args.require_compile_clear or not pending)
        row = {
            'time': utc_now(),
            'check': check_index,
            'recovered': recovered,
            'pending_compile_count': len(pending),
            'compile_rows': compile_rows,
            'room_probe': room_result,
        }
        write_jsonl(status_path, row)
        log(
            f"check={check_index} recovered={recovered} "
            f"pending_compile={len(pending)} room_ok={room_result.get('ok')} "
            f"room={room_result.get('room_id')} match={room_result.get('match_id')}"
        )
        if recovered:
            if args.callback:
                return run_callback(args.callback, ROOT)
            return 0
        if max_checks and check_index >= max_checks:
            return 1
        sleep_sec = max(60.0, float(args.interval))
        log(f'sleeping {sleep_sec:.0f}s')
        time.sleep(sleep_sec)


if __name__ == '__main__':
    raise SystemExit(main())
