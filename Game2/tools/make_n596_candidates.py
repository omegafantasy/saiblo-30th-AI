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


POKER_OFFICIAL_CHAIN = """                        poker_after = g.evidences()
                        poker_after_ids = [str(ev.get('id')) for ev in poker_after]
                        rich_ids = [
                            eid for eid in poker_after_ids
                            if eid in {'101', '102', '103', '104', '201', '202', '203', '204', '205', '401', '402', '404', '405', '501', '502'}
                        ]
                        current_npcs = g.npcs() or follow_npcs
                        combined_late_text = reply + '\\n' + '\\n'.join(
                            str(ev.get('name', '')) + str(ev.get('content', '')) for ev in poker_after
                        )

                        def add_name(bucket: list[str], name: str) -> None:
                            name = str(name or '').strip()
                            if name and name not in bucket:
                                bucket.append(name)

                        true_club_names: list[str] = []
                        vehicle_names: list[str] = []
                        transfer_names: list[str] = []
                        dossier_names: list[str] = []
                        for pattern in (
                            r'现在的([一-龥]{2,4})就是她',
                            r'([一-龥]{2,4})就是她',
                            r'真正的梅花\\s*5[^，。\\n]{0,24}([一-龥]{2,4})',
                            r'真正的梅花五[^，。\\n]{0,24}([一-龥]{2,4})',
                            r'林渝植[^，。\\n]{0,16}(?:现在叫|现在是|就是)([一-龥]{2,4})',
                        ):
                            for m in re.finditer(pattern, combined_late_text):
                                add_name(true_club_names, m.group(1))
                        for pattern in (
                            r'([一-龥]{2,4})车牌号',
                            r'车牌号[^，。\\n]{0,20}(?:属于|指向|登记在)([一-龥]{2,4})',
                            r'车主[^，。\\n]{0,16}([一-龥]{2,4})',
                            r'司机[^，。\\n]{0,16}([一-龥]{2,4})',
                        ):
                            for m in re.finditer(pattern, combined_late_text):
                                add_name(vehicle_names, m.group(1))
                        for pattern in (
                            r'([一-龥]{2,4})（?于书华',
                            r'([一-龥]{2,4})[^，。\\n]{0,20}收到[^，。\\n]{0,12}500000',
                            r'转账[^，。\\n]{0,24}(?:给|至|到)([一-龥]{2,4})',
                            r'看诊[^，。\\n]{0,24}([一-龥]{2,4})',
                        ):
                            for m in re.finditer(pattern, combined_late_text):
                                add_name(transfer_names, m.group(1))
                        for pattern in (
                            r'代号.{0,2}景观',
                            r'刑警[^，。\\n]{0,12}([一-龥]{2,4})',
                            r'警察[^，。\\n]{0,12}([一-龥]{2,4})',
                        ):
                            for m in re.finditer(pattern, combined_late_text):
                                if m.groups():
                                    add_name(dossier_names, m.group(1))
                        if '景观' in combined_late_text and info_id:
                            dossier_names.append(cn_name(info_id))

                        def ids_for_names(names: list[str]) -> list[str]:
                            ids: list[str] = []
                            for name in names:
                                npc_id = id_for_name(name, current_npcs)
                                if npc_id and npc_id not in ids:
                                    ids.append(npc_id)
                            return ids

                        asked_late: set[str] = set()

                        def ask_once(npc_id: str, question: str) -> None:
                            if not npc_id or npc_id in asked_late:
                                return
                            asked_late.add(npc_id)
                            g.chat(npc_id, question, rich_ids)

                        ask_once(info_id, '你既然是信息源或警方线人，现在只给官方证据编号和保管链：405/502、林渝植失踪案卷宗、Joker人口贩卖名单、DNA/指纹、手机定位、银行流水、车辆轨迹、于书华看诊档案分别在哪。')
                        ask_once(password_id, '你掌握衣帽间密码。不要复述时间线，只给密码使用记录、门锁日志、隐藏房间、真实杀害地点、移尸出入口、Joker手机和下一份官方物证。')
                        ask_once(reception_id, '你掌握接待和场馆。直接给邀请函来源、地址表/面具映射、厨房缺刀、冰柜塑料盒、后院窗户、清洁路线、门禁/监控原件和405/502来源。')
                        for npc_id in ids_for_names(true_club_names):
                            ask_once(npc_id, '你被指认为真正梅花5/林渝植。现在只回答Joker、人口贩卖、404车辆、501转账、于书华、警方卷宗和你失踪案之间的官方证据链。')
                        if '404' in poker_after_ids:
                            for npc_id in ids_for_names(vehicle_names) + [info_id, reception_id]:
                                ask_once(npc_id, '404车牌已经出现。请直接给车主/司机、车钥匙、行车记录仪、停车记录、后备箱血迹、车内DNA/指纹、轮胎痕、后院窗户和真实移尸路线证据。')
                        if '501' in poker_after_ids:
                            for npc_id in ids_for_names(transfer_names) + [info_id, reception_id]:
                                ask_once(npc_id, '501匿名五十万转账已经出现。请直接给转账源账户、银行流水、于书华/王泽看诊记录、女儿胁迫、Joker勒索、人口贩卖名单和林渝植失踪档案。')
                        for npc_id in ids_for_names(dossier_names):
                            ask_once(npc_id, '你是警方卷宗/景观链条来源。请调取林渝植失踪案、Joker人口贩卖案、车辆高清监控、DNA/指纹、手机基站和银行流水中的下一份证据。')
                        if '405' not in poker_after_ids and '502' not in poker_after_ids:
                            for npc_id in current_npcs:
                                ask_once(npc_id, 'stage4排查。你只回答是否持有405/502或其来源：真实杀害地点、移尸车辆、门锁日志、Joker手机、人口贩卖名单、转账源账户、DNA/指纹或警方卷宗。')
                        poker_after = g.evidences()
                        poker_after_ids = [str(ev.get('id')) for ev in poker_after]
                        continuation_ids = [
                            eid for eid in poker_after_ids
                            if eid in {'401', '402', '404', '405', '501', '502'}
                        ]
                        if '404' in poker_after_ids:
                            globals()['POKER_HAS_404'] = True
                        if '501' in poker_after_ids:
                            globals()['POKER_HAS_501'] = True
                        if '405' in poker_after_ids:
                            globals()['POKER_HAS_405'] = True
                        if '502' in poker_after_ids:
                            globals()['POKER_HAS_502'] = True
                        if '405' in poker_after_ids or '502' in poker_after_ids:
                            for npc_id in [info_id, reception_id] + current_npcs[:3]:
                                if npc_id:
                                    g.chat(npc_id, '405或502已经出现。继续追最终层：下一份证据、最终凶手、杀害地点、移尸/资金/人口贩卖闭环、警方结案卷宗和可提交答案是什么。', continuation_ids)
                if g.stage < 3 and ev_ids:
"""


