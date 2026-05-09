#!/usr/bin/env python3
from __future__ import annotations

import argparse
import collections
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
IN_JSON = ROOT / 'docs' / 'generated' / 'game2_room_score_factors.json'
OUT_JSON = ROOT / 'docs' / 'generated' / 'game2_poker_residual_roles.json'
OUT_MD = ROOT / 'docs' / 'generated' / 'game2_poker_residual_roles.md'


PINYIN_TO_CN = {
    'BaiJingTing': '白井霆',
    'ChuRongZhen': '楚戎臻',
    'CuiAnYan': '崔安彦',
    'DengDaLing': '邓达岭',
    'FanMinMin': '范敏敏',
    'GuYunShu': '顾云舒',
    'JiangMuQing': '江沐青',
    'LinWanZhou': '林晚舟',
    'LuoFangChen': '罗方琛',
    'LuYiChu': '陆亦初',
    'ShenZhiYao': '沈知遥',
    'WangKeJin': '王科瑾',
    'WangZe': '王泽',
    'XiaoDingAng': '萧定昂',
    'XiaoDingGang': '萧定刚',
    'XuQingHe': '许清和',
    'YeQingHeng': '叶青衡',
    'YeWenXiao': '叶文潇',
    'ZhangShuo': '张朔',
    'ZhangYi': '张壹',
    'ZhangZiHan': '张子韩',
    'ZhaoYiCheng': '赵一橙',
    'ZhouLinJun': '周林君',
}
CN_TO_PINYIN = {cn: pinyin for pinyin, cn in PINYIN_TO_CN.items()}


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return {}


def is_current_label(row: dict[str, Any]) -> bool:
    return re.fullmatch(r'n\d+[a-z]', str(row.get('base_label') or '')) is not None


def as_int(value: Any, default: int = 0) -> int:
    return value if isinstance(value, int) else default


def rose_bucket(row: dict[str, Any]) -> str:
    index = row.get('rose_stage6_index')
    if not isinstance(index, int):
        return 'unknown'
    return 'fast' if index <= 28 else 'late'


def poker_layer(row: dict[str, Any]) -> int:
    stage = row.get('poker_stage')
    if stage == 3:
        return 100
    if stage == 2:
        return 50
    return 0


def lattice_expected(row: dict[str, Any]) -> int | None:
    if row.get('rose_answer_key') != 'mTmTmT':
        return None
    if as_int(row.get('z_err8_count')) != 2:
        return None
    if row.get('poker_stage') not in (None, 1, 2, 3):
        return None
    bucket = rose_bucket(row)
    if bucket == 'unknown':
        return None
    return 2657 + poker_layer(row) - (40 if bucket == 'late' else 0)


def result_state(record: Any) -> dict[str, Any]:
    if isinstance(record, dict) and isinstance(record.get('result_state'), dict):
        return record['result_state']
    return {}


def hint_text(record: Any) -> str:
    state = result_state(record)
    hint = state.get('hint')
    if isinstance(hint, str):
        return hint
    if isinstance(record, dict) and isinstance(record.get('hint'), str):
        return str(record.get('hint'))
    return ''


def cn_name(npc_id: str) -> str:
    return PINYIN_TO_CN.get(npc_id, npc_id)


def id_for_name(name: str, npcs: list[str]) -> str:
    direct = CN_TO_PINYIN.get(name, '')
    if direct in npcs:
        return direct
    for npc in npcs:
        if cn_name(npc) == name:
            return npc
    return ''


def normalize_marks(raw_marks: Any) -> list[str]:
    if isinstance(raw_marks, list):
        return [str(npc) for npc in raw_marks]
    if isinstance(raw_marks, dict):
        return [str(npc) for npc, value in raw_marks.items() if value]
    return []


def find_poker_segment(records: list[Any]) -> tuple[int | None, int | None]:
    start: int | None = None
    for index, record in enumerate(records):
        hint = hint_text(record)
        if '案发现场' in hint and '信息来源' in hint:
            start = index
            break
    if start is None:
        return None, None

    end: int | None = None
    for index in range(start + 1, len(records)):
        hint = hint_text(records[index])
        if not hint:
            continue
        if not ('案发现场' in hint or '接待者' in hint or '扑克' in hint):
            end = index
            break
    return start, end


