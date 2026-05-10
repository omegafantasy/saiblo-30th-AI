#!/usr/bin/env python3
from __future__ import annotations

import shutil
from pathlib import Path

from make_n600_candidates import add_deep_block


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'Game2' / 'deepclue_ai'
POKER_BASE = OUT / 'n600a' / 'ai.py'
FULL_BASE = OUT / 'n597e' / 'ai.py'


def poker_605_block(mode: str) -> str:
    if mode == 'liaison':
        first = (
            '现在只查红桃Q/刘瑄/张朔这条线：她为什么负责接待和联络，密码从哪里来，'
            '她怎样把Joker引入衣帽间，她与周克、于书华、POKER纹身组织和林渝植失踪案是什么关系。'
        )
        second = (
            '如果张朔真名刘瑄并负责联络，请直接交出她的组织档案、密码记录、聊天原件、衣帽间约见记录、'
            'Joker周克入场记录和能够证明谁杀Joker的那份现场证据。'
        )
    elif mode == 'identity':
        first = (
            '现在只查刘丽雯女儿/林渝植身份原件：失踪报案、亲子鉴定、心形胎记医疗记录、完整档案、'
            'LYZ项链来源、2010失踪少女名单和Joker周克人口贩卖名册。'
        )
        second = (
            '如果缺的那份证据在现场，请不要再说时机未到；直接说明保管人、物证名称、内容，'
            '以及它如何证明真正梅花5、刘丽雯女儿和最终凶手。'
        )
    else:
        first = (
            '你刚才说605已经在现场掌握但现在不是交出的时候。现在请直接交出这份证据：'
            '它到底是刘丽雯女儿失踪报案、亲子鉴定、林渝植档案、心形胎记医疗记录、红桃Q/刘瑄联络档案、'
            'Joker周克名册，还是衣帽间密码/约见记录？'
        )
        second = (
            '不要再等待时机。请按一份物证说清605的名称、保管人、内容、指向的真实姓名、'
            '它如何解释张朔/刘瑄、于书华、Joker周克、林渝植和谁杀了Joker。'
        )

    return f'''                if 'poker_after_ids' in locals():
                    n603_current = list(locals().get('current_npcs', follow_npcs) or follow_npcs)
                    n603_ids = [
                        eid for eid in list(locals().get('poker_after_ids', []))
                        if eid in {{'101', '102', '103', '104', '201', '202', '203', '204', '205', '401', '402', '404', '501', '502', '503', '504', '601', '602', '603', '604', '605', '606', '607', '608'}}
                    ]
                    n603_text = str(globals().get('N600_DEEP_TEXT', '')) + '\\n' + str(locals().get('combined_late_text', ''))
                    n603_text += '\\n' + str(globals().get('N601_FINAL_TEXT', '')) + '\\n' + str(globals().get('N602_TEXT', ''))
                    n603_text += '\\n' + '\\n'.join(
                        str(ev.get('name', '')) + str(ev.get('content', '')) for ev in g.evidences()
                    )
                    n603_targets: list[str] = []

                    def n603_add(npc_id: str) -> None:
                        if npc_id and npc_id not in n603_targets:
                            n603_targets.append(npc_id)

                    def n603_ask(npc_id: str, question: str) -> str:
                        if not npc_id:
                            return ''
                        if npc_id in n603_current:
                            resp = g.chat(npc_id, question, n603_ids)
                        else:
                            resp = g.probe_chat_once(npc_id, question, n603_ids)
                        text_value = response_text(resp)
                        if text_value:
                            globals()['N603_TEXT'] = str(globals().get('N603_TEXT', '')) + '\\n' + text_value
                        return text_value

                    for npc_id in [
                        str(locals().get('info_id', '')),
                        str(locals().get('reception_id', '')),
                        str(locals().get('password_id', '')),
                    ]:
                        n603_add(npc_id)
                    for pattern in (
                        r'红桃\\s*Q[^。\\n]{{0,12}}是([一-龥]{{2,4}})',
                        r'戴红桃\\s*Q\\s*的是([一-龥]{{2,4}})',
                        r'([一-龥]{{2,4}})[^。\\n]{{0,12}}真名叫刘瑄',
                        r'([一-龥]{{2,4}})[^。\\n]{{0,20}}知道密码',
                        r'([一-龥]{{2,4}})[^。\\n]{{0,20}}给了我密码',
                        r'([一-龥]{{2,4}})（?于书华',
                        r'真正的梅花\\s*5[^。\\n]{{0,24}}([一-龥]{{2,4}})',
                    ):
                        for match in re.finditer(pattern, n603_text):
                            for npc_id in global_name_ids(match.group(1), n603_current):
                                n603_add(npc_id)
                    for name in extract_story_names(n603_text):
                        for npc_id in global_name_ids(name, n603_current):
                            n603_add(npc_id)
                    for cn in ('张朔', '张子韩', '刘瑄', '于书华', '刘丽雯', '林渝植', '王科瑾', '许清和', '陆亦初', '周林君'):
                        for npc_id in global_name_ids(cn, n603_current):
                            n603_add(npc_id)
                    for npc_id in n603_current:
                        n603_add(npc_id)

                    if {{'601', '602', '603', '604', '606'}} & set(n603_ids):
                        for npc_id in n603_targets[:18]:
                            n603_ask(npc_id, '{first}')
                        n603_ids = [
                            str(ev.get('id')) for ev in g.evidences()
                            if str(ev.get('id')) in {{'101', '102', '103', '104', '201', '202', '203', '204', '205', '401', '402', '404', '501', '502', '503', '504', '601', '602', '603', '604', '605', '606', '607', '608'}}
                        ]
                        for npc_id in n603_targets[:18]:
                            n603_ask(npc_id, '{second}')
                    globals()['N603_POKER_IDS'] = ','.join(str(ev.get('id')) for ev in g.evidences())
                    poker_after_ids = [str(ev.get('id')) for ev in g.evidences()]
'''


