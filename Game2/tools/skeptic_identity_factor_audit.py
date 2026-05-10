#!/usr/bin/env python3
from __future__ import annotations

import argparse
import collections
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_AUDIT_JSON = ROOT / 'docs' / 'generated' / 'game2_skeptic_gap_mode_audit.json'
OUT_JSON = ROOT / 'docs' / 'generated' / 'game2_skeptic_identity_factor_audit.json'
OUT_MD = ROOT / 'docs' / 'generated' / 'game2_skeptic_identity_factor_audit.md'
BASE_RE = re.compile(r'(n\d+[a-z])')


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Audit identity-level factors for residual-only score gaps')
    parser.add_argument('--audit-json', default=str(DEFAULT_AUDIT_JSON))
    parser.add_argument('--label-prefix', default='sk548')
    parser.add_argument('--target-residual', type=int, default=200)
    parser.add_argument(
        '--target-mode',
        default='residual_only',
        help='target mode filter: residual_only, any, or explicit mode string',
    )
    parser.add_argument('--min-support', type=int, default=2)
    parser.add_argument('--top-k', type=int, default=50)
    parser.add_argument('--out-json', default=str(OUT_JSON))
    parser.add_argument('--out-md', default=str(OUT_MD))
    return parser.parse_args()


def normalized_group(label: str) -> str:
    if label.startswith('sk'):
        return label.split('_probe', 1)[0]
    match = BASE_RE.match(label)
    return match.group(1) if match else label


def choice_records(decoded_records: list[Any]) -> list[dict[str, bool]]:
    out: list[dict[str, bool]] = []
    for row in decoded_records:
        if not isinstance(row, dict):
            continue
        if not row:
            continue
        values = list(row.values())
        if values and all(isinstance(value, bool) for value in values):
            out.append({str(key): bool(value) for key, value in row.items()})
    return out


def features_from_analysis(path: Path) -> set[str]:
    data = load_json(path)
    if not isinstance(data, dict):
        return set()
    records = data.get('decoded_stdin_records')
    if not isinstance(records, list) or not records:
        return set()

    out: set[str] = set()
    first = records[0] if isinstance(records[0], dict) else {}
    state = first.get('result_state') if isinstance(first, dict) else {}
    if not isinstance(state, dict):
        state = {}

    visible = [str(item) for item in state.get('visible_npcs', []) if isinstance(item, str)]
    marks = [str(item) for item in state.get('npc_marks', []) if isinstance(item, str)]
    visible_set = set(visible)
    marks_set = set(marks)
    false_marks = sorted(visible_set - marks_set)

    if visible:
        out.add('init.visible_set=' + '/'.join(sorted(visible)))
        for name in sorted(visible_set):
            out.add('init.visible_has=' + name)
    if marks:
        out.add('init.mark_set=' + '/'.join(sorted(marks)))
    if false_marks:
        out.add('init.false_marks=' + '/'.join(false_marks))
        for name in false_marks:
            out.add('init.false_mark=' + name)

    for index, choice in enumerate(choice_records(records), start=1):
        false_names = sorted(name for name, value in choice.items() if not value)
        true_names = sorted(name for name, value in choice.items() if value)
        out.add(f'choice{index}.size={len(choice)}')
        if false_names:
            out.add(f'choice{index}.false_set=' + '/'.join(false_names))
            for name in false_names:
                out.add(f'choice{index}.false=' + name)
        if true_names:
            out.add(f'choice{index}.true_set=' + '/'.join(true_names))
    return out


