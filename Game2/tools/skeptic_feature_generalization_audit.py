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
OUT_JSON = ROOT / 'docs' / 'generated' / 'game2_skeptic_feature_generalization_audit.json'
OUT_MD = ROOT / 'docs' / 'generated' / 'game2_skeptic_feature_generalization_audit.md'

BASE_RE = re.compile(r'(n\d+[a-z])')
ABOUT_RE = re.compile(r'关于(.+)$')
KILLER_RE = re.compile(r'凶手[:：]\s*([^,，。\s]+)')
BANKER_RE = re.compile(r'爱慕并想独占([^,，。\s]+)')


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Audit whether skeptical features generalize across independent groups')
    parser.add_argument('--audit-json', default=str(DEFAULT_AUDIT_JSON))
    parser.add_argument('--label-prefix', default='sk548')
    parser.add_argument('--target-residual', type=int, default=200)
    parser.add_argument('--target-mode', default='residual_only', help='residual_only, any, or explicit mode')
    parser.add_argument('--min-support-total', type=int, default=4)
    parser.add_argument('--min-support-group', type=int, default=2)
    parser.add_argument('--top-k', type=int, default=60)
    parser.add_argument('--out-json', default=str(OUT_JSON))
    parser.add_argument('--out-md', default=str(OUT_MD))
    return parser.parse_args()


def normalized_group(label: str) -> str:
    if label.startswith('sk'):
        base = label
        for sep in ('_probe', '_auto'):
            if sep in base:
                base = base.split(sep, 1)[0]
        return base
    match = BASE_RE.match(label)
    return match.group(1) if match else label


def role_from_match_download(path: Path) -> dict[str, str]:
    data = load_json(path)
    if not isinstance(data, dict):
        return {}
    rows = data.get('0')
    if not isinstance(rows, list) or not rows or not isinstance(rows[0], dict):
        return {}
    state = rows[0].get('result_state')
    if not isinstance(state, dict):
        return {}

    visible = [str(item) for item in state.get('visible_npcs', []) if isinstance(item, str)]
    marks = [str(item) for item in state.get('npc_marks', []) if isinstance(item, str)]
    mark_set = set(marks)
    false_set = [name for name in visible if name not in mark_set]

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
                mem[evid_id] = m.group(1).strip()

    return {
        'false_mark': false_set[0] if false_set else '',
        'host_like': mem.get('002', ''),
        'partner_like': mem.get('003', ''),
        'banker_like': mem.get('004', ''),
        'triplet': '|'.join([mem.get('002', ''), mem.get('003', ''), mem.get('004', '')]),
    }


def killer_banker_from_analysis(path: Path) -> tuple[str, str]:
    data = load_json(path)
    if not isinstance(data, dict):
        return '', ''
    cases = data.get('cases')
    first = cases[0] if isinstance(cases, list) and cases and isinstance(cases[0], dict) else {}
    answer = str(first.get('final_answer') or '')
    killer_m = KILLER_RE.search(answer)
    banker_m = BANKER_RE.search(answer)
    killer = killer_m.group(1).strip() if killer_m else ''
    banker = banker_m.group(1).strip() if banker_m else ''
    return killer, banker


def row_features(analysis_path: Path, match_download_path: Path) -> list[str]:
    role = role_from_match_download(match_download_path)
    killer, banker = killer_banker_from_analysis(analysis_path)
    out: set[str] = set()

    for key in ('false_mark', 'host_like', 'partner_like', 'banker_like', 'triplet'):
        value = str(role.get(key) or '').strip()
        if value:
            out.add(f'{key}={value}')

    if killer:
        out.add(f'killer_cn={killer}')
    if banker:
        out.add(f'banker_cn={banker}')
    if killer and banker:
        out.add(f'killer_banker={killer}|{banker}')
    if role.get('false_mark') and role.get('banker_like'):
        out.add(f'false_banker={role["false_mark"]}|{role["banker_like"]}')
    if role.get('false_mark') and killer:
        out.add(f'false_killer={role["false_mark"]}|{killer}')
    return sorted(out)