def name_from_info_hint(hint: str, npcs: list[str]) -> str:
    for npc in npcs:
        name = cn_name(npc)
        if name and name in hint:
            return name
    for pattern in (
        r'([一-龥]{2,4})是个好的信息来源',
        r'([一-龥]{2,4})会是[^，。]*好的信息来源',
        r'问问([一-龥]{2,4})关于',
    ):
        match = re.search(pattern, hint)
        if match:
            return match.group(1).strip()
    return ''


def name_from_reception_hint(hint: str) -> str:
    match = re.search(r'接待者([一-龥]{2,4})知道', hint)
    return match.group(1).strip() if match else ''


def doctor_name_from_text(text: str) -> str:
    for pattern in (
        r'([一-龥]{2,3})(?:女士|先生)?似乎是(?:一名)?医生',
        r'([一-龥]{2,3})(?:女士|先生)?或许能提供[^。！？]{0,20}尸',
    ):
        match = re.search(pattern, text)
        if match and match.group(1).strip() in CN_TO_PINYIN:
            return match.group(1).strip()
    return ''


def first_reply_kind(text: str) -> str:
    if not text:
        return 'none'
    if '人口贩卖' in text:
        return 'people_group'
    if any(word in text for word in ('时机', '不能', '不行', '证据')):
        return 'withheld'
    if '聊天记录' in text and ('公馆' in text or 'Joker' in text):
        return 'chat_record'
    if '手机' in text or '随身物品' in text:
        return 'phone_items'
    return 'other'


def extract_poker(path: Path) -> dict[str, Any]:
    data = load_json(ROOT / path)
    records = data.get('decoded_stdin_records')
    if not isinstance(records, list):
        return {}
    start, end = find_poker_segment(records)
    if start is None:
        return {}

    state = result_state(records[start])
    hint = str(state.get('hint') or '')
    npcs = [str(npc) for npc in state.get('visible_npcs', [])] if isinstance(state.get('visible_npcs'), list) else []
    marks = normalize_marks(state.get('npc_marks'))
    info_name = name_from_info_hint(hint, npcs)
    info_id = id_for_name(info_name, npcs) if info_name else (marks[0] if len(marks) == 1 else '')

    segment = records[start : end if end is not None else len(records)]
    reception_name = ''
    replies: list[tuple[int | None, str]] = []
    for record in segment:
        hint = hint_text(record)
        if hint and not reception_name:
            reception_name = name_from_reception_hint(hint)
        if isinstance(record, dict) and isinstance(record.get('reply'), str):
            stage = record.get('stage')
            replies.append((stage if isinstance(stage, int) else None, str(record.get('reply'))))

    reception_id = id_for_name(reception_name, npcs) if reception_name else ''
    stage3_text = '\n'.join(reply for stage, reply in replies if stage == 3)
    doctor_name = doctor_name_from_text(stage3_text)
    doctor_id = id_for_name(doctor_name, npcs) if doctor_name else ''
    first_reply = replies[0][1] if replies else ''

    return {
        'poker_npcs': npcs,
        'poker_marks': marks,
        'poker_mark_pattern': ''.join('T' if npc in set(marks) else 'F' for npc in npcs),
        'info_name': info_name,
        'info_id': info_id,
        'info_pos': npcs.index(info_id) if info_id in npcs else None,
        'reception_name': reception_name,
        'reception_id': reception_id,
        'reception_pos': npcs.index(reception_id) if reception_id in npcs else None,
        'doctor_name': doctor_name,
        'doctor_id': doctor_id,
        'doctor_pos': npcs.index(doctor_id) if doctor_id in npcs else None,
        'poker_reply_count': len(replies),
        'poker_stage_sequence': '/'.join(str(stage) for stage, _ in replies),
        'first_reply_kind': first_reply_kind(first_reply),
        'first_has_phone': '手机' in first_reply,
        'first_has_people_group': '人口贩卖' in first_reply,
        'first_has_refusal': any(word in first_reply for word in ('时机', '不能', '不行', '证据')),
        'first_has_joker': 'Joker' in first_reply or '聊天记录' in first_reply,
    }


