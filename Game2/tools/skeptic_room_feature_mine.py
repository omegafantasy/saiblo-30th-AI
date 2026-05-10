#!/usr/bin/env python3
from __future__ import annotations

import collections
import json
import math
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ROOM_DIR = ROOT / 'Game2' / 'runtime' / 'room_matches'
OUT_JSON = ROOT / 'docs' / 'generated' / 'game2_skeptic_room_feature_mine.json'
OUT_MD = ROOT / 'docs' / 'generated' / 'game2_skeptic_room_feature_mine.md'


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return None


def compact(value: Any, limit: int = 90) -> str:
    text = re.sub(r'\s+', ' ', str(value or '')).strip()
    return text[:limit]


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


def run_label_from_path(path: Path) -> str:
    room = path.parents[2].name
    return room.rsplit('_room', 1)[0].split('_', 2)[-1]


def record_state(record: Any) -> dict[str, Any]:
    if not isinstance(record, dict):
        return {}
    state = record.get('result_state')
    if isinstance(state, dict):
        return state
    return record


def record_hint(record: Any) -> str:
    state = record_state(record)
    hint = state.get('hint')
    return str(hint) if isinstance(hint, str) else ''


def record_stage(record: Any) -> int | None:
    state = record_state(record)
    stage = state.get('stage')
    return stage if isinstance(stage, int) else None


def record_reply(record: Any) -> str:
    if isinstance(record, dict) and isinstance(record.get('reply'), str):
        return str(record.get('reply'))
    interaction = record.get('interaction') if isinstance(record, dict) else {}
    if not isinstance(interaction, dict):
        return ''
    reply = interaction.get('npc_reply')
    if isinstance(reply, dict) and isinstance(reply.get('content'), str):
        return str(reply.get('content'))
    return ''


def evidence_ids(record: Any) -> list[str]:
    state = record_state(record)
    ids: list[str] = []
    visible = state.get('visible_evidences')
    if isinstance(visible, list):
        ids.extend(str(item) for item in visible)
    evidences = state.get('evidences')
    if isinstance(evidences, list):
        for item in evidences:
            if isinstance(item, dict) and item.get('id') is not None:
                ids.append(str(item.get('id')))
    return sorted(set(ids))


def is_case_start(record: Any) -> bool:
    if not isinstance(record, dict):
        return False
    state = record.get('result_state')
    if not isinstance(state, dict):
        return False
    return record.get('step_id') == 0 and isinstance(state.get('hint'), str)


def split_segments(records: list[Any]) -> list[list[Any]]:
    starts = [index for index, record in enumerate(records) if is_case_start(record)]
    segments: list[list[Any]] = []
    for pos, start in enumerate(starts):
        end = starts[pos + 1] if pos + 1 < len(starts) else len(records)
        segments.append(records[start:end])
    return segments


def marks_from_segment(segment: list[Any]) -> tuple[list[str], list[str], list[str]]:
    if not segment:
        return [], [], []
    state = record_state(segment[0])
    visible = [str(item) for item in state.get('visible_npcs', []) if isinstance(item, str)]
    true_marks = [str(item) for item in state.get('npc_marks', []) if isinstance(item, str)]
    false_marks = sorted(set(visible) - set(true_marks))
    return sorted(visible), sorted(true_marks), false_marks


def segment_kind(segment: list[Any], index: int) -> str:
    hint = record_hint(segment[0]) if segment else ''
    if 'Rose' in hint:
        return 'rose'
    if 'Z' in hint or 'F' in hint or '宿舍' in hint or 'U盘' in hint:
        return 'zf'
    if '信息来源' in hint or '扑克公馆' in hint or '梅花' in hint:
        return 'poker'
    if '袁樱瞳' in hint or '碎尸' in hint or '课程展示' in hint:
        return 'yuan'
    return f'case{index}'


def max_stage(segment: list[Any]) -> int | None:
    stages = [stage for record in segment if (stage := record_stage(record)) is not None]
    return max(stages) if stages else None


def joined(items: list[str]) -> str:
    return ','.join(items)


def all_hints(segment: list[Any]) -> list[str]:
    seen: list[str] = []
    for record in segment:
        hint = record_hint(record)
        if hint and hint not in seen:
            seen.append(hint)
    return seen


def all_evidence_ids(segment: list[Any]) -> list[str]:
    ids: set[str] = set()
    for record in segment:
        ids.update(evidence_ids(record))
    return sorted(ids)


def replies(segment: list[Any]) -> list[str]:
    return [reply for record in segment if (reply := record_reply(record))]


def find_name(pattern: str, text: str) -> str:
    match = re.search(pattern, text)
    return match.group(1) if match else ''


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


def rose_answer_key(match_dir: Path) -> str:
    trace = load_json(match_dir / 'match_download.json')
    result = find_answer_result(trace) or {}
    return ''.join(f'{key[0]}{"T" if value else "F"}' for key, value in sorted(result.items()))