LIAISON_ANSWER_PATCH = """    final_mode = str(globals().get('N603_ANSWER_MODE', ''))
    if final_mode == 'liaison':
        final_text = str(globals().get('N603_TEXT', '')) + '\\n' + str(globals().get('N600_DEEP_TEXT', ''))
        final_ids = str(globals().get('N603_POKER_IDS', '')) + ',' + str(globals().get('N600_POKER_IDS', ''))
        liaison = ''
        for pattern in (
            r'戴红桃\\s*Q\\s*的是([一-龥]{2,4})',
            r'([一-龥]{2,4})[^。\\n]{0,12}真名叫刘瑄',
            r'([一-龥]{2,4})[^。\\n]{0,20}知道密码',
        ):
            match = re.search(pattern, final_text)
            if match:
                liaison = match.group(1)
                break
        if liaison and ('606' in final_ids or '601' in final_ids):
            g.answer(
                murderer=liaison,
                motivation=f'{liaison}即红桃Q/刘瑄，是POKER组织接待与联络人，掌握密码和约见安排；为切断Joker周克、于书华、林渝植失踪案和花纹村人口贩卖线索而杀死Joker。',
                method=f'{liaison}利用接待身份、特殊邀请函、8:50梅花5与Joker聊天、衣帽间密码和面具身份混淆，把Joker周克引入衣帽间，再借刀具、移尸和LYZ随身物制造梅花5死亡假象。'
            )
            return
    g.answer(murderer=suspect, motivation='未知', method=method)
"""


def add_poker_605(src: str, mode: str) -> str:
    marker = "                if g.stage < 3 and ev_ids:\n"
    idx = src.rfind(marker)
    if idx < 0:
        raise RuntimeError('poker insertion marker missing')
    return src[:idx] + poker_605_block(mode) + src[idx:]


def add_liaison_answer(src: str) -> str:
    src = src.replace('DEBUG = False\n', "DEBUG = False\nN603_ANSWER_MODE = 'liaison'\n", 1)
    old = "    g.answer(murderer=suspect, motivation='未知', method=method)\n"
    if old not in src:
        raise RuntimeError('answer anchor missing')
    return src.replace(old, LIAISON_ANSWER_PATCH, 1)


def write_candidate(label: str, text: str) -> None:
    target = OUT / label
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    (target / 'ai.py').write_text(text, encoding='utf-8')


def main() -> int:
    poker = POKER_BASE.read_text(encoding='utf-8')
    full = add_deep_block(FULL_BASE.read_text(encoding='utf-8'))
    specs = {
        'n603a': add_poker_605(poker, 'direct'),
        'n603b': add_poker_605(poker, 'identity'),
        'n603c': add_poker_605(poker, 'liaison'),
        'n603d': add_poker_605(full, 'direct'),
        'n603e': add_liaison_answer(add_poker_605(full, 'liaison')),
        'n603f': add_liaison_answer(add_poker_605(poker, 'liaison')),
    }
    for label, text in specs.items():
        write_candidate(label, text)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
