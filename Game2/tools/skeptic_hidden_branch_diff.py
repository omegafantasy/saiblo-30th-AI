#!/usr/bin/env python3
from __future__ import annotations

import argparse
import collections
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_GAP_AUDIT = ROOT / 'docs' / 'generated' / 'game2_skeptic_gap_mode_audit.json'
OUT_JSON = ROOT / 'docs' / 'generated' / 'game2_skeptic_hidden_branch_diff.json'
OUT_MD = ROOT / 'docs' / 'generated' / 'game2_skeptic_hidden_branch_diff.md'

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
    parser = argparse.ArgumentParser(description='Compare hidden-branch feature enrichments between low-score tiers and high-score tier')
    parser.add_argument('--gap-audit-json', default=str(DEFAULT_GAP_AUDIT))
    parser.add_argument('--label-prefix', default='sk548e0909')
    parser.add_argument('--ref-score', type=int, default=2157)
    parser.add_argument('--min-support', type=int, default=3)
    parser.add_argument('--top-k', type=int, default=20)
    parser.add_argument('--out-json', default=str(OUT_JSON))
    parser.add_argument('--out-md', default=str(OUT_MD))
    return parser.parse_args()


def normalized_group(label: str) -> str:
    if label.startswith('sk'):
        return label.split('_probe', 1)[0]
    match = BASE_RE.match(label)
    return match.group(1) if match else label


def parse_room_label(path: Path) -> str:
    room = path.parents[2].name
    base = room.rsplit('_room', 1)[0]
    return base.split('_', 2)[-1]


def record_state(record: Any) -> dict[str, Any]:
    if not isinstance(record, dict):
        return {}
    state = record.get('result_state')
    return state if isinstance(state, dict) else record


def record_hint(record: Any) -> str:
    state = record_state(record)
    hint = state.get('hint')
    return str(hint) if isinstance(hint, str) else ''


def record_stage(record: Any) -> int | None:
    state = record_state(record)
    stage = state.get('stage')
    return stage if isinstance(stage, int) else None


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


def final_answer_names(answer_text: str) -> tuple[str, str]:
    killer_m = KILLER_RE.search(answer_text or '')
    banker_m = BANKER_RE.search(answer_text or '')
    killer = killer_m.group(1).strip() if killer_m else ''
    banker = banker_m.group(1).strip() if banker_m else ''
    return killer, banker


def stage6_step(case0: dict[str, Any]) -> int | None:
    transitions = case0.get('stage_transitions')
    if not isinstance(transitions, list):
        return None
    for row in transitions:
        if not isinstance(row, dict):
            continue
        if row.get('to_stage') == 6 and isinstance(row.get('step_id'), int):
            return int(row['step_id'])
    return None


def role_map_from_step0(match_download: dict[str, Any]) -> dict[str, str]:
    rows = match_download.get('0')
    if not isinstance(rows, list) or not rows or not isinstance(rows[0], dict):
        return {}
    state = rows[0].get('result_state')
    if not isinstance(state, dict):
        return {}

    visible = [str(item) for item in state.get('visible_npcs', []) if isinstance(item, str)]
    marks = [str(item) for item in state.get('npc_marks', []) if isinstance(item, str)]
    mark_set = set(marks)
    false_set = [npc for npc in visible if npc not in mark_set]

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


def features_of_row(row: dict[str, Any]) -> list[str]:
    features: set[str] = set()
    for key in (
        'killer_cn',
        'banker_cn',
        'pair_killer_banker',
        'false_mark',
        'host_like',
        'partner_like',
        'banker_like',
        'triplet',
        'pair_false_banker',
    ):
        value = str(row.get(key) or '').strip()
        if value:
            features.add(f'{key}={value}')

    for key in ('rose_step_count', 'rose_stage6_step', 'poker_step_count', 'poker_max_stage'):
        value = row.get(key)
        if isinstance(value, int):
            features.add(f'{key}={value}')
    return sorted(features)


def rows_from_gap_audit(data: dict[str, Any], label_prefix: str) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    labels = data.get('labels')
    if not isinstance(labels, list):
        return out
    for label_row in labels:
        if not isinstance(label_row, dict):
            continue
        rows = label_row.get('rows')
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            label = str(row.get('label') or '')
            if not label.startswith(label_prefix):
                continue
            path = str(row.get('path') or '')
            if not path:
                continue
            out[path] = row
    return out


