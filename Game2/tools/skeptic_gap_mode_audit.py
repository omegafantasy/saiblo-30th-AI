#!/usr/bin/env python3
from __future__ import annotations

import collections
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ROOM_DIR = ROOT / 'Game2' / 'runtime' / 'room_matches'
OUT_JSON = ROOT / 'docs' / 'generated' / 'game2_skeptic_gap_mode_audit.json'
OUT_MD = ROOT / 'docs' / 'generated' / 'game2_skeptic_gap_mode_audit.md'


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return None


def parse_room_label(path: Path) -> str:
    room = path.parents[2].name
    base = room.rsplit('_room', 1)[0]
    return base.split('_', 2)[-1]


def base_label(label: str) -> str:
    match = re.match(r'(n\d+[a-z])', label)
    return match.group(1) if match else label


def record_state(record: Any) -> dict[str, Any]:
    if not isinstance(record, dict):
        return {}
    state = record.get('result_state')
    if isinstance(state, dict):
        return state
    return record


def record_hint(record: Any) -> str:
    state = record_state(record)
    hint = state.get('hint')
    return str(hint) if isinstance(hint, str) else ''


def record_stage(record: Any) -> int | None:
    state = record_state(record)
    stage = state.get('stage')
    return stage if isinstance(stage, int) else None


def evidence_ids(record: Any) -> list[str]:
    state = record_state(record)
    out: list[str] = []
    visible = state.get('visible_evidences')
    if isinstance(visible, list):
        out.extend(str(item) for item in visible if item is not None)
    evidences = state.get('evidences')
    if isinstance(evidences, list):
        for item in evidences:
            if isinstance(item, dict) and item.get('id') is not None:
                out.append(str(item.get('id')))
    return sorted(set(out))


def is_case_start(record: Any) -> bool:
    if not isinstance(record, dict):
        return False
    state = record.get('result_state')
    if not isinstance(state, dict):
        return False
    return record.get('step_id') == 0 and isinstance(state.get('hint'), str)


def split_segments(records: list[Any]) -> list[list[Any]]:
    starts = [i for i, record in enumerate(records) if is_case_start(record)]
    segments: list[list[Any]] = []
    for pos, start in enumerate(starts):
        end = starts[pos + 1] if pos + 1 < len(starts) else len(records)
        segments.append(records[start:end])
    return segments


def segment_kind(segment: list[Any], index: int) -> str:
    hint = record_hint(segment[0]) if segment else ''
    if 'Rose' in hint:
        return 'rose'
    if 'Z' in hint or 'F' in hint or '宿舍' in hint or 'U盘' in hint:
        return 'zf'
    if '信息来源' in hint or '扑克公馆' in hint or '梅花' in hint:
        return 'poker'
    if '袁樱瞳' in hint or '碎尸' in hint or '课程展示' in hint:
        return 'yuan'
    return f'case{index}'


def max_stage(segment: list[Any]) -> int | None:
    stages = [stage for record in segment if (stage := record_stage(record)) is not None]
    return max(stages) if stages else None


def first_stage_index(segment: list[Any], target_stage: int) -> int | None:
    for index, record in enumerate(segment):
        if record_stage(record) == target_stage:
            return index
    return None


def segment_evidence(segment: list[Any]) -> list[str]:
    out: set[str] = set()
    for record in segment:
        out.update(evidence_ids(record))
    return sorted(out)


def row_from_analysis(path: Path) -> dict[str, Any] | None:
    data = load_json(path)
    if not isinstance(data, dict):
        return None
    players = data.get('players')
    first = players[0] if isinstance(players, list) and players and isinstance(players[0], dict) else {}
    score = first.get('score')
    if first.get('end_state') != 'OK' or not isinstance(score, int) or score <= 0:
        return None
    records = data.get('decoded_stdin_records')
    if not isinstance(records, list):
        records = []
    label = parse_room_label(path)

    rose_stage6_index = None
    rose_max_stage = None
    poker_max_stage = None
    poker_evidence: list[str] = []
    yuan_evidence: list[str] = []
    for idx, segment in enumerate(split_segments(records)):
        kind = segment_kind(segment, idx)
        if kind == 'rose':
            rose_stage6_index = first_stage_index(segment, 6)
            rose_max_stage = max_stage(segment)
        elif kind == 'poker':
            poker_max_stage = max_stage(segment)
            poker_evidence = segment_evidence(segment)
        elif kind == 'yuan':
            yuan_evidence = segment_evidence(segment)

    err8_count = sum(
        1
        for record in records
        if isinstance(record, dict) and "Internal Server Error: '8'" in str(record.get('error', ''))
    )
    return {
        'label': label,
        'base_label': base_label(label),
        'match_id': str(data.get('match_id') or path.parent.name),
        'score': int(score),
        'path': str(path.relative_to(ROOT)),
        'record_count': len(records),
        'rose_stage6_index': rose_stage6_index,
        'rose_max_stage': rose_max_stage,
        'poker_max_stage': poker_max_stage,
        'poker_evidence_ids': poker_evidence,
        'yuan_evidence_ids': yuan_evidence,
        'z_err8_count': err8_count,
    }


