#!/usr/bin/env python3
from __future__ import annotations

import argparse
import collections
import json
import statistics
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_AUDIT_JSON = ROOT / 'docs' / 'generated' / 'game2_skeptic_gap_mode_audit.json'
OUT_JSON = ROOT / 'docs' / 'generated' / 'game2_skeptic_residual_trace_diff.json'
OUT_MD = ROOT / 'docs' / 'generated' / 'game2_skeptic_residual_trace_diff.md'
KNOWN_KEYS = {
    'step_id',
    'npc',
    'interaction',
    'result_state',
    'hint',
    'evidences',
    'reply',
    'stage',
    'achievements',
    'unlock_testimony',
    'error',
}


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return None


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

    if isinstance(record, dict):
        evidences2 = record.get('evidences')
        if isinstance(evidences2, list):
            for item in evidences2:
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


def choice_pattern(record: Any) -> str:
    if not isinstance(record, dict):
        return ''
    keys = set(str(key) for key in record.keys())
    if not keys or not keys.isdisjoint(KNOWN_KEYS):
        return ''
    values = list(record.values())
    if not values or not all(isinstance(value, bool) for value in values):
        return ''
    return ''.join('T' if bool(value) else 'F' for value in values)


def segment_features(segment: list[Any]) -> dict[str, Any]:
    stage_first: dict[int, int] = {}
    stage_seq: list[int] = []
    evidence_first: dict[str, int] = {}
    choice_patterns: list[str] = []
    error_count = 0

    for index, record in enumerate(segment):
        stage = record_stage(record)
        if stage is not None:
            if stage not in stage_first:
                stage_first[stage] = index
            if not stage_seq or stage_seq[-1] != stage:
                stage_seq.append(stage)

        for eid in evidence_ids(record):
            evidence_first.setdefault(eid, index)

        pattern = choice_pattern(record)
        if pattern:
            choice_patterns.append(pattern)

        if isinstance(record, dict) and isinstance(record.get('error'), str):
            if 'Internal Server Error' in str(record.get('error')):
                error_count += 1

    return {
        'length': len(segment),
        'stage_first': {str(key): value for key, value in sorted(stage_first.items())},
        'stage_seq': stage_seq,
        'evidence_first': dict(sorted(evidence_first.items(), key=lambda item: (item[1], item[0]))),
        'choice_patterns': choice_patterns,
        'error_count': error_count,
    }


def row_features(path: Path) -> dict[str, Any] | None:
    data = load_json(path)
    if not isinstance(data, dict):
        return None
    players = data.get('players')
    first = players[0] if isinstance(players, list) and players and isinstance(players[0], dict) else {}
    score = first.get('score')
    if not isinstance(score, int):
        return None
    records = data.get('decoded_stdin_records')
    if not isinstance(records, list):
        records = []

    segments = split_segments(records)
    by_kind: dict[str, dict[str, Any]] = {}
    kind_order: list[str] = []
    for index, segment in enumerate(segments):
        kind = segment_kind(segment, index)
        by_kind[kind] = segment_features(segment)
        kind_order.append(kind)

    global_choices: list[str] = []
    for record in records:
        pattern = choice_pattern(record)
        if pattern:
            global_choices.append(pattern)

    signature_items: list[str] = []
    for kind in kind_order:
        feature = by_kind.get(kind, {})
        signature_items.append(
            f'{kind}|len={feature.get("length")}|stage={"-".join(str(x) for x in feature.get("stage_seq", []))}|'
            f'choices={",".join(feature.get("choice_patterns", []))}|errs={feature.get("error_count", 0)}'
        )
    signature_items.append(f'global_choices={"|".join(global_choices)}')

    return {
        'score': score,
        'record_count': len(records),
        'kind_order': kind_order,
        'segments': by_kind,
        'global_choice_patterns': global_choices,
        'trace_signature': ' || '.join(signature_items),
    }


def median_int(values: list[int]) -> int | None:
    if not values:
        return None
    return int(statistics.median(values))


def mode_str(values: list[str]) -> str:
    if not values:
        return ''
    return collections.Counter(values).most_common(1)[0][0]