def build(args: argparse.Namespace) -> dict[str, Any]:
    gap = load_json(Path(args.gap_audit_json).resolve())
    if not isinstance(gap, dict):
        return {'error': f'invalid gap audit json: {args.gap_audit_json}'}
    gap_rows = rows_from_gap_audit(gap, args.label_prefix)

    rows: list[dict[str, Any]] = []
    for analysis_path in sorted((ROOT / 'Game2' / 'runtime' / 'room_matches').glob('*/matches/*/analysis.json')):
        analysis = load_json(analysis_path)
        if not isinstance(analysis, dict):
            continue
        players = analysis.get('players')
        first = players[0] if isinstance(players, list) and players and isinstance(players[0], dict) else {}
        score = first.get('score')
        if first.get('end_state') != 'OK' or not isinstance(score, int) or score <= 0:
            continue
        label = parse_room_label(analysis_path)
        if not label.startswith(args.label_prefix):
            continue

        rel_path = str(analysis_path.relative_to(ROOT))
        gap_row = gap_rows.get(rel_path, {})

        match_download_path = analysis_path.parent / 'match_download.json'
        match_download = load_json(match_download_path)
        if not isinstance(match_download, dict):
            match_download = {}

        role_map = role_map_from_step0(match_download)
        cases = analysis.get('cases')
        case0 = cases[0] if isinstance(cases, list) and cases and isinstance(cases[0], dict) else {}
        answer_text = str(case0.get('final_answer') or '')
        killer_cn, banker_cn = final_answer_names(answer_text)

        decoded = analysis.get('decoded_stdin_records')
        decoded_rows = decoded if isinstance(decoded, list) else []
        rose_step_count = None
        poker_step_count = None
        poker_max_stage = None
        for idx, seg in enumerate(split_segments(decoded_rows)):
            kind = segment_kind(seg, idx)
            if kind == 'rose':
                rose_step_count = len(seg)
            elif kind == 'poker':
                poker_step_count = len(seg)
                poker_max_stage = max_stage(seg)

        row: dict[str, Any] = {
            'group': normalized_group(label),
            'label': label,
            'match_id': str(analysis.get('match_id') or analysis_path.parent.name),
            'score': int(score),
            'path': rel_path,
            'mode': str(gap_row.get('mode') or ''),
            'residual_gap': gap_row.get('residual_gap'),
            'killer_cn': killer_cn,
            'banker_cn': banker_cn,
            'pair_killer_banker': f'{killer_cn}|{banker_cn}' if killer_cn and banker_cn else '',
            'false_mark': role_map.get('false_mark', ''),
            'host_like': role_map.get('host_like', ''),
            'partner_like': role_map.get('partner_like', ''),
            'banker_like': role_map.get('banker_like', ''),
            'triplet': role_map.get('triplet', ''),
            'pair_false_banker': f'{role_map.get("false_mark", "")}|{role_map.get("banker_like", "")}'
            if role_map.get('false_mark') and role_map.get('banker_like')
            else '',
            'rose_step_count': int(rose_step_count) if isinstance(rose_step_count, int) else None,
            'rose_stage6_step': stage6_step(case0),
            'poker_step_count': int(poker_step_count) if isinstance(poker_step_count, int) else None,
            'poker_max_stage': int(poker_max_stage) if isinstance(poker_max_stage, int) else None,
        }
        row['features'] = features_of_row(row)
        rows.append(row)

    if not rows:
        return {'error': f'no rows for label-prefix {args.label_prefix}'}

    score_counter = collections.Counter(int(row['score']) for row in rows)
    ref_score = int(args.ref_score) if int(args.ref_score) > 0 else max(score_counter.keys())
    ref_rows = [row for row in rows if int(row['score']) == ref_score]
    if not ref_rows:
        return {'error': f'reference score {ref_score} not found in rows'}

    tier_reports: list[dict[str, Any]] = []
    for score in sorted(score_counter.keys()):
        if score == ref_score:
            continue
        low_rows = [row for row in rows if int(row['score']) == score]
        low_n = len(low_rows)
        ref_n = len(ref_rows)
        if low_n == 0 or ref_n == 0:
            continue

        feat_low = collections.Counter()
        feat_ref = collections.Counter()
        for row in low_rows:
            for feat in set(row.get('features', [])):
                feat_low[str(feat)] += 1
        for row in ref_rows:
            for feat in set(row.get('features', [])):
                feat_ref[str(feat)] += 1

        merged = set(feat_low) | set(feat_ref)
        scored: list[dict[str, Any]] = []
        for feat in merged:
            low_hits = int(feat_low.get(feat, 0))
            ref_hits = int(feat_ref.get(feat, 0))
            support = low_hits + ref_hits
            if support < int(args.min_support) or low_hits <= 0:
                continue
            low_rate = low_hits / low_n
            ref_rate = ref_hits / ref_n
            lift = None if ref_rate == 0 else round(low_rate / ref_rate, 6)
            scored.append(
                {
                    'feature': feat,
                    'low_hits': low_hits,
                    'low_rate': round(low_rate, 6),
                    'ref_hits': ref_hits,
                    'ref_rate': round(ref_rate, 6),
                    'lift': lift,
                }
            )
        scored.sort(
            key=lambda item: (
                -1.0 if item['lift'] is None else -float(item['lift']),
                -float(item['low_rate']),
                -int(item['low_hits']),
                item['feature'],
            )
        )

        mode_dist = collections.Counter(str(row.get('mode') or '') for row in low_rows)
        tier_reports.append(
            {
                'score': int(score),
                'count': low_n,
                'mode_distribution': dict(sorted(mode_dist.items())),
                'top_enriched_features': scored[: max(0, int(args.top_k))],
                'examples': [
                    {
                        'label': row['label'],
                        'match_id': row['match_id'],
                        'mode': row.get('mode'),
                        'residual_gap': row.get('residual_gap'),
                        'killer_cn': row.get('killer_cn'),
                        'banker_cn': row.get('banker_cn'),
                        'false_mark': row.get('false_mark'),
                    }
                    for row in low_rows[:10]
                ],
            }
        )

    tier_reports.sort(key=lambda row: int(row.get('score', 0)))
    return {
        'label_prefix': args.label_prefix,
        'ref_score': ref_score,
        'min_support': int(args.min_support),
        'top_k': int(args.top_k),
        'total_rows': len(rows),
        'score_distribution': dict(sorted(score_counter.items())),
        'group_distribution': dict(sorted(collections.Counter(row['group'] for row in rows).items())),
        'tiers': tier_reports,
    }


