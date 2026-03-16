#!/usr/bin/env python3
"""
Game2 iteration cycle orchestrator.
Usage:
  python run_cycle.py --source PATH_TO_AI.py --entity-name ENTITY [--top-k 2] [--timeout 600]
  python run_cycle.py --resume  # resume from state.json (e.g. poll pending batch)

Workflow:
1. Read state.json
2. If no pending work: upload source, wait compile, activate, create batch
3. If batch pending: poll batch
4. If batch done: download replays, analyze all matches, write comparison report
5. Update state.json with results
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
import traceback
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

TOOLS_DIR = ROOT / 'Game2' / 'tools'
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

from saiblo_tools import (
    resolve_token,
    require_token,
    get_profile,
    get_user_entities,
    create_entity,
    upload_entity_code,
    activate_code,
    get_entity_codes,
    fetch_ladders,
    api_request,
    api_download,
)
from analyze_match import analyze_match_payload, render_markdown as render_match_markdown
from compare_match_runs import load_run, render_markdown as render_compare_markdown
from summarize_versions import build_summary as build_version_summary, render_md as render_version_md

GAME_ID = 53
AUTO_DIR = Path(__file__).resolve().parent
STATE_PATH = AUTO_DIR / 'state.json'
LOGS_DIR = AUTO_DIR / 'logs'


# ---------------------------------------------------------------------------
# State persistence
# ---------------------------------------------------------------------------

def read_state() -> dict[str, Any]:
    if STATE_PATH.is_file():
        try:
            data = json.loads(STATE_PATH.read_text(encoding='utf-8'))
            if isinstance(data, dict):
                return data
        except Exception:
            pass
    return {
        'current_state': 'idle',
        'iteration': 0,
        'current_version': None,
        'current_code_id': None,
        'current_batch_id': None,
        'entity_name': 'g2auto',
        'history': [],
    }


def write_state(state: dict[str, Any]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding='utf-8')


def iteration_dir(iteration: int) -> Path:
    d = LOGS_DIR / f'iteration_{iteration}'
    d.mkdir(parents=True, exist_ok=True)
    return d


def log(msg: str) -> None:
    ts = time.strftime('%Y-%m-%d %H:%M:%S')
    print(f'[{ts}] {msg}', file=sys.stderr, flush=True)


# ---------------------------------------------------------------------------
# Step 1: Submit (upload, compile, activate)
# ---------------------------------------------------------------------------

def step_submit(
    state: dict[str, Any],
    source: Path,
    entity_name: str,
    token: str,
    poll_interval: float = 2.0,
    poll_max: int = 30,
) -> dict[str, Any]:
    """Upload source, wait for compilation, activate. Returns updated state."""
    log(f'Submitting {source} as entity={entity_name}')
    profile = get_profile(token)
    username = str(profile.get('user', {}).get('username', '')).strip()
    if not username:
        raise RuntimeError('cannot resolve username from profile')

    # Find or create entity
    entities_data = get_user_entities(username, GAME_ID, token)
    entities = entities_data.get('entities', []) if isinstance(entities_data, dict) else []
    entity = None
    for item in entities:
        if isinstance(item, dict) and str(item.get('name', '')).strip() == entity_name:
            entity = item
            break
    created = False
    if entity is None:
        log(f'Creating new entity: {entity_name}')
        entity = create_entity(username, GAME_ID, entity_name, 'python', token)
        created = True
    entity_id = int(entity.get('id', 0))

    # Upload
    uploaded = upload_entity_code(entity_id, source, f'auto iteration {state["iteration"]}', token)
    code_id = str(uploaded.get('id', '')).strip()
    version = uploaded.get('version')
    log(f'Uploaded code_id={code_id} version={version}')

    # Wait compile
    compile_status = ''
    for _ in range(max(1, poll_max)):
        codes = get_entity_codes(entity_id, token)
        current = {}
        for code in codes:
            if str(code.get('id', '')).strip() == code_id:
                current = code
                break
        compile_status = str(current.get('compile_status', '')).strip()
        if compile_status and compile_status not in ('未编译', '编译中', '等待中', 'Pending', 'Compiling', ''):
            break
        time.sleep(max(0.2, poll_interval))

    log(f'Compile status: {compile_status}')
    if compile_status != '编译成功':
        state['current_state'] = 'failed'
        state['error'] = f'Compilation failed: {compile_status}'
        write_state(state)
        raise RuntimeError(f'Compilation failed with status: {compile_status}')

    # Activate
    activate_code(entity_id, code_id, token)
    log('Code activated')

    # Save source copy
    it_dir = iteration_dir(state['iteration'])
    shutil.copy2(source, it_dir / source.name)
    write_json(it_dir / 'upload_info.json', {
        'username': username,
        'entity_name': entity_name,
        'entity_id': entity_id,
        'entity_created': created,
        'code_id': code_id,
        'version': version,
        'compile_status': compile_status,
        'source': str(source),
    })

    state['current_code_id'] = code_id
    state['current_version'] = version
    state['current_state'] = 'submitted'
    state['entity_name'] = entity_name
    state['_entity_id'] = entity_id
    state['_username'] = username
    write_state(state)
    return state


# ---------------------------------------------------------------------------
# Step 2: Create batch evaluation
# ---------------------------------------------------------------------------

def step_create_batch(
    state: dict[str, Any],
    token: str,
    top_k: int = 2,
    ladder_limit: int = 10,
) -> dict[str, Any]:
    """Create a batch against top-k ladder opponents. Returns updated state."""
    code_id = state['current_code_id']
    entity_name = state['entity_name']
    log(f'Creating batch for code_id={code_id} against top-{top_k}')

    # Resolve entity_id if not cached
    entity_id = state.get('_entity_id')
    if not entity_id:
        username = state.get('_username', '')
        if not username:
            profile = get_profile(token)
            username = str(profile.get('user', {}).get('username', '')).strip()
            state['_username'] = username
        entities_data = get_user_entities(username, GAME_ID, token)
        for item in (entities_data.get('entities', []) if isinstance(entities_data, dict) else []):
            if isinstance(item, dict) and str(item.get('name', '')).strip() == entity_name:
                entity_id = int(item.get('id', 0))
                state['_entity_id'] = entity_id
                break
        if not entity_id:
            raise RuntimeError(f'entity {entity_name!r} not found')

    # Pick opponents from ladder
    ladder = fetch_ladders(GAME_ID, ladder_limit, 0, token)
    results = ladder.get('results', []) if isinstance(ladder, dict) else []
    opponent_codes: list[str] = []
    my_code_clean = code_id.replace('-', '')
    for row in results:
        if not isinstance(row, dict):
            continue
        code = row.get('code', {}) if isinstance(row.get('code'), dict) else {}
        entity = code.get('entity', {}) if isinstance(code.get('entity'), dict) else {}
        cid = str(code.get('id', '')).strip().replace('-', '')
        if not cid or cid == my_code_clean:
            continue
        if int(entity.get('id', -1) or -1) == entity_id:
            continue
        opponent_codes.append(cid)
        if len(opponent_codes) >= top_k:
            break

    if not opponent_codes:
        raise RuntimeError('no opponent codes found from ladder')

    log(f'Opponents: {opponent_codes}')
    created = api_request('POST', '/api/batches/', token=token, payload={
        'game': GAME_ID,
        'code': code_id,
        'codes': opponent_codes,
    })
    batch_id = int(created.get('id', 0) or 0)
    log(f'Batch created: batch_id={batch_id}')

    it_dir = iteration_dir(state['iteration'])
    write_json(it_dir / 'batch_create.json', {
        'batch_id': batch_id,
        'my_code_id': code_id,
        'opponent_codes': opponent_codes,
    })

    state['current_batch_id'] = batch_id
    state['current_state'] = 'batch_created'
    state['_opponent_codes'] = opponent_codes
    write_state(state)
    return state


# ---------------------------------------------------------------------------
# Step 3: Poll batch until done
# ---------------------------------------------------------------------------

def step_poll_batch(
    state: dict[str, Any],
    token: str,
    timeout: float = 600.0,
    poll_interval: float = 3.0,
) -> dict[str, Any]:
    """Poll the batch until all matches are done or timeout. Returns updated state."""
    batch_id = state['current_batch_id']
    log(f'Polling batch_id={batch_id} (timeout={timeout}s)')
    state['current_state'] = 'batch_polling'
    write_state(state)

    deadline = time.time() + timeout
    batch_data: dict[str, Any] = {}
    network_errors = 0
    while True:
        try:
            batch_data = api_request('GET', f'/api/batches/{batch_id}/', token=token)
            network_errors = 0  # reset on success
        except Exception as exc:
            network_errors += 1
            log(f'Batch poll network error ({network_errors}): {exc}')
            if network_errors >= 5:
                raise  # give up after 5 consecutive network errors
            time.sleep(min(30, poll_interval * network_errors * 2))
            continue
        if not isinstance(batch_data, dict):
            batch_data = {}
        pending = 0
        for pair in batch_data.get('matches', []):
            if not isinstance(pair, list):
                continue
            for match in pair:
                if str(match.get('state', '')) in ('准备中', '评测中'):
                    pending += 1
        log(f'Batch {batch_id}: pending={pending}')
        if pending == 0:
            break
        if time.time() >= deadline:
            log(f'Batch polling timed out after {timeout}s with {pending} pending')
            break
        time.sleep(max(0.2, poll_interval))

    it_dir = iteration_dir(state['iteration'])
    write_json(it_dir / 'batch_result.json', batch_data)
    state['_batch_data'] = batch_data
    state['current_state'] = 'batch_done'
    write_state(state)
    return state


# ---------------------------------------------------------------------------
# Step 4: Analyze results
# ---------------------------------------------------------------------------

def _flatten_finished_match_ids(batch: dict[str, Any]) -> list[int]:
    out: list[int] = []
    for pair in batch.get('matches', []):
        if not isinstance(pair, list):
            continue
        for match in pair:
            if not isinstance(match, dict):
                continue
            if str(match.get('state', '')) in ('准备中', '评测中'):
                continue
            mid = int(match.get('id', 0) or 0)
            if mid:
                out.append(mid)
    return out


def _summarize_batch(batch: dict[str, Any], my_code_id: str) -> list[dict[str, Any]]:
    """Produce per-opponent summary rows from batch data."""
    rows: list[dict[str, Any]] = []
    for pair in batch.get('matches', []):
        if not isinstance(pair, list) or not pair:
            continue
        bucket: dict[str, Any] = {
            'opponent_code_id': None,
            'opponent_user': None,
            'opponent_entity': None,
            'my_match_id': None,
            'my_score': None,
            'opp_match_id': None,
            'opp_score': None,
            'games': [],
        }
        for match in pair:
            info = match.get('info', [])
            if not isinstance(info, list) or not info or not isinstance(info[0], dict):
                continue
            first = info[0]
            second = info[1] if len(info) > 1 and isinstance(info[1], dict) else None
            first_code = first.get('code', {}) if isinstance(first.get('code'), dict) else {}
            first_cid = str(first_code.get('id', '')).replace('-', '')
            non_my = second if first_cid == my_code_id.replace('-', '') else first
            if isinstance(non_my, dict) and bucket['opponent_code_id'] is None:
                code = non_my.get('code', {}) if isinstance(non_my.get('code'), dict) else {}
                user = non_my.get('user', {}) if isinstance(non_my.get('user'), dict) else {}
                entity = code.get('entity', {})
                bucket['opponent_code_id'] = code.get('id')
                bucket['opponent_user'] = user.get('username')
                bucket['opponent_entity'] = entity.get('name') if isinstance(entity, dict) else entity
            bucket['games'].append({
                'match_id': match.get('id'),
                'state': match.get('state'),
            })
            if first_cid == my_code_id.replace('-', ''):
                bucket['my_match_id'] = match.get('id')
                if str(match.get('state', '')) == '评测成功' and isinstance(first.get('score'), (int, float)):
                    bucket['my_score'] = first.get('score')
            else:
                bucket['opp_match_id'] = match.get('id')
                if str(match.get('state', '')) == '评测成功' and isinstance(first.get('score'), (int, float)):
                    bucket['opp_score'] = first.get('score')
        rows.append(bucket)
    return rows


def step_analyze(
    state: dict[str, Any],
    token: str,
) -> dict[str, Any]:
    """Download replays, analyze all matches, write reports. Returns updated state."""
    batch_data = state.get('_batch_data')
    if not batch_data:
        it_dir = iteration_dir(state['iteration'])
        batch_path = it_dir / 'batch_result.json'
        if batch_path.is_file():
            batch_data = json.loads(batch_path.read_text(encoding='utf-8'))
        else:
            raise RuntimeError('No batch data available for analysis')

    code_id = state['current_code_id']
    it_dir = iteration_dir(state['iteration'])
    matches_dir = it_dir / 'matches'
    matches_dir.mkdir(parents=True, exist_ok=True)

    log('Analyzing finished matches...')
    match_reports: list[dict[str, Any]] = []
    for match_id in _flatten_finished_match_ids(batch_data):
        log(f'  Analyzing match {match_id}')
        detail = api_request('GET', f'/api/matches/{match_id}/', token=token)
        trace: dict[str, Any] = {}
        download_error = ''
        try:
            body, _ = api_download(f'/api/matches/{match_id}/download/', token=token)
            text = body.decode('utf-8', errors='replace')
            loaded = json.loads(text) if text.strip() else {}
            trace = loaded if isinstance(loaded, dict) else {}
        except Exception as exc:
            download_error = f'{type(exc).__name__}: {exc}'

        analysis = analyze_match_payload(detail if isinstance(detail, dict) else {}, trace, download_error)
        match_dir = matches_dir / str(match_id)
        match_dir.mkdir(parents=True, exist_ok=True)
        write_json(match_dir / 'match_detail.json', detail)
        write_json(match_dir / 'match_download.json', trace)
        write_json(match_dir / 'analysis.json', analysis)
        (match_dir / 'analysis.md').write_text(render_match_markdown(analysis), encoding='utf-8')
        match_reports.append({
            'match_id': match_id,
            'dir': str(match_dir),
            'analysis': analysis,
        })

    # Build batch summary rows
    batch_rows = _summarize_batch(batch_data, code_id)

    # Build structured iteration summary
    iteration_summary = _build_iteration_summary(
        state=state,
        batch_data=batch_data,
        batch_rows=batch_rows,
        match_reports=match_reports,
    )

    # Try comparison with previous iteration
    prev_iteration = state['iteration'] - 1
    comparison: dict[str, Any] | None = None
    if prev_iteration >= 1:
        comparison = _compare_with_previous(state['iteration'], prev_iteration, it_dir)

    iteration_summary['comparison_with_previous'] = comparison

    write_json(it_dir / 'iteration_summary.json', iteration_summary)

    # Write human-readable report
    report_md = _render_iteration_report(iteration_summary)
    (it_dir / 'iteration_report.md').write_text(report_md, encoding='utf-8')

    log(f'Iteration {state["iteration"]} analysis complete -> {it_dir}')

    # Update history
    history_entry = {
        'iteration': state['iteration'],
        'code_id': code_id,
        'version': state.get('current_version'),
        'batch_id': state.get('current_batch_id'),
        'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'match_count': len(match_reports),
        'scores': {r['match_id']: _extract_my_score(r['analysis']) for r in match_reports},
        'dir': str(it_dir),
    }
    state.setdefault('history', []).append(history_entry)
    state['current_state'] = 'completed'
    # Clear transient keys
    for key in ('_batch_data', '_entity_id', '_username', '_opponent_codes'):
        state.pop(key, None)
    write_state(state)
    return state


def _extract_my_score(analysis: dict[str, Any]) -> int | None:
    for player in analysis.get('players', []):
        if not isinstance(player, dict):
            continue
        user = player.get('user', {}) if isinstance(player.get('user'), dict) else {}
        # Return first player's score (typically ours when we are player 0)
        score = player.get('score')
        if isinstance(score, (int, float)):
            return int(score)
    return None


def _build_iteration_summary(
    state: dict[str, Any],
    batch_data: dict[str, Any],
    batch_rows: list[dict[str, Any]],
    match_reports: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build a structured summary of the entire iteration."""
    cases_all: list[dict[str, Any]] = []
    question_patterns: list[str] = []

    for report in match_reports:
        analysis = report.get('analysis', {})
        for case in analysis.get('cases', []):
            if not isinstance(case, dict):
                continue
            case_entry: dict[str, Any] = {
                'match_id': report['match_id'],
                'case_id': case.get('case_id'),
                'step_count': case.get('step_count'),
                'final_stage': case.get('final_stage'),
                'final_result': case.get('final_result', {}),
                'final_answer': case.get('final_answer', ''),
                'npc_question_counts': case.get('npc_question_counts', {}),
                'evidence_submission_counts': case.get('evidence_submission_counts', {}),
            }
            # Score correctness per dimension
            result = case.get('final_result', {})
            if isinstance(result, dict):
                case_entry['correct_dimensions'] = {k: v for k, v in result.items() if v is True}
                case_entry['incorrect_dimensions'] = {k: v for k, v in result.items() if v is False}
                case_entry['total_correct'] = sum(1 for v in result.values() if v is True)
                case_entry['total_incorrect'] = sum(1 for v in result.values() if v is False)
            cases_all.append(case_entry)

            # Collect question patterns from first questions
            for q_info in case.get('first_questions', []):
                if isinstance(q_info, dict):
                    q = q_info.get('question', '')
                    if q and not q.startswith('提交最终答案:'):
                        question_patterns.append(q)

    # Aggregate my scores and opponent scores
    my_scores: list[int | float | None] = []
    opp_scores: list[int | float | None] = []
    for row in batch_rows:
        my_scores.append(row.get('my_score'))
        opp_scores.append(row.get('opp_score'))

    return {
        'iteration': state['iteration'],
        'code_id': state.get('current_code_id'),
        'version': state.get('current_version'),
        'batch_id': state.get('current_batch_id'),
        'entity_name': state.get('entity_name'),
        'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'batch_overview': {
            'opponent_count': len(batch_rows),
            'rows': batch_rows,
            'my_scores': my_scores,
            'opp_scores': opp_scores,
        },
        'cases': cases_all,
        'question_pattern_sample': question_patterns[:30],
        'match_reports_summary': [
            {
                'match_id': r['match_id'],
                'case_count': len(r['analysis'].get('cases', [])),
                'my_score': _extract_my_score(r['analysis']),
                'has_trace': r['analysis'].get('has_trace'),
                'error': r['analysis'].get('error'),
            }
            for r in match_reports
        ],
        'comparison_with_previous': None,  # filled later
    }


