#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analyze_match import analyze_match_payload, render_markdown as render_match_markdown
from saiblo_tools import (
    api_download,
    api_request,
    get_entity_codes,
    get_profile,
    get_user_entities,
    require_token,
    resolve_token,
)

GAME_ID = 53
RUNTIME_DIR = ROOT / 'Game2' / 'runtime' / 'room_matches'
LATEST_MD = ROOT / 'docs' / 'generated' / 'game2_latest_room_eval.md'
LATEST_JSON = ROOT / 'docs' / 'generated' / 'game2_latest_room_eval.json'


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding='utf-8')


def log(message: str) -> None:
    print(f'[room-eval] {message}', file=sys.stderr, flush=True)


def normalized_code_id(value: Any) -> str:
    return str(value or '').replace('-', '').strip().lower()


def create_single_player_match(game_id: int, code_id: str, token: str, timeout: float) -> dict[str, Any]:
    room = api_request(
        'POST',
        '/api/rooms/',
        token=token,
        payload={'game_id': int(game_id), 'player_number': 1},
        timeout=timeout,
    )
    room_id = int(room.get('id', 0) or 0)
    if not room_id:
        raise RuntimeError(f'cannot create room: {room!r}')
    try:
        api_request(
            'POST',
            f'/api/rooms/{room_id}/join/',
            token=token,
            payload={'order': 0, 'enter': True, 'is_user': False, 'is_remote': False, 'entity': code_id},
            timeout=timeout,
        )
    except Exception as exc:
        detail = api_request('GET', f'/api/rooms/{room_id}/', token=token, timeout=timeout)
        positions = detail.get('positions', []) if isinstance(detail, dict) else []
        seated = any(isinstance(pos, dict) and isinstance(pos.get('code'), dict) for pos in positions)
        if not seated:
            raise
        log(f'room {room_id}: join raised {type(exc).__name__}, but room detail shows a seated code; continuing to begin_match')
    begin = api_request('POST', f'/api/rooms/{room_id}/begin_match/', token=token, payload={}, timeout=timeout)
    match_id = int(begin.get('match_id', 0) or 0)
    if not match_id:
        raise RuntimeError(f'cannot begin match for room {room_id}: {begin!r}')
    return {'room_id': room_id, 'match_id': match_id, 'code_id': code_id}


def fetch_match(match_id: int, token: str, timeout: float) -> dict[str, Any]:
    data = api_request('GET', f'/api/matches/{int(match_id)}/', token=token, timeout=timeout)
    return data if isinstance(data, dict) else {}


def is_finished(state: Any) -> bool:
    value = str(state or '').strip()
    return bool(value) and value not in ('准备中', '评测中')


def wait_match(match_id: int, token: str, timeout_sec: float, poll_interval: float) -> dict[str, Any]:
    deadline = time.time() + max(1.0, timeout_sec)
    detail: dict[str, Any] = {}
    while True:
        detail = fetch_match(match_id, token, timeout=30.0)
        if is_finished(detail.get('state')):
            return detail
        if time.time() >= deadline:
            return detail
        time.sleep(max(0.2, poll_interval))


def download_trace(match_id: int, token: str) -> tuple[dict[str, Any], str]:
    try:
        body, _ = api_download(f'/api/matches/{int(match_id)}/download/', token=token)
        text = body.decode('utf-8', errors='replace')
        loaded = json.loads(text) if text.strip() else {}
        return (loaded if isinstance(loaded, dict) else {}), ''
    except Exception as exc:
        return {}, f'{type(exc).__name__}: {exc}'


def score_from_detail(detail: dict[str, Any], code_id: str) -> int | float | None:
    wanted = normalized_code_id(code_id)
    info = detail.get('info', [])
    if not isinstance(info, list):
        return None
    for row in info:
        if not isinstance(row, dict):
            continue
        code = row.get('code', {}) if isinstance(row.get('code'), dict) else {}
        if normalized_code_id(code.get('id')) == wanted:
            score = row.get('score')
            return score if isinstance(score, (int, float)) else None
    return None


def resolve_latest_entity_code(entity_name: str, token: str) -> str:
    username = str(get_profile(token).get('user', {}).get('username', '')).strip()
    if not username:
        raise RuntimeError('cannot resolve username')
    data = get_user_entities(username, GAME_ID, token)
    entities = data.get('entities', []) if isinstance(data, dict) else []
    entity_id = 0
    for entity in entities:
        if isinstance(entity, dict) and str(entity.get('name', '')).strip() == entity_name:
            entity_id = int(entity.get('id', 0) or 0)
            break
    if not entity_id:
        raise RuntimeError(f'entity not found: {entity_name}')
    codes = [c for c in get_entity_codes(entity_id, token) if isinstance(c, dict)]
    compiled = [c for c in codes if str(c.get('compile_status', '')).strip() == '编译成功']
    pool = compiled or codes
    if not pool:
        raise RuntimeError(f'no code found for entity: {entity_name}')
    latest = max(pool, key=lambda c: int(c.get('version', 0) or 0))
    return normalized_code_id(latest.get('id'))


