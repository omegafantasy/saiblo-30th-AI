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
OUT_JSON = ROOT / 'docs' / 'generated' / 'game2_skeptic_role_mapping_audit.json'
OUT_MD = ROOT / 'docs' / 'generated' / 'game2_skeptic_role_mapping_audit.md'
BASE_RE = re.compile(r'(n\d+[a-z])')
ABOUT_RE = re.compile(r'关于(.+)$')


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Audit role-mapping factors from match_download against residual targets')
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


def step0_state(match_download: Path) -> dict[str, Any]:
    data = load_json(match_download)
    if not isinstance(data, dict):
        return {}
    rows = data.get('0')
    if not isinstance(rows, list) or not rows:
        return {}
    first = rows[0]
    if not isinstance(first, dict):
        return {}
    state = first.get('result_state')
    return state if isinstance(state, dict) else {}


def role_features(match_download: Path) -> set[str]:
    state = step0_state(match_download)
    if not state:
        return set()

    out: set[str] = set()
    mem: dict[str, str] = {}
    evidences = state.get('evidences')
    if isinstance(evidences, list):
        for item in evidences:
            if not isinstance(item, dict):
                continue
            evid_id = str(item.get('id') or '').strip()
            evid_name = str(item.get('name') or '').strip()
            m = ABOUT_RE.search(evid_name)
            if evid_id and m:
                name = m.group(1).strip()
                mem[evid_id] = name
                out.add(f'mem_{evid_id}={name}')

    if '002' in mem:
        out.add('role.host_like=' + mem['002'])
    if '003' in mem:
        out.add('role.partner_like=' + mem['003'])
    if '004' in mem:
        out.add('role.banker_like=' + mem['004'])
    if {'002', '003', '004'}.issubset(mem):
        out.add('role.triplet=' + '|'.join([mem['002'], mem['003'], mem['004']]))

    visible = state.get('visible_npcs')
    marks = state.get('npc_marks')
    visible_set = set(str(item) for item in visible if isinstance(item, str)) if isinstance(visible, list) else set()
    marks_set = set(str(item) for item in marks if isinstance(item, str)) if isinstance(marks, list) else set()
    if visible_set:
        out.add('init.visible_set=' + '/'.join(sorted(visible_set)))
    if marks_set:
        out.add('init.mark_set=' + '/'.join(sorted(marks_set)))
    if visible_set and marks_set:
        false_marks = sorted(visible_set - marks_set)
        if false_marks:
            out.add('init.false_set=' + '/'.join(false_marks))
            for name in false_marks:
                out.add('init.false=' + name)
                if '002' in mem:
                    out.add('cross.host_false=' + mem['002'] + '|' + name)
                if '003' in mem:
                    out.add('cross.partner_false=' + mem['003'] + '|' + name)
                if '004' in mem:
                    out.add('cross.banker_false=' + mem['004'] + '|' + name)
    return out


def build(args: argparse.Namespace) -> dict[str, Any]:
    audit = load_json(Path(args.audit_json).resolve())
    if not isinstance(audit, dict):
        return {'error': f'invalid audit json: {args.audit_json}'}

    labels = audit.get('labels')
    if not isinstance(labels, list):
        return {'error': 'audit json missing labels[]'}

    rows: list[dict[str, Any]] = []
    mode_filter = str(args.target_mode or 'residual_only').strip()
    for label_row in labels:
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
            mode = str(item.get('mode') or '')
            residual = item.get('residual_gap')
            mode_ok = (mode_filter == 'any') or (mode == mode_filter)
            target = bool(
                isinstance(residual, int)
                and int(residual) >= int(args.target_residual)
                and mode_ok
            )

            analysis_rel = str(item.get('path') or '')
            analysis_path = ROOT / analysis_rel
            match_dir = analysis_path.parent
            match_download = match_dir / 'match_download.json'
            if not match_download.is_file():
                continue

            rows.append(
                {
                    'group': normalized_group(label),
                    'label': label,
                    'match_id': str(item.get('match_id') or match_dir.name),
                    'score': item.get('score'),
                    'gap': item.get('score_gap_to_label_max'),
                    'residual_gap': residual,
                    'mode': mode,
                    'path': str(analysis_path.relative_to(ROOT)),
                    'is_target': target,
                    'features': sorted(role_features(match_download)),
                }
            )

    total_rows = len(rows)
    target_rows = sum(1 for row in rows if row['is_target'])
    base_rate = (target_rows / total_rows) if total_rows else 0.0

    feat_total: collections.Counter[str] = collections.Counter()
    feat_hits: collections.Counter[str] = collections.Counter()
    for row in rows:
        feats = set(str(item) for item in row.get('features', []))
        for feat in feats:
            feat_total[feat] += 1
            if row['is_target']:
                feat_hits[feat] += 1

    scored: list[dict[str, Any]] = []
    for feat, support in feat_total.items():
        if int(support) < int(args.min_support):
            continue
        hits = int(feat_hits.get(feat, 0))
        rate = hits / support if support else 0.0
        lift = (rate / base_rate) if base_rate > 0 else 0.0
        scored.append(
            {
                'feature': feat,
                'support': int(support),
                'target_hits': hits,
                'target_rate': round(rate, 6),
                'lift': round(lift, 6),
            }
        )
    scored.sort(
        key=lambda item: (
            float(item['lift']),
            float(item['target_rate']),
            int(item['target_hits']),
            int(item['support']),
            item['feature'],
        ),
        reverse=True,
    )
    top = scored[: max(0, int(args.top_k))]

    group_stats: dict[str, dict[str, int]] = collections.defaultdict(lambda: {'rows': 0, 'targets': 0})
    for row in rows:
        group = str(row['group'])
        group_stats[group]['rows'] += 1
        if row['is_target']:
            group_stats[group]['targets'] += 1
    group_summary = []
    for group, st in sorted(group_stats.items()):
        rows_n = int(st['rows'])
        targets_n = int(st['targets'])
        group_summary.append(
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
        'target_mode': mode_filter,
        'total_rows': total_rows,
        'target_rows': target_rows,
        'target_base_rate': round(base_rate, 6),
        'group_summary': group_summary,
        'top_features': top,
        'target_examples': target_examples,
    }


def render_md(data: dict[str, Any]) -> str:
    lines = ['# Game2 Skeptic Role Mapping Audit', '']
    if 'error' in data:
        lines.append(f"- error: `{data['error']}`")
        return '\n'.join(lines) + '\n'

    lines.append('This audit extracts role mapping from `match_download` step0 memories and checks correlation with residual targets.')
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

    lines.append('## Top Features')
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
    lines.append('- High-lift role features indicate branch dependence may be tied to identity permutation.')
    lines.append('- Low support means these are hypotheses, not final causal proof.')
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
