#!/usr/bin/env python3
from __future__ import annotations

import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'Game2' / 'deepclue_ai'
POKER_BASE = OUT / 'n597a' / 'ai.py'
FULL_BASE = OUT / 'n597e' / 'ai.py'


POKER_DEEP_BLOCK = r'''                if 'poker_after_ids' in locals():
                    deep_current = list(locals().get('current_npcs', follow_npcs) or follow_npcs)
                    deep_ids = [
                        eid for eid in list(locals().get('poker_after_ids', []))
                        if eid in {'101', '102', '103', '104', '201', '202', '203', '204', '205', '401', '402', '404', '405', '501', '502', '503', '504', '601', '602', '603', '604', '605', '606'}
                    ]
                    deep_text = str(locals().get('combined_late_text', ''))
                    deep_targets: list[str] = []

                    def add_deep(npc_id: str) -> None:
                        if npc_id and npc_id not in deep_targets:
                            deep_targets.append(npc_id)

                    def deep_ask(npc_id: str, question: str) -> str:
                        if not npc_id:
                            return ''
                        if npc_id in deep_current:
                            resp = g.chat(npc_id, question, deep_ids)
                        else:
                            resp = g.probe_chat_once(npc_id, question, deep_ids)
                        text = response_text(resp)
                        if text:
                            globals()['N600_DEEP_TEXT'] = str(globals().get('N600_DEEP_TEXT', '')) + '\n' + text
                        return text

                    for npc_id in [
                        str(locals().get('info_id', '')),
                        str(locals().get('password_id', '')),
                        str(locals().get('reception_id', '')),
                    ]:
                        add_deep(npc_id)
                    for cn in ('王科瑾', '于书华', '张子韩', '刘丽雯', '沈知遥', '叶青衡', '楚戎臻', '顾云舒', '张壹'):
                        for npc_id in global_name_ids(cn, deep_current):
                            add_deep(npc_id)
                    for npc_id in deep_current:
                        add_deep(npc_id)

                    info_deep = deep_ask(
                        str(locals().get('info_id', '')),
                        '你是景观/警方来源。不要总结时间线，直接交出501-504及后续：车主、匿名转账、死者手机里梅花5与Joker聊天、梅花5特殊邀请函、刻着LYZ的随身物、DNA/指纹和下一阶段证据。',
                    )
                    deep_text += '\n' + info_deep
                    poker_after_ids = [str(ev.get('id')) for ev in g.evidences()]
                    deep_ids = [
                        eid for eid in poker_after_ids
                        if eid in {'101', '102', '103', '104', '201', '202', '203', '204', '205', '401', '402', '404', '405', '501', '502', '503', '504', '601', '602', '603', '604', '605', '606'}
                    ]
                    deep_text += '\n' + '\n'.join(
                        str(ev.get('name', '')) + str(ev.get('content', '')) for ev in g.evidences()
                    )

                    for pattern in (
                        r'真正的梅花\s*5\s*是([一-龥]{2,4})',
                        r'医生[——-]([一-龥]{2,4})',
                        r'([一-龥]{2,4})（?于书华',
                        r'车是([一-龥]{2,4})的',
                        r'转账是([一-龥]{2,4})账户',
                    ):
                        for match in re.finditer(pattern, deep_text):
                            for npc_id in global_name_ids(match.group(1), deep_current):
                                add_deep(npc_id)
                    for cn in CN_TO_PINYIN:
                        if cn in deep_text:
                            for npc_id in global_name_ids(cn, deep_current):
                                add_deep(npc_id)

                    for npc_id in deep_targets[:16]:
                        deep_ask(
                            npc_id,
                            '501-504已经出现或即将出现。请直接给后续证据601/602/603/604/605/606：人口失踪案、人口贩卖集团、医生刘丽雯/张子韩、失踪女儿、心形胎记、LYZ项链、梅花5邀请函、Joker真实身份和最终凶手。',
                        )
                    poker_after_ids = [str(ev.get('id')) for ev in g.evidences()]
                    deep_ids = [
                        eid for eid in poker_after_ids
                        if eid in {'101', '102', '103', '104', '201', '202', '203', '204', '205', '401', '402', '404', '405', '501', '502', '503', '504', '601', '602', '603', '604', '605', '606'}
                    ]
                    if {'601', '602', '603', '604'} & set(poker_after_ids):
                        for npc_id in deep_targets[:16]:
                            deep_ask(
                                npc_id,
                                '601-604已经出现。继续追605/606或最终层：2010失踪少女、右眼角心形胎记、刘丽雯手术事故、张子韩复学、林渝植真实身份、谁把Joker引入衣帽间、谁杀死Joker、警方结案证据。',
                            )
                    globals()['N600_POKER_IDS'] = ','.join(poker_after_ids)
                    poker_after_ids = [str(ev.get('id')) for ev in g.evidences()]
'''