def render_md(summary: dict[str, Any]) -> str:
    lines = ['# Game2 Latest Room Eval', '']
    meta = summary.get('meta', {})
    lines.append(f"- entity_name: `{meta.get('entity_name')}`")
    lines.append(f"- code_id: `{meta.get('code_id')}`")
    lines.append(f"- count: `{meta.get('count')}`")
    lines.append(f"- completed: `{meta.get('completed')}`")
    lines.append('')
    lines.append('Results:')
    for row in summary.get('rows', []):
        lines.append(
            f"- match `{row.get('match_id')}` room=`{row.get('room_id')}` state=`{row.get('state')}` score=`{row.get('score')}`"
        )
    return '\n'.join(lines) + '\n'


def main() -> int:
    parser = argparse.ArgumentParser(description='Run Game53 direct single-player room evals')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--code-id', default='')
    group.add_argument('--entity-name', default='')
    parser.add_argument('--label', default='')
    parser.add_argument('--count', type=int, default=1)
    parser.add_argument('--timeout', type=float, default=420.0)
    parser.add_argument('--poll-interval', type=float, default=2.0)
    parser.add_argument('--request-timeout', type=float, default=60.0)
    args = parser.parse_args()

    token, _ = resolve_token('')
    token = require_token(token, 'game2-room-eval')
    code_id = normalized_code_id(args.code_id) if args.code_id else resolve_latest_entity_code(args.entity_name, token)
    label = args.label or args.entity_name or code_id[:8]

    ts = time.strftime('%Y%m%d_%H%M%S', time.gmtime())
    out_dir = RUNTIME_DIR / f'{ts}_{label}_room'
    out_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, Any]] = []
    reports: list[dict[str, Any]] = []
    for index in range(max(1, int(args.count))):
        log(f'{label} sample {index + 1}/{max(1, int(args.count))}: create room')
        started: dict[str, Any] = {}
        match_id = 0
        detail: dict[str, Any] = {}
        trace: dict[str, Any] = {}
        download_error = ''
        try:
            started = create_single_player_match(GAME_ID, code_id, token, timeout=float(args.request_timeout))
            match_id = int(started['match_id'])
            log(f'{label} sample {index + 1}: match {match_id} started')
            detail = wait_match(match_id, token, timeout_sec=float(args.timeout), poll_interval=float(args.poll_interval))
            if is_finished(detail.get('state')):
                trace, download_error = download_trace(match_id, token)
            analysis = analyze_match_payload(detail, trace, download_error)
            row = {
                'index': index,
                'room_id': started.get('room_id'),
                'match_id': match_id,
                'state': detail.get('state'),
                'score': score_from_detail(detail, code_id),
                'end_state': (detail.get('info') or [{}])[0].get('end_state') if isinstance(detail.get('info'), list) and detail.get('info') else None,
            }
        except Exception as exc:
            analysis = {'error': f'{type(exc).__name__}: {exc}'}
            row = {
                'index': index,
                'room_id': started.get('room_id'),
                'match_id': match_id or None,
                'state': detail.get('state'),
                'score': None,
                'end_state': None,
                'error': f'{type(exc).__name__}: {exc}',
            }
            log(f'{label} sample {index + 1}: error {type(exc).__name__}: {exc}')
        match_dir = out_dir / 'matches' / str(match_id or f'failed_{index}')
        write_json(match_dir / 'match_detail.json', detail)
        write_json(match_dir / 'match_download.json', trace)
        write_json(match_dir / 'analysis.json', analysis)
        (match_dir / 'analysis.md').write_text(render_match_markdown(analysis), encoding='utf-8')
        if row.get('score') is not None:
            log(f'{label} sample {index + 1}: state={row.get("state")} score={row.get("score")}')
        rows.append(row)
        reports.append({'match_id': match_id, 'dir': str(match_dir), 'analysis': analysis})

    summary = {
        'meta': {
            'entity_name': args.entity_name or '',
            'code_id': code_id,
            'label': label,
            'count': len(rows),
            'completed': sum(1 for row in rows if is_finished(row.get('state'))),
            'out_dir': str(out_dir),
        },
        'rows': rows,
        'match_reports': reports,
    }
    write_json(out_dir / 'summary.json', summary)
    write_json(LATEST_JSON, summary)
    LATEST_MD.parent.mkdir(parents=True, exist_ok=True)
    LATEST_MD.write_text(render_md(summary), encoding='utf-8')
    print(json.dumps({'out_dir': str(out_dir), **summary}, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
