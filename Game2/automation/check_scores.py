#!/usr/bin/env python3
"""Quick script to check all pending match scores."""
import json, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from saiblo_tools import api_request, resolve_token

token, _ = resolve_token('')

log_dir = os.path.join(os.path.dirname(__file__), 'logs')
for d in sorted(os.listdir(log_dir)):
    if not d.startswith('iteration_'):
        continue
    summary = os.path.join(log_dir, d, 'iteration_summary.json')
    if not os.path.exists(summary):
        continue
    with open(summary, encoding='utf-8') as f:
        s = json.load(f)
    iteration = s.get('iteration')
    version = s.get('version')
    for row in s.get('batch_overview', {}).get('rows', []):
        mid = row.get('my_match_id')
        if not mid:
            continue
        try:
            m = api_request('GET', f'/api/matches/{mid}/', token=token, timeout=10.0)
            for p in m.get('info', []):
                if p.get('user', {}).get('username') == 'theend':
                    score = p.get('score')
                    end = p.get('end_state')
                    exit_code = p.get('exit_code')
                    status = 'DONE' if end is not None else 'running...'
                    print(f"iter {iteration:2d} (ver{version:2d}): match {mid} score={score:5d} [{status}]")
        except Exception as e:
            print(f"iter {iteration:2d} (ver{version:2d}): match {mid} ERR: {str(e)[:60]}")
