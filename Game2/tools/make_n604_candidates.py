#!/usr/bin/env python3
from __future__ import annotations

import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'Game2' / 'deepclue_ai'
BASE = OUT / 'sk548e0910qad' / 'ai.py'


POKER_MARKER = "                if g.stage < 3 and ev_ids:\n"
YUAN_MARKER = "        ask_all('结合现有证据重新推理袁樱瞳死亡：实际死者是谁，凌晨照片是谁，张壹传闻哪里错，生物馆和世纪林尸块如何连接？', yuan_ids)\n"
SOLVE_CASE_START = "def solve_case(g: Game, case_idx: int) -> bool:\n"
MAIN_START = "def main() -> int:\n"


def poker_question_pack(mode: str) -> tuple[str, str, str]:
    if mode == 'photo':
        return (
            '后续材料已经指向Joker周克、于书华、林渝植、刘丽雯女儿和花纹村组织。现在不要复述时间线，只查那张三人合照、左臂POKER纹身、照片原件来源、组织成员名单和现场尚未交出的原始物证；请说清证据名、保管人、内容和它如何证明谁把Joker引入衣帽间。',
            '如果三人照片或POKER纹身已经出现，请继续查照片中每个人的真实姓名、红桃Q或接待者身份、Joker周克与于书华的关系、花纹村人口贩卖名单、林渝植身份原件和最终结案卷宗。',
            '照片纹身链',
        )
    if mode == 'liaison':
        return (
            '现在只查接待和联络链：红桃Q、刘瑄、张朔、密码、特殊邀请函、8:50衣帽间约见、面具编号和Joker周克入场记录。请直接说明谁掌握密码，谁安排约见，谁把Joker引入衣帽间，现场未交原件是什么。',
            '如果张朔只是表面名字，请说出刘瑄/红桃Q的完整身份、她与Joker周克、于书华、花纹村组织、林渝植失踪案的关系，以及能证明最终凶手的原始联络记录或结案证据。',
            '联络密码链',
        )
    if mode == 'identity':
        return (
            '现在只查身份原件：刘丽雯女儿失踪报案、亲子鉴定、心形胎记医疗记录、林渝植档案、LYZ项链来源、张子韩复学和Joker人口贩卖名单。请说明哪份原件在现场已经掌握但还没有交出。',
            '如果林渝植就是刘丽雯女儿或真正梅花5，请直接给DNA/亲子/医疗/报案/警方卷宗的证据名、持有人和内容，并说明它如何闭环Joker周克、于书华和最终凶手。',
            '身份原件链',
        )
    return (
        'Poker后续不再猜凶手，只查官方结案来源：死者手机云端名单、Joker账号实名和设备、邀请函源文件、花纹村组织档案、POKER纹身照片、刘丽雯女儿身份原件、车辆/转账/DNA/指纹卷宗。请直接给下一份证据名、保管人和内容。',
        '如果某份证据已经在现场掌握但不能交，请解释不能交的条件；若条件已经满足，请交出原始物证、最终卷宗或可提交答案所需的最后一环。',
        '官方卷宗链',
    )