def add_feature(features: dict[str, str], key: str, value: Any) -> None:
    text = compact(value, 140)
    if text:
        features[key] = text


def row_from_analysis(path: Path) -> dict[str, Any] | None:
    data = load_json(path)
    if not isinstance(data, dict):
        return None
    player = first_player(data)
    score = player.get('score')
    if player.get('end_state') != 'OK' or not isinstance(score, int) or score <= 0:
        return None
    records = data.get('decoded_stdin_records')
    if not isinstance(records, list):
        records = []

    label = label_from_path(path, player)
    run_label = run_label_from_path(path)
    features: dict[str, str] = {}
    segments_by_kind: dict[str, list[Any]] = {}
    for index, segment in enumerate(split_segments(records)):
        kind = segment_kind(segment, index)
        segments_by_kind[kind] = segment
        visible, true_marks, false_marks = marks_from_segment(segment)
        hints = all_hints(segment)
        reps = replies(segment)
        add_feature(features, f'{kind}.visible', joined(visible))
        add_feature(features, f'{kind}.marks_true', joined(true_marks))
        add_feature(features, f'{kind}.marks_false', joined(false_marks))
        add_feature(features, f'{kind}.max_stage', max_stage(segment))
        add_feature(features, f'{kind}.reply_count', len(reps))
        add_feature(features, f'{kind}.evidence_ids', joined(all_evidence_ids(segment)))
        if hints:
            add_feature(features, f'{kind}.hint0', hints[0])
            add_feature(features, f'{kind}.hint_last', hints[-1])
        if reps:
            add_feature(features, f'{kind}.reply1', reps[0])
            add_feature(features, f'{kind}.reply_last', reps[-1])

    poker = segments_by_kind.get('poker', [])
    if poker:
        hints = all_hints(poker)
        reps = replies(poker)
        add_feature(features, 'poker.info_name', find_name(r'([\u4e00-\u9fff]{2,4})是个好的信息来源', hints[0] if hints else ''))
        add_feature(features, 'poker.receptionist_name', find_name(r'接待者([\u4e00-\u9fff]{2,4})知道', ' '.join(hints)))
        if len(reps) >= 2:
            add_feature(features, 'poker.info_reply_pair', ' / '.join(compact(reply, 50) for reply in reps[:2]))
        if len(reps) >= 3:
            add_feature(features, 'poker.receptionist_reply', reps[2])
            add_feature(features, 'poker.receptionist_style', classify_poker_receptionist(reps[2]))

    yuan = segments_by_kind.get('yuan', [])
    if yuan:
        visible, true_marks, false_marks = marks_from_segment(yuan)
        add_feature(features, 'yuan.suspect_guess', false_marks[0] if false_marks else '')
        reps = replies(yuan)
        if reps:
            add_feature(features, 'yuan.reply1', reps[0])

    err8_count = sum(1 for record in records if isinstance(record, dict) and "Internal Server Error: '8'" in str(record.get('error', '')))
    features['z.err8_count'] = str(err8_count)
    features['record_count'] = str(len(records))
    perf = data.get('performance') if isinstance(data.get('performance'), dict) else {}
    for key in ('sample_count', 'time_max', 'memory_max'):
        add_feature(features, f'perf.{key}', perf.get(key))

    return {
        'score': score,
        'label': label,
        'run_label': run_label,
        'base_label': base_label(label),
        'match_id': str(data.get('match_id') or path.parent.name),
        'path': str(path.relative_to(ROOT)),
        'rose_answer_key': rose_answer_key(path.parent),
        'features': features,
    }


def classify_poker_receptionist(reply: str) -> str:
    tags = []
    if '真详细' in reply:
        tags.append('detailed')
    if '真细致' in reply:
        tags.append('careful')
    if '有些急' in reply or '一下子问了太多' in reply:
        tags.append('rushed')
    if 'Joker' in reply or 'joker' in reply:
        tags.append('joker')
    if '医生' in reply:
        tags.append('doctor')
    if '电脑' in reply:
        tags.append('computer')
    if '塑料盒' in reply:
        tags.append('box')
    if '三把刀' in reply or '刀具' in reply:
        tags.append('knife')
    return '+'.join(tags) if tags else 'plain'


def mine_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(ROOM_DIR.glob('*/matches/*/analysis.json')):
        row = row_from_analysis(path)
        if row is not None:
            rows.append(row)
    return rows