def aggregate_ref(ref_features: list[dict[str, Any]]) -> dict[str, Any]:
    kind_set: set[str] = set()
    for row in ref_features:
        kind_set.update(str(kind) for kind in row.get('kind_order', []))

    kinds: dict[str, Any] = {}
    for kind in sorted(kind_set):
        rows = [row.get('segments', {}).get(kind) for row in ref_features if isinstance(row.get('segments', {}).get(kind), dict)]
        if not rows:
            continue
        lengths = [int(row.get('length', 0)) for row in rows]
        stage_keys: set[str] = set()
        evidence_keys: set[str] = set()
        for row in rows:
            stage_keys.update(str(key) for key in row.get('stage_first', {}).keys())
            evidence_keys.update(str(key) for key in row.get('evidence_first', {}).keys())
        stage_ref = {}
        for key in sorted(stage_keys, key=lambda item: int(item) if item.isdigit() else item):
            vals = [int(row.get('stage_first', {}).get(key)) for row in rows if isinstance(row.get('stage_first', {}).get(key), int)]
            med = median_int(vals)
            if med is not None:
                stage_ref[key] = med
        evidence_ref = {}
        for key in sorted(evidence_keys):
            vals = [int(row.get('evidence_first', {}).get(key)) for row in rows if isinstance(row.get('evidence_first', {}).get(key), int)]
            med = median_int(vals)
            if med is not None:
                evidence_ref[key] = med

        seq_mode = mode_str(['-'.join(str(v) for v in row.get('stage_seq', [])) for row in rows])
        choice_mode = mode_str([','.join(str(v) for v in row.get('choice_patterns', [])) for row in rows])

        kinds[kind] = {
            'count': len(rows),
            'length_median': median_int(lengths),
            'stage_first_median': stage_ref,
            'stage_seq_mode': seq_mode,
            'evidence_first_median': evidence_ref,
            'choice_patterns_mode': choice_mode,
            'error_count_mode': mode_str([str(row.get('error_count', 0)) for row in rows]),
        }

    global_choice_mode = mode_str([','.join(str(v) for v in row.get('global_choice_patterns', [])) for row in ref_features])
    return {'kinds': kinds, 'global_choice_mode': global_choice_mode}


def diff_target_against_ref(target: dict[str, Any], ref: dict[str, Any]) -> dict[str, Any]:
    kind_diffs: dict[str, Any] = {}
    total_diff_count = 0

    target_segments = target.get('segments', {})
    ref_kinds = ref.get('kinds', {})
    for kind, kind_ref in ref_kinds.items():
        target_seg = target_segments.get(kind)
        if not isinstance(target_seg, dict):
            kind_diffs[kind] = {'missing_segment': True}
            total_diff_count += 1
            continue
        row: dict[str, Any] = {}

        length_ref = kind_ref.get('length_median')
        length_cur = target_seg.get('length')
        if isinstance(length_ref, int) and isinstance(length_cur, int) and length_cur != length_ref:
            row['length_delta'] = int(length_cur - length_ref)

        stage_deltas: dict[str, int] = {}
        for stage, stage_ref in kind_ref.get('stage_first_median', {}).items():
            stage_cur = target_seg.get('stage_first', {}).get(stage)
            if isinstance(stage_ref, int) and isinstance(stage_cur, int):
                delta = int(stage_cur - stage_ref)
                if delta != 0:
                    stage_deltas[stage] = delta
            elif isinstance(stage_ref, int) and stage_cur is None:
                stage_deltas[stage] = 999
        if stage_deltas:
            row['stage_first_deltas'] = stage_deltas

        seq_ref = str(kind_ref.get('stage_seq_mode') or '')
        seq_cur = '-'.join(str(v) for v in target_seg.get('stage_seq', []))
        if seq_ref and seq_ref != seq_cur:
            row['stage_seq_mismatch'] = {'target': seq_cur, 'ref_mode': seq_ref}

        evidence_ref = kind_ref.get('evidence_first_median', {})
        evidence_cur = target_seg.get('evidence_first', {})
        missing = sorted(set(evidence_ref.keys()) - set(evidence_cur.keys()))
        if missing:
            row['evidence_missing'] = missing
        late: dict[str, int] = {}
        for eid, idx_ref in evidence_ref.items():
            idx_cur = evidence_cur.get(eid)
            if isinstance(idx_ref, int) and isinstance(idx_cur, int) and idx_cur > idx_ref:
                late[eid] = int(idx_cur - idx_ref)
        if late:
            row['evidence_late'] = late

        choice_ref = str(kind_ref.get('choice_patterns_mode') or '')
        choice_cur = ','.join(str(v) for v in target_seg.get('choice_patterns', []))
        if choice_ref and choice_ref != choice_cur:
            row['choice_pattern_mismatch'] = {'target': choice_cur, 'ref_mode': choice_ref}

        if row:
            kind_diffs[kind] = row
            total_diff_count += len(row)

    global_row: dict[str, Any] = {}
    global_ref = str(ref.get('global_choice_mode') or '')
    global_cur = ','.join(str(v) for v in target.get('global_choice_patterns', []))
    if global_ref and global_ref != global_cur:
        global_row['global_choice_mismatch'] = {'target': global_cur, 'ref_mode': global_ref}

    if global_row:
        total_diff_count += len(global_row)

    return {'total_diff_count': total_diff_count, 'kind_diffs': kind_diffs, 'global_diffs': global_row}


