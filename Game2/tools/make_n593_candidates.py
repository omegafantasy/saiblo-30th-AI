#!/usr/bin/env python3
from __future__ import annotations

import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'Game2' / 'deepclue_ai'
POKER_ISO_BASE = OUT / 'n579a' / 'ai.py'
POKER_FULL_BASE = OUT / 'n579b' / 'ai.py'
YUAN_FULL_BASE = OUT / 'n559a' / 'ai.py'

POST_ANCHOR = """                        g.evidences()
                if g.stage < 3 and ev_ids:
"""

SOLVE_CASE_BRANCH = """    if 'Rose' in text:
        solve_rose(g, npcs, marks, evidences)
    elif 'Z失踪' in text or 'F无法联络' in text:
        solve_z_script(g, npcs, evidences)
    else:
        solve_unknown(g, npcs, marks, hint, evidences)
"""


POKER_STAGE4_FANOUT = """                        poker_after = g.evidences()
                        poker_after_ids = [str(ev.get('id')) for ev in poker_after]
                        rich_ids = [
                            eid for eid in poker_after_ids
                            if eid in {'101', '102', '103', '104', '201', '202', '203', '204', '205', '401', '402', '404', '405', '501', '502'}
                        ]
                        current_npcs = g.npcs() or follow_npcs
                        true_club_name = ''
                        for pattern in (
                            r'现在的([一-龥]{2,4})就是她',
                            r'([一-龥]{2,4})就是她',
                            r'真正的梅花\\s*5[^，。]*[，,就是\\s]*([一-龥]{2,4})',
                            r'真正的梅花五[^，。]*[，,就是\\s]*([一-龥]{2,4})',
                        ):
                            m = re.search(pattern, reply)
                            if m:
                                true_club_name = m.group(1)
                                break
                        true_club_id = id_for_name(true_club_name, current_npcs) if true_club_name else ''
                        owner_name = ''
                        recipient_name = ''
                        for ev in poker_after:
                            ev_text = str(ev.get('name', '')) + str(ev.get('content', ''))
                            if str(ev.get('id')) == '404':
                                m = re.search(r'([一-龥]{2,4})车牌号', ev_text)
                                if m:
                                    owner_name = m.group(1)
                            if str(ev.get('id')) == '501':
                                m = re.search(r'([一-龥]{2,4})（?于书华', ev_text)
                                if m:
                                    recipient_name = m.group(1)
                        owner_id = id_for_name(owner_name, current_npcs) if owner_name else ''
                        recipient_id = id_for_name(recipient_name, current_npcs) if recipient_name else ''
                        asked_late: set[str] = set()
                        if info_id:
                            asked_late.add(info_id)
                            g.chat(info_id, '按最高层官方卷宗继续。不要复述时间线，请直接交出405或502之后的证据：真实杀害地点、移尸车辆、后备箱血迹、车内DNA/指纹、Joker手机、人口贩卖名单、转账源账户、于书华女儿胁迫或林渝植失踪案档案。', rich_ids)
                        if password_id and password_id not in asked_late:
                            asked_late.add(password_id)
                            g.chat(password_id, '你掌握衣帽间密码或0512。请只说明密码使用记录、谁开过衣帽间、死者手机/隐藏房间、真实死亡地点、移尸路线和下一份官方证据。', rich_ids)
                        if true_club_id and true_club_id not in asked_late:
                            asked_late.add(true_club_id)
                            g.chat(true_club_id, '你被指认真正梅花5/林渝植。请直接说明你、Joker、人口贩卖集团、404车辆、501转账、于书华和警方卷宗之间的下一份物证。', rich_ids)
                        if owner_id and owner_id not in asked_late:
                            asked_late.add(owner_id)
                            g.chat(owner_id, '404车牌指向你。请直接给车主/司机、车钥匙、行车记录仪、后备箱血迹、车内DNA、轮胎痕、停车记录、后院窗户和移尸路线证据。', rich_ids)
                        if recipient_id and recipient_id not in asked_late:
                            asked_late.add(recipient_id)
                            g.chat(recipient_id, '501转账指向你或于书华。请直接给看诊记录、转账源账户、银行流水、女儿胁迫、Joker勒索、人口贩卖名单和林渝植失踪档案。', rich_ids)
                        if reception_id and reception_id not in asked_late:
                            asked_late.add(reception_id)
                            g.chat(reception_id, '从接待和场馆角度补最后一层：门锁/密码、厨房冰柜、后院窗户、清洁路线、车停靠点、Joker手机和人口贩卖名单在哪里。', rich_ids)
                        poker_after_ids = [str(ev.get('id')) for ev in g.evidences()]
                        if '404' in poker_after_ids:
                            globals()['POKER_HAS_404'] = True
                        if '501' in poker_after_ids:
                            globals()['POKER_HAS_501'] = True
                if g.stage < 3 and ev_ids:
"""