def build(args: argparse.Namespace) -> dict[str, Any]:
    audit = load_json(Path(args.audit_json).resolve())
    if not isinstance(audit, dict):
        return {'error': f'invalid audit json: {args.audit_json}'}

    labels = audit.get('labels')
    if not isinstance(labels, list):
        return {'error': 'audit json missing labels[]'}

    mode_filter = str(args.target_mode or 'residual_only').strip()
    rows: list[dict[str, Any]] = []
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
            analysis_rel = str(item.get('path') or '')
            analysis_path = ROOT / analysis_rel
            match_download_path = analysis_path.parent / 'match_download.json'
            if not analysis_path.is_file() or not match_download_path.is_file():
                continue

            mode = str(item.get('mode') or '')
            residual = item.get('residual_gap')
            mode_ok = (mode_filter == 'any') or (mode == mode_filter)
            is_target = bool(
                isinstance(residual, int)
                and int(residual) >= int(args.target_residual)
                and mode_ok
            )

            rows.append(
                {
                    'group': normalized_group(label),
                    'label': label,
                    'match_id': str(item.get('match_id') or analysis_path.parent.name),
                    'score': item.get('score'),
                    'mode': mode,
                    'residual_gap': residual,
                    'is_target': is_target,
                    'features': row_features(analysis_path, match_download_path),
                }
            )

    if not rows:
        return {'error': f'no rows for label-prefix {args.label_prefix}'}

    groups = sorted(set(str(row['group']) for row in rows))
    group_rows: dict[str, list[dict[str, Any]]] = {group: [row for row in rows if row['group'] == group] for group in groups}
    group_base_rate: dict[str, float] = {}
    for group, grows in group_rows.items():
        total = len(grows)
        hit = sum(1 for row in grows if row['is_target'])
        group_base_rate[group] = (hit / total) if total else 0.0

    total_rows = len(rows)
    total_targets = sum(1 for row in rows if row['is_target'])
    base_rate = (total_targets / total_rows) if total_rows else 0.0

    feat_total: collections.Counter[str] = collections.Counter()
    feat_target: collections.Counter[str] = collections.Counter()
    for row in rows:
        feats = set(str(item) for item in row.get('features', []))
        for feat in feats:
            feat_total[feat] += 1
            if row['is_target']:
                feat_target[feat] += 1

    results: list[dict[str, Any]] = []
    for feat, support_total in feat_total.items():
        if int(support_total) < int(args.min_support_total):
            continue
        hit_total = int(feat_target.get(feat, 0))
        rate_total = hit_total / support_total if support_total else 0.0
        lift_total = (rate_total / base_rate) if base_rate > 0 else 0.0

        group_stats = []
        better_count = 0
        equal_or_better_count = 0
        for group in groups:
            grows = group_rows[group]
            grows_feat = [row for row in grows if feat in set(str(item) for item in row.get('features', []))]
            g_support = len(grows_feat)
            g_target = sum(1 for row in grows_feat if row['is_target'])
            g_rate = (g_target / g_support) if g_support else None
            g_base = group_base_rate[group]
            g_lift = (g_rate / g_base) if (g_rate is not None and g_base > 0) else None
            if g_rate is not None and g_base > 0 and g_rate > g_base:
                better_count += 1
            if g_rate is not None and g_base > 0 and g_rate >= g_base:
                equal_or_better_count += 1
            group_stats.append(
                {
                    'group': group,
                    'support': g_support,
                    'target_hits': g_target,
                    'target_rate': None if g_rate is None else round(g_rate, 6),
                    'base_rate': round(g_base, 6),
                    'lift': None if g_lift is None else round(g_lift, 6),
                }
            )

        # Leave-one-group-out stability check.
        logo = []
        for holdout in groups:
            train_rows = [row for row in rows if row['group'] != holdout]
            train_feat = [row for row in train_rows if feat in set(str(item) for item in row.get('features', []))]
            train_support = len(train_feat)
            train_hit = sum(1 for row in train_feat if row['is_target'])
            train_rate = (train_hit / train_support) if train_support else None
            train_base = (sum(1 for row in train_rows if row['is_target']) / len(train_rows)) if train_rows else 0.0
            train_lift = (train_rate / train_base) if (train_rate is not None and train_base > 0) else None

            hold_rows = group_rows[holdout]
            hold_feat = [row for row in hold_rows if feat in set(str(item) for item in row.get('features', []))]
            hold_support = len(hold_feat)
            hold_hit = sum(1 for row in hold_feat if row['is_target'])
            hold_rate = (hold_hit / hold_support) if hold_support else None
            hold_base = group_base_rate[holdout]
            hold_lift = (hold_rate / hold_base) if (hold_rate is not None and hold_base > 0) else None
            logo.append(
                {
                    'holdout': holdout,
                    'train_support': train_support,
                    'train_lift': None if train_lift is None else round(train_lift, 6),
                    'holdout_support': hold_support,
                    'holdout_lift': None if hold_lift is None else round(hold_lift, 6),
                }
            )

        stable_holds = 0
        for row_logo in logo:
            if int(row_logo['holdout_support']) < int(args.min_support_group):
                continue
            hold_lift = row_logo.get('holdout_lift')
            if isinstance(hold_lift, (int, float)) and float(hold_lift) >= 1.0:
                stable_holds += 1

        results.append(
            {
                'feature': feat,
                'support_total': int(support_total),
                'target_hits_total': hit_total,
                'target_rate_total': round(rate_total, 6),
                'lift_total': round(lift_total, 6),
                'better_group_count': better_count,
                'equal_or_better_group_count': equal_or_better_count,
                'stable_holdouts': stable_holds,
                'group_stats': group_stats,
                'logo': logo,
            }
        )

    results.sort(
        key=lambda item: (
            int(item['stable_holdouts']),
            int(item['better_group_count']),
            float(item['lift_total']),
            int(item['target_hits_total']),
            int(item['support_total']),
            item['feature'],
        ),
        reverse=True,
    )

    return {
        'audit_json': str(Path(args.audit_json).resolve()),
        'label_prefix': args.label_prefix,
        'target_residual': int(args.target_residual),
        'target_mode': mode_filter,
        'rows': total_rows,
        'target_rows': total_targets,
        'target_base_rate': round(base_rate, 6),
        'groups': groups,
        'group_base_rate': {k: round(v, 6) for k, v in group_base_rate.items()},
        'features': results[: max(0, int(args.top_k))],
    }