def fmt_lift(value: Any) -> str:
    if value is None:
        return 'inf'
    return str(value)


def render_md(data: dict[str, Any]) -> str:
    lines = ['# Game2 Skeptic Hidden Branch Diff', '']
    if 'error' in data:
        lines.append(f"- error: `{data['error']}`")
        return '\n'.join(lines) + '\n'

    lines.append('This report compares low-score tiers against a fixed high-score reference to expose hidden-branch enrichments.')
    lines.append('')
    lines.append('## Global')
    lines.append(f"- label_prefix: `{data.get('label_prefix')}`")
    lines.append(f"- ref_score: `{data.get('ref_score')}`")
    lines.append(f"- rows: `{data.get('total_rows')}`")
    lines.append(f"- score distribution: `{data.get('score_distribution')}`")
    lines.append(f"- group distribution: `{data.get('group_distribution')}`")
    lines.append('')

    for tier in data.get('tiers', []):
        score = tier.get('score')
        lines.append(f'## Tier {score} vs Ref')
        lines.append(f"- rows: `{tier.get('count')}`")
        lines.append(f"- mode distribution: `{tier.get('mode_distribution')}`")
        lines.append('')
        lines.append('| feature | low_hits | low_rate | ref_hits | ref_rate | lift |')
        lines.append('| --- | ---: | ---: | ---: | ---: | ---: |')
        for row in tier.get('top_enriched_features', []):
            lines.append(
                f"| `{row.get('feature')}` | {row.get('low_hits')} | {row.get('low_rate')} | "
                f"{row.get('ref_hits')} | {row.get('ref_rate')} | {fmt_lift(row.get('lift'))} |"
            )
        lines.append('')
        lines.append('| label | match | mode | residual | killer | banker | false_mark |')
        lines.append('| --- | --- | --- | ---: | --- | --- | --- |')
        for row in tier.get('examples', []):
            lines.append(
                f"| `{row.get('label')}` | `{row.get('match_id')}` | `{row.get('mode')}` | "
                f"{row.get('residual_gap')} | `{row.get('killer_cn')}` | `{row.get('banker_cn')}` | "
                f"`{row.get('false_mark')}` |"
            )
        lines.append('')
    lines.append('Interpretation:')
    lines.append('- If specific role/answer features remain enriched after sample growth, hidden scoring likely depends on identity permutation.')
    lines.append('- Features with high lift but low support are hypotheses; prioritize those repeatedly enriched across multiple tiers.')
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
                'tiers': len(data.get('tiers', [])) if isinstance(data.get('tiers'), list) else 0,
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