def _compare_with_previous(
    current_iter: int,
    prev_iter: int,
    current_dir: Path,
) -> dict[str, Any] | None:
    """Try to build a comparison between current and previous iteration."""
    prev_dir = LOGS_DIR / f'iteration_{prev_iter}'
    if not prev_dir.is_dir():
        return None

    prev_summary_path = prev_dir / 'iteration_summary.json'
    curr_summary_path = current_dir / 'iteration_summary.json'
    if not prev_summary_path.is_file() or not curr_summary_path.is_file():
        return None

    try:
        prev_summary = json.loads(prev_summary_path.read_text(encoding='utf-8'))
        curr_summary = json.loads(curr_summary_path.read_text(encoding='utf-8'))
    except Exception:
        return None

    prev_cases = prev_summary.get('cases', []) if isinstance(prev_summary, dict) else []
    curr_cases = curr_summary.get('cases', []) if isinstance(curr_summary, dict) else []

    return {
        'previous_iteration': prev_iter,
        'current_iteration': current_iter,
        'previous_code_id': prev_summary.get('code_id') if isinstance(prev_summary, dict) else None,
        'current_code_id': curr_summary.get('code_id') if isinstance(curr_summary, dict) else None,
        'previous_my_scores': (prev_summary.get('batch_overview', {}) or {}).get('my_scores', []),
        'current_my_scores': (curr_summary.get('batch_overview', {}) or {}).get('my_scores', []),
        'previous_case_count': len(prev_cases),
        'current_case_count': len(curr_cases),
        'previous_total_correct': sum(
            c.get('total_correct', 0) for c in prev_cases if isinstance(c, dict)
        ),
        'current_total_correct': sum(
            c.get('total_correct', 0) for c in curr_cases if isinstance(c, dict)
        ),
        'previous_total_incorrect': sum(
            c.get('total_incorrect', 0) for c in prev_cases if isinstance(c, dict)
        ),
        'current_total_incorrect': sum(
            c.get('total_incorrect', 0) for c in curr_cases if isinstance(c, dict)
        ),
    }


