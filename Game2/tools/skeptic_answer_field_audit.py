#!/usr/bin/env python3
from __future__ import annotations

import argparse
import collections
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ROOM_DIR = ROOT / 'Game2' / 'runtime' / 'room_matches'
OUT_JSON = ROOT / 'docs' / 'generated' / 'game2_skeptic_answer_field_audit.json'
OUT_MD = ROOT / 'docs' / 'generated' / 'game2_skeptic_answer_field_audit.md'


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def label_from_path(path: Path) -> str:
    room_dir = path.parents[2].name
    m = re.match(r'^\d{8}_\d{6}_(.+)_room$', room_dir)
    return m.group(1) if m else room_dir


def base_label(label: str) -> str:
    m = re.match(r'(n\d+[a-z]|sk\d+[a-z]\d+[a-z0-9]+)', label)
    return m.group(1) if m else label


def normalize_person_name(text: str) -> str:
    value = str(text or '').strip()
    if not value:
        return ''
    value = re.sub(r'^(银行家|凶手|作案手法|作案工具|动机)[:：]?\s*', '', value)
    value = re.split(r'[,，。；;！!\s]', value, maxsplit=1)[0].strip()
    return value


def extract_answer_entities(final_answer: str) -> tuple[str, str]:
    text = str(final_answer or '')
    killer = ''
    banker = ''
    m = re.search(r'凶手[:：]\s*([^,，]+)', text)
    if m:
        killer = normalize_person_name(m.group(1))

    # Preferred parse path: banker appears in “爱慕并想独占X” style text.
    m = re.search(r'独占([^,，。；;！!\s]+)', text)
    if m:
        banker = normalize_person_name(m.group(1))
    if not banker:
        m = re.search(r'银行家[:：]?\s*([^,，。；;！!\s]+)', text)
        if m:
            banker = normalize_person_name(m.group(1))
    return killer, banker


