#!/usr/bin/env python3
from __future__ import annotations

import argparse
import collections
import json
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SESSION_ROOT = Path('/root/.codex/sessions')
DEFAULT_ROOM_DIR = ROOT / 'Game2' / 'runtime' / 'room_matches'
DEFAULT_CANDIDATE_DIR = ROOT / 'Game2' / 'deepclue_ai'
DEFAULT_RUNTIME_DIR = ROOT / 'Game2' / 'runtime' / 'skeptic_watch'
DEFAULT_STATE_JSON = DEFAULT_RUNTIME_DIR / 'state.json'
DEFAULT_STATUS_JSON = DEFAULT_RUNTIME_DIR / 'status.json'
DEFAULT_HISTORY_JSONL = DEFAULT_RUNTIME_DIR / 'history.jsonl'
DEFAULT_LOG_FILE = DEFAULT_RUNTIME_DIR / 'watch.log'

LABEL_RE = re.compile(r'(?<![0-9A-Za-z])n\d{3,}[a-z](?![0-9A-Za-z])')
ROOM_LABEL_RE = re.compile(r'(?<![0-9A-Za-z])n\d{3,}[a-z](?=_room(?:$|[^0-9A-Za-z]))')
ACTION_TRIGGER_SET = {'always', 'on_change', 'on_new_label', 'on_low_score', 'on_upload_signal'}


def utc_now() -> str:
    return time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())


def utc_ts() -> str:
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def compact(text: Any, limit: int = 220) -> str:
    value = re.sub(r'\s+', ' ', str(text or '')).strip()
    if len(value) <= limit:
        return value
    return value[: max(0, limit - 3)] + '...'


def log_line(path: Path, message: str) -> None:
    line = f'[{utc_now()}] {message}'
    print(line, flush=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a', encoding='utf-8') as handle:
        handle.write(line + '\n')


def read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a', encoding='utf-8') as handle:
        handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + '\n')


def default_state() -> dict[str, Any]:
    return {
        'version': 1,
        'created_at': utc_ts(),
        'session_offsets': {},
        'session_file_meta': {},
        'analysis_mtime': {},
        'room_dir_mtime': {},
        'candidate_dir_mtime': {},
        'seen_labels': [],
        'label_max_score': {},
        'label_min_score': {},
        'action_last_epoch': {},
    }


def normalize_state(raw: dict[str, Any]) -> dict[str, Any]:
    state = default_state()
    if not raw:
        return state
    for key in state:
        value = raw.get(key)
        if isinstance(state[key], dict) and isinstance(value, dict):
            state[key] = value
        elif isinstance(state[key], list) and isinstance(value, list):
            state[key] = value
        elif not isinstance(state[key], (dict, list)) and value is not None:
            state[key] = value
    return state


def parse_room_label(room_dir_name: str) -> str:
    base = room_dir_name.rsplit('_room', 1)[0]
    return base.split('_', 2)[-1]


def list_session_files(session_root: Path, session_glob: str, max_age_hours: float) -> list[Path]:
    if not session_root.is_dir():
        return []
    now = time.time()
    max_age_sec = max(0.0, float(max_age_hours)) * 3600.0
    rows: list[tuple[float, str, Path]] = []
    for path in session_root.glob(session_glob):
        if not path.is_file():
            continue
        try:
            st = path.stat()
        except OSError:
            continue
        if max_age_sec > 0 and (now - st.st_mtime) > max_age_sec:
            continue
        rows.append((float(st.st_mtime), str(path), path))
    rows.sort(key=lambda item: (item[0], item[1]))
    return [item[2] for item in rows]


def list_room_dirs(room_dir: Path) -> list[Path]:
    if not room_dir.is_dir():
        return []
    rows: list[tuple[float, str, Path]] = []
    for path in room_dir.iterdir():
        if not path.is_dir():
            continue
        try:
            st = path.stat()
        except OSError:
            continue
        rows.append((float(st.st_mtime), path.name, path))
    rows.sort(key=lambda item: (item[0], item[1]))
    return [item[2] for item in rows]