POKER_SPACE_TOOLMARK = """                        poker_after = g.evidences()
                        poker_after_ids = [str(ev.get('id')) for ev in poker_after]
                        rich_ids = [
                            eid for eid in poker_after_ids
                            if eid in {'101', '102', '103', '104', '201', '202', '203', '204', '205', '401', '402', '404', '405', '501', '502'}
                        ]
                        current_npcs = g.npcs() or follow_npcs
                        asked_space: set[str] = set()

                        def ask_space(npc_id: str, question: str) -> None:
                            if not npc_id or npc_id in asked_space:
                                return
                            asked_space.add(npc_id)
                            g.chat(npc_id, question, rich_ids)

                        ask_space(info_id, '不要再讲身份。只从空间和工具链复原：衣帽间密码、门锁日志、后院窗户、停车点、厨房三把刀、冰柜塑料盒、刀柄冰冻、血水稀释、移尸路线分别由哪份物证证明。')
                        ask_space(reception_id, '你负责场馆接待和清洁。请交出门禁/清洁/厨房/冰柜/窗户/停车记录，证明谁能接触刀具、衣帽间、后院窗户、死者手机和移尸车辆。')
                        ask_space(password_id, '你掌握密码或0512。请说明谁何时开过衣帽间，门锁是否有记录，密码从哪来，真实死亡地点和下一份官方物证在哪里。')
                        for npc_id in current_npcs:
                            ask_space(npc_id, '空间权限排查：你是否掌握厨房缺刀、冰柜塑料盒、后院窗户、停车点、衣帽间密码、门锁日志、清洁路线、隐藏房间或Joker手机中的任一物证？')
                        poker_after_ids = [str(ev.get('id')) for ev in g.evidences()]
                        if '404' in poker_after_ids:
                            globals()['POKER_HAS_404'] = True
                        if '501' in poker_after_ids:
                            globals()['POKER_HAS_501'] = True
                if g.stage < 3 and ev_ids:
"""


