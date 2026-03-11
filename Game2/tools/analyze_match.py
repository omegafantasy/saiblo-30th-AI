#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import statistics
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from saiblo_tools import api_download, api_request, require_token, resolve_token


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding='utf-8')


def safe_json_loads(text: str) -> dict[str, Any]:
    if not text.strip():
        return {}
    try:
        data = json.loads(text)
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def decode_message_blob(text: str | None) -> dict[str, Any]:
    if not text:
        return {}
    try:
        data = json.loads(text)
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def decode_text_blob(text: str | None) -> str:
    if not text:
        return ''
    raw = str(text)
    try:
        data = base64.b64decode(raw, validate=True)
        decoded = data.decode('utf-8', errors='replace')
        if any(ch.isprintable() for ch in decoded):
            return decoded
    except Exception:
        pass
    return raw


def decode_stdin_record(record: str) -> list[dict[str, Any]]:
    try:
        raw = base64.b64decode(record)
    except Exception:
        return []
    out: list[dict[str, Any]] = []
    pos = 0
    while pos + 4 <= len(raw):
        frame_len = int.from_bytes(raw[pos:pos + 4], 'big', signed=False)
        pos += 4
        if frame_len <= 0 or pos + frame_len > len(raw):
            break
        chunk = raw[pos:pos + frame_len]
        pos += frame_len
        try:
            data = json.loads(chunk.decode('utf-8', errors='replace'))
        except Exception:
            continue
        if isinstance(data, dict):
            out.append(data)
    return out


def extract_question(step: dict[str, Any]) -> str:
    interaction = step.get('interaction', {}) if isinstance(step, dict) else {}
    if not isinstance(interaction, dict):
        return ''
    ask = interaction.get('ask', {})
    if isinstance(ask, dict) and ask.get('content'):
        return str(ask.get('content'))
    if interaction.get('ask_content'):
        return str(interaction.get('ask_content'))
    return ''


def extract_evidence_ids(step: dict[str, Any]) -> list[str]:
    interaction = step.get('interaction', {}) if isinstance(step, dict) else {}
    if not isinstance(interaction, dict):
        return []
    submit_evidence = interaction.get('submit_evidence', {})
    if isinstance(submit_evidence, dict) and isinstance(submit_evidence.get('evidence_id'), list):
        return [str(x) for x in submit_evidence.get('evidence_id', [])]
    if isinstance(interaction.get('submit_evidence_id'), list):
        return [str(x) for x in interaction.get('submit_evidence_id', [])]
    return []


def extract_reply(step: dict[str, Any]) -> str:
    interaction = step.get('interaction', {}) if isinstance(step, dict) else {}
    if not isinstance(interaction, dict):
        return ''
    reply = interaction.get('npc_reply', {})
    if isinstance(reply, dict) and reply.get('content'):
        return str(reply.get('content'))
    if interaction.get('npc_reply'):
        return str(interaction.get('npc_reply'))
    return ''


def extract_npc(step: dict[str, Any]) -> str:
    npc = step.get('npc', {}) if isinstance(step, dict) else {}
    if isinstance(npc, dict) and npc.get('id'):
        return str(npc.get('id'))
    if step.get('npc_id'):
        return str(step.get('npc_id'))
    return ''


def analyze_trace(detail: dict[str, Any], trace: dict[str, Any]) -> dict[str, Any]:
    message = decode_message_blob(detail.get('message'))
    record = message.get('record', []) if isinstance(message.get('record'), list) else []
    samples = []
    for chunk in record:
        if not isinstance(chunk, list):
            continue
        for item in chunk:
            if isinstance(item, dict) and item.get('status') is not None:
                samples.append(item)
    runtimes = [float(x.get('time', 0.0) or 0.0) for x in samples]
    memories = [int(x.get('memory', 0) or 0) for x in samples]
    status_counter = Counter(str(x.get('status', '')) for x in samples)

    decoded_inputs = []
    for rec in message.get('stdinRecords', []) if isinstance(message.get('stdinRecords'), list) else []:
        if isinstance(rec, str) and rec:
            decoded_inputs.extend(decode_stdin_record(rec))

    cases = []
    for case_id in sorted(trace.keys(), key=lambda x: int(x) if str(x).isdigit() else str(x)):
        steps = trace.get(case_id, [])
        if not isinstance(steps, list):
            continue
        npc_counter = Counter()
        evidence_counter = Counter()
        transitions = []
        final_answer = ''
        final_result = {}
        prev_stage = None
        for step in steps:
            npc = extract_npc(step)
            if npc:
                npc_counter[npc] += 1
            evidences = extract_evidence_ids(step)
            for eid in evidences:
                evidence_counter[eid] += 1
            rs = step.get('result_state', {}) if isinstance(step, dict) else {}
            stage = rs.get('stage')
            question = extract_question(step)
            if stage != prev_stage:
                transitions.append({
                    'step_id': step.get('step_id'),
                    'from_stage': prev_stage,
                    'to_stage': stage,
                    'npc': npc,
                    'question': question,
                })
                prev_stage = stage
            if question.startswith('提交最终答案:'):
                final_answer = question
            if isinstance(rs.get('answer_result'), dict):
                final_result = dict(rs.get('answer_result'))
        cases.append({
            'case_id': case_id,
            'step_count': len(steps),
            'final_stage': prev_stage,
            'npc_question_counts': dict(npc_counter.most_common()),
            'evidence_submission_counts': dict(evidence_counter.most_common()),
            'stage_transitions': transitions,
            'first_questions': [
                {
                    'npc': extract_npc(step),
                    'question': extract_question(step),
                    'evidences': extract_evidence_ids(step),
                    'reply': extract_reply(step)[:240],
                }
                for step in steps[:8]
            ],
            'last_questions': [
                {
                    'npc': extract_npc(step),
                    'question': extract_question(step),
                    'evidences': extract_evidence_ids(step),
                    'reply': extract_reply(step)[:240],
                }
                for step in steps[-5:]
            ],
            'final_answer': final_answer,
            'final_result': final_result,
        })

    return {
        'match_id': detail.get('id'),
        'state': detail.get('state'),
        'game': detail.get('game'),
        'players': detail.get('info'),
        'performance': {
            'sample_count': len(samples),
            'status_counts': dict(status_counter),
            'time_avg': statistics.fmean(runtimes) if runtimes else 0.0,
            'time_max': max(runtimes) if runtimes else 0.0,
            'memory_max': max(memories) if memories else 0,
        },
        'decoded_stdin_records': decoded_inputs,
        'cases': cases,
    }


