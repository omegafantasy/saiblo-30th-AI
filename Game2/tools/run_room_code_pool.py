#!/usr/bin/env python3
from __future__ import annotations

import argparse
import collections
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
OUT_ROOT = ROOT / 'Game2' / 'runtime' / 'room_code_pool'


def utc_stamp() -> str:
    return time.strftime('%Y%m%d_%H%M%S', time.gmtime())


def safe_name(value: str) -> str:
    raw = str(value or '').strip()
    safe = ''.join(ch if ch.isalnum() or ch in ('-', '_') else '_' for ch in raw)
    return safe[:80] or 'candidate'


def log(message: str) -> None:
    print(f'[room-pool] {message}', file=sys.stderr, flush=True)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def parse_candidate(value: str) -> dict[str, str]:
    if '=' not in value:
        raise argparse.ArgumentTypeError('candidate must be label=code_id')
    label, code_id = value.split('=', 1)
    label = safe_name(label)
    code_id = code_id.replace('-', '').strip().lower()
    if not label or not code_id:
        raise argparse.ArgumentTypeError('candidate must be label=code_id')
    return {'label': label, 'code_id': code_id}


def load_candidates(args: argparse.Namespace) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for item in args.candidate or []:
        rows.append(item)
    if args.candidates_json:
        data = json.loads(Path(args.candidates_json).read_text(encoding='utf-8'))
        if not isinstance(data, list):
            raise RuntimeError('--candidates-json must contain a list')
        for item in data:
            if not isinstance(item, dict):
                continue
            label = safe_name(str(item.get('label') or item.get('name') or item.get('entity') or ''))
            code_id = str(item.get('code_id') or item.get('code') or '').replace('-', '').strip().lower()
            if label and code_id:
                rows.append({'label': label, 'code_id': code_id})
    deduped: list[dict[str, str]] = []
    seen: set[str] = set()
    for row in rows:
        key = row['code_id']
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    if not deduped:
        raise RuntimeError('no candidates')
    return deduped


def parse_stdout_summary(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding='utf-8', errors='replace').strip()
    if not text:
        return {}
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return {'stdout_tail': text[-2000:]}
    return data if isinstance(data, dict) else {}


def row_from_summary(summary: dict[str, Any]) -> dict[str, Any]:
    rows = summary.get('rows')
    row = rows[0] if isinstance(rows, list) and rows and isinstance(rows[0], dict) else {}
    return {
        'room_id': row.get('room_id'),
        'match_id': row.get('match_id'),
        'state': row.get('state'),
        'score': row.get('score'),
        'end_state': row.get('end_state'),
        'error': row.get('error'),
        'out_dir': (summary.get('meta') or {}).get('out_dir') if isinstance(summary.get('meta'), dict) else None,
    }


def summarize(candidates: list[dict[str, Any]], results: list[dict[str, Any]]) -> dict[str, Any]:
    by_label: dict[str, dict[str, Any]] = {}
    for cand in candidates:
        by_label[cand['label']] = {
            'label': cand['label'],
            'code_id': cand['code_id'],
            'attempts': 0,
            'valid': 0,
            'failures': 0,
            'scores': [],
            'states': {},
        }
    for result in results:
        item = by_label.setdefault(
            result['label'],
            {
                'label': result['label'],
                'code_id': result['code_id'],
                'attempts': 0,
                'valid': 0,
                'failures': 0,
                'scores': [],
                'states': {},
            },
        )
        item['attempts'] += 1
        state_key = str(result.get('end_state') or result.get('state') or result.get('error') or 'unknown')
        item['states'][state_key] = int(item['states'].get(state_key, 0)) + 1
        score = result.get('score')
        if result.get('end_state') == 'OK' and isinstance(score, int) and score > 0:
            item['valid'] += 1
            item['scores'].append(score)
        else:
            item['failures'] += 1
    rows: list[dict[str, Any]] = []
    for item in by_label.values():
        scores = item.pop('scores')
        counter = dict(sorted(collections.Counter(scores).items()))
        avg = sum(scores) / len(scores) if scores else None
        rows.append(
            {
                **item,
                'avg': round(avg, 3) if avg is not None else None,
                'min': min(scores) if scores else None,
                'max': max(scores) if scores else None,
                'distribution': counter,
            }
        )
    rows.sort(key=lambda row: (row['avg'] if row['avg'] is not None else -1, row['valid'], row['max'] or -1), reverse=True)
    return {'rows': rows, 'results': results}


def render_md(summary: dict[str, Any]) -> str:
    lines = ['# Game2 Room Code Pool', '']
    lines.append('Only direct single-player room evals are included. Valid samples require `end_state=OK` and `score>0`.')
    lines.append('')
    lines.append('| label | valid | attempts | avg | min | max | distribution | states | code_id |')
    lines.append('| --- | ---: | ---: | ---: | ---: | ---: | --- | --- | --- |')
    for row in summary.get('rows', []):
        dist = ', '.join(f'{score} x{count}' for score, count in row.get('distribution', {}).items())
        states = ', '.join(f'{state} x{count}' for state, count in sorted(row.get('states', {}).items()))
        lines.append(
            f"| `{row.get('label')}` | {row.get('valid')} | {row.get('attempts')} | "
            f"{row.get('avg') if row.get('avg') is not None else ''} | "
            f"{row.get('min') if row.get('min') is not None else ''} | "
            f"{row.get('max') if row.get('max') is not None else ''} | "
            f"{dist} | {states} | `{row.get('code_id')}` |"
        )
    return '\n'.join(lines) + '\n'