def render_md(data: dict[str, Any]) -> str:
    lines = ['# Game2 Skeptic Feature Generalization Audit', '']
    if 'error' in data:
        lines.append(f"- error: `{data['error']}`")
        return '\n'.join(lines) + '\n'

    lines.append('This audit checks whether high-lift skeptical features hold across independent groups instead of one-group overfit.')
    lines.append('')
    lines.append('## Global')
    lines.append(f"- label_prefix: `{data.get('label_prefix')}`")
    lines.append(f"- rows: `{data.get('rows')}`")
    lines.append(f"- target rows: `{data.get('target_rows')}`")
    lines.append(f"- target base rate: `{data.get('target_base_rate')}`")
    lines.append(f"- group base rates: `{data.get('group_base_rate')}`")
    lines.append('')

    lines.append('## Top Features')
    lines.append('| feature | support | target_hits | rate | lift | better_groups | stable_holdouts |')
    lines.append('| --- | ---: | ---: | ---: | ---: | ---: | ---: |')
    for row in data.get('features', []):
        lines.append(
            f"| `{row.get('feature')}` | {row.get('support_total')} | {row.get('target_hits_total')} | "
            f"{row.get('target_rate_total')} | {row.get('lift_total')} | "
            f"{row.get('better_group_count')} | {row.get('stable_holdouts')} |"
        )
    lines.append('')
    lines.append('Interpretation:')
    lines.append('- Prefer features with `stable_holdouts` high; low/zero means likely group-specific noise.')
    lines.append('- A feature that only wins in one group should not drive global causal claims.')
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
                'rows': data.get('rows', 0),
                'target_rows': data.get('target_rows', 0),
                'features': len(data.get('features', [])) if isinstance(data.get('features'), list) else 0,
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
