#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


def read_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding='utf-8'))
    return data if isinstance(data, dict) else {}


def resolve_paths(raw: str) -> tuple[Path, Path]:
    path = Path(raw).resolve()
    if path.is_dir():
        return path / 'analysis.json', path / 'match_download.json'
    if path.name == 'analysis.json':
        return path, path.with_name('match_download.json')
    raise ValueError(f'unsupported path: {raw}')


def extract_question(step: dict[str, Any]) -> str:
    interaction = step.get('interaction', {}) if isinstance(step, dict) else {}
    if not isinstance(interaction, dict):
        return ''
    ask = interaction.get('ask', {})
    if isinstance(ask, dict):
        return str(ask.get('content', '') or '')
    return ''


def extract_npc(step: dict[str, Any]) -> str:
    npc = step.get('npc', {}) if isinstance(step, dict) else {}
    if isinstance(npc, dict):
        return str(npc.get('id', '') or '')
    return ''


def parse_final_answer(text: str) -> dict[str, str]:
    src = str(text or '').strip()
    out = {'murderer': '', 'motivation': '', 'method': ''}
    if not src:
        return out
    murder = re.search(r'凶手[:：]\s*([^,，]+)', src)
    motive = re.search(r'动机[:：]\s*(.*?)(?:[,，]\s*手法[:：]|$)', src)
    method = re.search(r'手法[:：]\s*(.*)$', src)
    if murder:
        out['murderer'] = murder.group(1).strip()
    if motive:
        out['motivation'] = motive.group(1).strip()
    if method:
        out['method'] = method.group(1).strip()
    return out


def score_of_self(analysis: dict[str, Any]) -> int | None:
    best = None
    for player in analysis.get('players', []):
        if not isinstance(player, dict):
            continue
        user = player.get('user', {}) if isinstance(player.get('user'), dict) else {}
        if str(user.get('username', '')).strip() != 'theend':
            continue
        score = player.get('score')
        if isinstance(score, int):
            best = score
            break
    return best


def load_run(label: str, raw: str) -> dict[str, Any]:
    analysis_path, trace_path = resolve_paths(raw)
    analysis = read_json(analysis_path)
    trace = read_json(trace_path) if trace_path.exists() else {}
    cases: list[dict[str, Any]] = []
    for case in analysis.get('cases', []):
        if not isinstance(case, dict):
            continue
        case_id = str(case.get('case_id'))
        steps = trace.get(case_id, []) if isinstance(trace.get(case_id), list) else []
        questions = []
        for step in steps:
            if not isinstance(step, dict):
                continue
            question = extract_question(step)
            if not question or question.startswith('提交最终答案:'):
                continue
            questions.append({'npc': extract_npc(step), 'question': question})
        parsed = parse_final_answer(str(case.get('final_answer', '')))
        result = case.get('final_result', {}) if isinstance(case.get('final_result'), dict) else {}
        cases.append({
            'case_id': case_id,
            'step_count': int(case.get('step_count', 0) or 0),
            'final_stage': case.get('final_stage'),
            'final_result': result,
            'correct_count': sum(1 for v in result.values() if v is True),
            'npc_question_counts': case.get('npc_question_counts', {}),
            'questions': questions,
            'final_answer': str(case.get('final_answer', '')),
            'parsed_answer': parsed,
        })
    return {
        'label': label,
        'analysis_path': str(analysis_path),
        'match_id': analysis.get('match_id'),
        'state': analysis.get('state'),
        'my_score': score_of_self(analysis),
        'cases': cases,
    }


def question_strings(case: dict[str, Any]) -> list[str]:
    return [f"{item.get('npc')}|{item.get('question')}" for item in case.get('questions', [])]


def question_counter(case: dict[str, Any]) -> Counter[str]:
    return Counter(question_strings(case))


def render_run_summary(run: dict[str, Any]) -> list[str]:
    lines = [
        f"## {run.get('label')}",
        '',
        f"- match_id: `{run.get('match_id')}`",
        f"- state: `{run.get('state')}`",
        f"- my_score: `{run.get('my_score')}`",
        f"- source: `{run.get('analysis_path')}`",
        '',
    ]
    for case in run.get('cases', []):
        parsed = case.get('parsed_answer', {})
        lines.append(
            f"- case `{case.get('case_id')}`: steps=`{case.get('step_count')}` stage=`{case.get('final_stage')}` correct=`{case.get('correct_count')}/3` murderer=`{parsed.get('murderer')}`"
        )
        lines.append(
            f"  top_npcs=`{list((case.get('npc_question_counts') or {}).items())[:5]}`"
        )
        lines.append(
            f"  answer=`{str(case.get('final_answer', ''))[:220]}`"
        )
    lines.append('')
    return lines


def render_case_compare(base: dict[str, Any], other: dict[str, Any], case_idx: int) -> list[str]:
    if case_idx >= len(base.get('cases', [])) or case_idx >= len(other.get('cases', [])):
        return []
    a = base['cases'][case_idx]
    b = other['cases'][case_idx]
    aq = question_counter(a)
    bq = question_counter(b)
    added = sorted((bq - aq).elements())
    removed = sorted((aq - bq).elements())
    lines = [
        f"### case {case_idx}: `{base.get('label')}` vs `{other.get('label')}`",
        '',
        f"- steps: `{a.get('step_count')}` -> `{b.get('step_count')}`",
        f"- final_stage: `{a.get('final_stage')}` -> `{b.get('final_stage')}`",
        f"- correct_count: `{a.get('correct_count')}` -> `{b.get('correct_count')}`",
        f"- murderer: `{a.get('parsed_answer', {}).get('murderer')}` -> `{b.get('parsed_answer', {}).get('murderer')}`",
        '',
        'Added questions:',
    ]
    if added:
        for item in added[:8]:
            lines.append(f"- `{item}`")
    else:
        lines.append('- `(none)`')
    lines.append('')
    lines.append('Removed questions:')
    if removed:
        for item in removed[:8]:
            lines.append(f"- `{item}`")
    else:
        lines.append('- `(none)`')
    lines.append('')
    return lines


def render_markdown(runs: list[dict[str, Any]]) -> str:
    lines = ['# Game2 Run Comparison', '']
    if not runs:
        return '# Game2 Run Comparison\n'
    lines.append('## Summary')
    lines.append('')
    for run in runs:
        lines.append(
            f"- `{run.get('label')}` match=`{run.get('match_id')}` score=`{run.get('my_score')}`"
        )
    lines.append('')
    for run in runs:
        lines.extend(render_run_summary(run))
    base = runs[0]
    for other in runs[1:]:
        lines.append(f"## Compare `{base.get('label')}` vs `{other.get('label')}`")
        lines.append('')
        for case_idx in range(min(len(base.get('cases', [])), len(other.get('cases', [])))):
            lines.extend(render_case_compare(base, other, case_idx))
    return '\n'.join(lines).rstrip() + '\n'


def main() -> int:
    parser = argparse.ArgumentParser(description='Compare multiple Game2 match runs')
    parser.add_argument(
        '--input',
        action='append',
        required=True,
        help='LABEL=PATH where PATH is a match dir or analysis.json path',
    )
    parser.add_argument('--out', default='')
    args = parser.parse_args()

    runs = []
    for item in args.input:
        if '=' not in item:
            raise ValueError(f'invalid input {item!r}, expected LABEL=PATH')
        label, raw = item.split('=', 1)
        runs.append(load_run(label.strip(), raw.strip()))
    markdown = render_markdown(runs)
    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(markdown, encoding='utf-8')
    print(markdown)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