def _render_iteration_report(summary: dict[str, Any]) -> str:
    """Generate a markdown report from the iteration summary."""
    lines: list[str] = []
    lines.append(f'# Iteration {summary.get("iteration")} Report')
    lines.append('')
    lines.append(f'- code_id: `{summary.get("code_id")}`')
    lines.append(f'- version: `{summary.get("version")}`')
    lines.append(f'- batch_id: `{summary.get("batch_id")}`')
    lines.append(f'- entity: `{summary.get("entity_name")}`')
    lines.append(f'- timestamp: `{summary.get("timestamp")}`')
    lines.append('')

    # Batch overview
    overview = summary.get('batch_overview', {})
    lines.append('## Batch Overview')
    lines.append('')
    lines.append(f'- opponents: `{overview.get("opponent_count")}`')
    lines.append(f'- my_scores: `{overview.get("my_scores")}`')
    lines.append(f'- opp_scores: `{overview.get("opp_scores")}`')
    for row in overview.get('rows', []):
        if not isinstance(row, dict):
            continue
        lines.append(
            f'- vs `{row.get("opponent_user")}/{row.get("opponent_entity")}`: '
            f'my=`{row.get("my_score")}` opp=`{row.get("opp_score")}`'
        )
    lines.append('')

    # Match reports
    lines.append('## Match Reports')
    lines.append('')
    for mr in summary.get('match_reports_summary', []):
        lines.append(
            f'- match `{mr.get("match_id")}`: score=`{mr.get("my_score")}` '
            f'cases=`{mr.get("case_count")}` trace=`{mr.get("has_trace")}` '
            f'error=`{mr.get("error")}`'
        )
    lines.append('')

    # Per-case breakdown
    lines.append('## Case Breakdown')
    lines.append('')
    for case in summary.get('cases', []):
        if not isinstance(case, dict):
            continue
        lines.append(
            f'### Match {case.get("match_id")} / Case {case.get("case_id")}'
        )
        lines.append('')
        lines.append(f'- steps: `{case.get("step_count")}`')
        lines.append(f'- final_stage: `{case.get("final_stage")}`')
        correct = case.get('correct_dimensions', {})
        incorrect = case.get('incorrect_dimensions', {})
        total_c = case.get('total_correct', 0)
        total_i = case.get('total_incorrect', 0)
        lines.append(f'- correctness: `{total_c}` correct, `{total_i}` incorrect')
        if correct:
            lines.append(f'  - correct: `{list(correct.keys())}`')
        if incorrect:
            lines.append(f'  - incorrect: `{list(incorrect.keys())}`')
        answer = case.get('final_answer', '')
        if answer:
            lines.append(f'- final_answer: `{answer[:300]}`')
        npcs = case.get('npc_question_counts', {})
        if npcs:
            lines.append(f'- npc_visits: `{dict(list(npcs.items())[:8])}`')
        lines.append('')

    # Question patterns
    patterns = summary.get('question_pattern_sample', [])
    if patterns:
        lines.append('## Question Pattern Sample')
        lines.append('')
        for q in patterns[:15]:
            lines.append(f'- `{str(q)[:200]}`')
        lines.append('')

    # Comparison
    comp = summary.get('comparison_with_previous')
    if isinstance(comp, dict):
        lines.append('## Comparison with Previous Iteration')
        lines.append('')
        lines.append(f'- previous iteration: `{comp.get("previous_iteration")}`')
        lines.append(f'- previous scores: `{comp.get("previous_my_scores")}`')
        lines.append(f'- current scores: `{comp.get("current_my_scores")}`')
        lines.append(
            f'- correctness: `{comp.get("previous_total_correct")}` -> `{comp.get("current_total_correct")}` correct'
        )
        lines.append(
            f'- errors: `{comp.get("previous_total_incorrect")}` -> `{comp.get("current_total_incorrect")}` incorrect'
        )
        lines.append('')

    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

