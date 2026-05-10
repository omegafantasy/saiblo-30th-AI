#!/usr/bin/env python3
from __future__ import annotations

import collections
import json
import math
import statistics
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
TOOLS_DIR = ROOT / 'Game2' / 'tools'
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from skeptic_room_feature_mine import mine_rows  # noqa: E402


OUT_JSON = ROOT / 'docs' / 'generated' / 'game2_skeptic_eval_gate.json'
OUT_MD = ROOT / 'docs' / 'generated' / 'game2_skeptic_eval_gate.md'


def wilson_upper(k: int, n: int, z: float = 1.96) -> float | None:
    if n <= 0:
        return None
    p = k / n
    denom = 1.0 + z * z / n
    center = (p + z * z / (2.0 * n)) / denom
    half = z * math.sqrt((p * (1.0 - p) / n) + (z * z / (4.0 * n * n))) / denom
    return min(1.0, center + half)


def distribution(scores: list[int]) -> dict[int, int]:
    return dict(sorted(collections.Counter(scores).items()))


def summarize_group(label: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    scores = [int(row['score']) for row in rows]
    n = len(scores)
    low_2657 = sum(1 for score in scores if score < 2657)
    low_2717 = sum(1 for score in scores if score < 2717)
    low_2757 = sum(1 for score in scores if score < 2757)
    avg = statistics.fmean(scores) if scores else 0.0
    return {
        'label': label,
        'n': n,
        'avg': round(avg, 3),
        'min': min(scores) if scores else None,
        'max': max(scores) if scores else None,
        'distribution': distribution(scores),
        'low_below_2657': low_2657,
        'low_below_2717': low_2717,
        'low_below_2757': low_2757,
        'wilson_upper_below_2657': round(wilson_upper(low_2657, n) or 0.0, 4),
        'wilson_upper_below_2717': round(wilson_upper(low_2717, n) or 0.0, 4),
        'wilson_upper_below_2757': round(wilson_upper(low_2757, n) or 0.0, 4),
    }


def by_key(rows: list[dict[str, Any]], key: str, min_n: int) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for row in rows:
        groups[str(row.get(key) or '')].append(row)
    summaries = [summarize_group(label, group) for label, group in groups.items() if label and len(group) >= min_n]
    summaries.sort(
        key=lambda item: (
            item['wilson_upper_below_2657'],
            -item['min'] if item['min'] is not None else 99999,
            -item['avg'],
            -item['n'],
        )
    )
    return summaries


def format_dist(value: dict[Any, Any]) -> str:
    return ', '.join(f'{score} x{count}' for score, count in value.items())


def render_table(rows: list[dict[str, Any]], limit: int = 30) -> list[str]:
    lines = [
        '| label | n | avg | min | max | distribution | <2657 | U95 <2657 | U95 <2717 | U95 <2757 |',
        '| --- | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: |',
    ]
    for row in rows[:limit]:
        lines.append(
            f"| `{row['label']}` | {row['n']} | {row['avg']} | {row['min']} | {row['max']} | "
            f"{format_dist(row['distribution'])} | {row['low_below_2657']} | "
            f"{row['wilson_upper_below_2657']} | {row['wilson_upper_below_2717']} | {row['wilson_upper_below_2757']} |"
        )
    return lines


def render_md(data: dict[str, Any]) -> str:
    lines = ['# Game2 Skeptic Eval Gate', '']
    lines.append('This report uses Wilson 95% upper bounds to avoid treating short high-score prefixes as stability evidence.')
    lines.append('The most useful floor check here is `<2657`, because `n518b` has min 2657 and is the current conservative floor.')
    lines.append('')
    lines.append('Interpretation: `U95 <2657 = 0.13` means the data still permits roughly a 13% low-tail probability at 95% confidence.')
    lines.append('')
    lines.append('## Base Labels')
    lines.extend(render_table(data['base_labels']))
    lines.append('')
    lines.append('## Run Labels')
    lines.extend(render_table(data['run_labels']))
    lines.append('')
    lines.append('## Critical Notes')
    lines.append('- `4/4` all-2757 still has a Wilson 95% upper bound near 49% for non-2757 outcomes, so it is not a stability result.')
    lines.append('- `16/16` all-clean still leaves a double-digit upper bound for a rare low tail; use it as a promotion screen, not as proof.')
    lines.append('- A candidate with high average but any `<2657` sample should stay experimental until the low-tail source is explained or deliberately accepted.')
    return '\n'.join(lines) + '\n'


def main() -> int:
    rows = mine_rows()
    data = {
        'base_labels': by_key(rows, 'base_label', min_n=5),
        'run_labels': by_key(rows, 'run_label', min_n=4),
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    OUT_MD.write_text(render_md(data), encoding='utf-8')
    print(json.dumps({'base_labels': len(data['base_labels']), 'run_labels': len(data['run_labels']), 'out_json': str(OUT_JSON), 'out_md': str(OUT_MD)}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
