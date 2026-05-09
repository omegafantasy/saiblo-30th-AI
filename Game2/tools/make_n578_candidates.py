#!/usr/bin/env python3
from __future__ import annotations

import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'Game2' / 'deepclue_ai'
BASE_STAGE3 = OUT / 'n559a' / 'ai.py'
BASE_MONITOR = OUT / 'n568c' / 'ai.py'

SOLVE_CASE_BRANCH = """    if 'Rose' in text:
        solve_rose(g, npcs, marks, evidences)
    elif 'Z失踪' in text or 'F无法联络' in text:
        solve_z_script(g, npcs, evidences)
    else:
        solve_unknown(g, npcs, marks, hint, evidences)
"""

POKER_METHOD_LINE = "        method = '凶手利用扑克公馆全员戴面具、身份混淆和场馆密室条件，在衣帽间用刀杀害并伪装死者。'\n"
ANSWER_LINE = "    g.answer(murderer=suspect, motivation='未知', method=method)\n"

POKER_ANCHOR = """                poker_evidences = g.evidences()
                ev_ids = [str(ev.get('id')) for ev in poker_evidences if str(ev.get('id')) in {'101', '201', '202', '203'}]
                if g.stage < 3 and ev_ids:
                    g.chat(info_id, '结合邀请函、聊天记录、宾客到达表和电脑浏览记录，死者真实身份、林渝植、梅花5之间是什么关系？', ev_ids)
                    g.evidences()
"""

RESPONSIBILITY_PROBE = """                poker_evidences = g.evidences()
                ev_ids = [str(ev.get('id')) for ev in poker_evidences if str(ev.get('id')) in {'101', '201', '202', '203'}]
                if reception_id:
                    g.chat(reception_id, '不要重复到达表。只说明你是否隐瞒Joker身份、谁让你安排邀请函、谁提前进出公馆、谁可能伪装梅花5，以及你隐瞒这些的原因。')
                if g.stage < 3 and ev_ids:
                    g.chat(info_id, '结合邀请函、聊天记录、宾客到达表和电脑浏览记录，死者真实身份、林渝植、梅花5之间是什么关系？', ev_ids)
                    g.evidences()
"""

DOCTOR_MINIMAL_PROBE = """                poker_evidences = g.evidences()
                ev_ids = [str(ev.get('id')) for ev in poker_evidences if str(ev.get('id')) in {'101', '201', '202', '203'}]
                for p_npc in (g.npcs() or npcs):
                    if p_npc == info_id or (reception_id and p_npc == reception_id):
                        continue
                    g.chat(p_npc, '如果你接触过尸体或尸检，请只说死亡时间、背部三刀、小臂烧伤、血水稀释、冰冻刀柄和无指纹刀具这些事实。')
                    break
                if g.stage < 3 and ev_ids:
                    g.chat(info_id, '结合邀请函、聊天记录、宾客到达表和电脑浏览记录，死者真实身份、林渝植、梅花5之间是什么关系？', ev_ids)
                    g.evidences()
"""


def write_candidate(label: str, text: str) -> None:
    target = OUT / label
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    (target / 'ai.py').write_text(text, encoding='utf-8')


def isolate_poker(text: str) -> str:
    replacement = """    if '扑克公馆' in text:
        solve_unknown(g, npcs, marks, hint, evidences)
    else:
        g.answer(murderer='无名氏', motivation='无', method='无')
"""
    if SOLVE_CASE_BRANCH not in text:
        raise RuntimeError('solve_case branch missing')
    return text.replace(SOLVE_CASE_BRANCH, replacement)


def replace_poker_anchor(text: str, replacement: str) -> str:
    if POKER_ANCHOR not in text:
        raise RuntimeError('poker anchor missing')
    return text.replace(POKER_ANCHOR, replacement)


def replace_answer(text: str, mode: str) -> str:
    if POKER_METHOD_LINE not in text:
        raise RuntimeError('poker method anchor missing')
    if ANSWER_LINE not in text:
        raise RuntimeError('answer anchor missing')

    if mode == 'method_unknown':
        text = text.replace(POKER_METHOD_LINE, "        method = '未知'\n")
        return text
    if mode == 'murderer_unknown':
        return text.replace(ANSWER_LINE, "    g.answer(murderer='无名氏', motivation='未知', method=method)\n")
    if mode == 'motivation_identity':
        return text.replace(
            ANSWER_LINE,
            "    g.answer(murderer=suspect, motivation='凶手利用Joker邀请函、梅花5面具、到达表和监控时间线掩盖真实身份与死亡方式。', method=method)\n",
        )
    if mode == 'monitor_method':
        method = "        method = '凶手没有只靠衣帽间行凶，而是先利用Joker接待、梅花5面具、7:30进门与8:20离开的大门监控、12:00餐厅监控制造身份错位，再用电脑搜索冰冻刀柄、方形塑料盒和缺失厨房刀具布置死亡方式误导。'\n"
        text = text.replace(POKER_METHOD_LINE, method)
        return text.replace(
            ANSWER_LINE,
            "    g.answer(murderer=suspect, motivation='利用身份错位和监控时间线掩盖真实死者与作案过程。', method=method)\n",
        )
    raise RuntimeError(f'unknown answer mode: {mode}')


def main() -> int:
    stage3 = BASE_STAGE3.read_text(encoding='utf-8')
    monitor = BASE_MONITOR.read_text(encoding='utf-8')
    specs = {
        'n578a': isolate_poker(replace_answer(stage3, 'method_unknown')),
        'n578b': isolate_poker(replace_answer(stage3, 'murderer_unknown')),
        'n578c': isolate_poker(replace_answer(stage3, 'motivation_identity')),
        'n578d': isolate_poker(replace_answer(monitor, 'monitor_method')),
        'n578e': replace_poker_anchor(stage3, RESPONSIBILITY_PROBE),
        'n578f': replace_poker_anchor(stage3, DOCTOR_MINIMAL_PROBE),
    }
    for label, text in specs.items():
        write_candidate(label, text)
    print('\\n'.join(sorted(specs)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
