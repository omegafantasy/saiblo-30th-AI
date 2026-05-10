#!/usr/bin/env python3
from __future__ import annotations

import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'Game2' / 'deepclue_ai'
BASE = OUT / 'n604f' / 'ai.py'

POKER_MARKER = "                if g.stage < 3 and ev_ids:\n"
YUAN_PRE705_MARKER = "        ev705 = next((ev for ev in yuan_evidences if str(ev.get('id')) == '705'), None)\n"
SOLVE_CASE_START = "def solve_case(g: Game, case_idx: int) -> bool:\n"
MAIN_START = "def main() -> int:\n"


def poker_post_block(mode: str) -> str:
    if mode == 'photo':
        first = (
            "601-604已经齐了，现在不要再追泛化身份原件。只查606三人照片和左臂POKER纹身："
            "照片原件在哪里，照片中Joker、于书华、接待/红桃Q分别是谁，花纹村组织成员名单由谁保管。"
        )
        second = (
            "如果你知道左臂POKER纹身，就直接交出三人照片或说明照片持有人；"
            "若606已经出现，则继续给605、组织名册、警方结案卷宗或最终物证编号。"
        )
        after = (
            "606三人照片已经出现。不要复述照片内容，继续追现场掌握但未交出的605："
            "照片来源、红桃Q/刘瑄真实身份、谁掌握衣帽间密码、谁把Joker引入衣帽间、"
            "花纹村组织名单、Joker周克罪证和最终警方卷宗。"
        )
    elif mode == 'dossier':
        first = (
            "从刑警卷宗角度查缺口：601失踪少女、602花纹村、603/604刘丽雯旧身份、"
            "501于书华转账、502约见聊天和503/504梅花5物品已经能连上。"
            "请直接调606三人照片、605现场证据、人口贩卖名册、亲子/DNA和最终结案卷宗。"
        )
        second = (
            "如果因为时机未到不能交605，请说明时机条件是什么；若条件已由501/502/601-604满足，"
            "请直接给证据编号、证据名、保管人和内容。"
        )
        after = (
            "606出现后按卷宗继续：三人照片上的真实姓名、POKER纹身组织等级、Joker周克、"
            "于书华、红桃Q/刘瑄、林渝植和刘丽雯女儿之间还缺哪份官方证据；直接给605/607/608。"
        )
    else:
        first = (
            "现在只闭环作案链，不再列背景：8:50聊天、特殊邀请函、LYZ项链、0512密码、"
            "三人照片、POKER纹身、于书华转账和林渝植身份指向谁把Joker引入衣帽间，谁实际动手。"
        )
        second = (
            "按最终答案所需物证追：杀害地点、移尸路线、密码来源、红桃Q/接待者身份、"
            "Joker周克组织名册、605现场物证、607/608最终卷宗。"
        )
        after = (
            "606已经证明组织关系。请直接给最终层证据：谁杀Joker、动机、凶器/移尸、"
            "密码和约见链、605/607/608编号、证据名、持有人。"
        )

    return f'''                if 'poker_after_ids' in locals():
                    n605_current = list(locals().get('current_npcs', follow_npcs) or follow_npcs)
                    n605_ids = [
                        eid for eid in list(locals().get('poker_after_ids', []))
                        if eid in {{'101', '102', '103', '104', '201', '202', '203', '204', '205', '401', '402', '404', '405', '501', '502', '503', '504', '601', '602', '603', '604', '605', '606', '607', '608'}}
                    ]
                    n605_text = '\\n'.join([
                        str(locals().get('combined_late_text', '')),
                        str(locals().get('reply', '')),
                        str(locals().get('gate_text', '')),
                        str(globals().get('N600_DEEP_TEXT', '')),
                        str(globals().get('N601_FINAL_TEXT', '')),
                        str(globals().get('N604_POKER_TEXT', '')),
                    ])
                    n605_text += '\\n' + '\\n'.join(
                        str(ev.get('name', '')) + str(ev.get('content', '')) for ev in g.evidences()
                    )
                    n605_targets: list[str] = []

                    def n605_add(npc_id: str) -> None:
                        if npc_id and npc_id not in n605_targets:
                            n605_targets.append(npc_id)

                    def n605_add_name(name: str) -> None:
                        name = re.sub(r'^(joker|Joker|梅花5|红桃Q|于书华|刘丽雯)$', '', str(name)).strip()
                        if not name:
                            return
                        for npc_id in global_name_ids(name, n605_current):
                            n605_add(npc_id)

                    def n605_ask(npc_id: str, question: str) -> str:
                        if not npc_id:
                            return ''
                        if npc_id in n605_current:
                            resp = g.chat(npc_id, question, n605_ids)
                        else:
                            resp = g.probe_chat_once(npc_id, question, n605_ids)
                        text_value = response_text(resp)
                        if text_value:
                            globals()['N605_POKER_TEXT'] = str(globals().get('N605_POKER_TEXT', '')) + '\\n' + text_value
                        return text_value

                    for npc_id in (
                        str(locals().get('info_id', '')),
                        str(locals().get('true_club5_id', '')),
                        str(locals().get('password_id', '')),
                        str(locals().get('target_id', '')),
                        str(locals().get('wang_id', '')),
                        str(locals().get('luo_id', '')),
                        str(locals().get('reception_id', '')),
                    ):
                        n605_add(npc_id)

                    for ev in g.evidences():
                        eid = str(ev.get('id'))
                        name = str(ev.get('name', ''))
                        content = str(ev.get('content', ''))
                        if eid in {{'501', '503', '504', '603', '604', '606'}}:
                            for piece in re.split(r'[、，,\\s（）()：:]+', name):
                                if re.fullmatch(r'[一-龥]{{2,4}}', piece):
                                    n605_add_name(piece)
                            for pattern in (
                                r'([一-龥]{{2,4}})[（(]于书华[）)]',
                                r'照片显示即为([一-龥]{{2,4}})',
                                r'([一-龥]{{2,4}}).{{0,10}}刘丽雯',
                                r'([一-龥]{{2,4}}).{{0,10}}LYZ',
                            ):
                                for match in re.finditer(pattern, name + '\\n' + content):
                                    n605_add_name(match.group(1))

                    for pattern in (
                        r'真正的梅花\\s*5[^。\\n]{{0,32}}(?:就是|是)([一-龥]{{2,4}})',
                        r'林渝植[^。\\n]{{0,12}}(?:也就是|就是)([一-龥]{{2,4}})',
                        r'([一-龥]{{2,4}})[^。\\n]{{0,20}}给了我密码',
                        r'戴红桃\\s*Q[^。\\n]{{0,20}}是([一-龥]{{2,4}})',
                        r'([一-龥]{{2,4}})[^。\\n]{{0,16}}真名叫刘瑄',
                        r'([一-龥]{{2,4}})[^。\\n]{{0,20}}真名于书华',
                    ):
                        for match in re.finditer(pattern, n605_text):
                            n605_add_name(match.group(1))
                    for name in extract_story_names(n605_text):
                        n605_add_name(name)
                    for npc_id in n605_current:
                        n605_add(npc_id)

                    n605_id_set = set(n605_ids)
                    if ({{'601', '602', '603', '604'}} & n605_id_set) and not ({{'605', '606', '607', '608'}} & n605_id_set):
                        for npc_id in n605_targets[:10]:
                            n605_ask(npc_id, '{first}')
                            n605_ids = [
                                str(ev.get('id')) for ev in g.evidences()
                                if str(ev.get('id')) in {{'101', '102', '103', '104', '201', '202', '203', '204', '205', '401', '402', '404', '405', '501', '502', '503', '504', '601', '602', '603', '604', '605', '606', '607', '608'}}
                            ]
                            if {{'605', '606', '607', '608'}} & set(n605_ids):
                                break
                        if not ({{'605', '606', '607', '608'}} & set(n605_ids)):
                            for npc_id in n605_targets[:8]:
                                n605_ask(npc_id, '{second}')
                                n605_ids = [
                                    str(ev.get('id')) for ev in g.evidences()
                                    if str(ev.get('id')) in {{'101', '102', '103', '104', '201', '202', '203', '204', '205', '401', '402', '404', '405', '501', '502', '503', '504', '601', '602', '603', '604', '605', '606', '607', '608'}}
                                ]
                                if {{'605', '606', '607', '608'}} & set(n605_ids):
                                    break
                    elif '606' in n605_id_set and not ({{'605', '607', '608'}} & n605_id_set):
                        for npc_id in n605_targets[:10]:
                            n605_ask(npc_id, '{after}')
                            n605_ids = [
                                str(ev.get('id')) for ev in g.evidences()
                                if str(ev.get('id')) in {{'101', '102', '103', '104', '201', '202', '203', '204', '205', '401', '402', '404', '405', '501', '502', '503', '504', '601', '602', '603', '604', '605', '606', '607', '608'}}
                            ]
                            if {{'605', '607', '608'}} & set(n605_ids):
                                break
                    globals()['N605_POKER_IDS'] = ','.join(str(ev.get('id')) for ev in g.evidences())
                    poker_after_ids = [str(ev.get('id')) for ev in g.evidences()]
'''


