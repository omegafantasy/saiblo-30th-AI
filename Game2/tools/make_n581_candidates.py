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
                        if str(ev.get('id')) in {'101', '102', '103', '104', '201', '202', '203', '204', '205', '401', '402', '404', '501'}
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

POST_CHAIN_TAIL = """                        g.evidences()
                if g.stage < 3 and ev_ids:
                    g.chat(info_id, '结合邀请函、聊天记录、宾客到达表和电脑浏览记录，死者真实身份、林渝植、梅花5之间是什么关系？', ev_ids)
                    g.evidences()
"""

POKER_501_FOLLOWUP = """                        poker_after_ids = [str(ev.get('id')) for ev in g.evidences()]
                        if '501' in poker_after_ids:
                            rich_ids = [eid for eid in poker_after_ids if eid in {'101', '102', '103', '104', '201', '202', '203', '204', '205', '401', '402', '404', '501'}]
                            g.chat(info_id, '501匿名巨额转账和死者看诊、Joker、林渝植、人口贩卖集团之间是什么关系？请只说明可由证据确认的链路。', rich_ids)
                            if reception_id and reception_id != info_id:
                                g.chat(reception_id, '你掌握的Joker聊天记录、到达表和501匿名转账能否说明看诊、林渝植身份和人口贩卖集团同源？', rich_ids)
                if g.stage < 3 and ev_ids:
                    g.chat(info_id, '结合邀请函、聊天记录、宾客到达表和电脑浏览记录，死者真实身份、林渝植、梅花5之间是什么关系？', ev_ids)
                    g.evidences()
"""

POKER_404_FOLLOWUP = """                        poker_after_ids = [str(ev.get('id')) for ev in g.evidences()]
                        if '404' in poker_after_ids:
                            car_ids = [eid for eid in poker_after_ids if eid in {'101', '102', '103', '104', '201', '202', '203', '204', '205', '401', '402', '404', '501'}]
                            g.chat(info_id, '404车牌、7:20车辆、司机、移尸地点、后院窗户和衣帽间现场之间是什么关系？请只说明可由证据确认的链路。', car_ids)
                            if reception_id and reception_id != info_id:
                                g.chat(reception_id, '你能否用到达表、监控和404车牌解释7:20车辆、司机、移尸地点、后院窗户与衣帽间的关系？', car_ids)
                if g.stage < 3 and ev_ids:
                    g.chat(info_id, '结合邀请函、聊天记录、宾客到达表和电脑浏览记录，死者真实身份、林渝植、梅花5之间是什么关系？', ev_ids)
                    g.evidences()
"""

POKER_501_MARK = """                        poker_after_ids = [str(ev.get('id')) for ev in g.evidences()]
                        if '501' in poker_after_ids:
                            globals()['POKER_HAS_501'] = True
                if g.stage < 3 and ev_ids:
                    g.chat(info_id, '结合邀请函、聊天记录、宾客到达表和电脑浏览记录，死者真实身份、林渝植、梅花5之间是什么关系？', ev_ids)
                    g.evidences()
"""

YUAN_FIRST_ASK = "        ask_all('袁樱瞳碎尸案请完整说明：手机、凌晨1点女性尸体照片、lo裙、栗色假发、黄色行李箱、投票异常、出国名额、张朔、张壹、生物馆、世纪林、李海天、1919黑车、保安奇怪网站分别是什么线索？')\n"

YUAN_705_FIRST_ASK = "        ask_all('先只围绕跨线索说明：李海天尸检报告、海豚挂件、501匿名转账、人口贩卖、1919黑车和生物馆分别与袁樱瞳碎尸案有什么关系？')\n"

YUAN_BRANCH_START = """    elif '袁樱瞳' in text or '碎尸案' in text:
        yuan_replies: dict[str, str] = {}
        def ask_all(question: str, evidences_arg: list[str] | None = None) -> None:
            for ynpc in (g.npcs() or npcs):
                resp = g.chat(ynpc, question, evidences_arg)
                yuan_replies[ynpc] = yuan_replies.get(ynpc, '') + '\\n' + response_text(resp)
"""

YUAN_501_META_PREFIX = """    elif '袁樱瞳' in text or '碎尸案' in text:
        yuan_replies: dict[str, str] = {}
        def ask_all(question: str, evidences_arg: list[str] | None = None) -> None:
            for ynpc in (g.npcs() or npcs):
                resp = g.chat(ynpc, question, evidences_arg)
                yuan_replies[ynpc] = yuan_replies.get(ynpc, '') + '\\n' + response_text(resp)
        if globals().get('POKER_HAS_501'):
            yuan_ids = [str(ev.get('id')) for ev in g.evidences() if str(ev.get('id')) in {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706'}]
            ask_all('李海天、袁樱瞳、Joker/人口贩卖、匿名转账是否同源？只回答是否同源和证据编号。', yuan_ids)
            g.answer(murderer='无名氏', motivation='无', method='无')
            return
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


def replace_post_tail(text: str, replacement: str) -> str:
    if POST_CHAIN_TAIL not in text:
        raise RuntimeError('post-monitor tail missing')
    return text.replace(POST_CHAIN_TAIL, replacement)


def yuan_first_705(text: str) -> str:
    if YUAN_FIRST_ASK not in text:
        raise RuntimeError('yuan first ask missing')
    return text.replace(YUAN_FIRST_ASK, YUAN_705_FIRST_ASK)


def yuan_501_meta(text: str) -> str:
    if YUAN_BRANCH_START not in text:
        raise RuntimeError('yuan branch start missing')
    return text.replace(YUAN_BRANCH_START, YUAN_501_META_PREFIX)


def main() -> int:
    base = BASE.read_text(encoding='utf-8')
    chain = post_monitor(base)
    specs = {
        'n581a': isolate_poker(replace_post_tail(chain, POKER_501_FOLLOWUP)),
        'n581b': isolate_poker(replace_post_tail(chain, POKER_404_FOLLOWUP)),
        'n581c': yuan_first_705(chain),
        'n581d': yuan_501_meta(replace_post_tail(chain, POKER_501_MARK)),
    }
    for label, text in specs.items():
        write_candidate(label, text)
    print('\\n'.join(sorted(specs)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