Y_705_STAGE2_ISO = """    elif '袁樱瞳' in text or '碎尸案' in text:
        current_npcs = g.npcs() or npcs
        current_marks = g.marks() or marks
        true_ids = [npc for npc in current_npcs if current_marks.get(npc) is True]
        false_ids = [npc for npc in current_npcs if current_marks.get(npc) is False]
        ordered = true_ids + false_ids + [npc for npc in current_npcs if npc not in true_ids + false_ids]
        replies: dict[str, str] = {}
        def ask(npc: str, question: str, evidences_arg: list[str] | None = None) -> None:
            resp = g.chat(npc, question, evidences_arg)
            replies[npc] = replies.get(npc, '') + '\\n' + response_text(resp)
        for ynpc in ordered:
            ask(ynpc, '先按证据来源说清楚：袁樱瞳手机、投票原件、1919黑车、生物馆十点半、保安网页、世纪林尸块、李海天尸检报告、蓝色背包海豚挂件分别是谁亲眼看到或保管。')
        yuan_evidences = g.evidences()
        yuan_ids = [str(ev.get('id')) for ev in yuan_evidences if str(ev.get('id')) in {'001', '703', '704', '705', '706', '707', '708'}]
        combined = '\\n'.join(replies.values())
        runner_name = ''
        guard_name = ''
        source_name = ''
        for pattern in (
            r'看到([一-龥]{2,4})[^。；\\n]{0,22}从生物馆',
            r'([一-龥]{2,4})[^。；\\n]{0,22}从生物馆跑出来',
        ):
            m = re.search(pattern, combined)
            if m:
                runner_name = m.group(1)
                break
        m_guard = re.search(r'保安([一-龥]{2,4})', combined)
        if m_guard:
            guard_name = m_guard.group(1)
        for ev in yuan_evidences:
            if str(ev.get('id')) == '705':
                m = re.search(r'([一-龥]{2,4})处获得的官方尸检报告', str(ev.get('content', '')))
                if m:
                    source_name = m.group(1)
                break
        target_ids: list[str] = []
        for name in (source_name, runner_name, guard_name):
            npc_id = id_for_name(name, current_npcs) if name else ''
            if npc_id and npc_id not in target_ids:
                target_ids.append(npc_id)
        if '705' in yuan_ids and target_ids:
            for npc_id in target_ids:
                ask(npc_id, '705李海天尸检报告已经出现。请不要复述死状，直接给706或下一阶段来源：尸检原件、DNA比对、海豚挂件来源、蓝色背包主人、生物馆监控、1919车辆登记、保安网页日志或警方旧案卷宗。', yuan_ids)
        elif '705' in yuan_ids:
            for ynpc in ordered:
                ask(ynpc, '705李海天尸检报告已经出现。谁能继续提供706：DNA、海豚挂件、蓝色背包、生物馆监控、1919车、保安网页、世纪林旧案或警方卷宗？', yuan_ids)
        else:
            for ynpc in ordered:
                ask(ynpc, '当前缺705/706。请直接说李海天尸检报告、海豚挂件、蓝色背包、DNA、生物馆监控、1919车辆登记、保安网页日志或世纪林旧案卷宗由谁保管。', yuan_ids)
        g.answer(murderer='无名氏', motivation='无', method='无')
        return
"""