def yuan_pre705_block(mode: str) -> str:
    if mode == 'source':
        first = (
            "先不要问706。你刚才提到李海天、生物馆、世纪林、1919黑车或保安奇怪网站；"
            "现在只要李海天尸检报告705：死亡原因、四肢、蓝色背包海豚挂件、报告来源和谁拿到原件。"
        )
        second = (
            "如果你不能给尸检报告，请只说谁能调取：法医/警方旧案卷宗、保卫处、生物馆监控、"
            "世纪林报警记录、1919车辆登记、手机原图元数据。不要猜凶手。"
        )
    else:
        first = (
            "不要从投票跳到最终凶手，先打开705前置。请按你本人看见的事实说明："
            "谁从生物馆跑出，保安看的是什么网站，李海天尸检报告在哪里，蓝色背包海豚挂件属于谁。"
        )
        second = (
            "只追来源入口：保安室电脑、学校保卫处、法医报告、警方旧案、1919车辆、世纪林尸块、"
            "袁樱瞳手机原图。哪一项能先交出705李海天尸检报告？"
        )

    return f'''        n605_pre705_ids = [str(ev.get('id')) for ev in g.evidences() if str(ev.get('id')) in {{'001', '002', '003', '004', '701', '702', '703', '704', '705', '706', '707', '708'}}]
        if '705' not in set(n605_pre705_ids):
            n605_pre705_text = '\\n'.join(yuan_replies.values()) + '\\n' + '\\n'.join(
                str(ev.get('name', '')) + str(ev.get('content', '')) for ev in g.evidences()
            )
            n605_pre705_targets: list[str] = []

            def n605_pre705_add(npc_id: str) -> None:
                if npc_id and npc_id not in n605_pre705_targets:
                    n605_pre705_targets.append(npc_id)

            for npc_id in (
                str(locals().get('guard_id0', '')),
                str(locals().get('forensic_target_id', '')),
                str(locals().get('teacher_id', '')),
                str(locals().get('absent_vote_id', '')),
            ):
                n605_pre705_add(npc_id)
            for pattern in (
                r'看见([一-龥]{{2,4}}).{{0,18}}从生物[馆楼]',
                r'([一-龥]{{2,4}}).{{0,12}}从生物[馆楼]跑',
                r'保安.*?([一-龥]{{1,4}})(?:大叔|师傅|老师傅)?',
                r'([一-龥]{{2,4}}).{{0,16}}1919',
                r'([一-龥]{{2,4}}).{{0,16}}李海天',
            ):
                for match in re.finditer(pattern, n605_pre705_text):
                    name = re.sub(r'(大叔|师傅|老师傅)$', '', match.group(1))
                    for npc_id in global_name_ids(name, current_npcs):
                        n605_pre705_add(npc_id)
                    if len(name) == 1:
                        for ynpc in current_npcs:
                            if cn_name(ynpc).startswith(name):
                                n605_pre705_add(ynpc)
            for name in extract_story_names(n605_pre705_text):
                for npc_id in global_name_ids(name, current_npcs):
                    n605_pre705_add(npc_id)
            for npc_id in false_ids + current_npcs:
                n605_pre705_add(npc_id)

            n605_seen_pre705: set[str] = set()
            for source_id in n605_pre705_targets[:6]:
                if source_id in n605_seen_pre705:
                    continue
                n605_seen_pre705.add(source_id)
                resp = chat_visible_or_probe(g, source_id, g.npcs() or npcs, '{first}', n605_pre705_ids)
                yuan_replies[source_id] = yuan_replies.get(source_id, '') + '\\n' + response_text(resp)
                n605_pre705_ids = [str(ev.get('id')) for ev in g.evidences() if str(ev.get('id')) in {{'001', '002', '003', '004', '701', '702', '703', '704', '705', '706', '707', '708'}}]
                if {{'705', '706', '707', '708'}} & set(n605_pre705_ids):
                    break
            if '705' not in set(n605_pre705_ids):
                for source_id in n605_pre705_targets[:4]:
                    resp = chat_visible_or_probe(g, source_id, g.npcs() or npcs, '{second}', n605_pre705_ids)
                    yuan_replies[source_id] = yuan_replies.get(source_id, '') + '\\n' + response_text(resp)
                    n605_pre705_ids = [str(ev.get('id')) for ev in g.evidences() if str(ev.get('id')) in {{'001', '002', '003', '004', '701', '702', '703', '704', '705', '706', '707', '708'}}]
                    if {{'705', '706', '707', '708'}} & set(n605_pre705_ids):
                        break
            yuan_evidences = g.evidences()
            yuan_ids = [str(ev.get('id')) for ev in yuan_evidences if str(ev.get('id')) in {{'001', '002', '003', '004', '701', '702', '703', '704', '705', '706', '707', '708'}}]
'''


