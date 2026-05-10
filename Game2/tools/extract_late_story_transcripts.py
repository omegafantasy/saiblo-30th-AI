#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ROOM_ROOT = ROOT / 'Game2' / 'runtime' / 'room_matches'
OUT_JSON = ROOT / 'docs' / 'generated' / 'game2_late_story_transcripts.json'
OUT_MD = ROOT / 'docs' / 'generated' / 'game2_late_story_transcripts.md'

LABEL_RE = re.compile(r'(sk548e0910[a-z]+|n\d{3,}[a-z])')
TARGET_IDS = (
    '404', '405', '501', '502', '503', '504', '505',
    '601', '602', '603', '604', '605', '606', '607', '608',
    '703', '704', '705', '706', '707', '708',
)
POKER_IDS = {'404', '405', '501', '502', '503', '504', '505', '601', '602', '603', '604', '605', '606', '607', '608'}
YUAN_IDS = {'703', '704', '705', '706', '707', '708'}
POKER_KEYS = ('扑克公馆', 'Joker', '梅花5', '林渝植', '衣帽间', '人口贩卖', '于书华', '张子韩')
YUAN_KEYS = ('袁樱瞳', '李海天', '生物馆', '1919', '奇怪网站', '出国名额')


def compact(value: Any, limit: int = 220) -> str:
    text = re.sub(r'\s+', ' ', str(value or '')).strip()
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)] + '...'


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def room_label(room_dir: Path) -> str:
    matches = LABEL_RE.findall(room_dir.name)
    return matches[-1] if matches else ''