Y_705_CROSS_FULL = """    elif '袁樱瞳' in text or '碎尸案' in text:
        current_npcs = g.npcs() or npcs
        current_marks = g.marks() or marks
        true_ids = [npc for npc in current_npcs if current_marks.get(npc) is True]
        false_ids = [npc for npc in current_npcs if current_marks.get(npc) is False]
        ordered = true_ids + false_ids + [npc for npc in current_npcs if npc not in true_ids + false_ids]
        poker_late = bool(globals().get('POKER_HAS_404') or globals().get('POKER_HAS_501'))
        replies: dict[str, str] = {}
        def ask(npc: str, question: str, evidences_arg: list[str] | None = None) -> None:
            resp = g.chat(npc, question, evidences_arg)
            replies[npc] = replies.get(npc, '') + '\\n' + response_text(resp)
        if poker_late:
            for ynpc in ordered:
                ask(ynpc, '另一案已经出现404车辆或501转账。请只判断袁樱瞳、李海天、1919黑车、生物馆、保安网页、Joker、人口贩卖、匿名转账是否同一隐藏链，以及下一份官方证据在哪里。')
        else:
            for ynpc in ordered:
                ask(ynpc, '袁樱瞳案先按官方来源拆：手机、投票纸、1919黑车、生物馆十点半、保安网页、世纪林尸块、李海天尸检、海豚挂件分别由谁提供。')
        yuan_evidences = g.evidences()
        yuan_ids = [str(ev.get('id')) for ev in yuan_evidences if str(ev.get('id')) in {'001', '703', '704', '705', '706', '707', '708'}]
        combined = '\\n'.join(replies.values())
        runner_name = ''
        guard_name = ''
        source_name = ''
        for pattern in (
            r'看到([一-龥]{2,4})[^。；\\n]{0,22}从生物馆',
            r'([一-龥]{2,4})[^。；\\n]{0,22}从生物馆跑出来',
        ):
            m = re.search(pattern, combined)
            if m:
                runner_name = m.group(1)
                break
        m_guard = re.search(r'保安([一-龥]{2,4})', combined)
        if m_guard:
            guard_name = m_guard.group(1)
        for ev in yuan_evidences:
            if str(ev.get('id')) == '705':
                m = re.search(r'([一-龥]{2,4})处获得的官方尸检报告', str(ev.get('content', '')))
                if m:
                    source_name = m.group(1)
                break
        target_ids: list[str] = []
        for name in (source_name, runner_name, guard_name):
            npc_id = id_for_name(name, current_npcs) if name else ''
            if npc_id and npc_id not in target_ids:
                target_ids.append(npc_id)
        if target_ids:
            for npc_id in target_ids:
                ask(npc_id, '你是当前隐藏链关键来源。请直接给706或之后证据：DNA比对、手机照片元数据、生物馆门禁/监控、保安网页日志、1919车辆登记、尸检原件、海豚挂件来源，或连接Joker人口贩卖/501转账的官方材料。', yuan_ids)
        else:
            for ynpc in ordered:
                ask(ynpc, '当前不要给凶手结论，只找706来源：DNA、手机元数据、生物馆监控、保安网页日志、1919车、尸检原件、海豚挂件、人口贩卖名单或转账源账户。', yuan_ids)
        g.answer(murderer='无名氏', motivation='无', method='无')
        return
"""


def write_candidate(label: str, text: str) -> None:
    target = OUT / label
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    (target / 'ai.py').write_text(text, encoding='utf-8')


def insert_poker_block(text: str, block: str) -> str:
    if POST_ANCHOR not in text:
        raise RuntimeError('post-monitor anchor missing')
    return text.replace(POST_ANCHOR, block)


def replace_yuan_branch(text: str, branch: str) -> str:
    start = text.index("    elif '袁樱瞳' in text or '碎尸案' in text:\n")
    end = text.index("    else:\n        method = '未知'\n", start)
    return text[:start] + branch + text[end:]


def isolate_yuan(text: str) -> str:
    replacement = """    if '袁樱瞳' in text or '碎尸案' in text:
        solve_unknown(g, npcs, marks, hint, evidences)
    else:
        g.answer(murderer='无名氏', motivation='无', method='无')
"""
    if SOLVE_CASE_BRANCH not in text:
        raise RuntimeError('solve_case branch missing')
    return text.replace(SOLVE_CASE_BRANCH, replacement)


def main() -> int:
    poker_iso = POKER_ISO_BASE.read_text(encoding='utf-8')
    poker_full = POKER_FULL_BASE.read_text(encoding='utf-8')
    yuan_full = YUAN_FULL_BASE.read_text(encoding='utf-8')
    specs = {
        'n593a': insert_poker_block(poker_iso, POKER_STAGE4_FANOUT),
        'n593b': insert_poker_block(poker_full, POKER_STAGE4_FANOUT),
        'n593c': isolate_yuan(replace_yuan_branch(yuan_full, Y_705_STAGE2_ISO)),
        'n593d': replace_yuan_branch(insert_poker_block(poker_full, POKER_STAGE4_FANOUT), Y_705_CROSS_FULL),
    }
    for label, text in specs.items():
        write_candidate(label, text)
    print('\\n'.join(sorted(specs)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