def mode(values: list[Any]) -> Any:
    if not values:
        return None
    counter = collections.Counter(values)
    return counter.most_common(1)[0][0]


def reference_of_rows(rows: list[dict[str, Any]], max_score: int) -> dict[str, Any]:
    tops = [row for row in rows if int(row['score']) == max_score]
    rose_indices = [row['rose_stage6_index'] for row in tops if isinstance(row.get('rose_stage6_index'), int)]
    poker_stages = [row['poker_max_stage'] for row in tops if isinstance(row.get('poker_max_stage'), int)]
    z_counts = [row['z_err8_count'] for row in tops if isinstance(row.get('z_err8_count'), int)]
    # Use most common evidence set among top rows as reference.
    poker_sets = [','.join(row.get('poker_evidence_ids', [])) for row in tops if row.get('poker_evidence_ids')]
    return {
        'max_score': max_score,
        'rose_stage6_index': min(rose_indices) if rose_indices else None,
        'poker_max_stage': max(poker_stages) if poker_stages else None,
        'poker_evidence_ids': poker_sets and mode(poker_sets).split(',') or [],
        'z_err8_count': mode(z_counts),
        'top_count': len(tops),
    }


def explain_gap(row: dict[str, Any], ref: dict[str, Any], gap: int) -> dict[str, Any]:
    reasons: list[str] = []
    estimated = 0

    ref_rose_index = ref.get('rose_stage6_index')
    row_rose_index = row.get('rose_stage6_index')
    rose_lag = (
        isinstance(ref_rose_index, int)
        and isinstance(row_rose_index, int)
        and row_rose_index > ref_rose_index
    )
    if rose_lag:
        reasons.append('rose_lag')
        estimated += 40

    ref_poker_stage = ref.get('poker_max_stage')
    row_poker_stage = row.get('poker_max_stage')
    poker_stage_drop = (
        isinstance(ref_poker_stage, int)
        and isinstance(row_poker_stage, int)
        and row_poker_stage < ref_poker_stage
    )
    if poker_stage_drop:
        reasons.append(f'poker_stage_{ref_poker_stage}_to_{row_poker_stage}')
        if ref_poker_stage >= 3 and row_poker_stage <= 1:
            estimated += 100

    ref_poker_evidence = set(str(item) for item in ref.get('poker_evidence_ids', []))
    row_poker_evidence = set(str(item) for item in row.get('poker_evidence_ids', []))
    dropped = sorted(ref_poker_evidence - row_poker_evidence)
    if dropped:
        reasons.append(f'poker_evidence_drop:{"/".join(dropped)}')

    ref_z = ref.get('z_err8_count')
    row_z = row.get('z_err8_count')
    if isinstance(ref_z, int) and isinstance(row_z, int) and row_z != ref_z:
        reasons.append(f'z_err8_{ref_z}_to_{row_z}')

    residual = gap - estimated
    if gap <= 0:
        mode_name = 'max'
    elif residual <= 0:
        mode_name = '+'.join(reasons) if reasons else 'explained'
    elif reasons:
        mode_name = '+'.join(reasons) + '+residual'
    else:
        mode_name = 'residual_only'
    return {
        'mode': mode_name,
        'reasons': reasons,
        'estimated_gap': estimated,
        'residual_gap': residual,
    }