def build(args: argparse.Namespace) -> dict[str, Any]:
    audit = load_json(Path(args.audit_json).resolve())
    if not isinstance(audit, dict):
        return {'error': f'invalid audit json: {args.audit_json}'}

    label_rows = audit.get('labels')
    if not isinstance(label_rows, list):
        return {'error': 'audit json missing labels[]'}

    rows: list[dict[str, Any]] = []
    for label_row in label_rows:
        if not isinstance(label_row, dict):
            continue
        recs = label_row.get('rows')
        if not isinstance(recs, list):
            continue
        for item in recs:
            if not isinstance(item, dict):
                continue
            label = str(item.get('label') or '')
            if not label.startswith(args.label_prefix):
                continue
            path = ROOT / str(item.get('path') or '')
            if not path.is_file():
                continue
            residual = item.get('residual_gap')
            mode = str(item.get('mode') or '')
            target_mode = str(args.target_mode or 'residual_only').strip()
            mode_ok = (
                target_mode == 'any'
                or mode == target_mode
            )
            target = bool(
                isinstance(residual, int)
                and int(residual) >= int(args.target_residual)
                and mode_ok
            )
            rows.append(
                {
                    'group': normalized_group(label),
                    'label': label,
                    'match_id': str(item.get('match_id') or ''),
                    'score': item.get('score'),
                    'label_max': item.get('score') if item.get('score_gap_to_label_max') == 0 else item.get('score') + item.get('score_gap_to_label_max', 0) if isinstance(item.get('score'), int) and isinstance(item.get('score_gap_to_label_max'), int) else None,
                    'gap': item.get('score_gap_to_label_max'),
                    'residual_gap': residual,
                    'mode': mode,
                    'path': str(path.relative_to(ROOT)),
                    'is_target': target,
                    'features': sorted(features_from_analysis(path)),
                }
            )

    total = len(rows)
    target_total = sum(1 for row in rows if row['is_target'])
    base_rate = (target_total / total) if total else 0.0

    feature_counter: collections.Counter[str] = collections.Counter()
    feature_target_counter: collections.Counter[str] = collections.Counter()
    for row in rows:
        feats = set(str(item) for item in row.get('features', []))
        for feat in feats:
            feature_counter[feat] += 1
            if row['is_target']:
                feature_target_counter[feat] += 1

    feature_rows: list[dict[str, Any]] = []
    for feat, support in feature_counter.items():
        if int(support) < int(args.min_support):
            continue
        hit = int(feature_target_counter.get(feat, 0))
        rate = hit / support if support else 0.0
        lift = (rate / base_rate) if base_rate > 0 else 0.0
        feature_rows.append(
            {
                'feature': feat,
                'support': int(support),
                'target_hits': hit,
                'target_rate': round(rate, 6),
                'lift': round(lift, 6),
            }
        )

    feature_rows.sort(
        key=lambda item: (
            float(item['lift']),
            float(item['target_rate']),
            int(item['target_hits']),
            int(item['support']),
            item['feature'],
        ),
        reverse=True,
    )
    top = feature_rows[: max(0, int(args.top_k))]

    group_counter: dict[str, dict[str, int]] = collections.defaultdict(lambda: {'rows': 0, 'targets': 0})
    for row in rows:
        group = str(row['group'])
        group_counter[group]['rows'] += 1
        if row['is_target']:
            group_counter[group]['targets'] += 1

    group_rows = []
    for group, stats in sorted(group_counter.items()):
        rows_n = int(stats['rows'])
        targets_n = int(stats['targets'])
        group_rows.append(
            {
                'group': group,
                'rows': rows_n,
                'targets': targets_n,
                'target_rate': round(targets_n / rows_n, 6) if rows_n else 0.0,
            }
        )

    target_examples = [
        {
            'group': row['group'],
            'label': row['label'],
            'match_id': row['match_id'],
            'score': row['score'],
            'gap': row['gap'],
            'residual_gap': row['residual_gap'],
            'mode': row['mode'],
            'path': row['path'],
        }
        for row in rows
        if row['is_target']
    ]
    target_examples.sort(key=lambda item: (item['group'], item['label'], item['match_id']))

    return {
        'audit_json': str(Path(args.audit_json).resolve()),
        'label_prefix': args.label_prefix,
        'target_residual': int(args.target_residual),
        'target_mode': str(args.target_mode or 'residual_only'),
        'total_rows': total,
        'target_rows': target_total,
        'target_base_rate': round(base_rate, 6),
        'group_summary': group_rows,
        'top_features': top,
        'target_examples': target_examples,
    }


def render_md(data: dict[str, Any]) -> str:
    lines = ['# Game2 Skeptic Identity Factor Audit', '']
    if 'error' in data:
        lines.append(f"- error: `{data['error']}`")
        return '\n'.join(lines) + '\n'

    lines.append('This audit checks whether target residual rows correlate with identity-level features in decoded traces.')
    lines.append('')
    lines.append('## Global')
    lines.append(f"- label_prefix: `{data.get('label_prefix')}`")
    lines.append(f"- rows: `{data.get('total_rows')}`")
    lines.append(
        f"- target rows (`mode={data.get('target_mode')}` and residual >= threshold): `{data.get('target_rows')}`"
    )
    lines.append(f"- target base rate: `{data.get('target_base_rate')}`")
    lines.append('')

    lines.append('## Group Summary')
    lines.append('| group | rows | target_rows | target_rate |')
    lines.append('| --- | ---: | ---: | ---: |')
    for row in data.get('group_summary', []):
        lines.append(
            f"| `{row.get('group')}` | {row.get('rows')} | {row.get('targets')} | {row.get('target_rate')} |"
        )
    lines.append('')

    lines.append('## Top Identity Features')
    lines.append('| feature | support | target_hits | target_rate | lift |')
    lines.append('| --- | ---: | ---: | ---: | ---: |')
    for row in data.get('top_features', []):
        lines.append(
            f"| `{row.get('feature')}` | {row.get('support')} | {row.get('target_hits')} | {row.get('target_rate')} | {row.get('lift')} |"
        )
    lines.append('')

    lines.append('## Target Rows')
    lines.append('| group | label | match | score | gap | residual | mode |')
    lines.append('| --- | --- | --- | ---: | ---: | ---: | --- |')
    for row in data.get('target_examples', []):
        lines.append(
            f"| `{row.get('group')}` | `{row.get('label')}` | `{row.get('match_id')}` | "
            f"{row.get('score')} | {row.get('gap')} | {row.get('residual_gap')} | `{row.get('mode')}` |"
        )
    lines.append('')
    lines.append('Interpretation:')
    lines.append('- High-lift identity features suggest hidden branch dependency beyond visible stage/evidence flow.')
    lines.append('- If top features are weak/unstable, residual cause is likely not simple NPC-name mapping.')
    return '\n'.join(lines) + '\n'


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
                'rows': data.get('total_rows', 0),
                'target_rows': data.get('target_rows', 0),
                'target_base_rate': data.get('target_base_rate', 0),
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
