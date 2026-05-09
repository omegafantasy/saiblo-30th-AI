#!/usr/bin/env python3
from __future__ import annotations

import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'Game2' / 'deepclue_ai'
BASE = OUT / 'n559a' / 'ai.py'

SOLVE_CASE_BRANCH = """    if 'Rose' in text:
        solve_rose(g, npcs, marks, evidences)
    elif 'Z失踪' in text or 'F无法联络' in text:
        solve_z_script(g, npcs, evidences)
    else:
        solve_unknown(g, npcs, marks, hint, evidences)
"""

POKER_ANCHOR = """                poker_evidences = g.evidences()
                ev_ids = [str(ev.get('id')) for ev in poker_evidences if str(ev.get('id')) in {'101', '201', '202', '203'}]
                if g.stage < 3 and ev_ids:
                    g.chat(info_id, '结合邀请函、聊天记录、宾客到达表和电脑浏览记录，死者真实身份、林渝植、梅花5之间是什么关系？', ev_ids)
                    g.evidences()
"""

DOCTOR_PROBE = """                poker_evidences = g.evidences()
                ev_ids = [str(ev.get('id')) for ev in poker_evidences if str(ev.get('id')) in {'101', '201', '202', '203'}]
                for p_npc in (g.npcs() or npcs):
                    if p_npc == info_id or (reception_id and p_npc == reception_id):
                        continue
                    g.chat(p_npc, '如果你是医生或检查过尸体，请只说尸检事实：死亡时间、背部三刀贯穿伤、小臂烧伤、冰冻刀柄、血水稀释、无指纹刀具是否能说明真实死因。')
                if g.stage < 3 and ev_ids:
                    g.chat(info_id, '结合邀请函、聊天记录、宾客到达表和电脑浏览记录，死者真实身份、林渝植、梅花5之间是什么关系？', ev_ids)
                    g.evidences()
"""

RECEPTION_META = """                poker_evidences = g.evidences()
                ev_ids = [str(ev.get('id')) for ev in poker_evidences if str(ev.get('id')) in {'101', '201', '202', '203'}]
                if reception_id:
                    g.chat(reception_id, '除了到达表和异常发现，请只说明你是否隐瞒了Joker身份、谁让你安排邀请函、谁提前进出公馆、谁可能伪装梅花5。')
                if info_id:
                    g.chat(info_id, '你最初为什么不能公开全部信息？请只说明林渝植、Joker、梅花5、监控时间线和死者身份中哪一项还没公开。')
                if g.stage < 3 and ev_ids:
                    g.chat(info_id, '结合邀请函、聊天记录、宾客到达表和电脑浏览记录，死者真实身份、林渝植、梅花5之间是什么关系？', ev_ids)
                    g.evidences()
"""

SHORT_SELF_ANSWER = """        suspect = '死者本人'
        method = '死者本人或林渝植利用扑克公馆面具规则和梅花5身份混淆，借电脑搜索的冰冻刀柄方法、方形塑料盒、厨房缺失三刀和监控时间线，把自杀或死亡方式伪装成他杀现场。'
"""


def write_candidate(label: str, text: str) -> None:
    target = OUT / label
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    (target / 'ai.py').write_text(text, encoding='utf-8')


def replace_poker_anchor(text: str, replacement: str) -> str:
    if POKER_ANCHOR not in text:
        raise RuntimeError('poker anchor missing')
    return text.replace(POKER_ANCHOR, replacement)


def isolate_poker(text: str) -> str:
    replacement = """    if '扑克公馆' in text:
        solve_unknown(g, npcs, marks, hint, evidences)
    else:
        g.answer(murderer='无名氏', motivation='无', method='无')
"""
    if SOLVE_CASE_BRANCH not in text:
        raise RuntimeError('solve_case branch missing')
    return text.replace(SOLVE_CASE_BRANCH, replacement)


def self_answer(text: str) -> str:
    old = "        method = '凶手利用扑克公馆全员戴面具、身份混淆和场馆密室条件，在衣帽间用刀杀害并伪装死者。'\n"
    if old not in text:
        raise RuntimeError('poker method anchor missing')
    return text.replace(old, SHORT_SELF_ANSWER)


def main() -> int:
    base = BASE.read_text(encoding='utf-8')
    doctor = replace_poker_anchor(base, DOCTOR_PROBE)
    meta = replace_poker_anchor(base, RECEPTION_META)
    specs = {
        'n574a': isolate_poker(doctor),
        'n574b': doctor,
        'n574c': isolate_poker(meta),
        'n574d': isolate_poker(self_answer(base)),
    }
    for label, text in specs.items():
        write_candidate(label, text)
    print('\\n'.join(sorted(specs)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
