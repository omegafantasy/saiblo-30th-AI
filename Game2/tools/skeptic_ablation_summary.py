#!/usr/bin/env python3
from __future__ import annotations

import argparse
import collections
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SUMMARY_JSON = ROOT / 'docs' / 'generated' / 'game2_room_eval_summary.json'
OUT_JSON = ROOT / 'docs' / 'generated' / 'game2_skeptic_ablation_summary_sk548e0910.json'
OUT_MD = ROOT / 'docs' / 'generated' / 'game2_skeptic_ablation_summary_sk548e0910.md'
VARIANT_PREFIX_RE = re.compile(r'^(sk548e0910[a-z]_(?:ab|auto))\d+$')


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Aggregate skeptic ablation room results by label prefixes')
    parser.add_argument('--room-summary-json', default=str(DEFAULT_SUMMARY_JSON))
    parser.add_argument(
        '--prefix',
        action='append',
        default=[],
        help='label prefix to aggregate; can be specified multiple times',
    )
    parser.add_argument('--out-json', default=str(OUT_JSON))
    parser.add_argument('--out-md', default=str(OUT_MD))
    return parser.parse_args()


def default_prefixes() -> list[str]:
    return [
        'sk548e0909',
        'sk548e0909b_auto',
    ]


def discover_0910_variant_prefixes(rows: list[dict[str, Any]]) -> list[str]:
    found: set[str] = set()
    for row in rows:
        label = str(row.get('label') or '')
        match = VARIANT_PREFIX_RE.match(label)
        if match:
            found.add(match.group(1))
    return sorted(found)


def to_int(value: Any) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        try:
            return int(value.strip())
        except Exception:
            return None
    return None


def aggregate_group(rows: list[dict[str, Any]], prefix: str) -> dict[str, Any]:
    selected = [row for row in rows if str(row.get('label') or '').startswith(prefix)]
    distribution: collections.Counter[int] = collections.Counter()
    effective = 0
    for row in selected:
        effective += int(row.get('effective') or 0)
        dist = row.get('distribution')
        if not isinstance(dist, dict):
            continue
        for score_raw, count_raw in dist.items():
            score = to_int(score_raw)
            count = to_int(count_raw)
            if score is None or count is None:
                continue
            distribution[score] += count

    weighted_scores: list[int] = []
    for score, count in distribution.items():
        weighted_scores.extend([score] * count)
    avg = (sum(weighted_scores) / len(weighted_scores)) if weighted_scores else None

    return {
        'prefix': prefix,
        'labels': sorted(str(row.get('label') or '') for row in selected),
        'label_count': len(selected),
        'effective': effective,
        'avg': None if avg is None else round(avg, 3),
        'min': min(weighted_scores) if weighted_scores else None,
        'max': max(weighted_scores) if weighted_scores else None,
        'distribution': dict(sorted(distribution.items())),
    }


def build(args: argparse.Namespace) -> dict[str, Any]:
    summary = load_json(Path(args.room_summary_json).resolve())
    labels = summary.get('labels')
    rows = labels if isinstance(labels, list) else []
    label_rows = [item for item in rows if isinstance(item, dict)]

    prefixes = [token.strip() for token in args.prefix if str(token).strip()]
    if not prefixes:
        prefixes = default_prefixes()
        for prefix in discover_0910_variant_prefixes(label_rows):
            if prefix not in prefixes:
                prefixes.append(prefix)

    groups = [aggregate_group(label_rows, prefix) for prefix in prefixes]
    return {
        'room_summary_json': str(Path(args.room_summary_json).resolve()),
        'prefixes': prefixes,
        'groups': groups,
    }


def render_md(data: dict[str, Any]) -> str:
    lines = ['# Game2 Skeptic Ablation Summary', '']
    lines.append('Compact room-eval aggregation for independent skeptic A/B variants.')
    lines.append('')
    lines.append('| prefix | effective | avg | min | max | distribution |')
    lines.append('| --- | ---: | ---: | ---: | ---: | --- |')
    for group in data.get('groups', []):
        if not isinstance(group, dict):
            continue
        dist = group.get('distribution', {})
        if isinstance(dist, dict):
            dist_text = ', '.join(f'{score}x{count}' for score, count in dist.items())
        else:
            dist_text = ''
        lines.append(
            f"| `{group.get('prefix', '')}` | {group.get('effective', 0)} | "
            f"{group.get('avg', '') if group.get('avg') is not None else ''} | "
            f"{group.get('min', '') if group.get('min') is not None else ''} | "
            f"{group.get('max', '') if group.get('max') is not None else ''} | "
            f"{dist_text} |"
        )
    lines.append('')
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
                'groups': len(data.get('groups', [])),
                'out_json': str(out_json),
                'out_md': str(out_md),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