def list_candidate_dirs(candidate_dir: Path) -> list[Path]:
    if not candidate_dir.is_dir():
        return []
    rows: list[tuple[float, str, Path]] = []
    for path in candidate_dir.iterdir():
        if not path.is_dir():
            continue
        if not LABEL_RE.search(path.name):
            continue
        try:
            st = path.stat()
        except OSError:
            continue
        rows.append((float(st.st_mtime), path.name, path))
    rows.sort(key=lambda item: (item[0], item[1]))
    return [item[2] for item in rows]


def list_analysis_files(room_dir: Path) -> list[Path]:
    if not room_dir.is_dir():
        return []
    rows: list[tuple[float, str, Path]] = []
    for path in room_dir.glob('*/matches/*/analysis.json'):
        if not path.is_file():
            continue
        try:
            st = path.stat()
        except OSError:
            continue
        rows.append((float(st.st_mtime), str(path), path))
    rows.sort(key=lambda item: (item[0], item[1]))
    return [item[2] for item in rows]


def bootstrap_tail_state(state: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    session_files = list_session_files(Path(args.session_root), args.session_glob, args.session_max_age_hours)
    for path in session_files:
        key = str(path)
        try:
            st = path.stat()
        except OSError:
            continue
        state['session_offsets'][key] = int(st.st_size)
        state['session_file_meta'][key] = {'inode': int(st.st_ino), 'size': int(st.st_size)}

    labels: set[str] = set(state.get('seen_labels', []))
    for room_path in list_room_dirs(Path(args.room_dir)):
        key = str(room_path)
        try:
            st = room_path.stat()
        except OSError:
            continue
        state['room_dir_mtime'][key] = float(st.st_mtime)
        labels.update(LABEL_RE.findall(room_path.name))

    for analysis_path in list_analysis_files(Path(args.room_dir)):
        key = str(analysis_path)
        try:
            st = analysis_path.stat()
        except OSError:
            continue
        state['analysis_mtime'][key] = float(st.st_mtime)
    for candidate_path in list_candidate_dirs(Path(args.candidate_dir)):
        key = str(candidate_path)
        try:
            st = candidate_path.stat()
        except OSError:
            continue
        state['candidate_dir_mtime'][key] = float(st.st_mtime)
        labels.update(LABEL_RE.findall(candidate_path.name))
    state['seen_labels'] = sorted(labels)
    return {
        'session_file_count': len(session_files),
        'room_dir_count': len(state['room_dir_mtime']),
        'candidate_dir_count': len(state['candidate_dir_mtime']),
        'analysis_file_count': len(state['analysis_mtime']),
        'known_labels': len(state['seen_labels']),
    }


def parse_exec_command(payload: dict[str, Any]) -> str:
    if str(payload.get('name') or '') != 'exec_command':
        return ''
    args_raw = payload.get('arguments')
    if not isinstance(args_raw, str):
        return ''
    try:
        args_obj = json.loads(args_raw)
    except Exception:
        return compact(args_raw, 200)
    if not isinstance(args_obj, dict):
        return compact(args_raw, 200)
    cmd = str(args_obj.get('cmd') or '').strip()
    return compact(cmd, 220)


def extract_text(payload: dict[str, Any]) -> str:
    payload_type = str(payload.get('type') or '')
    if payload_type == 'message':
        items = payload.get('content')
        if isinstance(items, list):
            texts = [str(item.get('text') or '') for item in items if isinstance(item, dict)]
            return '\n'.join(texts)
    if payload_type == 'agent_message':
        return str(payload.get('message') or '')
    if payload_type == 'task_complete':
        return str(payload.get('last_agent_message') or '')
    return ''


def scan_sessions(state: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    files = list_session_files(Path(args.session_root), args.session_glob, args.session_max_age_hours)
    event_types: collections.Counter[str] = collections.Counter()
    payload_types: collections.Counter[str] = collections.Counter()
    phase_counts: collections.Counter[str] = collections.Counter()
    labels: set[str] = set()
    room_labels: set[str] = set()
    recent_commands: list[str] = []
    recent_messages: list[str] = []
    updated_files: list[str] = []
    parse_error_count = 0
    new_line_count = 0
    upload_signal_count = 0
    last_timestamp = ''

    old_offsets = state.get('session_offsets', {})
    old_meta = state.get('session_file_meta', {})
    offsets: dict[str, int] = {}
    meta: dict[str, dict[str, int]] = {}

    for path in files:
        key = str(path)
        try:
            st = path.stat()
        except OSError:
            continue
        inode = int(st.st_ino)
        size = int(st.st_size)
        prev_offset = int(old_offsets.get(key, 0))
        prev_meta = old_meta.get(key) if isinstance(old_meta.get(key), dict) else {}
        prev_inode = int(prev_meta.get('inode', inode))
        if prev_inode != inode or size < prev_offset:
            prev_offset = 0
        if prev_offset < size:
            updated_files.append(key)
            with path.open('r', encoding='utf-8', errors='replace') as handle:
                handle.seek(prev_offset)
                for raw in handle:
                    new_line_count += 1
                    scan_text = raw
                    if len(scan_text) > int(args.max_line_scan_chars):
                        scan_text = scan_text[: int(args.max_line_scan_chars)]
                    labels.update(LABEL_RE.findall(scan_text))
                    room_labels.update(ROOM_LABEL_RE.findall(scan_text))
                    if any(
                        token in scan_text
                        for token in ('upload-ai', 'submit_and_track.py', 'run_recovery_eval_queue.py', 'activate-code', '--activate')
                    ):
                        upload_signal_count += 1
                    try:
                        row = json.loads(raw)
                    except Exception:
                        parse_error_count += 1
                        continue
                    if not isinstance(row, dict):
                        continue
                    timestamp = str(row.get('timestamp') or '')
                    if timestamp:
                        last_timestamp = timestamp
                    row_type = str(row.get('type') or '')
                    event_types[row_type] += 1
                    payload = row.get('payload')
                    if not isinstance(payload, dict):
                        continue
                    payload_type = str(payload.get('type') or '')
                    if payload_type:
                        payload_types[payload_type] += 1
                    phase = str(payload.get('phase') or '')
                    if phase:
                        phase_counts[phase] += 1

                    cmd = parse_exec_command(payload)
                    if cmd and cmd not in recent_commands:
                        recent_commands.append(cmd)
                        if len(recent_commands) > int(args.recent_command_limit):
                            recent_commands.pop(0)

                    if payload_type in {'agent_message', 'message', 'task_complete'}:
                        text = extract_text(payload)
                        if text:
                            recent_messages.append(compact(text, 240))
                            if len(recent_messages) > 8:
                                recent_messages.pop(0)

            offsets[key] = size
        else:
            offsets[key] = prev_offset
        meta[key] = {'inode': inode, 'size': size}

    state['session_offsets'] = offsets
    state['session_file_meta'] = meta
    return {
        'file_count': len(files),
        'updated_file_count': len(updated_files),
        'updated_files': updated_files[-12:],
        'new_line_count': new_line_count,
        'parse_error_count': parse_error_count,
        'event_types': dict(event_types),
        'payload_types': dict(payload_types),
        'phase_counts': dict(phase_counts),
        'labels': sorted(labels),
        'room_labels': sorted(room_labels),
        'recent_commands': recent_commands,
        'recent_messages': recent_messages,
        'upload_signal_count': upload_signal_count,
        'last_timestamp': last_timestamp,
    }


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return None


def analysis_row(path: Path) -> dict[str, Any] | None:
    data = load_json(path)
    if not isinstance(data, dict):
        return None
    players = data.get('players')
    first = players[0] if isinstance(players, list) and players and isinstance(players[0], dict) else {}
    score = first.get('score')
    score_int = score if isinstance(score, int) else None
    end_state = str(first.get('end_state') or '')
    room_dir_name = path.parents[2].name
    label = parse_room_label(room_dir_name)
    match_id = str(data.get('match_id') or path.parent.name)
    return {
        'label': label,
        'room_dir': room_dir_name,
        'match_id': match_id,
        'score': score_int,
        'end_state': end_state,
        'path': str(path.relative_to(ROOT)),
    }


def scan_room_matches(state: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    room_dir = Path(args.room_dir)
    labels: set[str] = set()
    new_room_dirs: list[str] = []
    changed_room_dirs: list[str] = []
    room_dirs = list_room_dirs(room_dir)
    old_room_dir_mtime = state.get('room_dir_mtime', {})
    new_room_dir_mtime: dict[str, float] = {}

    for path in room_dirs:
        key = str(path)
        try:
            st = path.stat()
        except OSError:
            continue
        mtime = float(st.st_mtime)
        new_room_dir_mtime[key] = mtime
        labels.update(LABEL_RE.findall(path.name))
        old_mtime = old_room_dir_mtime.get(key)
        if old_mtime is None:
            new_room_dirs.append(path.name)
        elif mtime > float(old_mtime):
            changed_room_dirs.append(path.name)
    state['room_dir_mtime'] = new_room_dir_mtime

    old_analysis_mtime = state.get('analysis_mtime', {})
    new_analysis_mtime: dict[str, float] = {}
    new_rows: list[dict[str, Any]] = []
    updated_rows: list[dict[str, Any]] = []
    parse_error_count = 0
    low_scores: list[dict[str, Any]] = []
    score_drops: list[dict[str, Any]] = []
    score_counter: collections.Counter[int] = collections.Counter()
    label_counter: collections.Counter[str] = collections.Counter()

    label_max = state.get('label_max_score', {})
    label_min = state.get('label_min_score', {})

    for path in list_analysis_files(room_dir):
        key = str(path)
        try:
            st = path.stat()
        except OSError:
            continue
        mtime = float(st.st_mtime)
        new_analysis_mtime[key] = mtime
        old_mtime = old_analysis_mtime.get(key)
        if old_mtime is not None and mtime <= float(old_mtime):
            continue
        row = analysis_row(path)
        if row is None:
            parse_error_count += 1
            continue
        labels.add(str(row.get('label') or ''))
        score = row.get('score')
        if isinstance(score, int):
            score_counter[score] += 1
            label_counter[str(row['label'])] += 1
            prev_max = label_max.get(str(row['label']))
            if isinstance(prev_max, int) and score <= prev_max - int(args.drop_gap):
                score_drops.append(
                    {
                        'label': row['label'],
                        'match_id': row['match_id'],
                        'score': score,
                        'prev_max': prev_max,
                        'gap': prev_max - score,
                        'path': row['path'],
                    }
                )
            label_max[str(row['label'])] = max(score, int(prev_max)) if isinstance(prev_max, int) else score
            prev_min = label_min.get(str(row['label']))
            label_min[str(row['label'])] = min(score, int(prev_min)) if isinstance(prev_min, int) else score
        if isinstance(score, int) and row.get('end_state') == 'OK' and score > 0 and score < int(args.low_score_threshold):
            low_scores.append(
                {
                    'label': row['label'],
                    'match_id': row['match_id'],
                    'score': score,
                    'path': row['path'],
                }
            )
        if old_mtime is None:
            new_rows.append(row)
        else:
            updated_rows.append(row)

    state['analysis_mtime'] = new_analysis_mtime
    state['label_max_score'] = label_max
    state['label_min_score'] = label_min

    low_scores.sort(key=lambda item: (int(item['score']), str(item['label']), str(item['match_id'])))
    score_drops.sort(key=lambda item: (int(item['gap']), int(item['score'])), reverse=True)
    return {
        'room_dir_count': len(room_dirs),
        'new_room_dir_count': len(new_room_dirs),
        'new_room_dirs': new_room_dirs[-20:],
        'changed_room_dirs': changed_room_dirs[-20:],
        'analysis_file_count': len(new_analysis_mtime),
        'new_match_count': len(new_rows),
        'updated_match_count': len(updated_rows),
        'new_rows': new_rows[-60:],
        'updated_rows': updated_rows[-30:],
        'score_distribution_new_or_updated': dict(sorted(score_counter.items())),
        'label_distribution_new_or_updated': dict(sorted(label_counter.items())),
        'low_score_count': len(low_scores),
        'low_scores': low_scores[:60],
        'score_drop_count': len(score_drops),
        'score_drops': score_drops[:40],
        'parse_error_count': parse_error_count,
        'labels': sorted(label for label in labels if label),
    }


def scan_candidate_dirs(state: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    labels: set[str] = set()
    new_candidate_dirs: list[str] = []
    changed_candidate_dirs: list[str] = []
    old_candidate_mtime = state.get('candidate_dir_mtime', {})
    new_candidate_mtime: dict[str, float] = {}
    for path in list_candidate_dirs(Path(args.candidate_dir)):
        key = str(path)
        try:
            st = path.stat()
        except OSError:
            continue
        mtime = float(st.st_mtime)
        new_candidate_mtime[key] = mtime
        labels.update(LABEL_RE.findall(path.name))
        old_mtime = old_candidate_mtime.get(key)
        if old_mtime is None:
            new_candidate_dirs.append(path.name)
        elif mtime > float(old_mtime):
            changed_candidate_dirs.append(path.name)
    state['candidate_dir_mtime'] = new_candidate_mtime
    return {
        'candidate_dir_count': len(new_candidate_mtime),
        'new_candidate_dir_count': len(new_candidate_dirs),
        'new_candidate_dirs': new_candidate_dirs[-40:],
        'changed_candidate_dirs': changed_candidate_dirs[-40:],
        'labels': sorted(label for label in labels if label),
    }


def run_cmd(cmd: list[str], cwd: Path, timeout_sec: float) -> dict[str, Any]:
    started = time.time()
    try:
        completed = subprocess.run(cmd, cwd=str(cwd), text=True, capture_output=True, timeout=max(5.0, float(timeout_sec)), check=False)
        stdout = completed.stdout.strip()
        stderr = completed.stderr.strip()
        parsed = None
        if stdout:
            try:
                parsed_obj = json.loads(stdout)
                if isinstance(parsed_obj, dict):
                    parsed = parsed_obj
            except Exception:
                parsed = None
        return {
            'ok': completed.returncode == 0,
            'returncode': int(completed.returncode),
            'duration_sec': round(time.time() - started, 3),
            'stdout': compact(stdout, 600),
            'stderr': compact(stderr, 600),
            'parsed': parsed,
        }
    except subprocess.TimeoutExpired:
        return {
            'ok': False,
            'returncode': 124,
            'duration_sec': round(time.time() - started, 3),
            'stdout': '',
            'stderr': f'timeout after {timeout_sec}s',
            'parsed': None,
        }


def run_skeptic_tools(args: argparse.Namespace) -> dict[str, Any]:
    room_res = run_cmd(['python3', 'Game2/tools/skeptic_room_feature_mine.py'], ROOT, args.tool_timeout)
    gate_res = run_cmd(['python3', 'Game2/tools/skeptic_eval_gate.py'], ROOT, args.tool_timeout)
    gap_res = run_cmd(['python3', 'Game2/tools/skeptic_gap_mode_audit.py'], ROOT, args.tool_timeout)
    trace_res = run_cmd(['python3', 'Game2/tools/skeptic_residual_trace_diff.py'], ROOT, args.tool_timeout)
    ident_n548_res = run_cmd(
        [
            'python3',
            'Game2/tools/skeptic_identity_factor_audit.py',
            '--label-prefix',
            'n548',
            '--target-residual',
            '200',
            '--target-mode',
            'any',
            '--min-support',
            '2',
            '--top-k',
            '30',
            '--out-json',
            'docs/generated/game2_skeptic_identity_factor_audit_n548.json',
            '--out-md',
            'docs/generated/game2_skeptic_identity_factor_audit_n548.md',
        ],
        ROOT,
        args.tool_timeout,
    )
    ident_sk548_res = run_cmd(
        [
            'python3',
            'Game2/tools/skeptic_identity_factor_audit.py',
            '--label-prefix',
            'sk548',
            '--target-residual',
            '200',
            '--target-mode',
            'residual_only',
            '--min-support',
            '2',
            '--top-k',
            '30',
            '--out-json',
            'docs/generated/game2_skeptic_identity_factor_audit_sk548.json',
            '--out-md',
            'docs/generated/game2_skeptic_identity_factor_audit_sk548.md',
        ],
        ROOT,
        args.tool_timeout,
    )
    role_n548_res = run_cmd(
        [
            'python3',
            'Game2/tools/skeptic_role_mapping_audit.py',
            '--label-prefix',
            'n548',
            '--target-residual',
            '200',
            '--target-mode',
            'any',
            '--min-support',
            '2',
            '--top-k',
            '30',
            '--out-json',
            'docs/generated/game2_skeptic_role_mapping_audit_n548.json',
            '--out-md',
            'docs/generated/game2_skeptic_role_mapping_audit_n548.md',
        ],
        ROOT,
        args.tool_timeout,
    )
    role_sk548_res = run_cmd(
        [
            'python3',
            'Game2/tools/skeptic_role_mapping_audit.py',
            '--label-prefix',
            'sk548',
            '--target-residual',
            '200',
            '--target-mode',
            'residual_only',
            '--min-support',
            '2',
            '--top-k',
            '30',
            '--out-json',
            'docs/generated/game2_skeptic_role_mapping_audit_sk548.json',
            '--out-md',
            'docs/generated/game2_skeptic_role_mapping_audit_sk548.md',
        ],
        ROOT,
        args.tool_timeout,
    )
    hidden_sk548e_res = run_cmd(
        [
            'python3',
            'Game2/tools/skeptic_hidden_branch_diff.py',
            '--label-prefix',
            'sk548e0909',
            '--ref-score',
            '2157',
            '--min-support',
            '3',
            '--top-k',
            '24',
            '--out-json',
            'docs/generated/game2_skeptic_hidden_branch_diff_sk548e.json',
            '--out-md',
            'docs/generated/game2_skeptic_hidden_branch_diff_sk548e.md',
        ],
        ROOT,
        args.tool_timeout,
    )
    generalization_sk548_res = run_cmd(
        [
            'python3',
            'Game2/tools/skeptic_feature_generalization_audit.py',
            '--label-prefix',
            'sk548',
            '--target-residual',
            '200',
            '--target-mode',
            'residual_only',
            '--min-support-total',
            '4',
            '--min-support-group',
            '2',
            '--top-k',
            '60',
            '--out-json',
            'docs/generated/game2_skeptic_feature_generalization_audit_sk548.json',
            '--out-md',
            'docs/generated/game2_skeptic_feature_generalization_audit_sk548.md',
        ],
        ROOT,
        args.tool_timeout,
    )
    ablation_sk548e0910_res = run_cmd(
        [
            'python3',
            'Game2/tools/skeptic_ablation_summary.py',
            '--prefix',
            'sk548e0909',
            '--prefix',
            'sk548e0909b_auto',
            '--prefix',
            'sk548e0910d_ab',
            '--prefix',
            'sk548e0910f_ab',
            '--prefix',
            'sk548e0910g_ab',
            '--prefix',
            'sk548e0910h_ab',
            '--out-json',
            'docs/generated/game2_skeptic_ablation_summary_sk548e0910.json',
            '--out-md',
            'docs/generated/game2_skeptic_ablation_summary_sk548e0910.md',
        ],
        ROOT,
        args.tool_timeout,
    )
    return {
        'room_feature_mine': room_res,
        'eval_gate': gate_res,
        'gap_mode_audit': gap_res,
        'residual_trace_diff': trace_res,
        'identity_factor_audit_n548': ident_n548_res,
        'identity_factor_audit_sk548': ident_sk548_res,
        'role_mapping_audit_n548': role_n548_res,
        'role_mapping_audit_sk548': role_sk548_res,
        'hidden_branch_diff_sk548e': hidden_sk548e_res,
        'feature_generalization_audit_sk548': generalization_sk548_res,
        'ablation_summary_sk548e0910': ablation_sk548e0910_res,
    }


def parse_action_triggers(raw: str) -> set[str]:
    tokens = [token.strip() for token in str(raw or '').split(',') if token.strip()]
    triggers = {token for token in tokens if token in ACTION_TRIGGER_SET}
    return triggers or {'on_change'}


def maybe_run_action(
    state: dict[str, Any],
    args: argparse.Namespace,
    cycle_id: int,
    has_change: bool,
    new_labels: list[str],
    rooms_delta: dict[str, Any],
    sessions_delta: dict[str, Any],
) -> dict[str, Any]:
    cmd = str(args.action_cmd or '').strip()
    if not cmd:
        return {'status': 'skipped', 'reason': 'no-action-cmd'}
    triggers = parse_action_triggers(args.action_trigger)
    should = False
    reasons: list[str] = []
    if 'always' in triggers:
        should = True
        reasons.append('always')
    if has_change and 'on_change' in triggers:
        should = True
        reasons.append('on_change')
    if new_labels and 'on_new_label' in triggers:
        should = True
        reasons.append('on_new_label')
    if int(rooms_delta.get('low_score_count', 0)) > 0 and 'on_low_score' in triggers:
        should = True
        reasons.append('on_low_score')
    if int(sessions_delta.get('upload_signal_count', 0)) > 0 and 'on_upload_signal' in triggers:
        should = True
        reasons.append('on_upload_signal')
    if not should:
        return {'status': 'skipped', 'reason': 'trigger-not-met', 'triggers': sorted(triggers)}

    now_epoch = time.time()
    action_last = state.get('action_last_epoch', {})
    last_epoch = float(action_last.get('default', 0.0))
    cooldown = max(0.0, float(args.action_cooldown))
    if cooldown > 0 and last_epoch > 0 and (now_epoch - last_epoch) < cooldown:
        return {
            'status': 'skipped',
            'reason': 'cooldown',
            'cooldown_sec': cooldown,
            'remaining_sec': round(cooldown - (now_epoch - last_epoch), 3),
            'triggers': reasons,
        }

    env = os.environ.copy()
    env['SKEPTIC_CYCLE'] = str(cycle_id)
    env['SKEPTIC_NEW_LABELS'] = ','.join(new_labels)
    env['SKEPTIC_LOW_SCORE_COUNT'] = str(rooms_delta.get('low_score_count', 0))
    env['SKEPTIC_UPLOAD_SIGNAL_COUNT'] = str(sessions_delta.get('upload_signal_count', 0))
    env['SKEPTIC_STATUS_JSON'] = str(Path(args.status_json).resolve())
    started = time.time()
    completed = subprocess.run(cmd, cwd=str(ROOT), shell=True, text=True, capture_output=True, check=False, env=env)
    action_last['default'] = now_epoch
    state['action_last_epoch'] = action_last
    return {
        'status': 'ran',
        'ok': completed.returncode == 0,
        'returncode': int(completed.returncode),
        'duration_sec': round(time.time() - started, 3),
        'triggers': reasons,
        'command': compact(cmd, 260),
        'stdout': compact(completed.stdout, 600),
        'stderr': compact(completed.stderr, 600),
    }


def run_cycle(state: dict[str, Any], args: argparse.Namespace, cycle_id: int) -> dict[str, Any]:
    seen_before = set(str(item) for item in state.get('seen_labels', []))
    sessions_delta = scan_sessions(state, args)
    candidates_delta = scan_candidate_dirs(state, args)
    rooms_delta = scan_room_matches(state, args)

    labels_seen = (
        set(sessions_delta.get('labels', []))
        | set(sessions_delta.get('room_labels', []))
        | set(candidates_delta.get('labels', []))
        | set(rooms_delta.get('labels', []))
    )
    new_labels = sorted(labels_seen - seen_before)
    all_seen = sorted(seen_before | labels_seen)
    state['seen_labels'] = all_seen

    has_change = bool(
        int(sessions_delta.get('new_line_count', 0))
        or int(candidates_delta.get('new_candidate_dir_count', 0))
        or bool(candidates_delta.get('changed_candidate_dirs'))
        or int(rooms_delta.get('new_match_count', 0))
        or int(rooms_delta.get('updated_match_count', 0))
        or int(rooms_delta.get('new_room_dir_count', 0))
    )

    run_tools = str(args.run_tools)
    tools_row = {'status': 'skipped', 'reason': run_tools}
    if run_tools == 'always' or (run_tools == 'on_change' and has_change):
        tools_row = run_skeptic_tools(args)
        tools_row['status'] = 'ran'

    action_row = maybe_run_action(state, args, cycle_id, has_change, new_labels, rooms_delta, sessions_delta)

    record = {
        'time': utc_ts(),
        'cycle': cycle_id,
        'has_change': has_change,
        'new_labels': new_labels,
        'all_seen_label_count': len(all_seen),
        'session': sessions_delta,
        'candidates': candidates_delta,
        'rooms': rooms_delta,
        'tools': tools_row,
        'action': action_row,
    }
    return record


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Periodic skeptic watcher for Codex rollout sessions and Game2 room matches')
    parser.add_argument('--interval', type=float, default=300.0, help='seconds between cycles')
    parser.add_argument('--initial-delay', type=float, default=0.0)
    parser.add_argument('--once', action='store_true')
    parser.add_argument('--max-cycles', type=int, default=0, help='0 means unlimited')
    parser.add_argument('--session-root', default=str(DEFAULT_SESSION_ROOT))
    parser.add_argument('--session-glob', default='**/rollout-*.jsonl')
    parser.add_argument('--session-max-age-hours', type=float, default=72.0)
    parser.add_argument('--room-dir', default=str(DEFAULT_ROOM_DIR))
    parser.add_argument('--candidate-dir', default=str(DEFAULT_CANDIDATE_DIR))
    parser.add_argument('--state-json', default=str(DEFAULT_STATE_JSON))
    parser.add_argument('--status-json', default=str(DEFAULT_STATUS_JSON))
    parser.add_argument('--history-jsonl', default=str(DEFAULT_HISTORY_JSONL))
    parser.add_argument('--log-file', default=str(DEFAULT_LOG_FILE))
    parser.add_argument('--bootstrap-mode', choices=['tail', 'from-start'], default='tail')
    parser.add_argument('--run-tools', choices=['on_change', 'always', 'never'], default='on_change')
    parser.add_argument('--tool-timeout', type=float, default=300.0)
    parser.add_argument('--low-score-threshold', type=int, default=2657)
    parser.add_argument('--drop-gap', type=int, default=200)
    parser.add_argument('--max-line-scan-chars', type=int, default=40000)
    parser.add_argument('--recent-command-limit', type=int, default=12)
    parser.add_argument('--action-cmd', default='', help='optional shell command for upload/eval action')
    parser.add_argument('--action-trigger', default='on_change', help='comma list: always,on_change,on_new_label,on_low_score,on_upload_signal')
    parser.add_argument('--action-cooldown', type=float, default=1800.0, help='minimum seconds between action runs')
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    state_path = Path(args.state_json).resolve()
    status_path = Path(args.status_json).resolve()
    history_path = Path(args.history_jsonl).resolve()
    log_path = Path(args.log_file).resolve()

    state = normalize_state(read_json(state_path))
    if not state_path.is_file() and str(args.bootstrap_mode) == 'tail':
        baseline = bootstrap_tail_state(state, args)
        write_json(state_path, state)
        log_line(
            log_path,
            (
                f'bootstrap=tail session_files={baseline["session_file_count"]} '
                f'candidate_dirs={baseline["candidate_dir_count"]} '
                f'room_dirs={baseline["room_dir_count"]} '
                f'analysis={baseline["analysis_file_count"]} labels={baseline["known_labels"]}'
            ),
        )

    if float(args.initial_delay) > 0:
        sleep_sec = max(0.0, float(args.initial_delay))
        log_line(log_path, f'initial_delay={sleep_sec:.1f}s')
        time.sleep(sleep_sec)

    max_cycles = 1 if args.once else int(args.max_cycles)
    cycle = 0
    while True:
        cycle += 1
        record = run_cycle(state, args, cycle)
        write_json(state_path, state)
        write_json(status_path, record)
        append_jsonl(history_path, record)
        log_line(
            log_path,
            (
                f"cycle={cycle} change={record['has_change']} "
                f"session_lines={record['session']['new_line_count']} "
                f"new_candidates={record['candidates']['new_candidate_dir_count']} "
                f"new_matches={record['rooms']['new_match_count']} "
                f"low_scores={record['rooms']['low_score_count']} "
                f"new_labels={len(record['new_labels'])} "
                f"action={record['action'].get('status')}"
            ),
        )

        if args.once:
            return 0
        if max_cycles and cycle >= max_cycles:
            return 0
        sleep_sec = max(30.0, float(args.interval))
        time.sleep(sleep_sec)


if __name__ == '__main__':
    raise SystemExit(main())
