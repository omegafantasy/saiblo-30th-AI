#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
RUNTIME_DIR = ROOT / 'Game2' / 'runtime'
OUT_JSON = ROOT / 'docs' / 'generated' / 'game2_story_unlocks.json'
OUT_MD = ROOT / 'docs' / 'generated' / 'game2_story_unlocks.md'

TARGETS = {
    '102': 'Poker 现场信息/照片',
    '103': 'Poker 死者所在房间平面图',
    '104': 'Poker 公馆完整构造',
    '203': 'Poker 房间电脑浏览记录',
    '204': 'Poker 方形塑料盒',
    '205': 'Poker 厨房刀具丢失',
    '703': 'Yuan 袁樱瞳的手机',
    '704': 'Yuan 课程展示投票结果',
}


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def compact(text: Any, limit: int = 160) -> str:
    value = re.sub(r'\s+', ' ', str(text or '')).strip()
    return value[:limit]


def score(data: dict[str, Any]) -> int | None:
    players = data.get('players')
    if not isinstance(players, list) or not players or not isinstance(players[0], dict):
        return None
    value = players[0].get('score')
    return value if isinstance(value, int) else None


def evidence_ids(record: dict[str, Any]) -> set[str]:
    ids: set[str] = set()
    for source in (record, record.get('result_state') if isinstance(record.get('result_state'), dict) else {}):
        if not isinstance(source, dict):
            continue
        visible = source.get('visible_evidences')
        if isinstance(visible, list):
            ids.update(str(item) for item in visible)
        evidences = source.get('evidences')
        if isinstance(evidences, list):
            for item in evidences:
                if isinstance(item, dict) and item.get('id') is not None:
                    ids.add(str(item.get('id')))
    return ids


def record_stage(record: dict[str, Any]) -> int | None:
    candidates = [record.get('stage')]
    state = record.get('result_state')
    if isinstance(state, dict):
        candidates.append(state.get('stage'))
    for candidate in candidates:
        try:
            return int(candidate)
        except (TypeError, ValueError):
            continue
    return None


def record_text(record: dict[str, Any]) -> str:
    if 'reply' in record:
        return compact(record.get('reply'))
    interaction = record.get('interaction')
    if isinstance(interaction, dict):
        ask = interaction.get('ask')
        reply = interaction.get('npc_reply')
        if isinstance(ask, dict) and ask.get('content'):
            return compact(f"Q: {ask.get('content')}")
        if isinstance(reply, dict) and reply.get('content'):
            return compact(f"A: {reply.get('content')}")
    if 'hint' in record:
        return compact(f"hint: {record.get('hint')}")
    return ''


def context_records(records: list[dict[str, Any]], index: int, size: int = 4) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for pos in range(max(0, index - size), index):
        text = record_text(records[pos])
        if not text:
            continue
        out.append({'index': pos, 'stage': record_stage(records[pos]), 'text': text})
    return out


def label_for_path(path: Path) -> str:
    parts = path.relative_to(ROOT).parts
    if 'room_matches' in parts:
        idx = parts.index('room_matches')
        if idx + 1 < len(parts):
            return parts[idx + 1]
    if 'batches' in parts:
        idx = parts.index('batches')
        if idx + 1 < len(parts):
            return parts[idx + 1]
    if len(parts) >= 3 and parts[0] == 'Game2' and parts[1] == 'runtime':
        return parts[2]
    if len(parts) >= 3:
        return parts[-3]
    return path.parent.name


def scan(paths: list[Path]) -> dict[str, Any]:
    hits: dict[str, list[dict[str, Any]]] = {target: [] for target in TARGETS}
    scanned = 0
    with_records = 0
    for path in paths:
        data = load_json(path)
        if not data:
            continue
        scanned += 1
        records_raw = data.get('decoded_stdin_records')
        if not isinstance(records_raw, list):
            continue
        records = [item for item in records_raw if isinstance(item, dict)]
        if not records:
            continue
        with_records += 1
        first_seen: set[str] = set()
        max_stage = 0
        for index, record in enumerate(records):
            stage = record_stage(record)
            if stage is not None:
                max_stage = max(max_stage, stage)
            ids = evidence_ids(record)
            for target in TARGETS:
                if target not in ids or target in first_seen:
                    continue
                first_seen.add(target)
                hits[target].append(
                    {
                        'path': str(path.relative_to(ROOT)),
                        'label': label_for_path(path),
                        'match_id': data.get('match_id'),
                        'score': score(data),
                        'record_index': index,
                        'record_stage': stage,
                        'max_stage_so_far': max_stage,
                        'visible_evidences': sorted(ids),
                        'context': context_records(records, index),
                    }
                )

    for rows in hits.values():
        rows.sort(key=lambda row: (row.get('score') or -1, row.get('record_index') or 0), reverse=True)
    return {
        'scanned_analysis_files': scanned,
        'files_with_decoded_records': with_records,
        'targets': TARGETS,
        'hits': hits,
    }


def render_md(data: dict[str, Any], limit: int) -> str:
    lines = ['# Game2 Story Unlocks', '']
    lines.append(
        f"Scanned `{data.get('scanned_analysis_files')}` analysis files; "
        f"`{data.get('files_with_decoded_records')}` contained decoded records."
    )
    lines.append('')
    for target, title in TARGETS.items():
        rows = data.get('hits', {}).get(target, [])
        lines.append(f'## `{target}` {title}')
        lines.append('')
        lines.append(f'Occurrences: `{len(rows)}`')
        lines.append('')
        lines.append('| score | match | idx | stage | label | path | context |')
        lines.append('| ---: | --- | ---: | ---: | --- | --- | --- |')
        for row in rows[:limit]:
            context = ' / '.join(item.get('text', '') for item in row.get('context', [])[-2:])
            stage = row.get('record_stage')
            if stage is None:
                stage = row.get('max_stage_so_far')
            lines.append(
                f"| {row.get('score') if row.get('score') is not None else ''} | "
                f"`{row.get('match_id')}` | {row.get('record_index')} | "
                f"{stage if stage is not None else ''} | "
                f"`{row.get('label')}` | `{row.get('path')}` | {context} |"
            )
        lines.append('')
    return '\n'.join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description='Extract first-visible story evidence unlocks from Game2 runtime analysis logs.')
    parser.add_argument('--limit', type=int, default=12, help='maximum rows per target in markdown output')
    args = parser.parse_args()

    paths = sorted(RUNTIME_DIR.rglob('analysis.json'))
    data = scan(paths)
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    OUT_MD.write_text(render_md(data, max(1, int(args.limit))), encoding='utf-8')
    print(json.dumps({'analysis_files': data['scanned_analysis_files'], 'out_json': str(OUT_JSON), 'out_md': str(OUT_MD)}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
