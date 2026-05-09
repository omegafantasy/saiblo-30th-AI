#!/usr/bin/env python3
from __future__ import annotations

import argparse
import collections
import json
import re
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[2]
ROOM_DIR = ROOT / 'Game2' / 'runtime' / 'room_matches'
OUT_JSON = ROOT / 'docs' / 'generated' / 'game2_yuan_isolation.json'
OUT_MD = ROOT / 'docs' / 'generated' / 'game2_yuan_isolation.md'


FeatureFn = Callable[[dict[str, Any]], bool]


def load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def first_player(data: dict[str, Any]) -> dict[str, Any]:
    players = data.get('players')
    if isinstance(players, list) and players and isinstance(players[0], dict):
        return players[0]
    return {}


def player_label(player: dict[str, Any]) -> str:
    code = player.get('code') if isinstance(player.get('code'), dict) else {}
    return str(code.get('entity') or '').strip()


def result_state(record: Any) -> dict[str, Any]:
    if isinstance(record, dict) and isinstance(record.get('result_state'), dict):
        return record['result_state']
    return {}


def hint_text(record: Any) -> str:
    if isinstance(record, dict) and isinstance(record.get('hint'), str):
        return str(record.get('hint'))
    state = result_state(record)
    hint = state.get('hint')
    return str(hint) if isinstance(hint, str) else ''


def is_case_start(record: Any) -> bool:
    state = result_state(record)
    return bool(state.get('hint')) and bool(state.get('visible_npcs'))


def is_yuan_hint(text: str) -> bool:
    return '袁樱瞳' in text or '碎尸案' in text


def evidence_ids_from_record(record: Any) -> set[str]:
    ids: set[str] = set()
    if not isinstance(record, dict):
        return ids
    evidences = record.get('evidences')
    if isinstance(evidences, list):
        for ev in evidences:
            if isinstance(ev, dict) and ev.get('id') is not None:
                ids.add(str(ev.get('id')))
    state = result_state(record)
    visible = state.get('visible_evidences')
    if isinstance(visible, list):
        ids.update(str(item) for item in visible)
    state_evidences = state.get('evidences')
    if isinstance(state_evidences, list):
        for ev in state_evidences:
            if isinstance(ev, dict) and ev.get('id') is not None:
                ids.add(str(ev.get('id')))
    return ids


def find_yuan_segment(records: list[Any]) -> tuple[int | None, int | None, tuple[str, ...]]:
    start: int | None = None
    npcs: tuple[str, ...] = ()
    for index, record in enumerate(records):
        hint = hint_text(record)
        if is_yuan_hint(hint):
            start = index
            state = result_state(record)
            raw_npcs = state.get('visible_npcs')
            if isinstance(raw_npcs, list):
                npcs = tuple(str(npc) for npc in raw_npcs)
            break
    if start is None:
        return None, None, ()

    end: int | None = None
    for index in range(start + 1, len(records)):
        if is_case_start(records[index]) and not is_yuan_hint(hint_text(records[index])):
            end = index
            break
    return start, end, npcs


def row_from_analysis(path: Path, label_regex: re.Pattern[str], score_filter: set[int]) -> dict[str, Any] | None:
    data = load_json(path)
    player = first_player(data)
    score = player.get('score')
    if not isinstance(score, int) or score <= 0:
        return None
    if score_filter and score not in score_filter:
        return None
    label = player_label(player)
    if not label_regex.fullmatch(label):
        return None

    records = data.get('decoded_stdin_records')
    if not isinstance(records, list):
        return None
    start, end, npcs = find_yuan_segment(records)
    if start is None:
        return None
    segment = records[start : end if end is not None else len(records)]

    replies: list[str] = []
    evidences: set[str] = set()
    any_unlock = False
    for record in segment:
        if not isinstance(record, dict):
            continue
        if isinstance(record.get('reply'), str):
            replies.append(str(record.get('reply')))
            if record.get('achievements') or record.get('unlock_testimony'):
                any_unlock = True
        evidences.update(evidence_ids_from_record(record))

    text = '\n'.join(replies)
    features = extract_features(
        {
            'text': text,
            'evidence_ids': evidences,
            'reply_count': len(replies),
            'npcs': npcs,
            'any_unlock': any_unlock,
        }
    )
    return {
        'label': label,
        'score': score,
        'plus40': score in {247, 1647},
        'match_id': path.parent.name,
        'path': str(path.relative_to(ROOT)),
        'npcs': list(npcs),
        'reply_count': len(replies),
        'evidence_ids': sorted(evidences),
        'features': features,
    }