def summarize_distribution(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_score = collections.Counter(row['score'] for row in rows)
    by_label: dict[str, collections.Counter[int]] = collections.defaultdict(collections.Counter)
    by_run_label: dict[str, collections.Counter[int]] = collections.defaultdict(collections.Counter)
    for row in rows:
        by_label[str(row['base_label'])][int(row['score'])] += 1
        by_run_label[str(row['run_label'])][int(row['score'])] += 1
    return {
        'total': len(rows),
        'by_score': dict(sorted(by_score.items())),
        'by_base_label': {
            label: dict(sorted(counter.items()))
            for label, counter in sorted(by_label.items())
        },
        'by_run_label': {
            label: dict(sorted(counter.items()))
            for label, counter in sorted(by_run_label.items())
        },
    }


def feature_stats(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    high = [row for row in rows if int(row['score']) == 2757]
    low = [row for row in rows if int(row['score']) < 2757]
    keys = sorted({key for row in rows for key in row['features']})
    stats: list[dict[str, Any]] = []
    for key in keys:
        high_counter = collections.Counter(row['features'].get(key, '') for row in high)
        low_counter = collections.Counter(row['features'].get(key, '') for row in low)
        values = set(high_counter) | set(low_counter)
        for value in values:
            if not value:
                continue
            h = high_counter[value]
            l = low_counter[value]
            support = h + l
            if support < 3:
                continue
            high_rate = h / max(1, len(high))
            low_rate = l / max(1, len(low))
            score = abs(math.log((h + 0.5) / (len(high) + 1)) - math.log((l + 0.5) / (len(low) + 1)))
            stats.append(
                {
                    'feature': key,
                    'value': value,
                    'high_count': h,
                    'low_count': l,
                    'support': support,
                    'high_rate': round(high_rate, 3),
                    'low_rate': round(low_rate, 3),
                    'separation': round(score, 3),
                }
            )
    stats.sort(key=lambda item: (float(item['separation']), int(item['support'])), reverse=True)
    return stats


def core_filter(row: dict[str, Any]) -> bool:
    features = row['features']
    return (
        row.get('rose_answer_key') == 'mTmTmT'
        and features.get('poker.max_stage') == '3'
        and features.get('z.err8_count') == '2'
        and int(row['score']) in {2517, 2557, 2627, 2657, 2717, 2757}
    )


def suspicious_examples(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected = [row for row in rows if int(row['score']) in {2517, 2557, 2657, 2717}]
    selected.sort(key=lambda row: (int(row['score']), str(row['label']), str(row['match_id'])))
    out = []
    for row in selected[:80]:
        features = row['features']
        out.append(
            {
                'score': row['score'],
                'label': row['label'],
                'run_label': row['run_label'],
                'match_id': row['match_id'],
                'rose': row['rose_answer_key'],
                'poker_info': features.get('poker.info_name', ''),
                'poker_receptionist': features.get('poker.receptionist_name', ''),
                'poker_style': features.get('poker.receptionist_style', ''),
                'yuan_marks_true': features.get('yuan.marks_true', ''),
                'yuan_suspect_guess': features.get('yuan.suspect_guess', ''),
                'path': row['path'],
            }
        )
    return out


def numeric_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    keys = [
        'record_count',
        'rose.reply_count',
        'zf.reply_count',
        'poker.reply_count',
        'yuan.reply_count',
        'perf.sample_count',
        'perf.time_max',
    ]
    out: dict[str, Any] = {}
    for score in sorted({int(row['score']) for row in rows}):
        group = [row for row in rows if int(row['score']) == score]
        row_out: dict[str, Any] = {'count': len(group)}
        for key in keys:
            values = []
            for row in group:
                raw = row['features'].get(key)
                if raw is None:
                    continue
                try:
                    values.append(float(raw))
                except Exception:
                    continue
            if values:
                row_out[key] = {
                    'mean': round(sum(values) / len(values), 3),
                    'min': min(values),
                    'max': max(values),
                }
        out[str(score)] = row_out
    return out


def mixed_run_labels(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for row in rows:
        groups[str(row['run_label'])].append(row)
    out: list[dict[str, Any]] = []
    for label, group in groups.items():
        scores = [int(row['score']) for row in group]
        if 2757 not in scores or not any(score < 2757 for score in scores):
            continue
        counter = dict(sorted(collections.Counter(scores).items()))
        feature_notes = []
        for key in ('rose.reply_count', 'record_count', 'poker.reply_count', 'yuan.evidence_ids'):
            low_values = collections.Counter(row['features'].get(key, '') for row in group if int(row['score']) < 2757)
            high_values = collections.Counter(row['features'].get(key, '') for row in group if int(row['score']) == 2757)
            low_common = low_values.most_common(1)[0] if low_values else ('', 0)
            high_common = high_values.most_common(1)[0] if high_values else ('', 0)
            if low_common[0] and high_common[0] and low_common[0] != high_common[0]:
                feature_notes.append(f'{key}: low {low_common[0]} / high {high_common[0]}')
        out.append(
            {
                'run_label': label,
                'count': len(group),
                'distribution': counter,
                'notes': feature_notes[:4],
            }
        )
    out.sort(key=lambda item: (sum(count for score, count in item['distribution'].items() if int(score) < 2757), item['count']), reverse=True)
    return out


def render_counter(counter: dict[Any, Any]) -> str:
    return ', '.join(f'{key} x{value}' for key, value in counter.items())


def render_md(data: dict[str, Any]) -> str:
    lines = ['# Game2 Skeptic Room Feature Mine', '']
    lines.append('This report is generated by `Game2/tools/skeptic_room_feature_mine.py` from raw room match `analysis.json` files.')
    lines.append('It is intentionally independent from the existing hand-written score-factor summary.')
    lines.append('')
    lines.append('## Scope')
    lines.append('')
    all_summary = data['all_summary']
    core_summary = data['core_summary']
    lines.append(f"- all effective room matches: `{all_summary['total']}`")
    lines.append(f"- core comparable rows: `{core_summary['total']}`")
    lines.append(f"- all score distribution: `{render_counter(all_summary['by_score'])}`")
    lines.append(f"- core score distribution: `{render_counter(core_summary['by_score'])}`")
    lines.append('')
    lines.append('Core rows require Rose all true, Poker stage3, two Z/F `KeyError(8)` records, and score in the stage3 band.')
    lines.append('')
    lines.append('## Strongest Separators')
    lines.append('')
    lines.append('| feature | value | high 2757 | lower | high_rate | lower_rate | sep |')
    lines.append('| --- | --- | ---: | ---: | ---: | ---: | ---: |')
    for item in data['core_feature_stats'][:35]:
        lines.append(
            f"| `{item['feature']}` | {compact(item['value'], 80)} | {item['high_count']} | {item['low_count']} | "
            f"{item['high_rate']} | {item['low_rate']} | {item['separation']} |"
        )
    lines.append('')
    lines.append('## Numeric Means')
    lines.append('')
    lines.append('| score | n | record_count | rose replies | poker replies | yuan replies | samples | time_max |')
    lines.append('| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |')
    for score, item in data['core_numeric_summary'].items():
        def mean_of(key: str) -> str:
            value = item.get(key)
            return str(value.get('mean')) if isinstance(value, dict) else ''

        lines.append(
            f"| {score} | {item.get('count')} | {mean_of('record_count')} | {mean_of('rose.reply_count')} | "
            f"{mean_of('poker.reply_count')} | {mean_of('yuan.reply_count')} | {mean_of('perf.sample_count')} | {mean_of('perf.time_max')} |"
        )
    lines.append('')
    lines.append('## Mixed Run Labels')
    lines.append('')
    lines.append('| run label | n | distribution | notes |')
    lines.append('| --- | ---: | --- | --- |')
    for item in data['core_mixed_run_labels'][:30]:
        notes = '; '.join(item.get('notes', []))
        lines.append(f"| `{item['run_label']}` | {item['count']} | {render_counter(item['distribution'])} | {notes} |")
    lines.append('')
    lines.append('## Lower-Score Core Examples')
    lines.append('')
    lines.append('| score | label | run | match | poker info | receptionist | style | yuan marks | yuan suspect |')
    lines.append('| ---: | --- | --- | --- | --- | --- | --- | --- | --- |')
    for row in data['core_suspicious_examples'][:40]:
        lines.append(
            f"| {row['score']} | `{row['label']}` | `{row['run_label']}` | `{row['match_id']}` | "
            f"{row['poker_info']} | {row['poker_receptionist']} | {row['poker_style']} | "
            f"{row['yuan_marks_true']} | {row['yuan_suspect_guess']} |"
        )
    lines.append('')
    lines.append('## Critical Reading')
    lines.append('')
    lines.append('- If a separator is a candidate label, it is experiment-design leakage, not a game cause.')
    lines.append('- If a separator is an NPC identity or visible set, it points to random case-instance buckets that the current summaries mostly collapse away.')
    lines.append('- If no stable non-label separator dominates, the observed 40-200 point swing should be treated as hidden scoring or unobserved answer-result variance, not a proven Poker wording issue.')
    return '\n'.join(lines) + '\n'


def main() -> int:
    rows = mine_rows()
    core_rows = [row for row in rows if core_filter(row)]
    data = {
        'all_summary': summarize_distribution(rows),
        'core_summary': summarize_distribution(core_rows),
        'core_feature_stats': feature_stats(core_rows),
        'core_numeric_summary': numeric_summary(core_rows),
        'core_mixed_run_labels': mixed_run_labels(core_rows),
        'core_suspicious_examples': suspicious_examples(core_rows),
        'rows': rows,
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    OUT_MD.write_text(render_md(data), encoding='utf-8')
    print(json.dumps({'rows': len(rows), 'core_rows': len(core_rows), 'out_json': str(OUT_JSON), 'out_md': str(OUT_MD)}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
