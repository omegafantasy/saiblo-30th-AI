#!/usr/bin/env python3
from __future__ import annotations

import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'Game2' / 'deepclue_ai'
BASE = OUT / 'n559a' / 'ai.py'

POKER_ANCHOR = """                poker_evidences = g.evidences()
                ev_ids = [str(ev.get('id')) for ev in poker_evidences if str(ev.get('id')) in {'101', '201', '202', '203'}]
                if g.stage < 3 and ev_ids:
                    g.chat(info_id, '结合邀请函、聊天记录、宾客到达表和电脑浏览记录，死者真实身份、林渝植、梅花5之间是什么关系？', ev_ids)
                    g.evidences()
"""

MIN_MONITOR = """                poker_evidences = g.evidences()
                ev_ids = [str(ev.get('id')) for ev in poker_evidences if str(ev.get('id')) in {'101', '201', '202', '203'}]
                if reception_id:
                    g.chat(reception_id, '请直接调取扑克公馆仅有的两类监控：餐厅11:00到13:00、大门口0:00到13:00；把7:30不明身份人、8:20离开、8:50梅花5到达、12:00梅花5进餐厅、12:05离开这些记录给我。')
                    poker_evidences = g.evidences()
                if g.stage < 3 and ev_ids:
                    g.chat(info_id, '结合邀请函、聊天记录、宾客到达表和电脑浏览记录，死者真实身份、林渝植、梅花5之间是什么关系？', ev_ids)
                    g.evidences()
"""

SOLVE_CASE_BRANCH = """    if 'Rose' in text:
        solve_rose(g, npcs, marks, evidences)
    elif 'Z失踪' in text or 'F无法联络' in text:
        solve_z_script(g, npcs, evidences)
    else:
        solve_unknown(g, npcs, marks, hint, evidences)
"""


def write_candidate(label: str, text: str) -> None:
    target = OUT / label
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    (target / 'ai.py').write_text(text, encoding='utf-8')


def min_monitor(text: str) -> str:
    if POKER_ANCHOR not in text:
        raise RuntimeError('poker anchor missing')
    return text.replace(POKER_ANCHOR, MIN_MONITOR)


def isolate_poker(text: str) -> str:
    replacement = """    if '扑克公馆' in text:
        solve_unknown(g, npcs, marks, hint, evidences)
    else:
        g.answer(murderer='无名氏', motivation='无', method='无')
"""
    if SOLVE_CASE_BRANCH not in text:
        raise RuntimeError('solve_case branch missing')
    return text.replace(SOLVE_CASE_BRANCH, replacement)


def remove_extra_reception_joker(text: str) -> str:
    old = """                    if g.stage < 3:
                        g.chat(reception_id, 'Joker给你的聊天记录和宾客到达时间表在哪里？请把记录给我。')
                    if g.stage < 3:
                        g.chat(reception_id, '现在只说公馆内异常发现：死者房间电脑浏览记录、冰柜旁方形塑料盒、厨房缺失刀具分别是什么？')
"""
    new = """                    if g.stage < 3:
                        g.chat(reception_id, '现在只说公馆内异常发现：死者房间电脑浏览记录、冰柜旁方形塑料盒、厨房缺失刀具分别是什么？')
"""
    if old not in text:
        raise RuntimeError('reception joker block missing')
    return text.replace(old, new)


def main() -> int:
    base = BASE.read_text(encoding='utf-8')
    specs = {
        'n568a': min_monitor(base),
        'n568b': isolate_poker(min_monitor(base)),
        'n568c': min_monitor(remove_extra_reception_joker(base)),
    }
    for label, text in specs.items():
        write_candidate(label, text)
    print('\\n'.join(sorted(specs)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