ANSWER_PATCH = """    answer_mode = str(globals().get('N600_ANSWER_MODE', ''))
    deep_text = str(globals().get('N600_DEEP_TEXT', ''))
    deep_ids = str(globals().get('N600_POKER_IDS', ''))
    if answer_mode in {'doctor', 'club5'} and ('601' in deep_ids or '502' in deep_ids):
        doctor_name = ''
        club5_name = ''
        for pattern in (
            r'医生[——-]([一-龥]{2,4})',
            r'([一-龥]{2,4})[^。\\n]{0,20}刘丽雯',
            r'刘丽雯[^。\\n]{0,20}(?:即为|就是)([一-龥]{2,4})',
        ):
            m = re.search(pattern, deep_text)
            if m:
                doctor_name = m.group(1)
                break
        for pattern in (
            r'真正的梅花\\s*5\\s*是([一-龥]{2,4})',
            r'梅花5[^。\\n]{0,20}(?:就是|是)([一-龥]{2,4})',
            r'([一-龥]{2,4})[^。\\n]{0,20}林渝植',
        ):
            m = re.search(pattern, deep_text)
            if m:
                club5_name = m.group(1)
                break
        if answer_mode == 'doctor' and doctor_name:
            g.answer(
                murderer=doctor_name,
                motivation=f'{doctor_name}即刘丽雯，因2010年失踪少女、心形胎记、手术事故、复学改名和寻找女儿线索与Joker人口贩卖集团相连，追查到扑克公馆后杀死或协助杀死Joker。',
                method=f'{doctor_name}利用看诊、匿名五十万转账、梅花5特殊邀请函、衣帽间0512、死者手机聊天和LYZ随身物把Joker引入衣帽间，再借面具身份混淆、刀具和移尸现场掩盖真相。'
            )
            return
        if answer_mode == 'club5' and club5_name:
            g.answer(
                murderer=club5_name,
                motivation=f'{club5_name}即林渝植/真正梅花5，是2010年人口失踪与Joker人口贩卖链的受害者或关键幸存者，为复仇并揭露Joker而来到公馆。',
                method=f'{club5_name}按Joker在手机聊天中指示8:50到达衣帽间，利用特殊邀请函、LYZ项链、面具身份混淆、0512密码和公馆空间条件杀死Joker并制造梅花5死亡假象。'
            )
            return
    g.answer(murderer=suspect, motivation='未知', method=method)
"""


def add_deep_block(text: str) -> str:
    marker = "                if g.stage < 3 and ev_ids:\n"
    idx = text.rfind(marker)
    if idx < 0:
        raise RuntimeError('poker insertion marker missing')
    return text[:idx] + POKER_DEEP_BLOCK + text[idx:]


def add_answer_mode(text: str, mode: str) -> str:
    if mode == 'default':
        return text
    src = text.replace('DEBUG = False\n', f"DEBUG = False\nN600_ANSWER_MODE = '{mode}'\n", 1)
    old = "    g.answer(murderer=suspect, motivation='未知', method=method)\n"
    if old not in src:
        raise RuntimeError('answer anchor missing')
    return src.replace(old, ANSWER_PATCH, 1)


def write_candidate(label: str, text: str) -> None:
    target = OUT / label
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    (target / 'ai.py').write_text(text, encoding='utf-8')


def main() -> int:
    poker = add_deep_block(POKER_BASE.read_text(encoding='utf-8'))
    full = add_deep_block(FULL_BASE.read_text(encoding='utf-8'))
    specs = {
        'n600a': add_answer_mode(poker, 'default'),
        'n600b': add_answer_mode(poker, 'club5'),
        'n600c': add_answer_mode(poker, 'doctor'),
        'n600d': add_answer_mode(full, 'club5'),
        'n600e': add_answer_mode(full, 'doctor'),
    }
    for label, text in specs.items():
        write_candidate(label, text)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