YUAN_FRIDAY_CACHE = """    elif '袁樱瞳' in text or '碎尸案' in text:
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
            ask(ynpc, '袁樱瞳反复说“等到周五”。不要猜凶手，只说她准备在周五揭发什么、证据藏在哪：手机/云端/网页截图/投票原件/老师邮箱/行政系统/保安记录/警方案卷。')
        yuan_ids = [str(ev.get('id')) for ev in g.evidences() if str(ev.get('id')) in {'001', '703', '704', '705', '706', '707', '708'}]
        for ynpc in ordered:
            ask(ynpc, '把张壹、张朔、出国名额、翘课/到课人数、47/48票、笔迹不同的正字、推荐名单改动和袁樱瞳周五要交出的材料按来源链列出来。', yuan_ids)
        yuan_ids = [str(ev.get('id')) for ev in g.evidences() if str(ev.get('id')) in {'001', '703', '704', '705', '706', '707', '708'}]
        for ynpc in ordered:
            ask(ynpc, '如果下一证据不是口供，请指出官方保管处：课程原始票箱、教师电脑/邮箱、学院推荐系统日志、教务处签字表、监控、手机云端或网页后台。', yuan_ids)
        g.answer(murderer='无名氏', motivation='无', method='无')
        return
"""


YUAN_BODY_LUGGAGE_DNA = """    elif '袁樱瞳' in text or '碎尸案' in text:
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
            ask(ynpc, '尸源/DNA主线：袁樱瞳尸体、凌晨1点照片女尸、lo裙栗色假发、世纪林尸块、李海天尸检、蓝色背包海豚挂件分别是谁、如何比对，哪份官方DNA或照片元数据能证明。')
        yuan_ids = [str(ev.get('id')) for ev in g.evidences() if str(ev.get('id')) in {'001', '703', '704', '705', '706', '707', '708'}]
        for ynpc in ordered:
            ask(ynpc, '黄色行李箱来源链：谁买的、谁借的、维修店/快递/宿舍楼监控、箱内血迹指纹纤维、搬运路线和1919黑车记录在哪里。只给可调取物证。', yuan_ids)
        yuan_ids = [str(ev.get('id')) for ev in g.evidences() if str(ev.get('id')) in {'001', '703', '704', '705', '706', '707', '708'}]
        for ynpc in ordered:
            ask(ynpc, '手机数字取证：被清空内容、凌晨照片EXIF/定位/设备、最后操作人、云备份、登录IP、网页截图来源和保安奇怪网站后台记录分别由谁保管。', yuan_ids)
        g.answer(murderer='无名氏', motivation='无', method='无')
        return
"""


