#!/usr/bin/env python3
from __future__ import annotations

import base64
import collections
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ROOM_DIR = ROOT / 'Game2' / 'runtime' / 'room_matches'
OUT_JSON = ROOT / 'docs' / 'generated' / 'game2_room_score_factors.json'
OUT_MD = ROOT / 'docs' / 'generated' / 'game2_room_score_factors.md'


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def decode_stderr(value: Any) -> str:
    if not isinstance(value, str) or not value:
        return ''
    try:
        return base64.b64decode(value).decode('utf-8', errors='replace')
    except Exception:
        return value


def compact(text: Any, limit: int = 80) -> str:
    return re.sub(r'\s+', ' ', str(text or '')).strip()[:limit]


def first_player(data: dict[str, Any]) -> dict[str, Any]:
    players = data.get('players')
    if isinstance(players, list) and players and isinstance(players[0], dict):
        return players[0]
    return {}


def base_label(label: str) -> str:
    match = re.match(r'(n\d+[a-z])', label)
    return match.group(1) if match else label


def label_from_path(path: Path, player: dict[str, Any]) -> str:
    code = player.get('code') if isinstance(player.get('code'), dict) else {}
    entity = str(code.get('entity') or '').strip()
    if entity:
        return entity
    room = path.parents[2].name
    return room.rsplit('_room', 1)[0].split('_', 2)[-1]


def find_answer_result(obj: Any) -> dict[str, bool] | None:
    if isinstance(obj, dict):
        value = obj.get('answer_result')
        if isinstance(value, dict):
            return {str(k): bool(v) for k, v in value.items()}
        for child in obj.values():
            found = find_answer_result(child)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for child in obj:
            found = find_answer_result(child)
            if found is not None:
                return found
    return None


def result_state(record: Any) -> dict[str, Any]:
    if not isinstance(record, dict):
        return {}
    state = record.get('result_state')
    if isinstance(state, dict):
        return state
    return record


def visible_evidence_ids(record: Any) -> set[str]:
    state = result_state(record)
    ids: set[str] = set()
    visible = state.get('visible_evidences')
    if isinstance(visible, list):
        ids.update(str(item) for item in visible)
    evidences = state.get('evidences')
    if isinstance(evidences, list):
        for item in evidences:
            if isinstance(item, dict) and item.get('id') is not None:
                ids.add(str(item.get('id')))
    return ids


def hint_text(record: Any) -> str:
    state = result_state(record)
    hint = state.get('hint')
    if isinstance(hint, str):
        return hint
    if isinstance(record, dict) and isinstance(record.get('hint'), str):
        return str(record.get('hint'))
    return ''


def reply_stage(record: Any) -> int | None:
    if not isinstance(record, dict) or 'reply' not in record:
        return None
    value = record.get('stage')
    return value if isinstance(value, int) else None


def case_start_indices(records: list[Any]) -> dict[str, int]:
    starts: dict[str, int] = {}
    for index, record in enumerate(records):
        hint = hint_text(record)
        if 'Rose' in hint and 'rose' not in starts:
            starts['rose'] = index
        elif ('Z失踪' in hint or 'F无法联络' in hint) and 'zf' not in starts:
            starts['zf'] = index
        elif '案发现场' in hint and '信息来源' in hint and 'poker' not in starts:
            starts['poker'] = index
        elif '袁樱瞳' in hint and 'yuan' not in starts:
            starts['yuan'] = index
    return starts


def max_reply_stage(records: list[Any], start: int | None, end: int | None) -> int | None:
    if start is None:
        return None
    stages = [
        stage
        for record in records[start : end if end is not None else len(records)]
        if (stage := reply_stage(record)) is not None
    ]
    return max(stages) if stages else None


def first_reply_stage_index(records: list[Any], start: int | None, end: int | None, target_stage: int) -> int | None:
    if start is None:
        return None
    reply_index = 0
    for record in records[start : end if end is not None else len(records)]:
        if reply_stage(record) is None:
            continue
        reply_index += 1
        if reply_stage(record) == target_stage:
            return reply_index
    return None