def feature_definitions() -> dict[str, FeatureFn]:
    return {
        'has_704': lambda row: '704' in row['evidence_ids'],
        'has_703_only': lambda row: '703' in row['evidence_ids'] and '704' not in row['evidence_ids'],
        'reply_count_9': lambda row: row['reply_count'] == 9,
        'reply_count_12': lambda row: row['reply_count'] == 12,
        'kw_vote_abnormal': lambda row: any(k in row['text'] for k in ('46', '多出', '笔迹', '异笔迹')),
        'kw_46': lambda row: '46' in row['text'],
        'kw_24_23': lambda row: '24' in row['text'] and '23' in row['text'],
        'kw_biji': lambda row: '笔迹' in row['text'],
        'kw_duochu': lambda row: '多出' in row['text'],
        'kw_lht': lambda row: '李海天' in row['text'],
        'kw_lht_dead': lambda row: '李海天' in row['text'] and any(k in row['text'] for k in ('死', '遇害', '惨')),
        'kw_biology': lambda row: '生物馆' in row['text'],
        'kw_century': lambda row: '世纪林' in row['text'],
        'kw_1919': lambda row: '1919' in row['text'],
        'kw_zhangyi': lambda row: '张壹' in row['text'],
        'kw_guard': lambda row: '保安' in row['text'],
        'kw_website': lambda row: '奇怪网站' in row['text'] or '网站' in row['text'],
        'kw_limb': lambda row: any(k in row['text'] for k in ('双手双脚', '手脚', '被砍')),
        'kw_runout': lambda row: any(k in row['text'] for k in ('跑出来', '跑出', '离开')),
        'kw_ten30': lambda row: '十点半' in row['text'] or '22:30' in row['text'],
        'kw_similar': lambda row: '长得' in row['text'] or '相似' in row['text'],
        'kw_phone': lambda row: '手机' in row['text'],
        'kw_luggage': lambda row: '行李箱' in row['text'],
        'kw_lolita_wig': lambda row: 'lo裙' in row['text'] or '假发' in row['text'],
        'any_unlock': lambda row: bool(row['any_unlock']),
        'visible_npc_3': lambda row: len(row['npcs']) == 3,
    }


def extract_features(row: dict[str, Any]) -> list[str]:
    return [name for name, fn in feature_definitions().items() if fn(row)]