def run_cycle(
    source: Path | None,
    entity_name: str,
    top_k: int,
    timeout: float,
    poll_interval: float,
    resume: bool,
) -> int:
    token, _ = resolve_token('')
    token = require_token(token, 'game2-auto-cycle')

    state = read_state()
    current = state['current_state']
    log(f'State: {current}, iteration: {state["iteration"]}')

    try:
        if resume:
            # Resume from wherever we left off
            if current == 'idle':
                log('Nothing to resume (state=idle). Use --source to start a new cycle.')
                return 0
            elif current in ('submitted',):
                state = step_create_batch(state, token, top_k=top_k)
                current = state['current_state']
            if current in ('batch_created', 'batch_polling'):
                state = step_poll_batch(state, token, timeout=timeout, poll_interval=poll_interval)
                current = state['current_state']
            if current == 'batch_done':
                state = step_analyze(state, token)
                current = state['current_state']
            if current == 'completed':
                log(f'Iteration {state["iteration"]} completed.')
            elif current == 'failed':
                log(f'Iteration {state["iteration"]} failed: {state.get("error", "unknown")}')
                return 1
        else:
            # Full cycle from scratch
            if source is None:
                log('ERROR: --source is required when not resuming')
                return 1
            if not source.is_file():
                log(f'ERROR: source not found: {source}')
                return 1

            # Advance iteration if previous completed or idle
            if current in ('completed', 'idle'):
                state['iteration'] = state.get('iteration', 0) + 1
                state['current_state'] = 'idle'
                state['current_code_id'] = None
                state['current_batch_id'] = None
                state['current_version'] = None
                state.pop('error', None)
            elif current == 'failed':
                # Retry with same iteration number
                state['current_state'] = 'idle'
                state.pop('error', None)
            else:
                log(f'WARNING: State is {current}. Use --resume to continue or reset state.json.')
                return 1

            state['entity_name'] = entity_name
            write_state(state)

            # Step 1: Submit
            state = step_submit(state, source, entity_name, token)

            # Step 2: Create batch
            state = step_create_batch(state, token, top_k=top_k)

            # Step 3: Poll batch
            state = step_poll_batch(state, token, timeout=timeout, poll_interval=poll_interval)

            # Step 4: Analyze
            state = step_analyze(state, token)

            log(f'Iteration {state["iteration"]} completed successfully.')

    except Exception as exc:
        state['current_state'] = 'failed'
        state['error'] = f'{type(exc).__name__}: {exc}'
        write_state(state)
        log(f'FAILED: {exc}')
        traceback.print_exc(file=sys.stderr)
        return 1

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description='Game2 iteration cycle orchestrator')
    parser.add_argument('--source', type=str, default=None, help='Path to AI source file')
    parser.add_argument('--entity-name', type=str, default='g2auto', help='Entity name (default: g2auto)')
    parser.add_argument('--top-k', type=int, default=2, help='Number of top ladder opponents')
    parser.add_argument('--timeout', type=float, default=600.0, help='Batch polling timeout in seconds')
    parser.add_argument('--poll-interval', type=float, default=3.0, help='Polling interval in seconds')
    parser.add_argument('--resume', action='store_true', help='Resume from state.json')
    args = parser.parse_args()

    source = Path(args.source).resolve() if args.source else None
    return run_cycle(
        source=source,
        entity_name=args.entity_name,
        top_k=args.top_k,
        timeout=args.timeout,
        poll_interval=args.poll_interval,
        resume=args.resume,
    )


if __name__ == '__main__':
    raise SystemExit(main())