def build(args: argparse.Namespace) -> dict[str, Any]:
    audit = load_json(Path(args.audit_json).resolve())
    if not isinstance(audit, dict):
        return {'error': f'invalid audit json: {args.audit_json}'}

    unresolved = audit.get('unresolved_rows')
    unresolved_rows = unresolved if isinstance(unresolved, list) else []
    filtered: list[dict[str, Any]] = []
    for row in unresolved_rows:
        if not isinstance(row, dict):
            continue
        base = str(row.get('base_label') or '')
        residual = row.get('residual_gap')
        if not base.startswith(args.label_prefix):
            continue
        if not isinstance(residual, int) or residual < int(args.min_residual):
            continue
        filtered.append(row)

    filtered.sort(
        key=lambda item: (
            int(item.get('residual_gap', 0)),
            int(item.get('gap', 0)),
            str(item.get('base_label', '')),
            str(item.get('match_id', '')),
        ),
        reverse=True,
    )
    if int(args.top_k) > 0:
        filtered = filtered[: int(args.top_k)]

    labels = audit.get('labels')
    label_rows: dict[str, list[dict[str, Any]]] = {}
    if isinstance(labels, list):
        for label_row in labels:
            if not isinstance(label_row, dict):
                continue
            base = str(label_row.get('base_label') or '')
            rows = label_row.get('rows')
            if isinstance(rows, list):
                label_rows[base] = [item for item in rows if isinstance(item, dict)]

    outputs: list[dict[str, Any]] = []
    anomaly_counter: collections.Counter[str] = collections.Counter()
    for row in filtered:
        base = str(row.get('base_label') or '')
        target_path = ROOT / str(row.get('path') or '')
        if not target_path.is_file():
            outputs.append(
                {
                    'base_label': base,
                    'match_id': str(row.get('match_id') or ''),
                    'score': row.get('score'),
                    'label_max': row.get('label_max'),
                    'gap': row.get('gap'),
                    'residual_gap': row.get('residual_gap'),
                    'status': 'missing-target-path',
                    'path': str(row.get('path') or ''),
                }
            )
            anomaly_counter['missing-target-path'] += 1
            continue

        group = label_rows.get(base, [])
        label_max = int(row.get('label_max')) if isinstance(row.get('label_max'), int) else None
        ref_rows = [item for item in group if isinstance(item.get('score'), int) and (label_max is None or int(item['score']) == label_max)]
        ref_rows = ref_rows[: max(1, int(args.max_ref_rows))]

        target_feature = row_features(target_path)
        ref_features: list[dict[str, Any]] = []
        for ref_row in ref_rows:
            ref_path = ROOT / str(ref_row.get('path') or '')
            feature = row_features(ref_path)
            if feature is not None:
                ref_features.append(feature)

        if target_feature is None or not ref_features:
            outputs.append(
                {
                    'base_label': base,
                    'match_id': str(row.get('match_id') or ''),
                    'score': row.get('score'),
                    'label_max': row.get('label_max'),
                    'gap': row.get('gap'),
                    'residual_gap': row.get('residual_gap'),
                    'status': 'insufficient-features',
                    'path': str(row.get('path') or ''),
                    'ref_count': len(ref_features),
                }
            )
            anomaly_counter['insufficient-features'] += 1
            continue

        ref_agg = aggregate_ref(ref_features)
        diff = diff_target_against_ref(target_feature, ref_agg)
        total_diff = int(diff.get('total_diff_count', 0))
        status = 'trace-equivalent-residual' if total_diff == 0 else 'observable-diff'
        anomaly_counter[status] += 1

        outputs.append(
            {
                'base_label': base,
                'match_id': str(row.get('match_id') or ''),
                'score': int(row.get('score')) if isinstance(row.get('score'), int) else row.get('score'),
                'label_max': int(row.get('label_max')) if isinstance(row.get('label_max'), int) else row.get('label_max'),
                'gap': int(row.get('gap')) if isinstance(row.get('gap'), int) else row.get('gap'),
                'residual_gap': int(row.get('residual_gap')) if isinstance(row.get('residual_gap'), int) else row.get('residual_gap'),
                'mode': str(row.get('mode') or ''),
                'path': str(row.get('path') or ''),
                'status': status,
                'observable_diff_count': total_diff,
                'diff': diff,
                'target': {
                    'record_count': int(target_feature.get('record_count', 0)),
                    'kind_order': target_feature.get('kind_order', []),
                    'global_choice_patterns': target_feature.get('global_choice_patterns', []),
                    'trace_signature': target_feature.get('trace_signature', ''),
                },
                'reference': {
                    'count': len(ref_features),
                    'global_choice_mode': ref_agg.get('global_choice_mode'),
                },
            }
        )

    outputs.sort(key=lambda item: (str(item.get('status')), int(item.get('residual_gap', 0))), reverse=True)
    return {
        'audit_json': str(Path(args.audit_json).resolve()),
        'label_prefix': args.label_prefix,
        'min_residual': int(args.min_residual),
        'top_k': int(args.top_k),
        'max_ref_rows': int(args.max_ref_rows),
        'count': len(outputs),
        'status_distribution': dict(sorted(anomaly_counter.items())),
        'rows': outputs,
    }


