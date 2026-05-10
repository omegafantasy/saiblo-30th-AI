#!/usr/bin/env python3
from __future__ import annotations

import shutil
from pathlib import Path

from make_n600_candidates import add_deep_block


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'Game2' / 'deepclue_ai'
POKER_BASE = OUT / 'n600a' / 'ai.py'
FULL_BASE = OUT / 'n597e' / 'ai.py'
YUAN_OLD_BASE = OUT / 'n559a' / 'ai.py'


def poker_natural_block(mode: str) -> str:
    if mode == 'doctor':
        first = (
            '现在不要问编号。只查医生和失踪女儿：谁是刘丽雯或张壹，谁给于书华转过五十万，'
            '她的女儿是否是林渝植，心形胎记、LYZ项链、Joker和花纹村人口贩卖之间是什么关系。'
        )
        second = (
            '如果你是那名心理医生或认识她，请说明2010年前后女儿失踪、手术事故、病休复学、寻找女儿、'
            '被于书华骗钱和今天来到扑克公馆的完整经过。'
        )
    elif mode == 'missing':
        first = (
            '于书华、刘丽雯、张壹、林渝植、Joker和张子韩这条线已经串起来。请只补缺口：'
            '失踪女儿的报案记录、亲子或身份鉴定、心形胎记照片、花纹村组织名单、POKER纹身照片和谁把Joker引入衣帽间。'
        )
        second = (
            '如果还有一份材料没有交出，它应当是失踪少女/刘丽雯女儿/林渝植身份的原件。'
            '请说清它由谁保管，内容是什么，如何证明最终凶手。'
        )
    else:
        first = (
            '你就是于书华或掌握那笔五十万的人。不要装糊涂：是谁给你转账找失踪女儿，'
            '你如何利用刘丽雯/张壹寻找林渝植，Joker、花纹村人口贩卖、心形胎记和LYZ项链到底是什么关系。'
        )
        second = (
            '围绕五十万转账继续说自然案情：医生女儿失踪、于书华骗钱、Joker幕后黑手、林渝植幸存、'
            '真正梅花5到场、张子韩接待/密码和今天谁杀了Joker。'
        )

    return f'''                if 'poker_after_ids' in locals():
                    n602_current = list(locals().get('current_npcs', follow_npcs) or follow_npcs)
                    n602_ids = [
                        eid for eid in list(locals().get('poker_after_ids', []))
                        if eid in {{'101', '102', '103', '104', '201', '202', '203', '204', '205', '401', '402', '404', '501', '502', '503', '504', '601', '602', '603', '604', '605', '606', '607', '608'}}
                    ]
                    n602_text = str(globals().get('N600_DEEP_TEXT', '')) + '\\n' + str(locals().get('combined_late_text', ''))
                    n602_text += '\\n' + '\\n'.join(
                        str(ev.get('name', '')) + str(ev.get('content', '')) for ev in g.evidences()
                    )
                    n602_targets: list[str] = []

                    def n602_add(npc_id: str) -> None:
                        if npc_id and npc_id not in n602_targets:
                            n602_targets.append(npc_id)

                    def n602_ask(npc_id: str, question: str) -> str:
                        if not npc_id:
                            return ''
                        if npc_id in n602_current:
                            resp = g.chat(npc_id, question, n602_ids)
                        else:
                            resp = g.probe_chat_once(npc_id, question, n602_ids)
                        text_value = response_text(resp)
                        if text_value:
                            globals()['N602_TEXT'] = str(globals().get('N602_TEXT', '')) + '\\n' + text_value
                        return text_value

                    for npc_id in [
                        str(locals().get('info_id', '')),
                        str(locals().get('reception_id', '')),
                        str(locals().get('password_id', '')),
                    ]:
                        n602_add(npc_id)
                    for pattern in (
                        r'([一-龥]{{2,4}})（?于书华',
                        r'([一-龥]{{2,4}})[^。\\n]{{0,16}}收到[^。\\n]{{0,8}}500000',
                        r'([一-龥]{{2,4}})[^。\\n]{{0,16}}长庚医院',
                        r'([一-龥]{{2,4}})[^。\\n]{{0,16}}心理医生',
                        r'([一-龥]{{2,4}})[^。\\n]{{0,24}}给了我密码',
                        r'真正的梅花\\s*5[^。\\n]{{0,24}}([一-龥]{{2,4}})',
                    ):
                        for match in re.finditer(pattern, n602_text):
                            for npc_id in global_name_ids(match.group(1), n602_current):
                                n602_add(npc_id)
                    for cn in ('于书华', '王泽', '王科瑾', '叶青衡', '沈知遥', '刘丽雯', '张壹', '张子韩', '林渝植', '许清和'):
                        for npc_id in global_name_ids(cn, n602_current):
                            n602_add(npc_id)
                    for npc_id in n602_current:
                        n602_add(npc_id)

                    if {{'501', '502', '503', '504'}} & set(n602_ids):
                        for npc_id in n602_targets[:14]:
                            n602_ask(npc_id, '{first}')
                        n602_ids = [
                            str(ev.get('id')) for ev in g.evidences()
                            if str(ev.get('id')) in {{'101', '102', '103', '104', '201', '202', '203', '204', '205', '401', '402', '404', '501', '502', '503', '504', '601', '602', '603', '604', '605', '606', '607', '608'}}
                        ]
                        for npc_id in n602_targets[:14]:
                            n602_ask(npc_id, '{second}')
                    if {{'601', '602', '603', '604'}} & set(n602_ids):
                        for npc_id in n602_targets[:14]:
                            n602_ask(
                                npc_id,
                                '报纸、花纹村、手术事故和复学证明已经串上。继续自然说明：左臂POKER纹身、三人照片、失踪女儿身份原件、亲子鉴定、谁给密码、谁把Joker引入衣帽间、谁杀了Joker。',
                            )
                    globals()['N602_POKER_IDS'] = ','.join(str(ev.get('id')) for ev in g.evidences())
                    poker_after_ids = [str(ev.get('id')) for ev in g.evidences()]
'''


