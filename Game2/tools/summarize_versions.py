#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
SUBMISSIONS_DIR = ROOT / 'Game2' / 'runtime' / 'submissions'
BATCHES_DIR = ROOT / 'Game2' / 'runtime' / 'batches'
OUT_JSON = ROOT / 'docs' / 'generated' / 'game2_version_summary.json'
OUT_MD = ROOT / 'docs' / 'generated' / 'game2_version_summary.md'


def read_json(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def load_submissions() -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for path in sorted(SUBMISSIONS_DIR.glob('*/summary.json')):
        data = read_json(path)
        if not data:
            continue
        upload = data.get('upload', {}) if isinstance(data.get('upload'), dict) else {}
        ladder = data.get('ladder', {}) if isinstance(data.get('ladder'), dict) else {}
        row = ladder.get('row', {}) if isinstance(ladder.get('row'), dict) else {}
        code_id = str(upload.get('uploaded_code_id', '')).strip()
        if not code_id:
            continue
        rows[code_id] = {
            'code_id': code_id,
            'entity_name': upload.get('entity_name'),
            'entity_id': upload.get('entity_id'),
            'version': upload.get('uploaded_version'),
            'remark': (upload.get('uploaded') or {}).get('remark') if isinstance(upload.get('uploaded'), dict) else None,
            'compile_status': upload.get('compile_status'),
            'submission_dir': str(path.parent),
            'ladder_score': row.get('score'),
            'ladder_rank': row.get('idx'),
        }
    return rows


def load_batches() -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, dict[tuple[Any, ...], dict[str, Any]]] = defaultdict(dict)
    for path in sorted(BATCHES_DIR.glob('*/summary.json')):
        data = read_json(path)
        if not data:
            continue
        meta = data.get('meta', {}) if isinstance(data.get('meta'), dict) else {}
        code_id = str(meta.get('my_code_id', '')).replace('-', '').strip()
        if not code_id:
            continue
        for row in data.get('rows', []) if isinstance(data.get('rows'), list) else []:
            if not isinstance(row, dict):
                continue
            item = {
                'batch_id': meta.get('batch_id'),
                'batch_dir': str(path.parent),
                'opponent_entity': row.get('opponent_entity'),
                'opponent_user': row.get('opponent_user'),
                'my_score': row.get('my_score'),
                'opp_score': row.get('opp_score'),
                'my_match_id': row.get('my_match_id'),
                'opp_match_id': row.get('opp_match_id'),
                'my_run_state': row.get('my_run_state'),
                'opp_run_state': row.get('opp_run_state'),
                'completed_matches': row.get('completed_matches'),
                'pending_matches': row.get('pending_matches'),
            }
            dedupe_key = (
                item.get('batch_id'),
                item.get('my_match_id'),
                item.get('opp_match_id'),
                item.get('opponent_user'),
                item.get('opponent_entity'),
            )
            prev = grouped[code_id].get(dedupe_key)
            if prev is None or _row_priority(item) >= _row_priority(prev):
                grouped[code_id][dedupe_key] = item
    return {k: list(v.values()) for k, v in grouped.items()}


def _row_priority(item: dict[str, Any]) -> tuple[int, int, str]:
    pending = int(item.get('pending_matches', 0) or 0)
    completed = int(item.get('completed_matches', 0) or 0)
    terminal = 1 if pending == 0 else 0
    informative = 1 if isinstance(item.get('my_score'), (int, float)) or isinstance(item.get('opp_score'), (int, float)) else 0
    return (terminal + informative, completed, str(item.get('batch_dir', '')))


def build_summary() -> dict[str, Any]:
    submissions = load_submissions()
    batches = load_batches()
    rows: list[dict[str, Any]] = []
    for code_id, sub in submissions.items():
        key = code_id.replace('-', '')
        batch_rows = batches.get(key, [])
        best_score = None
        best_batch = None
        for item in batch_rows:
            score = item.get('my_score')
            if not isinstance(score, (int, float)):
                continue
            if best_score is None or score > best_score:
                best_score = score
                best_batch = item
        rows.append({
            **sub,
            'batch_count': len(batch_rows),
            'best_my_score': best_score,
            'best_batch': best_batch,
            'batch_rows': batch_rows,
        })
    rows.sort(key=lambda x: (
        -1 if isinstance(x.get('best_my_score'), (int, float)) else 0,
        -(x.get('best_my_score') if isinstance(x.get('best_my_score'), (int, float)) else -1),
        -(int(x.get('version', 0) or 0)),
    ))
    return {'rows': rows}


def render_md(summary: dict[str, Any]) -> str:
    lines = ['# Game2 Version Summary', '']
    for row in summary.get('rows', []):
        lines.append(
            f"- `v{row.get('version')}` code=`{row.get('code_id')}` entity=`{row.get('entity_name')}` ladder=`{row.get('ladder_score')}` best_my=`{row.get('best_my_score')}` batches=`{row.get('batch_count')}` remark=`{row.get('remark')}`"
        )
        best = row.get('best_batch')
        if isinstance(best, dict):
            lines.append(
                f"  best_batch=`{best.get('batch_id')}` vs `{best.get('opponent_user')}/{best.get('opponent_entity')}` my=`{best.get('my_score')}` opp=`{best.get('opp_score')}` my_match=`{best.get('my_match_id')}`"
            )
    return '\n'.join(lines) + '\n'


def main() -> int:
    summary = build_summary()
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    OUT_MD.write_text(render_md(summary), encoding='utf-8')
    print(json.dumps({'out_json': str(OUT_JSON), 'out_md': str(OUT_MD), **summary}, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
