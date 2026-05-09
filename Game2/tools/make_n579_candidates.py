#!/usr/bin/env python3
from __future__ import annotations

import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'Game2' / 'deepclue_ai'
BASE = OUT / 'n568c' / 'ai.py'

SOLVE_CASE_BRANCH = """    if 'Rose' in text:
        solve_rose(g, npcs, marks, evidences)
    elif 'Z失踪' in text or 'F无法联络' in text:
        solve_z_script(g, npcs, evidences)
    else:
        solve_unknown(g, npcs, marks, hint, evidences)
"""

POKER_MONITOR_BLOCK = """                if reception_id:
                    g.chat(reception_id, '请直接调取扑克公馆仅有的两类监控：餐厅11:00到13:00、大门口0:00到13:00；把7:30不明身份人、8:20离开、8:50梅花5到达、12:00梅花5进餐厅、12:05离开这些记录给我。')
                    poker_evidences = g.evidences()
                if g.stage < 3 and ev_ids:
                    g.chat(info_id, '结合邀请函、聊天记录、宾客到达表和电脑浏览记录，死者真实身份、林渝植、梅花5之间是什么关系？', ev_ids)
                    g.evidences()
"""

POKER_POST_MONITOR_CHAIN = """                if reception_id:
                    g.chat(reception_id, '请直接调取扑克公馆仅有的两类监控：餐厅11:00到13:00、大门口0:00到13:00；把7:30不明身份人、8:20离开、8:50梅花5到达、12:00梅花5进餐厅、12:05离开这些记录给我。')
                    poker_evidences = g.evidences()
                    monitor_ids = [
                        str(ev.get('id'))
                        for ev in poker_evidences
                        if str(ev.get('id')) in {'101', '102', '103', '104', '201', '202', '203', '204', '205', '401', '402'}
                    ]
                    if {'401', '402'}.issubset(set(monitor_ids)) and info_id:
                        resp = g.chat(info_id, '我已经把时间线拼完整：7:30入馆和12:00餐厅里的梅花5才是真正活着的梅花5，8:50到达并死在衣帽间的是Joker伪装者。请确认真正梅花5、Joker和林渝植身份，并交出下一阶段证据。', monitor_ids)
                        reply = response_text(resp)
                        password_name = ''
                        for pattern in (
                            r'([一-龥]{2,4})已经给了我密码',
                            r'([一-龥]{2,4})给了我密码',
                            r'密码.*?([一-龥]{2,4})',
                        ):
                            m = re.search(pattern, reply)
                            if m:
                                password_name = m.group(1)
                                break
                        current_npcs = g.npcs() or follow_npcs
                        password_id = id_for_name(password_name, current_npcs) if password_name else ''
                        if password_id:
                            g.chat(password_id, '你给出的衣帽间密码是什么？请直接打开衣帽间，指出里面剩下的破绽、真正梅花5身份和下一阶段证据。', monitor_ids)
                        else:
                            g.chat(info_id, '推断过程是：402显示7:30有人提前入馆、8:20离开，8:50又有梅花5到达；401显示12:00餐厅还有梅花5活动。请直接给出衣帽间密码、血迹破绽、移尸证据和下一阶段证据。', monitor_ids)
                        g.evidences()
                if g.stage < 3 and ev_ids:
                    g.chat(info_id, '结合邀请函、聊天记录、宾客到达表和电脑浏览记录，死者真实身份、林渝植、梅花5之间是什么关系？', ev_ids)
                    g.evidences()
"""

POKER_METHOD_LINE = "        method = '凶手利用扑克公馆全员戴面具、身份混淆和场馆密室条件，在衣帽间用刀杀害并伪装死者。'\n"
ANSWER_LINE = "    g.answer(murderer=suspect, motivation='未知', method=method)\n"
FOURTH_YUAN_ASK = "        ask_all('如果你知道凶手或关键隐瞒者，请直接给出名字、动机、作案过程和证据链。', yuan_ids)\n"

CONDITIONAL_YUAN_FOURTH = """        yuan_ids = [str(ev.get('id')) for ev in g.evidences() if str(ev.get('id')) in {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706', '707', '708'}]
        if '705' in yuan_ids:
            ask_all('只围绕李海天尸检报告继续：蓝色背包海豚挂件、背部刀伤、失血死亡、肢体分离和袁樱瞳碎尸案之间哪项证据能打开下一阶段？', yuan_ids)
        else:
            ask_all('不要猜凶手。只说下一项最该查的物证：尸块DNA、手机删除记录、投票纸笔迹、行李箱来源、假发lo裙来源、1919黑车或生物馆监控。', yuan_ids)
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


def post_monitor(text: str) -> str:
    if POKER_MONITOR_BLOCK not in text:
        raise RuntimeError('monitor block missing')
    return text.replace(POKER_MONITOR_BLOCK, POKER_POST_MONITOR_CHAIN)


def monitor_answer(text: str) -> str:
    if POKER_METHOD_LINE not in text:
        raise RuntimeError('poker method anchor missing')
    if ANSWER_LINE not in text:
        raise RuntimeError('answer anchor missing')
    method = "        method = '凶手利用Joker接待、梅花5面具、7:30/8:20/8:50大门监控和12:00餐厅监控制造活着的梅花5与衣帽间死者错位；真正死亡地点不在衣帽间，之后用冰冻刀柄、方形塑料盒、厨房缺刀和强行撬动面具伪装现场。'\n"
    text = text.replace(POKER_METHOD_LINE, method)
    return text.replace(
        ANSWER_LINE,
        "    g.answer(murderer=suspect, motivation='利用梅花5与Joker身份错位、衣帽间密码和监控时间线掩盖真实死亡地点。', method=method)\n",
    )


def conditional_yuan(text: str) -> str:
    if FOURTH_YUAN_ASK not in text:
        raise RuntimeError('yuan fourth ask anchor missing')
    return text.replace(FOURTH_YUAN_ASK, CONDITIONAL_YUAN_FOURTH)


def main() -> int:
    base = BASE.read_text(encoding='utf-8')
    chain = post_monitor(base)
    specs = {
        'n579a': isolate_poker(chain),
        'n579b': chain,
        'n579c': conditional_yuan(chain),
        'n579d': isolate_poker(monitor_answer(chain)),
    }
    for label, text in specs.items():
        write_candidate(label, text)
    print('\\n'.join(sorted(specs)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