def render_md(data: dict[str, Any]) -> str:
    lines = ['# Game2 Skeptic Residual Trace Diff', '']
    lines.append('This report compares each residual-heavy row against same-label max-score references at detailed trace level.')
    lines.append('It is designed to falsify easy narratives: if no observable diff exists, residual likely comes from hidden factors.')
    lines.append('')
    lines.append('## Global')
    lines.append(f"- rows analyzed: `{data.get('count', 0)}`")
    lines.append(f"- label prefix: `{data.get('label_prefix', '')}`")
    lines.append(f"- min residual: `{data.get('min_residual', 0)}`")
    lines.append(f"- status distribution: `{data.get('status_distribution', {})}`")
    lines.append('')
    lines.append('## Residual Rows')
    lines.append('')
    lines.append('| label | match | score | label max | residual | status | diff_count |')
    lines.append('| --- | --- | ---: | ---: | ---: | --- | ---: |')
    for row in data.get('rows', []):
        lines.append(
            f"| `{row.get('base_label', '')}` | `{row.get('match_id', '')}` | {row.get('score', '')} | "
            f"{row.get('label_max', '')} | {row.get('residual_gap', '')} | `{row.get('status', '')}` | "
            f"{row.get('observable_diff_count', '')} |"
        )
    lines.append('')
    lines.append('## Skeptic Notes')
    for row in data.get('rows', []):
        label = row.get('base_label', '')
        match_id = row.get('match_id', '')
        status = row.get('status', '')
        lines.append(f"- `{label}` `{match_id}`: `{status}`")
        diff = row.get('diff', {})
        kind_diffs = diff.get('kind_diffs', {}) if isinstance(diff, dict) else {}
        if status == 'trace-equivalent-residual':
            lines.append('  - No observable stage/evidence/choice pattern deviation vs max-score refs.')
            lines.append('  - This is a strong hidden-factor candidate; avoid explaining it as simple stage lag.')
            continue
        if isinstance(kind_diffs, dict):
            for kind, details in kind_diffs.items():
                if not isinstance(details, dict):
                    continue
                detail_bits: list[str] = []
                if 'length_delta' in details:
                    detail_bits.append(f'len_delta={details["length_delta"]}')
                if 'stage_first_deltas' in details:
                    detail_bits.append(f'stage_delta={details["stage_first_deltas"]}')
                if 'evidence_missing' in details:
                    detail_bits.append(f'miss_evid={details["evidence_missing"]}')
                if 'evidence_late' in details:
                    detail_bits.append(f'late_evid={details["evidence_late"]}')
                if 'choice_pattern_mismatch' in details:
                    detail_bits.append('choice_mismatch')
                if detail_bits:
                    lines.append(f"  - `{kind}`: {', '.join(detail_bits)}")
    lines.append('')
    lines.append('Interpretation rule:')
    lines.append('- `trace-equivalent-residual` => current decoded records cannot explain score drop; prioritize hidden-branch forensics.')
    lines.append('- `observable-diff` => decoded trace still contains concrete deltas to test directly.')
    return '\n'.join(lines) + '\n'


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Residual trace-level diff against max-score references')
    parser.add_argument('--audit-json', default=str(DEFAULT_AUDIT_JSON))
    parser.add_argument('--label-prefix', default='n548')
    parser.add_argument('--min-residual', type=int, default=200)
    parser.add_argument('--top-k', type=int, default=12)
    parser.add_argument('--max-ref-rows', type=int, default=6)
    parser.add_argument('--out-json', default=str(OUT_JSON))
    parser.add_argument('--out-md', default=str(OUT_MD))
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    data = build(args)
    out_json = Path(args.out_json).resolve()
    out_md = Path(args.out_md).resolve()
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    out_md.write_text(render_md(data), encoding='utf-8')
    print(
        json.dumps(
            {
                'count': data.get('count', 0),
                'status_distribution': data.get('status_distribution', {}),
                'out_json': str(out_json),
                'out_md': str(out_md),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