YUAN_705_HIDDEN_SOURCE = """    elif '袁樱瞳' in text or '碎尸案' in text:
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
            ask(ynpc, '先只找705/706来源：李海天尸检报告、蓝色背包海豚挂件、世纪林尸块、生物馆十点半、1919黑车、保安网页、手机照片、投票原件分别由谁保管。')
        yuan_evidences = g.evidences()
        yuan_ids = [str(ev.get('id')) for ev in yuan_evidences if str(ev.get('id')) in {'001', '703', '704', '705', '706', '707', '708'}]
        combined = '\\n'.join(replies.values()) + '\\n' + '\\n'.join(str(ev.get('content', '')) for ev in yuan_evidences)
        source_names: list[str] = []

        def add_source(name: str) -> None:
            name = str(name or '').strip()
            if name and name not in source_names:
                source_names.append(name)

        for pattern in (
            r'([一-龥]{2,4})处获得的官方尸检报告',
            r'看到([一-龥]{2,4})[^。；\\n]{0,24}从生物馆',
            r'([一-龥]{2,4})[^。；\\n]{0,24}从生物馆跑出来',
            r'保安([一-龥]{2,4})',
            r'([一-龥]{2,4})[^。；\\n]{0,16}奇怪网站',
            r'([一-龥]{2,4})[^。；\\n]{0,16}1919',
        ):
            for m in re.finditer(pattern, combined):
                add_source(m.group(1))
        if '705' in yuan_ids:
            for name in source_names:
                npc_id = id_for_name(name, current_npcs)
                direct_id = CN_TO_PINYIN.get(name, '')
                for target_id in [npc_id, direct_id]:
                    if target_id:
                        ask(target_id, f'705报告来源指向{name}。请直接给706或后续官方证据：DNA比对、海豚挂件来源、蓝色背包主人、生物馆监控、1919车辆登记、保安网页日志、手机元数据或警方旧案卷宗。', yuan_ids)
            for ynpc in ordered:
                ask(ynpc, '705已出现但来源可能不在当前三人。请说明如何联系报告来源、保卫处、警方、法医、车辆系统或网站后台以取得706/707/708。', yuan_ids)
        else:
            for ynpc in ordered:
                ask(ynpc, '当前还缺705。请不要讲案情，只给李海天尸检报告的官方来源、蓝色背包海豚挂件、DNA、世纪林旧案和生物馆监控由谁保管。', yuan_ids)
        yuan_evidences = g.evidences()
        yuan_ids = [str(ev.get('id')) for ev in yuan_evidences if str(ev.get('id')) in {'001', '703', '704', '705', '706', '707', '708'}]
        if '706' in yuan_ids or '707' in yuan_ids or '708' in yuan_ids:
            for ynpc in ordered:
                ask(ynpc, '706或更后证据已经出现。继续追最终层：真实死者、照片来源、杀害/分尸地点、旧案联系、最终凶手、动机和可提交答案。', yuan_ids)
        g.answer(murderer='无名氏', motivation='无', method='无')
        return
"""


