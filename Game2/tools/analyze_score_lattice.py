#!/usr/bin/env python3
from __future__ import annotations

import argparse
import collections
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
IN_JSON = ROOT / 'docs' / 'generated' / 'game2_room_score_factors.json'
OUT_JSON = ROOT / 'docs' / 'generated' / 'game2_score_lattice.json'
OUT_MD = ROOT / 'docs' / 'generated' / 'game2_score_lattice.md'


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def is_current_label(row: dict[str, Any]) -> bool:
    return re.fullmatch(r'n\d+[a-z]', str(row.get('base_label') or '')) is not None


def as_int(value: Any, default: int = 0) -> int:
    return value if isinstance(value, int) else default


def rose_bucket(row: dict[str, Any]) -> str:
    index = row.get('rose_stage6_index')
    if not isinstance(index, int):
        return 'unknown'
    return 'fast' if index <= 28 else 'late'


def poker_layer(row: dict[str, Any]) -> int:
    stage = row.get('poker_stage')
    if stage == 3:
        return 100
    if stage == 2:
        return 50
    return 0


def lattice_expected(row: dict[str, Any]) -> int | None:
    if row.get('rose_answer_key') != 'mTmTmT':
        return None
    if as_int(row.get('z_err8_count')) != 2:
        return None
    if row.get('poker_stage') not in (None, 1, 2, 3):
        return None
    bucket = rose_bucket(row)
    if bucket == 'unknown':
        return None
    return 2657 + poker_layer(row) - (40 if bucket == 'late' else 0)