def segment_evidence_ids(records: list[Any], start: int | None, end: int | None) -> list[str]:
    if start is None:
        return []
    ids: set[str] = set()
    for record in records[start : end if end is not None else len(records)]:
        ids.update(visible_evidence_ids(record))
    return sorted(ids)


def extract_stderr_features(stderr: str) -> dict[str, Any]:
    stage6_questions = re.findall(r'stage 5->6 npc=[^ ]+ q=([^\n]+)', stderr)
    unknown_suspects = re.findall(r'unknown hint=.*? suspect=([^\n]+)', stderr)
    return {
        'rose_stage6_question': stage6_questions[0] if stage6_questions else '',
        'unknown_suspects': unknown_suspects,
    }


def count_err8(records: list[Any], stderr: str) -> int:
    count = stderr.count("Internal Server Error: '8'")
    for record in records:
        if isinstance(record, dict) and "Internal Server Error: '8'" in str(record.get('error', '')):
            count += 1
    return count


def analyze_match(path: Path) -> dict[str, Any] | None:
    data = load_json(path)
    player = first_player(data)
    score = player.get('score')
    if player.get('end_state') != 'OK' or not isinstance(score, int) or score <= 0:
        return None

    label = label_from_path(path, player)
    stderr = decode_stderr(player.get('stderr'))
    stderr_features = extract_stderr_features(stderr)
    records = data.get('decoded_stdin_records')
    if not isinstance(records, list):
        records = []

    starts = case_start_indices(records)
    rose_start = starts.get('rose')
    zf_start = starts.get('zf')
    poker_start = starts.get('poker')
    yuan_start = starts.get('yuan')
    poker_stage = max_reply_stage(records, poker_start, yuan_start)
    yuan_stage = max_reply_stage(records, yuan_start, None)

    download = load_json(path.with_name('match_download.json'))
    rose_result = find_answer_result(download) or {}

    row = {
        'score': score,
        'label': label,
        'base_label': base_label(label),
        'match_id': str(path.parent.name),
        'path': str(path.relative_to(ROOT)),
        'rose_answer_result': rose_result,
        'rose_answer_key': ''.join(f'{key[0]}{"T" if value else "F"}' for key, value in sorted(rose_result.items())),
        'rose_stage6_question': stderr_features['rose_stage6_question'],
        'rose_stage6_kind': 'like' if '喜欢你' in stderr_features['rose_stage6_question'] else ('attitude' if '态度怪' in stderr_features['rose_stage6_question'] else 'other'),
        'rose_stage6_index': first_reply_stage_index(records, rose_start, zf_start, 6),
        'z_err8_count': count_err8(records, stderr),
        'poker_stage': poker_stage,
        'poker_evidence_ids': segment_evidence_ids(records, poker_start, yuan_start),
        'yuan_stage': yuan_stage,
        'yuan_evidence_ids': segment_evidence_ids(records, yuan_start, None),
        'unknown_suspects': stderr_features['unknown_suspects'],
    }
    return row


def analyze() -> dict[str, Any]:
    rows = [
        row
        for path in sorted(ROOM_DIR.glob('*/matches/*/analysis.json'))
        if (row := analyze_match(path)) is not None
    ]

    by_score: dict[str, Any] = {}
    score_groups: dict[int, list[dict[str, Any]]] = collections.defaultdict(list)
    for row in rows:
        score_groups[int(row['score'])].append(row)
    for score, group in sorted(score_groups.items()):
        by_score[str(score)] = summarize_group(group)

    base_groups: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for row in rows:
        base_groups[str(row['base_label'])].append(row)

    return {
        'rows': rows,
        'by_score': by_score,
        'by_base_label': {label: summarize_group(group) for label, group in sorted(base_groups.items())},
    }