def score_distribution(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {str(score): count for score, count in sorted(collections.Counter(row['score'] for row in rows).items())}


def format_counter(counter: Any) -> str:
    if not isinstance(counter, dict):
        counter = dict(counter)
    return ', '.join(f'{key} x{value}' for key, value in counter.items())


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    positives = [row for row in rows if row.get('plus40')]
    negatives = [row for row in rows if not row.get('plus40')]

    feature_rows: list[dict[str, Any]] = []
    for name in feature_definitions():
        pos_hit = sum(1 for row in positives if name in row.get('features', []))
        neg_hit = sum(1 for row in negatives if name in row.get('features', []))
        pos_rate = round(pos_hit / len(positives), 4) if positives else 0.0
        neg_rate = round(neg_hit / len(negatives), 4) if negatives else 0.0
        feature_rows.append(
            {
                'feature': name,
                'plus_hits': pos_hit,
                'plus_total': len(positives),
                'non_hits': neg_hit,
                'non_total': len(negatives),
                'plus_rate': pos_rate,
                'non_rate': neg_rate,
                'diff': round(pos_rate - neg_rate, 4),
            }
        )
    feature_rows.sort(key=lambda row: (abs(row['diff']), row['feature']), reverse=True)

    by_label: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for row in rows:
        by_label[str(row['label'])].append(row)
    label_rows = []
    for label, group in sorted(by_label.items()):
        label_rows.append(
            {
                'label': label,
                'count': len(group),
                'score_distribution': score_distribution(group),
                'evidence_distribution': dict(sorted(collections.Counter('/'.join(row['evidence_ids']) for row in group).items())),
                'reply_distribution': dict(sorted(collections.Counter(str(row['reply_count']) for row in group).items())),
            }
        )

    return {
        'row_count': len(rows),
        'plus40_count': len(positives),
        'score_distribution': score_distribution(rows),
        'feature_rows': feature_rows,
        'label_rows': label_rows,
        'plus40_samples': positives,
        'rows': rows,
    }


def render_md(data: dict[str, Any], max_features: int, max_samples: int) -> str:
    lines: list[str] = ['# Game2 Yuan Isolation', '']
    lines.append(f"Rows: `{data['row_count']}`, plus40 rows: `{data['plus40_count']}`.")
    lines.append(f"Score distribution: {format_counter(data['score_distribution'])}")
    lines.append('')
    lines.append('## Feature Association')
    lines.append('')
    lines.append('| feature | plus | non-plus | diff |')
    lines.append('| --- | ---: | ---: | ---: |')
    for row in data.get('feature_rows', [])[:max_features]:
        lines.append(
            f"| `{row['feature']}` | {row['plus_hits']}/{row['plus_total']} ({row['plus_rate']}) | "
            f"{row['non_hits']}/{row['non_total']} ({row['non_rate']}) | {row['diff']} |"
        )
    lines.append('')
    lines.append('## By Label')
    lines.append('')
    lines.append('| label | count | scores | evidence_ids | replies |')
    lines.append('| --- | ---: | --- | --- | --- |')
    for row in data.get('label_rows', []):
        lines.append(
            f"| `{row['label']}` | {row['count']} | {format_counter(row['score_distribution'])} | "
            f"{format_counter(row['evidence_distribution'])} | {format_counter(row['reply_distribution'])} |"
        )
    lines.append('')
    lines.append('## Plus40 Samples')
    lines.append('')
    lines.append('| label | match | score | npcs | evidence_ids | reply_count | features |')
    lines.append('| --- | --- | ---: | --- | --- | ---: | --- |')
    for row in data.get('plus40_samples', [])[:max_samples]:
        lines.append(
            f"| `{row['label']}` | `{row['match_id']}` | {row['score']} | "
            f"{'/'.join(row['npcs'])} | {'/'.join(row['evidence_ids'])} | {row['reply_count']} | "
            f"{', '.join(row['features'])} |"
        )
    return '\n'.join(lines) + '\n'


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--label-regex', default=r'n(549|550|551|552)[a-z]')
    parser.add_argument('--scores', nargs='*', type=int, default=[207, 247, 1407, 1607, 1647])
    parser.add_argument('--out-json', type=Path, default=OUT_JSON)
    parser.add_argument('--out-md', type=Path, default=OUT_MD)
    parser.add_argument('--max-features', type=int, default=40)
    parser.add_argument('--max-samples', type=int, default=80)
    args = parser.parse_args()

    label_regex = re.compile(args.label_regex)
    score_filter = set(args.scores)
    rows = [
        row
        for path in sorted(ROOM_DIR.glob('*/matches/*/analysis.json'))
        if (row := row_from_analysis(path, label_regex, score_filter)) is not None
    ]
    data = summarize(rows)

    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    args.out_md.write_text(render_md(data, args.max_features, args.max_samples), encoding='utf-8')
    print(
        json.dumps(
            {
                'rows': data['row_count'],
                'plus40': data['plus40_count'],
                'out_json': str(args.out_json),
                'out_md': str(args.out_md),
            },
            indent=2,
        )
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