def score_distribution(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {str(score): count for score, count in sorted(collections.Counter(row.get('score') for row in rows).items())}


def format_counter(counter: dict[Any, int] | collections.Counter[Any]) -> str:
    return ', '.join(f'{key} x{value}' for key, value in sorted(counter.items(), key=lambda item: str(item[0])))


def format_score_counter(counter: dict[str, int] | collections.Counter[Any]) -> str:
    return ', '.join(f'{score} x{count}' for score, count in sorted(counter.items(), key=lambda item: int(item[0])))


def evidence_key(value: Any) -> str:
    if isinstance(value, list):
        return '/'.join(str(item) for item in value)
    return ''


def signature(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        row.get('rose_answer_key'),
        rose_bucket(row),
        row.get('rose_stage6_index'),
        as_int(row.get('z_err8_count')),
        row.get('poker_stage'),
        evidence_key(row.get('poker_evidence_ids')),
        row.get('yuan_stage'),
        evidence_key(row.get('yuan_evidence_ids')),
    )


def analyze(rows: list[dict[str, Any]], min_label_count: int) -> dict[str, Any]:
    current_rows = [row for row in rows if is_current_label(row)]
    lattice_rows: list[dict[str, Any]] = []
    for row in current_rows:
        expected = lattice_expected(row)
        if expected is None:
            continue
        residual = int(row['score']) - expected
        lattice_rows.append(
            {
                'score': row.get('score'),
                'expected': expected,
                'residual': residual,
                'label': row.get('label'),
                'base_label': row.get('base_label'),
                'match_id': row.get('match_id'),
                'rose_bucket': rose_bucket(row),
                'rose_stage6_index': row.get('rose_stage6_index'),
                'poker_stage': row.get('poker_stage'),
                'poker_layer': poker_layer(row),
                'yuan_stage': row.get('yuan_stage'),
                'poker_evidence_ids': row.get('poker_evidence_ids'),
                'yuan_evidence_ids': row.get('yuan_evidence_ids'),
                'path': row.get('path'),
            }
        )

    by_label: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for item in lattice_rows:
        by_label[str(item.get('base_label'))].append(item)

    label_rows: list[dict[str, Any]] = []
    for label, group in by_label.items():
        if len(group) < min_label_count:
            continue
        scores = [int(item['score']) for item in group]
        residuals = [int(item['residual']) for item in group]
        low_count = sum(1 for value in residuals if value < 0)
        label_rows.append(
            {
                'label': label,
                'count': len(group),
                'avg': round(sum(scores) / len(scores), 3),
                'min': min(scores),
                'max': max(scores),
                'low_residual_rate': round(low_count / len(group), 4),
                'score_distribution': {str(score): count for score, count in sorted(collections.Counter(scores).items())},
                'residual_distribution': {str(value): count for value, count in sorted(collections.Counter(residuals).items())},
            }
        )
    label_rows.sort(key=lambda item: (item['low_residual_rate'], -item['avg'], item['label']))

    sig_groups: dict[tuple[Any, ...], list[dict[str, Any]]] = collections.defaultdict(list)
    original_by_match = {str(row.get('match_id')): row for row in current_rows}
    for item in lattice_rows:
        source = original_by_match.get(str(item.get('match_id')))
        if source:
            sig_groups[signature(source)].append(item)

    collisions: list[dict[str, Any]] = []
    for sig, group in sig_groups.items():
        if len(group) < 5:
            continue
        residuals = collections.Counter(int(item['residual']) for item in group)
        if len(residuals) < 2:
            continue
        scores = collections.Counter(str(item['score']) for item in group)
        collisions.append(
            {
                'count': len(group),
                'residual_distribution': {str(value): count for value, count in sorted(residuals.items())},
                'score_distribution': {str(score): count for score, count in sorted(scores.items(), key=lambda item: int(item[0]))},
                'signature': {
                    'rose': sig[0],
                    'rose_bucket': sig[1],
                    'rose_stage6_index': sig[2],
                    'z_err8': sig[3],
                    'poker_stage': sig[4],
                    'poker_evidence': sig[5],
                    'yuan_stage': sig[6],
                    'yuan_evidence': sig[7],
                },
            }
        )
    collisions.sort(key=lambda item: (-item['count'], item['signature']['poker_stage'] or 0))

    stage_rows: list[dict[str, Any]] = []
    stage_groups: dict[tuple[Any, str, int], list[dict[str, Any]]] = collections.defaultdict(list)
    for item in lattice_rows:
        stage_groups[(item.get('poker_stage'), str(item.get('rose_bucket')), int(item.get('residual')))].append(item)
    for (stage, bucket, residual), group in sorted(stage_groups.items(), key=lambda item: (str(item[0][0]), item[0][1], item[0][2])):
        stage_rows.append(
            {
                'poker_stage': stage,
                'rose_bucket': bucket,
                'residual': residual,
                'count': len(group),
                'score_distribution': score_distribution(group),
            }
        )

    return {
        'source': str(IN_JSON.relative_to(ROOT)),
        'filter': 'base_label matches n[0-9]+[a-z]; sk* and other-thread labels excluded',
        'row_count': len(rows),
        'current_row_count': len(current_rows),
        'lattice_row_count': len(lattice_rows),
        'score_distribution': score_distribution(current_rows),
        'lattice_residual_distribution': {str(value): count for value, count in sorted(collections.Counter(item['residual'] for item in lattice_rows).items())},
        'lattice_score_distribution': score_distribution(lattice_rows),
        'stage_rows': stage_rows,
        'label_rows': label_rows,
        'signature_collisions': collisions,
    }


def render_md(data: dict[str, Any], max_labels: int, max_collisions: int) -> str:
    lines: list[str] = []
    lines.append('# Game2 Score Lattice')
    lines.append('')
    lines.append(f"Source: `{data['source']}`")
    lines.append(f"Filter: {data['filter']}")
    lines.append(f"Rows: total `{data['row_count']}`, current-thread `n*` rows `{data['current_row_count']}`, strict lattice rows `{data['lattice_row_count']}`.")
    lines.append('')
    lines.append('## Working Model')
    lines.append('')
    lines.append('- `207` is the robust zero baseline.')
    lines.append('- `1607 = 207 + Rose direct 600 + Z/F direct 600 + Poker direct 200`; Yuan direct currently has no stable answer score.')
    lines.append('- In the current full lattice, `2657` is Rose+Z/F full plus Poker direct with fast Rose stage6.')
    lines.append('- Poker stage2 and stage3 add `+50` each: `2707` and `2757` on the fast Rose branch.')
    lines.append('- Late Rose stage6 subtracts `40`: `2657 -> 2617`, `2707 -> 2667`, `2757 -> 2717`.')
    lines.append('- The remaining important low tail is residual `-200`: `2657 -> 2457`, `2707 -> 2507`, `2757 -> 2557`, and with late Rose `2717 -> 2517`.')
    lines.append('- Yuan has an isolated low-frequency `+40` (`207 -> 247`, `1607 -> 1647`), but it has not been observed above `2757` in the full lattice.')
    lines.append('')
    lines.append('## Distributions')
    lines.append('')
    lines.append(f"Current `n*` score distribution: {format_score_counter(data['score_distribution'])}")
    lines.append('')
    lines.append(f"Strict lattice score distribution: {format_score_counter(data['lattice_score_distribution'])}")
    lines.append('')
    lines.append(f"Strict lattice residual distribution: {format_counter(data['lattice_residual_distribution'])}")
    lines.append('')
    lines.append('## Residual By Poker/Rose')
    lines.append('')
    lines.append('| poker_stage | rose_bucket | residual | count | scores |')
    lines.append('| --- | --- | ---: | ---: | --- |')
    for row in data.get('stage_rows', []):
        lines.append(
            f"| {row.get('poker_stage')} | {row.get('rose_bucket')} | {row.get('residual')} | "
            f"{row.get('count')} | {format_score_counter(row.get('score_distribution', {}))} |"
        )
    lines.append('')
    lines.append('## Labels With Enough Strict Samples')
    lines.append('')
    lines.append('| label | count | avg | min | max | low_residual_rate | scores | residuals |')
    lines.append('| --- | ---: | ---: | ---: | ---: | ---: | --- | --- |')
    for row in data.get('label_rows', [])[:max_labels]:
        lines.append(
            f"| `{row.get('label')}` | {row.get('count')} | {row.get('avg')} | {row.get('min')} | {row.get('max')} | "
            f"{row.get('low_residual_rate')} | {format_score_counter(row.get('score_distribution', {}))} | "
            f"{format_counter(row.get('residual_distribution', {}))} |"
        )
    lines.append('')
    lines.append('## Same Visible Signature, Different Scores')
    lines.append('')
    lines.append('These groups have the same extracted visible signature but different residuals, so they are the strongest evidence that the `-200` tail is not explained by current visible factors.')
    lines.append('')
    lines.append('| count | residuals | scores | signature |')
    lines.append('| ---: | --- | --- | --- |')
    for row in data.get('signature_collisions', [])[:max_collisions]:
        sig = row.get('signature', {})
        sig_text = (
            f"rose={sig.get('rose')} {sig.get('rose_bucket')}#{sig.get('rose_stage6_index')}; "
            f"z_err8={sig.get('z_err8')}; poker={sig.get('poker_stage')} [{sig.get('poker_evidence')}]; "
            f"yuan={sig.get('yuan_stage')} [{sig.get('yuan_evidence')}]"
        )
        lines.append(
            f"| {row.get('count')} | {format_counter(row.get('residual_distribution', {}))} | "
            f"{format_score_counter(row.get('score_distribution', {}))} | {sig_text} |"
        )
    lines.append('')
    lines.append('## Immediate Implications')
    lines.append('')
    lines.append('- More blind variants of Poker stage3 are unlikely to explain the main bottleneck; stage3 is already modelled as a `+50` layer on top of stage2.')
    lines.append('- The largest stability issue is the invisible `-200` residual. It appears across Poker stages, so it must be mined against exact visible-signature collisions instead of blamed on one Poker question.')
    lines.append('- The largest upside issue is still a missing positive component, most plausibly Yuan answer/progress or a Poker component beyond current stage3. Yuan should stay isolated until `+40` or answer score becomes controllable.')
    return '\n'.join(lines) + '\n'


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', type=Path, default=IN_JSON)
    parser.add_argument('--out-json', type=Path, default=OUT_JSON)
    parser.add_argument('--out-md', type=Path, default=OUT_MD)
    parser.add_argument('--min-label-count', type=int, default=8)
    parser.add_argument('--max-labels', type=int, default=80)
    parser.add_argument('--max-collisions', type=int, default=20)
    args = parser.parse_args()

    source = load_json(args.input)
    rows = source.get('rows') if isinstance(source.get('rows'), list) else []
    data = analyze(rows, args.min_label_count)

    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    args.out_md.write_text(render_md(data, args.max_labels, args.max_collisions), encoding='utf-8')
    print(
        json.dumps(
            {
                'rows': data['row_count'],
                'current_rows': data['current_row_count'],
                'lattice_rows': data['lattice_row_count'],
                'out_json': str(args.out_json),
                'out_md': str(args.out_md),
            },
            indent=2,
        )
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