def summarize_group(group: list[dict[str, Any]]) -> dict[str, Any]:
    scores = [int(row['score']) for row in group]
    return {
        'count': len(group),
        'avg': round(sum(scores) / len(scores), 3) if scores else None,
        'score_distribution': dict(sorted(collections.Counter(scores).items())),
        'rose_answer_distribution': dict(sorted(collections.Counter(row.get('rose_answer_key') or '' for row in group).items())),
        'rose_stage6_distribution': dict(sorted(collections.Counter(row.get('rose_stage6_kind') or '' for row in group).items())),
        'rose_stage6_index_distribution': dict(sorted(collections.Counter(str(row.get('rose_stage6_index')) for row in group).items())),
        'poker_stage_distribution': dict(sorted(collections.Counter(str(row.get('poker_stage')) for row in group).items())),
        'z_err8_distribution': dict(sorted(collections.Counter(int(row.get('z_err8_count') or 0) for row in group).items())),
        'yuan_stage_distribution': dict(sorted(collections.Counter(str(row.get('yuan_stage')) for row in group).items())),
    }


def render_md(data: dict[str, Any]) -> str:
    lines = ['# Game2 Room Score Factors', '']
    lines.append('Only effective single-player room matches are included. This is diagnostic data; hidden cases still lack full answer_result.')
    lines.append('')
    lines.append('## By Score')
    lines.append('')
    lines.append('| score | count | poker_stage | rose_answer | rose_stage6 | rose6_idx | z_err8 | yuan_stage |')
    lines.append('| ---: | ---: | --- | --- | --- | --- | --- | --- |')
    for score, summary in sorted(data.get('by_score', {}).items(), key=lambda item: int(item[0])):
        lines.append(
            f"| {score} | {summary.get('count')} | "
            f"{format_counter(summary.get('poker_stage_distribution'))} | "
            f"{format_counter(summary.get('rose_answer_distribution'))} | "
            f"{format_counter(summary.get('rose_stage6_distribution'))} | "
            f"{format_counter(summary.get('rose_stage6_index_distribution'))} | "
            f"{format_counter(summary.get('z_err8_distribution'))} | "
            f"{format_counter(summary.get('yuan_stage_distribution'))} |"
        )
    lines.append('')
    lines.append('## By Base Label')
    lines.append('')
    lines.append('| label | count | avg | scores | poker_stage | rose_stage6 | rose6_idx |')
    lines.append('| --- | ---: | ---: | --- | --- | --- | --- |')
    for label, summary in sorted(data.get('by_base_label', {}).items()):
        lines.append(
            f"| `{label}` | {summary.get('count')} | {summary.get('avg') if summary.get('avg') is not None else ''} | "
            f"{format_counter(summary.get('score_distribution'))} | "
            f"{format_counter(summary.get('poker_stage_distribution'))} | "
            f"{format_counter(summary.get('rose_stage6_distribution'))} | "
            f"{format_counter(summary.get('rose_stage6_index_distribution'))} |"
        )
    lines.append('')
    lines.append('## Rows')
    lines.append('')
    lines.append('| score | label | match | rose | rose_q | rose6_idx | poker_stage | z_err8 | yuan_stage |')
    lines.append('| ---: | --- | --- | --- | --- | ---: | ---: | ---: | ---: |')
    for row in sorted(data.get('rows', []), key=lambda item: (int(item.get('score', 0)), str(item.get('label')), str(item.get('match_id')))):
        lines.append(
            f"| {row.get('score')} | `{row.get('label')}` | `{row.get('match_id')}` | "
            f"`{row.get('rose_answer_key')}` | {compact(row.get('rose_stage6_question'), 30)} | "
            f"{row.get('rose_stage6_index') if row.get('rose_stage6_index') is not None else ''} | "
            f"{row.get('poker_stage') if row.get('poker_stage') is not None else ''} | "
            f"{row.get('z_err8_count')} | {row.get('yuan_stage') if row.get('yuan_stage') is not None else ''} |"
        )
    return '\n'.join(lines) + '\n'


def format_counter(value: Any) -> str:
    if not isinstance(value, dict):
        return ''
    return ', '.join(f'{key} x{count}' for key, count in value.items())


def main() -> int:
    data = analyze()
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    OUT_MD.write_text(render_md(data), encoding='utf-8')
    print(json.dumps({'rows': len(data.get('rows', [])), 'out_json': str(OUT_JSON), 'out_md': str(OUT_MD)}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