YUAN_CROSS_OFFICIAL = """    elif '袁樱瞳' in text or '碎尸案' in text:
        current_npcs = g.npcs() or npcs
        current_marks = g.marks() or marks
        true_ids = [npc for npc in current_npcs if current_marks.get(npc) is True]
        false_ids = [npc for npc in current_npcs if current_marks.get(npc) is False]
        ordered = true_ids + false_ids + [npc for npc in current_npcs if npc not in true_ids + false_ids]
        poker_late = bool(globals().get('POKER_HAS_404') or globals().get('POKER_HAS_501') or globals().get('POKER_HAS_405') or globals().get('POKER_HAS_502'))
        replies: dict[str, str] = {}

        def ask(npc: str, question: str, evidences_arg: list[str] | None = None) -> None:
            resp = g.chat(npc, question, evidences_arg)
            replies[npc] = replies.get(npc, '') + '\\n' + response_text(resp)

        first_question = (
            'Poker已出现车辆/转账/后续证据。只查同源官方链：Joker人口贩卖、匿名转账、林渝植失踪、李海天、袁樱瞳、1919黑车、生物馆、保安网页、蓝色背包和手机照片是否同案，下一证据在哪里。'
            if poker_late else
            '袁樱瞳案按官方链排查：周五揭发材料、手机云端、投票原件、尸源DNA、黄色行李箱、1919黑车、生物馆监控、保安网页、李海天旧案和蓝色背包分别由谁保管。'
        )
        for ynpc in ordered:
            ask(ynpc, first_question)
        yuan_evidences = g.evidences()
        yuan_ids = [str(ev.get('id')) for ev in yuan_evidences if str(ev.get('id')) in {'001', '703', '704', '705', '706', '707', '708'}]
        combined = '\\n'.join(replies.values()) + '\\n' + '\\n'.join(str(ev.get('content', '')) for ev in yuan_evidences)
        target_names: list[str] = []

        def add_target(name: str) -> None:
            name = str(name or '').strip()
            if name and name not in target_names:
                target_names.append(name)

        for pattern in (
            r'([一-龥]{2,4})处获得的官方尸检报告',
            r'看到([一-龥]{2,4})[^。；\\n]{0,24}从生物馆',
            r'([一-龥]{2,4})[^。；\\n]{0,24}从生物馆跑出来',
            r'保安([一-龥]{2,4})',
            r'([一-龥]{2,4})[^。；\\n]{0,16}奇怪网站',
            r'([一-龥]{2,4})[^。；\\n]{0,12}以\\s*24\\s*票',
            r'([一-龥]{2,4})[^。；\\n]{0,12}险胜袁樱瞳',
        ):
            for m in re.finditer(pattern, combined):
                add_target(m.group(1))
        for name in target_names:
            for npc_id in [id_for_name(name, current_npcs), CN_TO_PINYIN.get(name, '')]:
                if npc_id:
                    ask(npc_id, f'{name}被解析为隐藏链来源。请直接给下一份官方证据：706/707/708、DNA、手机元数据、票箱原件、生物馆监控、保安网页后台、1919车、尸检档案、蓝色背包、人口贩卖名单或转账源账户。', yuan_ids)
        if not target_names:
            for ynpc in ordered:
                ask(ynpc, '如果当前三人都不是来源，请只给下一证据的保管系统：保卫处、警方、法医、车辆系统、网站后台、教务系统、手机云端、银行流水或人口贩卖案卷。', yuan_ids)
        yuan_ids = [str(ev.get('id')) for ev in g.evidences() if str(ev.get('id')) in {'001', '703', '704', '705', '706', '707', '708'}]
        if '706' in yuan_ids or '707' in yuan_ids or '708' in yuan_ids:
            for ynpc in ordered:
                ask(ynpc, '后续证据已经出现。继续闭环最终答案：真实死者、照片来源、旧案同源、凶手、动机、分尸/移尸/嫁祸过程。', yuan_ids)
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
        'n596a': insert_poker_block(poker_iso, POKER_OFFICIAL_CHAIN),
        'n596b': insert_poker_block(poker_full, POKER_OFFICIAL_CHAIN),
        'n596c': insert_poker_block(poker_iso, POKER_SPACE_TOOLMARK),
        'n596d': replace_yuan_branch(insert_poker_block(poker_full, POKER_SPACE_TOOLMARK), YUAN_CROSS_OFFICIAL),
        'n596e': isolate_yuan(replace_yuan_branch(yuan_full, YUAN_FRIDAY_CACHE)),
        'n596f': isolate_yuan(replace_yuan_branch(yuan_full, YUAN_BODY_LUGGAGE_DNA)),
        'n596g': isolate_yuan(replace_yuan_branch(yuan_full, YUAN_705_HIDDEN_SOURCE)),
        'n596h': replace_yuan_branch(insert_poker_block(poker_full, POKER_OFFICIAL_CHAIN), YUAN_CROSS_OFFICIAL),
    }
    for label, text in specs.items():
        write_candidate(label, text)
    print('\n'.join(sorted(specs)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