def evidence_text(evidences: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for ev in evidences:
        if isinstance(ev, dict):
            parts.append(str(ev.get('id', '')))
            parts.append(str(ev.get('name', '')))
            parts.append(str(ev.get('content', '')))
    return '\n'.join(parts)


def rec_evidences(rec: dict[str, Any]) -> list[dict[str, Any]]:
    top = rec.get('evidences')
    if isinstance(top, list):
        return [ev for ev in top if isinstance(ev, dict)]
    state = rec.get('result_state') or {}
    return [ev for ev in (state.get('evidences') or []) if isinstance(ev, dict)]


def rec_reply(rec: dict[str, Any]) -> str:
    if isinstance(rec.get('reply'), str):
        return str(rec.get('reply') or '')
    interaction = rec.get('interaction') or {}
    return str((interaction.get('npc_reply') or {}).get('content', '') or '')


def rec_ask(rec: dict[str, Any]) -> str:
    interaction = rec.get('interaction') or {}
    return str((interaction.get('ask') or {}).get('content', '') or '')


def rec_stage(rec: dict[str, Any]) -> Any:
    if 'stage' in rec:
        return rec.get('stage')
    state = rec.get('result_state') or {}
    return state.get('stage')


def record_text(rec: dict[str, Any]) -> str:
    state = rec.get('result_state') or {}
    return '\n'.join([str(state.get('hint', '')), rec_ask(rec), rec_reply(rec), evidence_text(rec_evidences(rec))])


def target_matches_case(target: str, text: str) -> bool:
    if target in POKER_IDS:
        return any(key in text for key in POKER_KEYS)
    if target in YUAN_IDS:
        return any(key in text for key in YUAN_KEYS)
    return True


def context_rows(records: list[dict[str, Any]], idx: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    start = max(0, idx - 2)
    end = min(len(records), idx + 5)
    for rec in records[start:end]:
        state = rec.get('result_state') or {}
        evidences = rec_evidences(rec)
        rows.append({
            'step_id': rec.get('step_id'),
            'stage': rec_stage(rec),
            'npc': (rec.get('npc') or {}).get('id', ''),
            'ask': compact(rec_ask(rec), 180),
            'reply': compact(rec_reply(rec), 260),
            'visible_evidence': [str(ev.get('id', '')) for ev in evidences],
        })
    return rows


def collect(room_root: Path) -> dict[str, Any]:
    events: dict[str, list[dict[str, Any]]] = defaultdict(list)
    analysis_paths = sorted(room_root.glob('*/matches/*/analysis.json'))
    for path in analysis_paths:
        analysis = load_json(path)
        records = [rec for rec in (analysis.get('decoded_stdin_records') or []) if isinstance(rec, dict)]
        if not records:
            continue
        room_dir = path.parents[2]
        label = room_label(room_dir)
        player = (analysis.get('players') or [{}])[0]
        score = player.get('score')
        first_seen: set[str] = set()
        for idx, rec in enumerate(records):
            evidences = rec_evidences(rec)
            ids = {str(ev.get('id', '')) for ev in evidences}
            text = record_text(rec)
            for target in TARGET_IDS:
                if target in first_seen or target not in ids or not target_matches_case(target, text):
                    continue
                first_seen.add(target)
                ev = next((item for item in evidences if str(item.get('id', '')) == target), {})
                events[target].append({
                'label': label or '(unknown)',
                    'room_dir': str(room_dir.relative_to(ROOT)),
                    'match_id': path.parent.name,
                    'score': score if isinstance(score, int) else None,
                    'step_id': rec.get('step_id'),
                    'stage': rec_stage(rec),
                    'evidence_name': compact(ev.get('name', ''), 160),
                    'evidence_content': compact(ev.get('content', ''), 360),
                    'context': context_rows(records, idx),
                })
    summary = {
        target: {
            'count': len(rows),
            'labels': dict(sorted({label: sum(1 for row in rows if row.get('label') == label) for label in {row.get('label') for row in rows}}.items())),
        }
        for target, rows in sorted(events.items())
    }
    return {'analysis_files': len(analysis_paths), 'summary': summary, 'events': events}


def write_outputs(data: dict[str, Any], max_samples: int) -> None:
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    lines = ['# Game2 Late Story Transcripts', '']
    lines.append(f"analysis files: `{data['analysis_files']}`")
    lines.append('')
    lines.append('| evidence | first-seen count | labels |')
    lines.append('| --- | ---: | --- |')
    for target in TARGET_IDS:
        item = data['summary'].get(target, {'count': 0, 'labels': {}})
        labels = ', '.join(f"{label}x{count}" for label, count in item.get('labels', {}).items()) or '-'
        lines.append(f"| `{target}` | {item.get('count', 0)} | {labels} |")
    lines.append('')

    for target in ('404', '501', '502', '503', '504', '505', '601', '602', '603', '604', '605', '606', '607', '608', '705', '405', '706', '707', '708'):
        rows = data['events'].get(target, [])[:max_samples]
        lines.append(f'## `{target}` Samples')
        if not rows:
            lines.append('')
            lines.append('No matching first-seen events.')
            lines.append('')
            continue
        for row in rows:
            lines.append('')
            lines.append(
                f"- `{row['label']}` match `{row['match_id']}` score `{row['score']}` "
                f"step `{row['step_id']}` stage `{row['stage']}`: {row['evidence_name']} - {row['evidence_content']}"
            )
            for ctx in row['context']:
                lines.append(
                    f"  - step `{ctx['step_id']}` stage `{ctx['stage']}` npc `{ctx['npc']}` "
                    f"ask: {ctx['ask']} reply: {ctx['reply']} ev: {','.join(ctx['visible_evidence'])}"
                )
        lines.append('')
    OUT_MD.write_text('\n'.join(lines), encoding='utf-8')


def main() -> int:
    parser = argparse.ArgumentParser(description='Extract first-seen Poker/Yuan late evidence transcript context')
    parser.add_argument('--room-root', default=str(ROOM_ROOT))
    parser.add_argument('--max-samples', type=int, default=8)
    args = parser.parse_args()
    data = collect(Path(args.room_root))
    write_outputs(data, args.max_samples)
    print(json.dumps({'out_json': str(OUT_JSON), 'out_md': str(OUT_MD)}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