def build() -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for path in sorted(ROOM_DIR.glob('*/matches/*/analysis.json')):
        row = row_from_analysis(path)
        if row is not None:
            rows.append(row)

    groups: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for row in rows:
        groups[str(row['base_label'])].append(row)

    label_summaries: list[dict[str, Any]] = []
    audited_rows: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    mode_counter: collections.Counter[str] = collections.Counter()
    for label, group in groups.items():
        scores = [int(row['score']) for row in group]
        max_score = max(scores)
        ref = reference_of_rows(group, max_score)
        out_rows = []
        for row in group:
            gap = int(max_score) - int(row['score'])
            exp = explain_gap(row, ref, gap)
            merged = {
                **row,
                'score_gap_to_label_max': gap,
                **exp,
            }
            out_rows.append(merged)
            audited_rows.append(merged)
            mode_counter[exp['mode']] += 1
            if int(merged['residual_gap']) >= 100:
                unresolved.append(
                    {
                        'base_label': label,
                        'match_id': merged['match_id'],
                        'score': merged['score'],
                        'label_max': max_score,
                        'gap': gap,
                        'estimated_gap': merged['estimated_gap'],
                        'residual_gap': merged['residual_gap'],
                        'mode': merged['mode'],
                        'reasons': merged['reasons'],
                        'rose_stage6_index': merged['rose_stage6_index'],
                        'poker_max_stage': merged['poker_max_stage'],
                        'poker_evidence_ids': merged['poker_evidence_ids'],
                        'path': merged['path'],
                    }
                )

        out_rows.sort(key=lambda item: (int(item['score']), str(item['match_id'])))
        mode_dist = collections.Counter(item['mode'] for item in out_rows)
        label_summaries.append(
            {
                'base_label': label,
                'count': len(group),
                'max_score': max_score,
                'min_score': min(scores),
                'avg_score': round(sum(scores) / len(scores), 3),
                'distribution': dict(sorted(collections.Counter(scores).items())),
                'reference': ref,
                'mode_distribution': dict(sorted(mode_dist.items())),
                'rows': out_rows,
            }
        )

    label_summaries.sort(key=lambda item: (int(item['max_score']), int(item['min_score']), item['base_label']), reverse=True)
    unresolved.sort(key=lambda item: (int(item['residual_gap']), int(item['gap']), item['base_label']), reverse=True)
    n548_rows = [row for row in audited_rows if str(row['base_label']).startswith('n548')]
    n548_rows.sort(key=lambda item: (str(item['base_label']), int(item['score']), str(item['match_id'])))

    return {
        'total_rows': len(rows),
        'total_labels': len(label_summaries),
        'mode_distribution': dict(sorted(mode_counter.items(), key=lambda item: (-item[1], item[0]))),
        'unresolved_rows': unresolved[:300],
        'n548_rows': n548_rows,
        'labels': label_summaries,
    }


def render_counter(counter: dict[Any, Any]) -> str:
    return ', '.join(f'{key} x{value}' for key, value in counter.items())


def render_md(data: dict[str, Any]) -> str:
    lines = ['# Game2 Skeptic Gap Mode Audit', '']
    lines.append('This audit decomposes each sample score into `label_max - score` gaps and separates explainable drops from residual drops.')
    lines.append('It is intentionally independent from the main iteration narrative and focuses on falsifiable gap modes.')
    lines.append('')
    lines.append('## Global')
    lines.append(f"- effective rows: `{data['total_rows']}`")
    lines.append(f"- base labels: `{data['total_labels']}`")
    lines.append(f"- mode distribution: `{render_counter(data['mode_distribution'])}`")
    lines.append('')
    lines.append('Gap estimator used here:')
    lines.append('- `rose_lag` (rose stage6 reached later than the label reference): `+40` estimated drop')
    lines.append('- `poker_stage_3_to_1` (or lower than label reference): `+100` estimated drop')
    lines.append('- residual gap = actual gap - estimated gap')
    lines.append('')
    lines.append('## n548 Focus')
    lines.append('')
    lines.append('| label | match | score | gap | estimated | residual | mode | rose_idx | poker_stage | poker_evidence |')
    lines.append('| --- | --- | ---: | ---: | ---: | ---: | --- | ---: | ---: | --- |')
    for row in data['n548_rows']:
        lines.append(
            f"| `{row['label']}` | `{row['match_id']}` | {row['score']} | {row['score_gap_to_label_max']} | "
            f"{row['estimated_gap']} | {row['residual_gap']} | `{row['mode']}` | "
            f"{'' if row['rose_stage6_index'] is None else row['rose_stage6_index']} | "
            f"{'' if row['poker_max_stage'] is None else row['poker_max_stage']} | "
            f"{'/'.join(row.get('poker_evidence_ids', []))} |"
        )
    lines.append('')
    lines.append('## Residual >= 100')
    lines.append('')
    lines.append('| label | match | score | label max | gap | estimated | residual | mode |')
    lines.append('| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |')
    for row in data['unresolved_rows'][:80]:
        lines.append(
            f"| `{row['base_label']}` | `{row['match_id']}` | {row['score']} | {row['label_max']} | "
            f"{row['gap']} | {row['estimated_gap']} | {row['residual_gap']} | `{row['mode']}` |"
        )
    lines.append('')
    lines.append('## Skeptic Reading')
    lines.append('- If low-tail rows are fully explained by `rose_lag`/`poker_stage` modes, it is a control-flow/stage-path issue, not hidden scorer randomness.')
    lines.append('- Rows with residual `>=100` under the same observable mode should be treated as genuine unresolved gaps and isolated first.')
    lines.append('- For n548, prioritize residual rows over generic “more samples” loops; repeated +40 rows alone will not unlock the next plateau.')
    return '\n'.join(lines) + '\n'


def main() -> int:
    data = build()
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    OUT_MD.write_text(render_md(data), encoding='utf-8')
    print(
        json.dumps(
            {
                'total_rows': data['total_rows'],
                'total_labels': data['total_labels'],
                'unresolved_rows': len(data['unresolved_rows']),
                'out_json': str(OUT_JSON),
                'out_md': str(OUT_MD),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
