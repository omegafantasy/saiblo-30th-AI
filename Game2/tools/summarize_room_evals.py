#!/usr/bin/env python3
from __future__ import annotations

import collections
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ROOM_DIR = ROOT / 'Game2' / 'runtime' / 'room_matches'
OUT_JSON = ROOT / 'docs' / 'generated' / 'game2_room_eval_summary.json'
OUT_MD = ROOT / 'docs' / 'generated' / 'game2_room_eval_summary.md'


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def score_from_analysis(path: Path) -> tuple[int | None, str | None]:
    data = load_json(path)
    players = data.get('players')
    if not isinstance(players, list) or not players:
        return None, None
    player = players[0] if isinstance(players[0], dict) else {}
    score = player.get('score')
    end_state = player.get('end_state')
    if isinstance(score, int):
        return score, str(end_state or '')
    return None, str(end_state or '') if end_state is not None else None


def label_from_dir(path: Path, summary: dict[str, Any]) -> str:
    meta = summary.get('meta') if isinstance(summary.get('meta'), dict) else {}
    label = str(meta.get('label') or '').strip()
    if label:
        return label
    name = path.name
    return name.rsplit('_room', 1)[0].split('_', 2)[-1]


def base_label(label: str) -> str:
    match = re.match(r'(n\d+[a-z])', label)
    return match.group(1) if match else label


def empty_item(label: str) -> dict[str, Any]:
    return {
        'label': label,
        'attempts': 0,
        'effective': 0,
        'failures': 0,
        'scores': [],
        'dirs': [],
    }


def finalize(items: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows_out: list[dict[str, Any]] = []
    for item in items.values():
        scores = item.pop('scores')
        counter = dict(sorted(collections.Counter(scores).items()))
        avg = sum(scores) / len(scores) if scores else None
        rows_out.append(
            {
                **item,
                'min': min(scores) if scores else None,
                'max': max(scores) if scores else None,
                'avg': round(avg, 3) if avg is not None else None,
                'distribution': counter,
            }
        )
    rows_out.sort(
        key=lambda row: (
            row['max'] if row['max'] is not None else -1,
            row['avg'] if row['avg'] is not None else -1,
            row['effective'],
        ),
        reverse=True,
    )
    return rows_out


def summarize() -> dict[str, Any]:
    labels: dict[str, dict[str, Any]] = {}
    bases: dict[str, dict[str, Any]] = {}
    for room in sorted(ROOM_DIR.glob('*_room')):
        summary = load_json(room / 'summary.json')
        label = label_from_dir(room, summary)
        base = base_label(label)
        items = [labels.setdefault(label, empty_item(label)), bases.setdefault(base, empty_item(base))]
        for item in items:
            item['dirs'].append(str(room.relative_to(ROOT)))
        rows = summary.get('rows') if isinstance(summary.get('rows'), list) else []
        for item in items:
            item['attempts'] += len(rows)
        if not rows:
            match_count = len(list((room / 'matches').glob('*')))
            for item in items:
                item['attempts'] += match_count
        for analysis in sorted(room.glob('matches/*/analysis.json')):
            score, end_state = score_from_analysis(analysis)
            if end_state == 'OK' and isinstance(score, int) and score > 0:
                for item in items:
                    item['scores'].append(score)
                    item['effective'] += 1
            elif score is None or score <= 0 or end_state not in (None, 'OK'):
                for item in items:
                    item['failures'] += 1

    return {'base_labels': finalize(bases), 'labels': finalize(labels)}


def render_md(data: dict[str, Any]) -> str:
    lines = ['# Game2 Room Eval Summary', '']
    lines.append('Only single-player room evals are summarized here. Effective samples require `end_state=OK` and `score>0`.')
    lines.append('')
    lines.append('## Base Labels')
    lines.append('')
    lines.append('| label | effective | avg | min | max | distribution |')
    lines.append('| --- | ---: | ---: | ---: | ---: | --- |')
    for row in data.get('base_labels', []):
        dist = ', '.join(f'{score} x{count}' for score, count in row.get('distribution', {}).items())
        lines.append(
            f"| `{row.get('label')}` | {row.get('effective')} | "
            f"{row.get('avg') if row.get('avg') is not None else ''} | "
            f"{row.get('min') if row.get('min') is not None else ''} | "
            f"{row.get('max') if row.get('max') is not None else ''} | {dist} |"
        )
    lines.append('')
    lines.append('## Exact Labels')
    lines.append('')
    lines.append('| label | effective | avg | min | max | distribution |')
    lines.append('| --- | ---: | ---: | ---: | ---: | --- |')
    for row in data.get('labels', []):
        dist = ', '.join(f'{score} x{count}' for score, count in row.get('distribution', {}).items())
        lines.append(
            f"| `{row.get('label')}` | {row.get('effective')} | "
            f"{row.get('avg') if row.get('avg') is not None else ''} | "
            f"{row.get('min') if row.get('min') is not None else ''} | "
            f"{row.get('max') if row.get('max') is not None else ''} | {dist} |"
        )
    return '\n'.join(lines) + '\n'


def main() -> int:
    data = summarize()
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    OUT_MD.write_text(render_md(data), encoding='utf-8')
    print(
        json.dumps(
            {'base_labels': len(data.get('base_labels', [])), 'labels': len(data.get('labels', [])), 'out_json': str(OUT_JSON), 'out_md': str(OUT_MD)},
            indent=2,
        )
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