def add_poker_natural(src: str, mode: str) -> str:
    marker = "                if g.stage < 3 and ev_ids:\n"
    idx = src.rfind(marker)
    if idx < 0:
        raise RuntimeError('poker insertion marker missing')
    return src[:idx] + poker_natural_block(mode) + src[idx:]


YUAN_ONLY_SOLVE_CASE = r'''def solve_case(g: Game, case_idx: int) -> bool:
    npcs = g.npcs()
    if not npcs:
        return False
    marks = g.marks()
    hint = g.hint()
    evidences = g.evidences()
    text = all_text(hint, evidences)
    log(f'[n602] case={case_idx} npcs={sorted(npcs)} marks={marks} hint={compact(hint, 60)}')
    if '袁樱瞳' in text or '碎尸案' in text:
        solve_unknown(g, npcs, marks, hint, evidences)
    else:
        g.answer(murderer='无名氏', motivation='无', method='无')
    return True


'''


def yuan_followup_block() -> str:
    return """        yuan_ids = [str(ev.get('id')) for ev in g.evidences() if str(ev.get('id')) in {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706', '707', '708'}]
        if '705' in yuan_ids:
            ask_all('李海天尸检报告已经出现。请只说这份官方报告原件是谁给你的、为什么会在你手里、蓝色背包海豚挂件属于谁、李海天与袁樱瞳死状哪里相同哪里不同。', yuan_ids)
            ask_all('继续沿着报告来源查：保安看的奇怪网站、我口袋里的网页截图、上周日保安缺岗、生物馆跑出者、1919黑车和警方旧案卷宗之间有什么联系？', yuan_ids)
            ask_all('如果你知道下一份证据，请用自然语言说出物证名称和保管人：DNA比对、网页后台、手机照片元数据、车辆登记、蓝色背包主人、旧案卷宗或凶手作案链。', yuan_ids)
"""


def add_yuan_old_followup(src: str) -> str:
    anchor = "        ask_all('如果你知道凶手或关键隐瞒者，请直接给出名字、动机、作案过程和证据链。', yuan_ids)\n"
    if anchor not in src:
        raise RuntimeError('yuan old anchor missing')
    return src.replace(anchor, anchor + yuan_followup_block(), 1)


def replace_solve_case(src: str, replacement: str) -> str:
    start = src.index('def solve_case(g: Game, case_idx: int) -> bool:\n')
    end = src.index('def main() -> int:\n', start)
    return src[:start] + replacement + src[end:]


def replace_yuan_branch(src: str, branch_src: str) -> str:
    start = src.index("    elif '袁樱瞳' in text or '碎尸案' in text:\n")
    end = src.index("    else:\n        method = '未知'\n", start)
    bstart = branch_src.index("    elif '袁樱瞳' in text or '碎尸案' in text:\n")
    bend = branch_src.index("    else:\n        method = '未知'\n", bstart)
    return src[:start] + branch_src[bstart:bend] + src[end:]


def write_candidate(label: str, text: str) -> None:
    target = OUT / label
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    (target / 'ai.py').write_text(text, encoding='utf-8')


def main() -> int:
    poker = POKER_BASE.read_text(encoding='utf-8')
    full = add_deep_block(FULL_BASE.read_text(encoding='utf-8'))
    yuan_old = add_yuan_old_followup(YUAN_OLD_BASE.read_text(encoding='utf-8'))
    specs = {
        'n602a': add_poker_natural(poker, 'transfer'),
        'n602b': add_poker_natural(poker, 'doctor'),
        'n602c': add_poker_natural(poker, 'missing'),
        'n602d': replace_yuan_branch(add_poker_natural(full, 'transfer'), yuan_old),
        'n602e': replace_solve_case(yuan_old, YUAN_ONLY_SOLVE_CASE),
        'n602f': replace_yuan_branch(add_poker_natural(full, 'missing'), yuan_old),
    }
    for label, text in specs.items():
        write_candidate(label, text)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