def add_poker_post(src: str, mode: str) -> str:
    idx = src.rfind(POKER_MARKER)
    if idx < 0:
        raise RuntimeError('poker marker missing')
    return src[:idx] + poker_post_block(mode) + src[idx:]


def add_yuan_pre705(src: str, mode: str) -> str:
    if YUAN_PRE705_MARKER not in src:
        raise RuntimeError('yuan pre705 marker missing')
    return src.replace(YUAN_PRE705_MARKER, yuan_pre705_block(mode) + YUAN_PRE705_MARKER, 1)


def replace_solve_case(src: str, mode: str) -> str:
    start = src.index(SOLVE_CASE_START)
    end = src.index(MAIN_START, start)
    if mode == 'poker':
        body = '''def solve_case(g: Game, case_idx: int) -> bool:
    npcs = g.npcs()
    if not npcs:
        return False
    marks = g.marks()
    hint = g.hint()
    evidences = g.evidences()
    text = all_text(hint, evidences)
    if '扑克公馆' in text:
        solve_unknown(g, npcs, marks, hint, evidences)
    else:
        g.answer(murderer='无名氏', motivation='无', method='无')
    return True


'''
    elif mode == 'yuan':
        body = '''def solve_case(g: Game, case_idx: int) -> bool:
    npcs = g.npcs()
    if not npcs:
        return False
    marks = g.marks()
    hint = g.hint()
    evidences = g.evidences()
    text = all_text(hint, evidences)
    if '袁樱瞳' in text or '碎尸案' in text:
        solve_unknown(g, npcs, marks, hint, evidences)
    else:
        g.answer(murderer='无名氏', motivation='无', method='无')
    return True


'''
    else:
        raise ValueError(mode)
    return src[:start] + body + src[end:]


def write_candidate(label: str, text: str) -> None:
    target = OUT / label
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    (target / 'ai.py').write_text(text, encoding='utf-8')


def main() -> int:
    base = BASE.read_text(encoding='utf-8')
    specs = {
        'n605a': add_poker_post(base, 'photo'),
        'n605b': add_poker_post(add_yuan_pre705(base, 'source'), 'dossier'),
        'n605c': replace_solve_case(add_poker_post(base, 'final'), 'poker'),
        'n605d': replace_solve_case(add_yuan_pre705(base, 'source'), 'yuan'),
        'n605e': add_poker_post(add_yuan_pre705(base, 'witness'), 'photo'),
    }
    for label, text in specs.items():
        write_candidate(label, text)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