def poker_block(mode: str) -> str:
    first, second, label = poker_question_pack(mode)
    return f'''                if 'poker_after_ids' in locals():
                    n604_current = list(locals().get('current_npcs', follow_npcs) or follow_npcs)
                    n604_ids = [
                        eid for eid in list(locals().get('poker_after_ids', []))
                        if eid in {{'101', '102', '103', '104', '201', '202', '203', '204', '205', '401', '402', '404', '405', '501', '502', '503', '504', '601', '602', '603', '604', '605', '606', '607', '608'}}
                    ]
                    n604_text = '\\n'.join([
                        str(locals().get('combined_late_text', '')),
                        str(globals().get('N600_DEEP_TEXT', '')),
                        str(globals().get('N601_FINAL_TEXT', '')),
                    ])
                    n604_text += '\\n' + '\\n'.join(
                        str(ev.get('name', '')) + str(ev.get('content', '')) for ev in g.evidences()
                    )
                    n604_targets: list[str] = []

                    def n604_add(npc_id: str) -> None:
                        if npc_id and npc_id not in n604_targets:
                            n604_targets.append(npc_id)

                    def n604_ask(npc_id: str, question: str) -> str:
                        if not npc_id:
                            return ''
                        if npc_id in n604_current:
                            resp = g.chat(npc_id, question, n604_ids)
                        else:
                            resp = g.probe_chat_once(npc_id, question, n604_ids)
                        text_value = response_text(resp)
                        if text_value:
                            globals()['N604_POKER_TEXT'] = str(globals().get('N604_POKER_TEXT', '')) + '\\n' + text_value
                        return text_value

                    for npc_id in [
                        str(locals().get('info_id', '')),
                        str(locals().get('reception_id', '')),
                        str(locals().get('password_id', '')),
                        str(locals().get('true_club5_id', '')),
                        str(locals().get('target_id', '')),
                        str(locals().get('wang_id', '')),
                        str(locals().get('luo_id', '')),
                    ]:
                        n604_add(npc_id)
                    for pattern in (
                        r'([一-龥]{{2,4}})[^。\\n]{{0,16}}周克',
                        r'([一-龥]{{2,4}})[^。\\n]{{0,16}}刘瑄',
                        r'([一-龥]{{2,4}})[^。\\n]{{0,16}}红桃\\s*Q',
                        r'([一-龥]{{2,4}})[^。\\n]{{0,18}}给了我密码',
                        r'真正的梅花\\s*5[^。\\n]{{0,24}}([一-龥]{{2,4}})',
                        r'([一-龥]{{2,4}})[（(]于书华[）)]',
                    ):
                        for match in re.finditer(pattern, n604_text):
                            for npc_id in global_name_ids(match.group(1), n604_current):
                                n604_add(npc_id)
                    for name in extract_story_names(n604_text):
                        for npc_id in global_name_ids(name, n604_current):
                            n604_add(npc_id)
                    for cn in ('张朔', '刘瑄', '周克', 'Joker', '于书华', '王科瑾', '王泽', '张子韩', '刘丽雯', '林渝植', '许清和', '顾云舒', '沈知遥', '叶青衡', '楚戎臻'):
                        for npc_id in global_name_ids(cn, n604_current):
                            n604_add(npc_id)
                    for npc_id in n604_current:
                        n604_add(npc_id)

                    if {{'601', '602', '603', '604', '606'}} & set(n604_ids):
                        for npc_id in n604_targets[:14]:
                            n604_ask(npc_id, '{first}')
                        n604_ids = [
                            str(ev.get('id')) for ev in g.evidences()
                            if str(ev.get('id')) in {{'101', '102', '103', '104', '201', '202', '203', '204', '205', '401', '402', '404', '405', '501', '502', '503', '504', '601', '602', '603', '604', '605', '606', '607', '608'}}
                        ]
                        for npc_id in n604_targets[:14]:
                            n604_ask(npc_id, '{second}')
                    elif {{'501', '502', '503', '504'}} & set(n604_ids):
                        for npc_id in n604_targets[:10]:
                            n604_ask(npc_id, '不要停在车牌、转账或邀请函。沿着{label}继续查：Joker真实姓名、死者手机、LYZ随身物、刘丽雯女儿、花纹村组织、POKER纹身照片和现场未交原件分别由谁保管。')
                    globals()['N604_POKER_IDS'] = ','.join(str(ev.get('id')) for ev in g.evidences())
                    poker_after_ids = [str(ev.get('id')) for ev in g.evidences()]
'''


