#!/usr/bin/env python3
from __future__ import annotations

import argparse
import collections
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_AUDIT_JSON = ROOT / 'docs' / 'generated' / 'game2_skeptic_gap_mode_audit.json'
OUT_DIR = ROOT / 'Game2' / 'runtime' / 'skeptic_watch'


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Select residual-heavy labels from skeptic gap audit and optionally run recovery queue')
    parser.add_argument('--audit-json', default=str(DEFAULT_AUDIT_JSON))
    parser.add_argument('--label-prefix', default='n548')
    parser.add_argument('--min-residual', type=int, default=200)
    parser.add_argument('--min-samples', type=int, default=1)
    parser.add_argument('--top-k', type=int, default=3)
    parser.add_argument('--count', type=int, default=5, help='room-eval count passed to run_recovery_eval_queue')
    parser.add_argument('--timeout', type=float, default=420.0)
    parser.add_argument('--dry-run-queue', action='store_true')
    parser.add_argument('--run-queue', action='store_true')
    parser.add_argument('--out-json', default=str(OUT_DIR / 'residual_followup_plan.json'))
    return parser.parse_args()


def select_labels(data: dict[str, Any], prefix: str, min_residual: int, min_samples: int, top_k: int) -> tuple[list[str], list[dict[str, Any]]]:
    unresolved = data.get('unresolved_rows')
    rows = unresolved if isinstance(unresolved, list) else []
    grouped: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for row in rows:
        if not isinstance(row, dict):
            continue
        label = str(row.get('base_label') or '').strip()
        if not label.startswith(prefix):
            continue
        residual = row.get('residual_gap')
        if not isinstance(residual, int) or residual < min_residual:
            continue
        grouped[label].append(row)

    ranked: list[dict[str, Any]] = []
    for label, group in grouped.items():
        if len(group) < min_samples:
            continue
        residuals = [int(item['residual_gap']) for item in group if isinstance(item.get('residual_gap'), int)]
        gaps = [int(item['gap']) for item in group if isinstance(item.get('gap'), int)]
        scores = [int(item['score']) for item in group if isinstance(item.get('score'), int)]
        ranked.append(
            {
                'label': label,
                'samples': len(group),
                'residual_avg': round(sum(residuals) / len(residuals), 3) if residuals else None,
                'residual_max': max(residuals) if residuals else None,
                'gap_avg': round(sum(gaps) / len(gaps), 3) if gaps else None,
                'score_min': min(scores) if scores else None,
                'score_max': max(scores) if scores else None,
                'examples': [
                    {
                        'match_id': str(item.get('match_id')),
                        'score': item.get('score'),
                        'residual_gap': item.get('residual_gap'),
                        'mode': item.get('mode'),
                    }
                    for item in sorted(group, key=lambda x: int(x.get('residual_gap', 0)), reverse=True)[:5]
                ],
            }
        )
    ranked.sort(key=lambda item: (int(item.get('residual_max') or 0), int(item.get('samples') or 0), item['label']), reverse=True)
    labels = [item['label'] for item in ranked[: max(0, int(top_k))]]
    return labels, ranked


def run_queue(labels: list[str], args: argparse.Namespace) -> dict[str, Any]:
    if not labels:
        return {'ran': False, 'reason': 'no-labels'}
    cmd = [
        'python3',
        'Game2/tools/run_recovery_eval_queue.py',
        '--labels',
        *labels,
        '--count',
        str(args.count),
        '--timeout',
        str(args.timeout),
        '--continue-on-error',
        '--allow-partial-eval',
    ]
    if args.dry_run_queue:
        cmd.append('--dry-run')
    completed = subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True, check=False)
    return {
        'ran': True,
        'ok': completed.returncode == 0,
        'returncode': int(completed.returncode),
        'command': ' '.join(cmd),
        'stdout': completed.stdout[-4000:],
        'stderr': completed.stderr[-4000:],
    }


def main() -> int:
    args = parse_args()
    data = load_json(Path(args.audit_json).resolve())
    labels, ranked = select_labels(data, args.label_prefix, args.min_residual, args.min_samples, args.top_k)
    out = {
        'audit_json': str(Path(args.audit_json).resolve()),
        'label_prefix': args.label_prefix,
        'min_residual': int(args.min_residual),
        'min_samples': int(args.min_samples),
        'top_k': int(args.top_k),
        'selected_labels': labels,
        'ranked_labels': ranked,
    }

    queue = {'ran': False}
    if args.run_queue:
        queue = run_queue(labels, args)
    out['queue'] = queue

    write_json(Path(args.out_json).resolve(), out)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if queue.get('ok', True) else 1


if __name__ == '__main__':
    raise SystemExit(main())