def main() -> int:
    parser = argparse.ArgumentParser(description='Evaluate existing Game53 code ids with bounded direct room concurrency')
    parser.add_argument('--candidate', action='append', type=parse_candidate, default=[], help='label=code_id; may be repeated')
    parser.add_argument('--candidates-json', default='')
    parser.add_argument('--target-valid', type=int, default=4)
    parser.add_argument('--max-attempts', type=int, default=8)
    parser.add_argument('--jobs', type=int, default=4)
    parser.add_argument('--timeout', type=float, default=900.0)
    parser.add_argument('--poll-interval', type=float, default=30.0)
    parser.add_argument('--request-timeout', type=float, default=180.0)
    parser.add_argument('--label-prefix', default='pool')
    parser.add_argument('--launch-delay', type=float, default=1.0)
    parser.add_argument('--poll-processes', type=float, default=5.0)
    parser.add_argument('--out-dir', default='')
    args = parser.parse_args()

    candidates = load_candidates(args)
    target_valid = max(1, int(args.target_valid))
    max_attempts = max(target_valid, int(args.max_attempts))
    jobs = max(1, int(args.jobs))
    out_dir = Path(args.out_dir) if args.out_dir else OUT_ROOT / f'{utc_stamp()}_{safe_name(args.label_prefix)}'
    out_dir.mkdir(parents=True, exist_ok=True)

    attempts: dict[str, int] = {cand['label']: 0 for cand in candidates}
    valid: dict[str, int] = {cand['label']: 0 for cand in candidates}
    results: list[dict[str, Any]] = []
    active: list[dict[str, Any]] = []
    cursor = 0

    def persist() -> None:
        summary = summarize(candidates, results)
        summary['meta'] = {
            'target_valid': target_valid,
            'max_attempts': max_attempts,
            'jobs': jobs,
            'out_dir': str(out_dir),
        }
        write_json(out_dir / 'summary.json', summary)
        (out_dir / 'summary.md').write_text(render_md(summary), encoding='utf-8')

    def candidate_done(cand: dict[str, str]) -> bool:
        label = cand['label']
        return valid[label] >= target_valid or attempts[label] >= max_attempts

    while True:
        still_active: list[dict[str, Any]] = []
        for item in active:
            proc: subprocess.Popen[str] = item['proc']
            rc = proc.poll()
            if rc is None:
                still_active.append(item)
                continue
            item['stdout'].close()
            item['stderr'].close()
            summary = parse_stdout_summary(item['stdout_path'])
            row = row_from_summary(summary)
            result = {
                'label': item['label'],
                'code_id': item['code_id'],
                'attempt': item['attempt'],
                'returncode': rc,
                'stdout_path': str(item['stdout_path']),
                'stderr_path': str(item['stderr_path']),
                **row,
            }
            score = result.get('score')
            if result.get('end_state') == 'OK' and isinstance(score, int) and score > 0:
                valid[item['label']] += 1
            results.append(result)
            log(
                f"{item['label']} attempt {item['attempt']} rc={rc} "
                f"state={result.get('state')} end={result.get('end_state')} score={result.get('score')}"
            )
            persist()
        active = still_active

        if all(candidate_done(cand) for cand in candidates) and not active:
            break

        active_labels = {item['label'] for item in active}
        launches = 0
        while len(active) < jobs and launches < len(candidates):
            cand = candidates[cursor % len(candidates)]
            cursor += 1
            launches += 1
            label = cand['label']
            if label in active_labels or candidate_done(cand):
                continue
            attempts[label] += 1
            attempt = attempts[label]
            run_label = safe_name(f'{args.label_prefix}_{label}_a{attempt}')
            stdout_path = out_dir / f'{run_label}.out'
            stderr_path = out_dir / f'{run_label}.err'
            stdout = stdout_path.open('w', encoding='utf-8')
            stderr = stderr_path.open('w', encoding='utf-8')
            cmd = [
                'python3',
                'Game2/tools/run_room_eval.py',
                '--code-id',
                cand['code_id'],
                '--label',
                run_label,
                '--count',
                '1',
                '--timeout',
                str(args.timeout),
                '--poll-interval',
                str(args.poll_interval),
                '--request-timeout',
                str(args.request_timeout),
            ]
            proc = subprocess.Popen(cmd, cwd=str(ROOT), text=True, stdout=stdout, stderr=stderr)
            active.append(
                {
                    'label': label,
                    'code_id': cand['code_id'],
                    'attempt': attempt,
                    'proc': proc,
                    'stdout': stdout,
                    'stderr': stderr,
                    'stdout_path': stdout_path,
                    'stderr_path': stderr_path,
                }
            )
            active_labels.add(label)
            log(f'started {label} attempt {attempt} pid={proc.pid}')
            time.sleep(max(0.0, float(args.launch_delay)))

        if active:
            time.sleep(max(0.5, float(args.poll_processes)))

    persist()
    print(json.dumps(json.loads((out_dir / 'summary.json').read_text(encoding='utf-8')), ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