def yuan_block(mode: str) -> str:
    if mode == 'source':
        first = '705尸检报告不能再只看内容，要查来源链：报告编号、法医/警方档案室、蓝色背包海豚挂件的物证袋、世纪林尸块DNA、生物馆监控、1919车辆登记、保安网页后台和教务投票原件分别在哪；请直接给下一份证据名和持有人。'
        second = '如果你不能交出下一份证据，请只说明官方系统入口：保卫处值班和监控、警方旧案卷宗、法医DNA库、车辆登记、手机云端原图、教务后台日志、网页访问记录，哪一个能打开后续物证。'
    elif mode == 'web':
        first = '开场的失忆侦探、眼熟保安和口袋模糊网页截图应当是主线。请只查这个网站：网址、登录账号、访问日志、后台记录、保安为什么认识我、1919黑车和世纪林尸块是否被网站记录，下一份官方证据在哪里。'
        second = '不要复述投票。围绕网页截图继续查：保安室电脑、浏览历史、后台数据库、上传的尸体照片、车辆/地点记录、李海天和袁樱瞳是否同源，以及物证06之后的持有人。'
    else:
        first = '现在只查尸源和身份鉴定：袁樱瞳、凌晨照片女性、世纪林尸块、李海天尸检、蓝色背包海豚挂件、黄色行李箱和lo裙栗色假发之间的DNA/指纹/纤维/监控闭环；请直接给下一份官方证据。'
        second = '如果袁樱瞳案存在替身、尸块二次利用或死亡时间伪造，请给手机原图元数据、尸源鉴定、行李箱维修记录、宿舍/生物馆监控、1919车辆路线和官方物证持有人。'
    return f'''        n604_yuan_ids = [str(ev.get('id')) for ev in g.evidences() if str(ev.get('id')) in {{'001', '002', '003', '004', '701', '702', '703', '704', '705', '706', '707', '708'}}]
        n604_yuan_text = '\\n'.join(yuan_replies.values()) + '\\n' + '\\n'.join(
            str(ev.get('name', '')) + str(ev.get('content', '')) for ev in g.evidences()
        )
        n604_yuan_targets: list[str] = []

        def n604_yuan_add(npc_id: str) -> None:
            if npc_id and npc_id not in n604_yuan_targets:
                n604_yuan_targets.append(npc_id)

        for npc_id in list(locals().get('post705_targets', [])):
            n604_yuan_add(npc_id)
        for npc_id in [
            str(locals().get('guard_id', '')),
            str(locals().get('runner_id', '')),
            str(locals().get('teacher_id', '')),
            str(locals().get('forensic_target_id', '')),
            str(locals().get('absent_vote_id', '')),
        ]:
            n604_yuan_add(npc_id)
        for pattern in (
            r'看见([一-龥]{{2,4}}).{{0,18}}从生物馆',
            r'保安.*?([一-龥]{{1,4}})(?:大叔|师傅|老师傅)?',
            r'([一-龥]{{2,4}})处获得',
            r'([一-龥]{{2,4}}).{{0,16}}海豚挂件',
            r'([一-龥]{{2,4}}).{{0,16}}1919',
        ):
            for match in re.finditer(pattern, n604_yuan_text):
                for npc_id in global_name_ids(re.sub(r'(大叔|师傅|老师傅)$', '', match.group(1)), current_npcs):
                    n604_yuan_add(npc_id)
        for name in extract_story_names(n604_yuan_text):
            for npc_id in global_name_ids(name, current_npcs):
                n604_yuan_add(npc_id)
        for npc_id in false_ids + current_npcs:
            n604_yuan_add(npc_id)

        if '706' not in set(n604_yuan_ids):
            n604_seen: set[str] = set()
            for source_id in n604_yuan_targets[:10]:
                if not source_id or source_id in n604_seen:
                    continue
                n604_seen.add(source_id)
                resp = chat_visible_or_probe(g, source_id, g.npcs() or npcs, '{first}', n604_yuan_ids)
                yuan_replies[source_id] = yuan_replies.get(source_id, '') + '\\n' + response_text(resp)
                n604_yuan_ids = [str(ev.get('id')) for ev in g.evidences() if str(ev.get('id')) in {{'001', '002', '003', '004', '701', '702', '703', '704', '705', '706', '707', '708'}}]
                if {{'706', '707', '708'}} & set(n604_yuan_ids):
                    break
            if not ({{'706', '707', '708'}} & set(n604_yuan_ids)):
                for source_id in n604_yuan_targets[:6]:
                    resp = chat_visible_or_probe(g, source_id, g.npcs() or npcs, '{second}', n604_yuan_ids)
                    yuan_replies[source_id] = yuan_replies.get(source_id, '') + '\\n' + response_text(resp)
                    n604_yuan_ids = [str(ev.get('id')) for ev in g.evidences() if str(ev.get('id')) in {{'001', '002', '003', '004', '701', '702', '703', '704', '705', '706', '707', '708'}}]
                    if {{'706', '707', '708'}} & set(n604_yuan_ids):
                        break
        yuan_ids = n604_yuan_ids
'''


def add_poker(src: str, mode: str) -> str:
    if POKER_MARKER not in src:
        raise RuntimeError('Poker marker missing')
    return src.replace(POKER_MARKER, poker_block(mode) + POKER_MARKER, 1)


def add_yuan(src: str, mode: str) -> str:
    if YUAN_MARKER not in src:
        raise RuntimeError('Yuan marker missing')
    return src.replace(YUAN_MARKER, yuan_block(mode) + YUAN_MARKER, 1)


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
        'n604a': add_poker(base, 'photo'),
        'n604b': add_poker(base, 'liaison'),
        'n604c': replace_solve_case(add_poker(add_poker(base, 'photo'), 'liaison'), 'poker'),
        'n604d': add_yuan(base, 'source'),
        'n604e': replace_solve_case(add_yuan(base, 'web'), 'yuan'),
        'n604f': add_yuan(add_poker(base, 'identity'), 'body'),
    }
    for label, text in specs.items():
        write_candidate(label, text)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