def bool_or_none(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    return None


def row_for_analysis(path: Path) -> dict[str, Any] | None:
    data = load_json(path)
    players = data.get('players')
    if not isinstance(players, list) or not players or not isinstance(players[0], dict):
        return None
    score = players[0].get('score')
    if not isinstance(score, int) or score <= 0:
        return None
    cases = data.get('cases')
    if not isinstance(cases, list) or not cases or not isinstance(cases[0], dict):
        return None
    case0 = cases[0]
    result = case0.get('final_result') if isinstance(case0.get('final_result'), dict) else {}
    murderer_ok = bool_or_none(result.get('murderer'))
    motivation_ok = bool_or_none(result.get('motivation'))
    method_ok = bool_or_none(result.get('method'))
    final_answer = str(case0.get('final_answer', ''))
    killer, banker = extract_answer_entities(final_answer)
    label = label_from_path(path)
    match_id = path.parent.name
    return {
        'label': label,
        'base_label': base_label(label),
        'match_id': match_id,
        'analysis_path': str(path.relative_to(ROOT)),
        'score': score,
        'murderer_ok': murderer_ok,
        'motivation_ok': motivation_ok,
        'method_ok': method_ok,
        'pattern': f'{"T" if murderer_ok else "F" if murderer_ok is False else "N"}'
        f'{"T" if motivation_ok else "F" if motivation_ok is False else "N"}'
        f'{"T" if method_ok else "F" if method_ok is False else "N"}',
        'killer_cn': killer,
        'banker_cn': banker,
    }


def mismatch(row: dict[str, Any]) -> bool:
    return any(row.get(key) is False for key in ('murderer_ok', 'motivation_ok', 'method_ok'))


def summarize(rows: list[dict[str, Any]], label_prefix: str) -> dict[str, Any]:
    filtered = [r for r in rows if not label_prefix or r['label'].startswith(label_prefix)]
    by_pattern = collections.Counter(r['pattern'] for r in filtered)
    mismatch_rows = [r for r in filtered if mismatch(r)]
    mismatch_by_score = collections.Counter(r['score'] for r in mismatch_rows)
    mismatch_by_label = collections.Counter(r['label'] for r in mismatch_rows)
    motivation_false_rows = [r for r in filtered if r.get('motivation_ok') is False]
    motivation_pair = collections.Counter((r.get('killer_cn', ''), r.get('banker_cn', '')) for r in motivation_false_rows)

    worst_rows = sorted(mismatch_rows, key=lambda r: (r['score'], r['label'], r['match_id']))[:40]
    top_labels = mismatch_by_label.most_common(30)
    top_pairs = motivation_pair.most_common(30)

    return {
        'label_prefix': label_prefix,
        'rows': len(filtered),
        'mismatch_rows': len(mismatch_rows),
        'pattern_distribution': dict(sorted(by_pattern.items())),
        'mismatch_score_distribution': dict(sorted(mismatch_by_score.items())),
        'top_mismatch_labels': [{'label': k, 'count': v} for k, v in top_labels],
        'top_motivation_false_pairs': [
            {'killer_cn': killer, 'banker_cn': banker, 'count': count}
            for (killer, banker), count in top_pairs
        ],
        'worst_rows': worst_rows,
    }


def render_md(data: dict[str, Any]) -> str:
    lines = ['# Game2 Skeptic Answer Field Audit', '']
    lines.append(f"- label_prefix: `{data.get('label_prefix')}`")
    lines.append(f"- rows: `{data.get('rows')}`")
    lines.append(f"- mismatch_rows: `{data.get('mismatch_rows')}`")
    lines.append('')

    lines.append('## Pattern Distribution')
    lines.append('')
    lines.append('| pattern (M/V/T) | count |')
    lines.append('| --- | ---: |')
    for k, v in sorted((data.get('pattern_distribution') or {}).items()):
        lines.append(f'| `{k}` | {v} |')
    lines.append('')

    lines.append('## Mismatch Score Distribution')
    lines.append('')
    lines.append('| score | count |')
    lines.append('| ---: | ---: |')
    for k, v in sorted((data.get('mismatch_score_distribution') or {}).items(), key=lambda x: int(x[0])):
        lines.append(f'| {k} | {v} |')
    lines.append('')

    lines.append('## Top Motivation-False Pairs')
    lines.append('')
    lines.append('| killer | banker | count |')
    lines.append('| --- | --- | ---: |')
    for row in data.get('top_motivation_false_pairs', []):
        lines.append(f"| `{row.get('killer_cn')}` | `{row.get('banker_cn')}` | {row.get('count')} |")
    lines.append('')

    lines.append('## Worst Rows')
    lines.append('')
    lines.append('| score | label | match | pattern | killer | banker |')
    lines.append('| ---: | --- | --- | --- | --- | --- |')
    for row in data.get('worst_rows', []):
        lines.append(
            f"| {row.get('score')} | `{row.get('label')}` | `{row.get('match_id')}` | "
            f"`{row.get('pattern')}` | `{row.get('killer_cn')}` | `{row.get('banker_cn')}` |"
        )
    lines.append('')
    return '\n'.join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description='Audit final answer field correctness (murderer/motivation/method) from room analyses')
    parser.add_argument('--label-prefix', default='', help='optional exact label prefix filter')
    parser.add_argument('--out-json', default=str(OUT_JSON))
    parser.add_argument('--out-md', default=str(OUT_MD))
    args = parser.parse_args()

    rows: list[dict[str, Any]] = []
    for path in sorted(ROOM_DIR.glob('*_room/matches/*/analysis.json')):
        row = row_for_analysis(path)
        if row is not None:
            rows.append(row)

    summary = summarize(rows, args.label_prefix.strip())
    out_json = Path(args.out_json).resolve()
    out_md = Path(args.out_md).resolve()
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    out_md.write_text(render_md(summary), encoding='utf-8')
    print(json.dumps({'rows': summary['rows'], 'mismatch_rows': summary['mismatch_rows'], 'out_json': str(out_json), 'out_md': str(out_md)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
