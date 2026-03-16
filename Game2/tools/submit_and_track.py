#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from saiblo_tools import (
    fetch_ladders,
    get_profile,
    get_user_entities,
    require_token,
    resolve_token,
    upload_entity_code,
    create_entity,
    activate_code,
    get_entity_codes,
)

RUNTIME_DIR = ROOT / 'Game2' / 'runtime' / 'submissions'
LATEST_MD = ROOT / 'docs' / 'generated' / 'game2_latest_submission.md'
LATEST_JSON = ROOT / 'docs' / 'generated' / 'game2_latest_submission.json'
GAME_ID = 53


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding='utf-8')


def compact_row(rows: list[dict[str, Any]], entity_id: int, code_id: str, username: str) -> dict[str, Any] | None:
    for row in rows:
        if int(row.get('entity_id', -1) or -1) == entity_id and str(row.get('code_id', '')).strip() == code_id:
            return row
    for row in rows:
        if int(row.get('entity_id', -1) or -1) == entity_id:
            return row
    for row in rows:
        if str(row.get('user', '')).strip() == username:
            return row
    return None


def wait_compile(entity_id: int, code_id: str, token: str, poll_interval: float, poll_max: int) -> dict[str, Any]:
    current: dict[str, Any] = {}
    for _ in range(max(1, poll_max)):
        codes = get_entity_codes(entity_id, token)
        for code in codes:
            if str(code.get('id', '')).strip() == code_id:
                current = code
                break
        status = str(current.get('compile_status', '')).strip()
        if status and status not in ('未编译', '编译中', '等待中', 'Pending', 'Compiling', ''):
            return current
        time.sleep(max(0.2, poll_interval))
    return current


def poll_ladder(entity_id: int, code_id: str, username: str, token: str, timeout_sec: float, poll_interval: float) -> dict[str, Any]:
    deadline = time.time() + timeout_sec
    snapshots: list[dict[str, Any]] = []
    stable_hits = 0
    last_marker = None
    while True:
        data = fetch_ladders(GAME_ID, 50, 0, token)
        rows = data.get('results', []) if isinstance(data, dict) else []
        compact = []
        for i, r in enumerate(rows):
            if not isinstance(r, dict):
                continue
            code = r.get('code', {}) if isinstance(r.get('code'), dict) else {}
            entity = code.get('entity', {}) if isinstance(code.get('entity'), dict) else {}
            compact.append({
                'idx': i,
                'user': r.get('user'),
                'score': r.get('score'),
                'code_id': code.get('id'),
                'entity_id': entity.get('id'),
                'entity_name': entity.get('name'),
                'version': code.get('version'),
            })
        row = compact_row(compact, entity_id, code_id, username)
        marker = None if row is None else (row.get('code_id'), row.get('score'), row.get('idx'))
        snapshots.append({'time': time.time(), 'row': row, 'rows': compact})
        if row is not None and row.get('code_id') == code_id:
            if marker == last_marker:
                stable_hits += 1
            else:
                stable_hits = 1
            if stable_hits >= 2:
                return {'row': row, 'snapshots': snapshots}
        last_marker = marker
        if time.time() >= deadline:
            return {'row': row, 'snapshots': snapshots}
        time.sleep(max(0.2, poll_interval))


def render_md(summary: dict[str, Any]) -> str:
    upload = summary.get('upload', {})
    ladder = summary.get('ladder', {})
    row = ladder.get('row') or {}
    return '\n'.join([
        '# Game2 Latest Submission',
        '',
        f"- entity: `{upload.get('entity_name')}`",
        f"- entity_id: `{upload.get('entity_id')}`",
        f"- code_id: `{upload.get('uploaded_code_id')}`",
        f"- compile_status: `{upload.get('compile_status')}`",
        f"- ladder_user: `{row.get('user')}`",
        f"- ladder_rank: `{row.get('idx')}`",
        f"- ladder_score: `{row.get('score')}`",
        f"- ladder_entity: `{row.get('entity_name')}`",
        f"- ladder_version: `{row.get('version')}`",
    ]) + '\n'


def main() -> int:
    parser = argparse.ArgumentParser(description='Upload one Game2 AI and archive ladder feedback')
    parser.add_argument('--source', required=True)
    parser.add_argument('--entity-name', required=True)
    parser.add_argument('--remark', default='game2 tracked submit')
    parser.add_argument('--language', default='python')
    parser.add_argument('--poll-interval', type=float, default=2.0)
    parser.add_argument('--poll-max', type=int, default=30)
    parser.add_argument('--score-timeout', type=float, default=90.0)
    args = parser.parse_args()

    token, _ = resolve_token('')
    token = require_token(token, 'game2-submit-track')
    profile = get_profile(token)
    username = str(profile.get('user', {}).get('username', '')).strip()
    if not username:
        raise RuntimeError('cannot resolve username')

    source = Path(args.source).resolve()
    if not source.is_file():
        raise RuntimeError(f'source not found: {source}')

    entities_data = get_user_entities(username, GAME_ID, token)
    entities = entities_data.get('entities', []) if isinstance(entities_data, dict) else []
    entity = None
    for item in entities:
        if isinstance(item, dict) and str(item.get('name', '')).strip() == args.entity_name:
            entity = item
            break
    created = False
    if entity is None:
        entity = create_entity(username, GAME_ID, args.entity_name, args.language, token)
        created = True
    entity_id = int(entity.get('id', 0))
    uploaded = upload_entity_code(entity_id, source, args.remark, token)
    code_id = str(uploaded.get('id', '')).strip()
    compiled = wait_compile(entity_id, code_id, token, args.poll_interval, args.poll_max)
    compile_status = str(compiled.get('compile_status', uploaded.get('compile_status', ''))).strip()
    activate_resp = None
    if compile_status == '编译成功':
        activate_resp = activate_code(entity_id, code_id, token)
    ladder = poll_ladder(entity_id, code_id, username, token, args.score_timeout, args.poll_interval)

    ts = time.strftime('%Y%m%d_%H%M%S', time.gmtime())
    out_dir = RUNTIME_DIR / f'{ts}_{args.entity_name}_v{uploaded.get("version", 0)}'
    out_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, out_dir / source.name)

    upload_summary = {
        'username': username,
        'game_id': GAME_ID,
        'entity_created': created,
        'entity_id': entity_id,
        'entity_name': args.entity_name,
        'uploaded_code_id': code_id,
        'uploaded_version': uploaded.get('version'),
        'compile_status': compile_status,
        'activate_response': activate_resp,
        'uploaded': compiled or uploaded,
    }
    summary = {
        'upload': upload_summary,
        'ladder': ladder,
    }
    write_json(out_dir / 'upload.json', upload_summary)
    write_json(out_dir / 'ladder.json', ladder)
    write_json(out_dir / 'summary.json', summary)
    write_json(LATEST_JSON, summary)
    LATEST_MD.parent.mkdir(parents=True, exist_ok=True)
    LATEST_MD.write_text(render_md(summary), encoding='utf-8')
    print(json.dumps({'out_dir': str(out_dir), **summary}, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
