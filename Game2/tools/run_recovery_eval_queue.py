#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from saiblo_tools import get_profile, require_token

DEFAULT_LABELS = ['n514d', 'n514e', 'n518a', 'n518b', 'n519a', 'n519b']
OUT_DIR = ROOT / 'Game2' / 'runtime' / 'recovery_eval_queue'


def utc_stamp() -> str:
    return time.strftime('%Y%m%d_%H%M%S', time.gmtime())


def log(message: str) -> None:
    print(f'[recovery-queue] {message}', file=sys.stderr, flush=True)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def run_command(cmd: list[str], dry_run: bool) -> subprocess.CompletedProcess[str] | None:
    log(' '.join(cmd))
    if dry_run:
        return None
    return subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True, check=False)


def parse_json_stdout(completed: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    text = completed.stdout.strip()
    if not text:
        return {}
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f'cannot parse JSON stdout: {exc}\n{text[-1000:]}') from exc
    return data if isinstance(data, dict) else {}


def verify_expected_username(expected_username: str) -> dict[str, Any]:
    expected = str(expected_username or '').strip()
    if not expected:
        return {'checked': False}
    token = require_token('', 'game2-recovery-eval-queue username check')
    profile = get_profile(token)
    user = profile.get('user', {}) if isinstance(profile.get('user'), dict) else {}
    username = str(user.get('username', '')).strip()
    row = {'checked': True, 'expected_username': expected, 'username': username}
    if username != expected:
        raise RuntimeError(f'current token username is {username!r}, expected {expected!r}; aborting before upload')
    return row


def upload_label(label: str, args: argparse.Namespace) -> dict[str, Any]:
    source = ROOT / 'Game2' / 'deepclue_ai' / label / 'ai.py'
    if not source.is_file():
        raise RuntimeError(f'source file missing for {label}: {source}')
    cmd = [
        'python3',
        'saiblo_tools.py',
        'upload-ai',
        '--game-id',
        '53',
        '--entity-name',
        label,
        '--create-if-missing',
        '--language',
        'python',
        '--source',
        str(source.relative_to(ROOT)),
        '--remark',
        'r',
        '--wait-compile',
        '--poll-interval',
        str(args.upload_poll_interval),
        '--poll-max',
        str(args.upload_poll_max),
    ]
    completed = run_command(cmd, args.dry_run)
    if completed is None:
        return {'dry_run': True, 'label': label, 'source': str(source)}
    if completed.returncode != 0:
        raise RuntimeError(f'upload failed for {label}: rc={completed.returncode}\nSTDERR:\n{completed.stderr}\nSTDOUT:\n{completed.stdout}')
    data = parse_json_stdout(completed)
    status = str(data.get('compile_status', '')).strip()
    if status != '编译成功':
        raise RuntimeError(f'upload did not compile for {label}: compile_status={status} data={data}')
    return data


def eval_code(label: str, code_id: str, args: argparse.Namespace) -> dict[str, Any]:
    cmd = [
        'python3',
        'Game2/tools/run_room_eval.py',
        '--code-id',
        code_id,
        '--label',
        label,
        '--count',
        str(args.count),
        '--timeout',
        str(args.timeout),
        '--poll-interval',
        str(args.eval_poll_interval),
        '--request-timeout',
        str(args.request_timeout),
    ]
    completed = run_command(cmd, args.dry_run)
    if completed is None:
        return {'dry_run': True, 'label': label, 'code_id': code_id}
    if completed.returncode != 0:
        raise RuntimeError(f'room eval failed for {label}: rc={completed.returncode}\nSTDERR:\n{completed.stderr}\nSTDOUT:\n{completed.stdout}')
    data = parse_json_stdout(completed)
    return data


def valid_eval_count(data: dict[str, Any]) -> int:
    rows = data.get('rows')
    if not isinstance(rows, list):
        return 0
    total = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        score = row.get('score')
        if row.get('end_state') == 'OK' and isinstance(score, int) and score > 0:
            total += 1
    return total


def main() -> int:
    parser = argparse.ArgumentParser(description='Upload and evaluate a neutral Game53 recovery queue without batch or ladder activation')
    parser.add_argument('--labels', nargs='+', default=DEFAULT_LABELS)
    parser.add_argument('--count', type=int, default=5)
    parser.add_argument('--timeout', type=float, default=420.0)
    parser.add_argument('--request-timeout', type=float, default=90.0)
    parser.add_argument('--eval-poll-interval', type=float, default=2.0)
    parser.add_argument('--upload-poll-interval', type=float, default=10.0)
    parser.add_argument('--upload-poll-max', type=int, default=30)
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--continue-on-error', action='store_true')
    parser.add_argument(
        '--allow-partial-eval',
        action='store_true',
        help='mark a label ok even if fewer than --count valid room samples were collected',
    )
    parser.add_argument(
        '--expected-username',
        default=os.environ.get('SAIBLO_EXPECTED_USERNAME', ''),
        help='optional safety guard; abort before upload unless the current token resolves to this username',
    )
    args = parser.parse_args()

    out_dir = OUT_DIR / utc_stamp()
    username_check = verify_expected_username(args.expected_username)
    rows: list[dict[str, Any]] = []
    for label in args.labels:
        row: dict[str, Any] = {'label': label}
        try:
            upload = upload_label(label, args)
            row['upload'] = upload
            code_id = str(upload.get('uploaded_code_id') or '').replace('-', '')
            if args.dry_run:
                code_id = '<uploaded-code-id>'
            if not code_id:
                raise RuntimeError(f'upload did not return code id for {label}: {upload}')
            eval_data = eval_code(label, code_id, args)
            row['eval'] = eval_data
            row['valid_eval_count'] = valid_eval_count(eval_data)
            if not args.dry_run and not args.allow_partial_eval and row['valid_eval_count'] < max(1, int(args.count)):
                raise RuntimeError(
                    f'room eval for {label} produced {row["valid_eval_count"]}/{args.count} valid samples'
                )
            row['ok'] = True
        except Exception as exc:
            row['ok'] = False
            row['error'] = f'{type(exc).__name__}: {exc}'
            log(row['error'])
            rows.append(row)
            if not args.continue_on_error:
                break
            continue
        rows.append(row)

    summary = {
        'labels': args.labels,
        'dry_run': bool(args.dry_run),
        'username_check': username_check,
        'rows': rows,
        'out_dir': str(out_dir),
    }
    write_json(out_dir / 'summary.json', summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if all(row.get('ok') for row in rows) else 1


if __name__ == '__main__':
    raise SystemExit(main())
