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
from saiblo_tools import require_token, resolve_token, get_profile, get_user_entities, fetch_ladders, api_request
from saiblo_tools import api_download

GAME_ID = 53
RUNTIME_DIR = ROOT / 'Game2' / 'runtime' / 'batches'
LATEST_MD = ROOT / 'docs' / 'generated' / 'game2_latest_batch.md'
LATEST_JSON = ROOT / 'docs' / 'generated' / 'game2_latest_batch.json'


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding='utf-8')


def create_batch(game_id: int, code_id: str, opponent_code_ids: list[str], token: str) -> dict[str, Any]:
    return api_request('POST', '/api/batches/', token=token, payload={'game': game_id, 'code': code_id, 'codes': opponent_code_ids})


def fetch_batch(batch_id: int, token: str) -> dict[str, Any]:
    data = api_request('GET', f'/api/batches/{batch_id}/', token=token)
    return data if isinstance(data, dict) else {}


def poll_batch(batch_id: int, token: str, timeout_sec: float, poll_interval: float) -> dict[str, Any]:
    deadline = time.time() + timeout_sec
    while True:
        data = fetch_batch(batch_id, token)
        pending = 0
        for pair in data.get('matches', []):
            for match in pair:
                if str(match.get('state', '')) in ('准备中', '评测中'):
                    pending += 1
        if pending == 0 or time.time() >= deadline:
            return data
        time.sleep(max(0.2, poll_interval))