def analyze_match_payload(detail: dict[str, Any], trace: dict[str, Any] | None = None, download_error: str = '') -> dict[str, Any]:
    detail = detail if isinstance(detail, dict) else {}
    trace = trace if isinstance(trace, dict) else {}
    analysis = analyze_trace(detail, trace)
    analysis['download_error'] = download_error
    analysis['has_trace'] = bool(trace)
    analysis['error'] = detail.get('error')
    analysis['err'] = detail.get('err')
    analysis['err_decoded'] = decode_text_blob(detail.get('err'))
    analysis['message_present'] = detail.get('message') is not None
    analysis['players'] = detail.get('info') if isinstance(detail.get('info'), list) else []
    return analysis


def render_markdown(analysis: dict[str, Any]) -> str:
    lines = ['# Game2 Match Analysis', '']
    lines.append(f"- match_id: `{analysis.get('match_id')}`")
    lines.append(f"- state: `{analysis.get('state')}`")
    lines.append(f"- has_trace: `{analysis.get('has_trace')}`")
    lines.append(f"- error: `{analysis.get('error')}`")
    lines.append(f"- err: `{analysis.get('err')}`")
    lines.append(f"- message_present: `{analysis.get('message_present')}`")
    err_decoded = str(analysis.get('err_decoded') or '').strip()
    if err_decoded:
        preview = err_decoded[-1600:].replace('`', "'")
        lines.append('- err_decoded_preview:')
        lines.append('```text')
        lines.append(preview)
        lines.append('```')
    if analysis.get('download_error'):
        lines.append(f"- download_error: `{analysis.get('download_error')}`")
    perf = analysis.get('performance', {})
    lines.append(f"- sample_count: `{perf.get('sample_count')}`")
    lines.append(f"- time_avg: `{perf.get('time_avg')}`")
    lines.append(f"- time_max: `{perf.get('time_max')}`")
    lines.append(f"- memory_max: `{perf.get('memory_max')}`")
    lines.append('')
    lines.append('Players:')
    for player in analysis.get('players', []) or []:
        if not isinstance(player, dict):
            continue
        code = player.get('code', {}) if isinstance(player.get('code'), dict) else {}
        user = player.get('user', {}) if isinstance(player.get('user'), dict) else {}
        lines.append(
            f"- `{user.get('username')}/{code.get('entity')}` rank=`{player.get('rank')}` score=`{player.get('score')}` code_id=`{code.get('id')}`"
        )
    for case in analysis.get('cases', []):
        lines.append('')
        lines.append(f"## Case {case.get('case_id')}")
        lines.append(f"- steps: `{case.get('step_count')}`")
        lines.append(f"- final_stage: `{case.get('final_stage')}`")
        lines.append(f"- final_result: `{case.get('final_result')}`")
        if case.get('final_answer'):
            lines.append(f"- final_answer: `{case.get('final_answer')}`")
        top_npcs = list((case.get('npc_question_counts') or {}).items())[:8]
        if top_npcs:
            lines.append('- top_npcs:')
            for npc, count in top_npcs:
                lines.append(f"  - `{npc}`: `{count}`")
        lines.append('- stage_transitions:')
        for item in case.get('stage_transitions', []) or []:
            lines.append(
                f"  - step `{item.get('step_id')}` `{item.get('from_stage')}` -> `{item.get('to_stage')}` npc=`{item.get('npc')}` q=`{item.get('question')}`"
            )
    return '\n'.join(lines) + '\n'


def main() -> int:
    parser = argparse.ArgumentParser(description='Download and analyze one Game2 match')
    parser.add_argument('--match-id', type=int, required=True)
    parser.add_argument('--out-dir', required=True)
    args = parser.parse_args()

    token, _ = resolve_token('')
    token = require_token(token, 'game2-analyze-match')
    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    detail = api_request('GET', f'/api/matches/{args.match_id}/', token=token)
    headers: dict[str, str] = {}
    trace: dict[str, Any] = {}
    download_error = ''
    try:
        body, headers = api_download(f'/api/matches/{args.match_id}/download/', token=token)
        download_text = body.decode('utf-8', errors='replace')
        trace = safe_json_loads(download_text)
    except Exception as exc:
        download_error = f'{type(exc).__name__}: {exc}'
    analysis = analyze_match_payload(detail if isinstance(detail, dict) else {}, trace, download_error)

    write_json(out_dir / 'match_detail.json', detail)
    write_json(out_dir / 'match_download.json', trace)
    write_json(out_dir / 'analysis.json', analysis)
    (out_dir / 'analysis.md').write_text(render_markdown(analysis), encoding='utf-8')
    print(json.dumps({'out_dir': str(out_dir), 'headers': headers, 'analysis': analysis}, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