def score_distribution(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {str(score): count for score, count in sorted(collections.Counter(row.get('score') for row in rows).items())}


def residual_distribution(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {str(score): count for score, count in sorted(collections.Counter(row.get('residual') for row in rows).items())}


def format_counter(counter: dict[Any, int] | collections.Counter[Any]) -> str:
    return ', '.join(f'{key} x{value}' for key, value in sorted(counter.items(), key=lambda item: str(item[0])))


def breakdown(rows: list[dict[str, Any]], field: str, min_count: int) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for row in rows:
        groups[str(row.get(field))].append(row)
    output: list[dict[str, Any]] = []
    for value, group in groups.items():
        if len(group) < min_count:
            continue
        low_count = sum(1 for row in group if int(row.get('residual', 0)) < 0)
        output.append(
            {
                'field': field,
                'value': value,
                'count': len(group),
                'low_count': low_count,
                'low_rate': round(low_count / len(group), 4),
                'scores': score_distribution(group),
                'residuals': residual_distribution(group),
            }
        )
    output.sort(key=lambda row: (-row['low_rate'], -row['count'], row['value']))
    return output


def is_top_stage3(row: dict[str, Any]) -> bool:
    return (
        row.get('rose_stage6_index') == 28
        and row.get('poker_stage') == 3
        and row.get('poker_evidence_ids') == ['001', '002', '101', '102', '103', '104', '201', '202', '203', '204', '205']
        and row.get('yuan_stage') is None
        and row.get('yuan_evidence_ids') == ['001']
    )


def summarize(rows: list[dict[str, Any]], min_count: int) -> dict[str, Any]:
    fields = [
        'base_label',
        'poker_stage',
        'rose_bucket',
        'info_id',
        'reception_id',
        'doctor_id',
        'doctor_pos',
        'poker_reply_count',
        'poker_stage_sequence',
        'first_reply_kind',
        'first_has_phone',
        'first_has_people_group',
        'first_has_refusal',
        'first_has_joker',
    ]

    label_groups: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for row in rows:
        label_groups[str(row.get('base_label'))].append(row)
    label_rows: list[dict[str, Any]] = []
    for label, group in label_groups.items():
        low_count = sum(1 for row in group if int(row.get('residual', 0)) < 0)
        if low_count == 0 and len(group) < min_count:
            continue
        label_rows.append(
            {
                'label': label,
                'count': len(group),
                'low_count': low_count,
                'low_rate': round(low_count / len(group), 4),
                'scores': score_distribution(group),
                'residuals': residual_distribution(group),
            }
        )
    label_rows.sort(key=lambda row: (-row['low_rate'], -row['count'], row['label']))

    top_rows = [row for row in rows if is_top_stage3(row)]
    return {
        'source': str(IN_JSON.relative_to(ROOT)),
        'row_count': len(rows),
        'score_distribution': score_distribution(rows),
        'residual_distribution': residual_distribution(rows),
        'top_stage3_count': len(top_rows),
        'top_stage3_score_distribution': score_distribution(top_rows),
        'top_stage3_residual_distribution': residual_distribution(top_rows),
        'label_rows': label_rows,
        'breakdowns': {field: breakdown(rows, field, min_count) for field in fields},
        'top_stage3_breakdowns': {field: breakdown(top_rows, field, min_count) for field in fields},
        'low_samples': [row for row in rows if int(row.get('residual', 0)) < 0],
        'rows': rows,
    }


def render_breakdown(lines: list[str], title: str, data: list[dict[str, Any]], limit: int) -> None:
    lines.append(f'## {title}')
    lines.append('')
    lines.append('| field | value | count | low | residuals | scores |')
    lines.append('| --- | --- | ---: | ---: | --- | --- |')
    for row in data[:limit]:
        lines.append(
            f"| `{row['field']}` | `{row['value']}` | {row['count']} | "
            f"{row['low_count']} ({row['low_rate']}) | {format_counter(row['residuals'])} | {format_counter(row['scores'])} |"
        )
    lines.append('')


def render_md(data: dict[str, Any], max_rows: int) -> str:
    lines: list[str] = ['# Game2 Poker Residual Roles', '']
    lines.append(f"Source: `{data['source']}`")
    lines.append(f"Strict current-thread rows: `{data['row_count']}`")
    lines.append(f"Scores: {format_counter(data['score_distribution'])}")
    lines.append(f"Residuals: {format_counter(data['residual_distribution'])}")
    lines.append('')
    lines.append(f"Top visible stage3 rows: `{data['top_stage3_count']}`")
    lines.append(f"Top visible stage3 scores: {format_counter(data['top_stage3_score_distribution'])}")
    lines.append(f"Top visible stage3 residuals: {format_counter(data['top_stage3_residual_distribution'])}")
    lines.append('')

    lines.append('## Labels With Residual Tail')
    lines.append('')
    lines.append('| label | count | low | residuals | scores |')
    lines.append('| --- | ---: | ---: | --- | --- |')
    for row in data.get('label_rows', [])[:max_rows]:
        lines.append(
            f"| `{row['label']}` | {row['count']} | {row['low_count']} ({row['low_rate']}) | "
            f"{format_counter(row['residuals'])} | {format_counter(row['scores'])} |"
        )
    lines.append('')

    for field, rows in data.get('breakdowns', {}).items():
        render_breakdown(lines, f'All Strict Rows By {field}', rows, max_rows)

    for field, rows in data.get('top_stage3_breakdowns', {}).items():
        render_breakdown(lines, f'Top Stage3 Rows By {field}', rows, max_rows)

    lines.append('## Low Residual Samples')
    lines.append('')
    lines.append('| label | match | score | residual | info | reception | doctor | replies | first | path |')
    lines.append('| --- | --- | ---: | ---: | --- | --- | --- | ---: | --- | --- |')
    for row in data.get('low_samples', [])[:max_rows]:
        lines.append(
            f"| `{row.get('base_label')}` | `{row.get('match_id')}` | {row.get('score')} | {row.get('residual')} | "
            f"{row.get('info_id') or ''} | {row.get('reception_id') or ''} | {row.get('doctor_id') or ''} | "
            f"{row.get('poker_reply_count')} | {row.get('first_reply_kind')} | `{row.get('path')}` |"
        )
    return '\n'.join(lines) + '\n'


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', type=Path, default=IN_JSON)
    parser.add_argument('--out-json', type=Path, default=OUT_JSON)
    parser.add_argument('--out-md', type=Path, default=OUT_MD)
    parser.add_argument('--min-count', type=int, default=5)
    parser.add_argument('--max-rows', type=int, default=30)
    args = parser.parse_args()

    source = load_json(args.input)
    raw_rows = source.get('rows') if isinstance(source, dict) else []
    rows: list[dict[str, Any]] = []
    for row in raw_rows if isinstance(raw_rows, list) else []:
        if not isinstance(row, dict) or not is_current_label(row):
            continue
        expected = lattice_expected(row)
        if expected is None:
            continue
        enriched = dict(row)
        enriched['expected'] = expected
        enriched['residual'] = int(row.get('score')) - expected
        enriched['rose_bucket'] = rose_bucket(row)
        enriched.update(extract_poker(Path(str(row.get('path') or ''))))
        rows.append(enriched)

    data = summarize(rows, args.min_count)
    args.out_json.parent.mkdir(parents=True, exist_ok=True)
    args.out_json.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    args.out_md.write_text(render_md(data, args.max_rows), encoding='utf-8')
    print(
        json.dumps(
            {
                'rows': data['row_count'],
                'residuals': data['residual_distribution'],
                'top_stage3_rows': data['top_stage3_count'],
                'out_json': str(args.out_json),
                'out_md': str(args.out_md),
            },
            indent=2,
        )
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