def summarize(batch: dict[str, Any], my_code_id: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for pair in batch.get('matches', []):
        if not isinstance(pair, list) or not pair:
            continue
        bucket: dict[str, Any] = {
            'opponent_code_id': None,
            'opponent_user': None,
            'opponent_entity': None,
            'games': [],
            'my_match_id': None,
            'my_run_state': None,
            'my_score': None,
            'my_exit_code': None,
            'my_end_state': None,
            'opp_match_id': None,
            'opp_run_state': None,
            'opp_score': None,
            'opp_exit_code': None,
            'opp_end_state': None,
        }
        for match in pair:
            info = match.get('info', [])
            if not isinstance(info, list) or not info or not isinstance(info[0], dict):
                continue
            first = info[0]
            second = info[1] if len(info) > 1 and isinstance(info[1], dict) else None
            first_code = first.get('code', {}) if isinstance(first.get('code'), dict) else {}
            first_cid = str(first_code.get('id', '')).replace('-', '')
            non_my = second if first_cid == my_code_id.replace('-', '') else first
            if isinstance(non_my, dict) and bucket['opponent_code_id'] is None:
                code = non_my.get('code', {}) if isinstance(non_my.get('code'), dict) else {}
                user = non_my.get('user', {}) if isinstance(non_my.get('user'), dict) else {}
                entity = code.get('entity', {})
                bucket['opponent_code_id'] = code.get('id')
                bucket['opponent_user'] = user.get('username')
                bucket['opponent_entity'] = entity.get('name') if isinstance(entity, dict) else entity
            bucket['games'].append({
                'match_id': match.get('id'),
                'state': match.get('state'),
                'first_code_id': first_code.get('id'),
                'first_entity': first_code.get('entity'),
                'first_score': first.get('score'),
                'first_exit_code': first.get('exit_code'),
                'first_end_state': first.get('end_state'),
            })
            if first_cid == my_code_id.replace('-', ''):
                bucket['my_match_id'] = match.get('id')
                bucket['my_run_state'] = match.get('state')
                bucket['my_exit_code'] = first.get('exit_code')
                bucket['my_end_state'] = first.get('end_state')
                if str(match.get('state', '')) == '评测成功' and isinstance(first.get('score'), (int, float)):
                    bucket['my_score'] = first.get('score')
            else:
                bucket['opp_match_id'] = match.get('id')
                bucket['opp_run_state'] = match.get('state')
                bucket['opp_exit_code'] = first.get('exit_code')
                bucket['opp_end_state'] = first.get('end_state')
                if str(match.get('state', '')) == '评测成功' and isinstance(first.get('score'), (int, float)):
                    bucket['opp_score'] = first.get('score')
        bucket['completed_matches'] = sum(1 for g in bucket['games'] if str(g.get('state', '')) == '评测成功')
        bucket['pending_matches'] = sum(1 for g in bucket['games'] if str(g.get('state', '')) in ('准备中', '评测中'))
        if isinstance(bucket.get('my_score'), (int, float)) and isinstance(bucket.get('opp_score'), (int, float)):
            bucket['wins'] = 1 if bucket['my_score'] > bucket['opp_score'] else 0
            bucket['losses'] = 1 if bucket['my_score'] < bucket['opp_score'] else 0
            bucket['ties'] = 1 if bucket['my_score'] == bucket['opp_score'] else 0
        else:
            bucket['wins'] = None
            bucket['losses'] = None
            bucket['ties'] = None
        rows.append(bucket)
    return rows


def render_md(summary: dict[str, Any]) -> str:
    lines = ['# Game2 Latest Batch', '']
    meta = summary.get('meta', {})
    lines.append(f"- batch_id: `{meta.get('batch_id')}`")
    lines.append(f"- my_code_id: `{meta.get('my_code_id')}`")
    lines.append(f"- opponents: `{meta.get('opponent_count')}`")
    lines.append(f"- completed_matches: `{meta.get('completed_matches')}`")
    lines.append(f"- pending_matches: `{meta.get('pending_matches')}`")
    lines.append('')
    lines.append('Results:')
    for row in summary.get('rows', []):
        lines.append(
            f"- `{row.get('opponent_user')}/{row.get('opponent_entity')}` completed=`{row.get('completed_matches')}` pending=`{row.get('pending_matches')}` my_score=`{row.get('my_score')}` opp_score=`{row.get('opp_score')}` wins=`{row.get('wins')}` losses=`{row.get('losses')}`"
        )
    return '\n'.join(lines) + '\n'


def flatten_finished_match_ids(batch: dict[str, Any]) -> list[int]:
    out: list[int] = []
    for pair in batch.get('matches', []):
        if not isinstance(pair, list):
            continue
        for match in pair:
            if not isinstance(match, dict):
                continue
            if str(match.get('state', '')) in ('准备中', '评测中'):
                continue
            mid = int(match.get('id', 0) or 0)
            if mid:
                out.append(mid)
    return out


def analyze_finished_matches(batch: dict[str, Any], token: str, out_dir: Path) -> list[dict[str, Any]]:
    reports: list[dict[str, Any]] = []
    matches_dir = out_dir / 'matches'
    matches_dir.mkdir(parents=True, exist_ok=True)
    for match_id in flatten_finished_match_ids(batch):
        detail = api_request('GET', f'/api/matches/{match_id}/', token=token)
        trace: dict[str, Any] = {}
        download_error = ''
        try:
            body, _ = api_download(f'/api/matches/{match_id}/download/', token=token)
            text = body.decode('utf-8', errors='replace')
            loaded = json.loads(text) if text.strip() else {}
            trace = loaded if isinstance(loaded, dict) else {}
        except Exception as exc:
            download_error = f'{type(exc).__name__}: {exc}'
        analysis = analyze_match_payload(detail if isinstance(detail, dict) else {}, trace, download_error)
        match_dir = matches_dir / str(match_id)
        match_dir.mkdir(parents=True, exist_ok=True)
        write_json(match_dir / 'match_detail.json', detail)
        write_json(match_dir / 'match_download.json', trace)
        write_json(match_dir / 'analysis.json', analysis)
        (match_dir / 'analysis.md').write_text(render_match_markdown(analysis), encoding='utf-8')
        reports.append({
            'match_id': match_id,
            'dir': str(match_dir),
            'analysis': analysis,
        })
    return reports


def main() -> int:
    parser = argparse.ArgumentParser(description='Run one Game2 batch against top ladder codes')
    parser.add_argument('--entity-name', required=True)
    parser.add_argument('--batch-id', type=int, default=0)
    parser.add_argument('--top-k', type=int, default=2)
    parser.add_argument('--ladder-limit', type=int, default=10)
    parser.add_argument('--timeout', type=float, default=300.0)
    parser.add_argument('--poll-interval', type=float, default=3.0)
    args = parser.parse_args()

    token, _ = resolve_token('')
    token = require_token(token, 'game2-batch-eval')

    opponent_codes: list[str] = []
    if args.batch_id:
        batch_id = int(args.batch_id)
        final = poll_batch(batch_id, token, args.timeout, args.poll_interval)
        batch_code = final.get('code', {}) if isinstance(final.get('code'), dict) else {}
        my_code_id = str(batch_code.get('id', '')).strip()
        if not my_code_id:
            raise RuntimeError(f'cannot resolve code id from batch {batch_id}')
    else:
        username = str(get_profile(token).get('user', {}).get('username', '')).strip()
        entities = get_user_entities(username, GAME_ID, token)
        active = entities.get('active', {}) if isinstance(entities, dict) else {}
        active_code = active.get('code', {}) if isinstance(active, dict) else {}
        target_entity_id = None
        for entity in (entities.get('entities', []) if isinstance(entities, dict) else []):
            if isinstance(entity, dict) and str(entity.get('name', '')).strip() == args.entity_name:
                target_entity_id = int(entity.get('id', 0) or 0)
                break
        if not target_entity_id:
            raise RuntimeError(f'entity {args.entity_name!r} not found')
        if int(active_code.get('entity', 0) or 0) != target_entity_id:
            raise RuntimeError(f'entity {args.entity_name!r} is not currently active')
        my_code_id = str(active_code.get('id', '')).strip()
        if not my_code_id:
            raise RuntimeError(f'active code for entity {args.entity_name!r} not found')
        ladder = fetch_ladders(GAME_ID, args.ladder_limit, 0, token)
        results = ladder.get('results', []) if isinstance(ladder, dict) else []
        for row in results:
            if not isinstance(row, dict):
                continue
            code = row.get('code', {}) if isinstance(row.get('code'), dict) else {}
            entity = code.get('entity', {}) if isinstance(code.get('entity'), dict) else {}
            code_id = str(code.get('id', '')).strip().replace('-', '')
            if not code_id or code_id == my_code_id.replace('-', ''):
                continue
            if int(entity.get('id', -1) or -1) == target_entity_id:
                continue
            opponent_codes.append(code_id)
            if len(opponent_codes) >= args.top_k:
                break
        if not opponent_codes:
            raise RuntimeError('no opponent codes found from ladder')
        created = create_batch(GAME_ID, my_code_id, opponent_codes, token)
        batch_id = int(created.get('id', 0) or 0)
        final = poll_batch(batch_id, token, args.timeout, args.poll_interval)

    rows = summarize(final, my_code_id)
    completed_matches = sum(1 for pair in final.get('matches', []) for match in pair if str(match.get('state', '')) == '评测成功')
    pending_matches = sum(1 for pair in final.get('matches', []) for match in pair if str(match.get('state', '')) in ('准备中', '评测中'))
    summary = {
        'meta': {
            'batch_id': batch_id,
            'my_code_id': my_code_id,
            'opponent_count': len(final.get('matches', [])) if final.get('matches') else len(opponent_codes),
            'opponent_code_ids': opponent_codes,
            'completed_matches': completed_matches,
            'pending_matches': pending_matches,
        },
        'rows': rows,
        'batch': final,
    }
    ts = time.strftime('%Y%m%d_%H%M%S', time.gmtime())
    out_dir = RUNTIME_DIR / f'{ts}_{args.entity_name}_batch_{batch_id}'
    out_dir.mkdir(parents=True, exist_ok=True)
    summary['match_reports'] = analyze_finished_matches(final, token, out_dir)
    write_json(out_dir / 'summary.json', summary)
    write_json(LATEST_JSON, summary)
    LATEST_MD.parent.mkdir(parents=True, exist_ok=True)
    LATEST_MD.write_text(render_md(summary), encoding='utf-8')
    print(json.dumps({'out_dir': str(out_dir), **summary}, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
