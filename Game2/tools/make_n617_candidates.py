#!/usr/bin/env python3
from __future__ import annotations

import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "Game2" / "deepclue_ai"
BASE_N614A = OUT / "n614a" / "ai.py"
BASE_N606A = OUT / "n606a" / "ai.py"
BASE_N612B = OUT / "n612b" / "ai.py"


def retitle(src: str, label: str) -> str:
    for old in ("n614a", "n606a", "n612b", "n556y1"):
        src = src.replace(f'"""Game2 DeepClue AI {old}.', f'"""Game2 DeepClue AI {label}.', 1)
    return src


def poker_expand_targets(src: str) -> str:
    old = """                    for npc_id in [
                        str(locals().get('info_id', '')),
                        str(locals().get('password_id', '')),
                        str(locals().get('reception_id', '')),
                    ]:
                        n601_add(npc_id)
"""
    new = """                    for npc_id in [
                        str(locals().get('info_id', '')),
                        str(locals().get('password_id', '')),
                        str(locals().get('reception_id', '')),
                        str(locals().get('true_club5_id', '')),
                        str(locals().get('target_id', '')),
                        str(locals().get('wang_id', '')),
                        str(locals().get('luo_id', '')),
                    ]:
                        n601_add(npc_id)
"""
    if old not in src:
        raise RuntimeError("Poker target anchor not found")
    return src.replace(old, new, 1)


def build_n617a(src: str) -> str:
    out = retitle(poker_expand_targets(src), "n617a")
    old_follow = """                                follow_q = (
                                    '你刚才已经明确确认照片原件在你这里、Joker手机和云端数据已经提取，'
                                    '并且605在你手上、607/608是警方最终卷宗。现在不是让你复述案情，而是做证据登记：'
                                    '请先把已经掌握的605交出，说明证据名、内容、保管链和它如何证明谁把Joker引入衣帽间、谁杀了Joker。'
                                    '如果607/608暂不能公开，请只说唯一公开条件和当前哪个可见持有人能满足。'
                                )
"""
    new_follow = """                                follow_q = (
                                    '你刚才确认照片原件、Joker手机云端、605和最终卷宗都已经在你或警方掌握。'
                                    '现在不索要内部卷宗，只做可公开登记：谁把Joker约进衣帽间、谁亲手杀死Joker、'
                                    '现场未交原件/自白笔录/凶器或手机云端中哪一份可以作为605公开。'
                                    '请直接给证据名、内容、保管链、签字人；如果需要林渝植或景观授权，只说当前应该找谁签字。'
                                )
"""
    if old_follow not in out:
        raise RuntimeError("n617a follow anchor not found")
    out = out.replace(old_follow, new_follow, 1)
    old_tail = """                        for npc_id in n601_targets[:18]:
                            n601_ask(npc_id, '若606三人照片已出现，不要再解释纹身含义；现在只追后续证据：照片原件的保管链、Joker周克手机云端/账号、红桃Q刘瑄联络记录、于书华组织名册、谁把Joker引入衣帽间、谁杀了Joker、现场已经掌握但未交出的605以及607/608最终警方卷宗。')
                    globals()['N601_POKER_IDS'] = ','.join(
"""
    new_tail = """                        for npc_id in n601_targets[:18]:
                            n601_ask(npc_id, '若606三人照片已出现，不要再解释纹身含义；现在只追后续证据：照片原件的保管链、Joker周克手机云端/账号、红桃Q刘瑄联络记录、于书华组织名册、谁把Joker引入衣帽间、谁杀了Joker、现场已经掌握但未交出的605以及607/608最终警方卷宗。')
                        n617_ids = [
                            str(ev.get('id')) for ev in g.evidences()
                            if str(ev.get('id')) in {'101', '102', '103', '104', '201', '202', '203', '204', '205', '401', '402', '404', '501', '502', '503', '504', '505', '601', '602', '603', '604', '605', '606', '607', '608'}
                        ]
                        if '606' in set(n617_ids) and not ({'605', '607', '608'} & set(n617_ids)):
                            for npc_id in n601_targets[:10]:
                                n601_ask(npc_id, '现在先不问组织名册和最终卷宗，只问凶手闭环：你是否亲眼知道或参与把Joker周克引入衣帽间并杀死他？若知道，请给可登记的供述、凶器/血迹/指纹、入室时间、手机云端约见记录或现场未交605；这份材料谁签字、谁保管？')
                                n617_ids = [
                                    str(ev.get('id')) for ev in g.evidences()
                                    if str(ev.get('id')) in {'101', '102', '103', '104', '201', '202', '203', '204', '205', '401', '402', '404', '501', '502', '503', '504', '505', '601', '602', '603', '604', '605', '606', '607', '608'}
                                ]
                                if {'605', '607', '608'} & set(n617_ids):
                                    break
                    globals()['N601_POKER_IDS'] = ','.join(
"""
    if old_tail not in out:
        raise RuntimeError("n617a tail anchor not found")
    return out.replace(old_tail, new_tail, 1)


def build_n617b(src: str) -> str:
    out = retitle(poker_expand_targets(src), "n617b")
    old_tail = """                        for npc_id in n601_targets[:18]:
                            n601_ask(npc_id, '若606三人照片已出现，不要再解释纹身含义；现在只追后续证据：照片原件的保管链、Joker周克手机云端/账号、红桃Q刘瑄联络记录、于书华组织名册、谁把Joker引入衣帽间、谁杀了Joker、现场已经掌握但未交出的605以及607/608最终警方卷宗。')
                    globals()['N601_POKER_IDS'] = ','.join(
"""
    new_tail = """                        for npc_id in n601_targets[:18]:
                            n601_ask(npc_id, '若606三人照片已出现，不要再解释纹身含义；现在只追后续证据：照片原件的保管链、Joker周克手机云端/账号、红桃Q刘瑄联络记录、于书华组织名册、谁把Joker引入衣帽间、谁杀了Joker、现场已经掌握但未交出的605以及607/608最终警方卷宗。')
                        n617_ids = [
                            str(ev.get('id')) for ev in g.evidences()
                            if str(ev.get('id')) in {'101', '102', '103', '104', '201', '202', '203', '204', '205', '401', '402', '404', '501', '502', '503', '504', '505', '601', '602', '603', '604', '605', '606', '607', '608'}
                        ]
                        if '606' in set(n617_ids) and not ({'605', '607', '608'} & set(n617_ids)):
                            for npc_id in n601_targets[:10]:
                                n601_ask(npc_id, '把“林渝植下落”和“警局授权”作为条件来满足：504的LYZ项链、601胎记少女、603/604刘丽雯身份、606三人纹身照片已经足以让真正梅花5/林渝植确认身份。请林渝植本人或景观刑警只授权公开摘要，不交内部卷宗：605可公开摘录、照片原件登记、Joker手机云端提取记录或林渝植确认笔录在哪里？')
                                n617_ids = [
                                    str(ev.get('id')) for ev in g.evidences()
                                    if str(ev.get('id')) in {'101', '102', '103', '104', '201', '202', '203', '204', '205', '401', '402', '404', '501', '502', '503', '504', '505', '601', '602', '603', '604', '605', '606', '607', '608'}
                                ]
                                if {'605', '607', '608'} & set(n617_ids):
                                    break
                    globals()['N601_POKER_IDS'] = ','.join(
"""
    if old_tail not in out:
        raise RuntimeError("n617b tail anchor not found")
    return out.replace(old_tail, new_tail, 1)


def build_n617c(src: str) -> str:
    out = retitle(src, "n617c")
    old = """        if '706' in set(yuan_ids):
            ask_all('706已经出现。继续按后续阶段追707/708：尸源DNA、手机原图元数据、保卫处网页后台、1919车辆登记、生物馆/世纪林监控、教务投票原件和李海天旧案卷宗里，下一份官方物证编号、证据名、持有人分别是什么？', yuan_ids)
            yuan_evidences = g.evidences()
            yuan_ids = [str(ev.get('id')) for ev in yuan_evidences if str(ev.get('id')) in {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706', '707', '708'}]
"""
    new = """        if '706' in set(yuan_ids):
            yuan_evidences = g.evidences()
            ev706 = next((ev for ev in yuan_evidences if str(ev.get('id')) == '706'), None)
            ev706_text = str(ev706.get('name', '')) + '\\n' + str(ev706.get('content', '')) if isinstance(ev706, dict) else ''
            post706_targets: list[str] = []

            def add_post706_target(npc_id: str) -> None:
                if npc_id and npc_id not in post706_targets:
                    post706_targets.append(npc_id)

            holder_match = re.search(r'([一-龥]{1,4})今天在失物招领处找到', ev706_text)
            if holder_match:
                for npc_id in global_name_ids(holder_match.group(1), current_npcs):
                    add_post706_target(npc_id)
            for npc_id in story_target_ids(ev706_text + '\\n' + '\\n'.join(yuan_replies.values()), current_npcs, max_ids=10):
                add_post706_target(npc_id)
            for name in ('李海天', '袁樱瞳', '王科瑾', '楚戎臻', '江沐青', '叶青衡', '沈知遥', '陆亦初', '张子韩', '张壹'):
                for npc_id in global_name_ids(name, current_npcs):
                    add_post706_target(npc_id)
            for npc_id in current_npcs:
                add_post706_target(npc_id)
            q1 = (
                '706 U盘已经出现，现在只打开U盘内容，不回到投票纸：电子系保研名单谁获利谁落选，'
                '李海天侵犯女生的视频照片里有哪些人，袁樱瞳周五准备揭发谁，谁拿走/隐藏U盘，'
                '谁清空袁樱瞳手机或伪造凌晨照片。若下一步需要运动少女联系方式、生物馆跑出者、手机原图或监控，请直接交出707/708。'
            )
            q2 = (
                '沿706的实物来源查：失物招领登记、U盘序列号、文件修改时间、李海天电脑、学生会办公室、'
                '袁樱瞳手机原图、QQ/微信/电话记录、生物馆22:30门禁和保卫处监控。哪一项能成为下一份物证？'
            )
            for source_id in post706_targets[:8]:
                resp = chat_visible_or_probe(g, source_id, g.npcs() or npcs, q1, yuan_ids)
                yuan_replies[source_id] = yuan_replies.get(source_id, '') + '\\n' + response_text(resp)
                yuan_ids = [str(ev.get('id')) for ev in g.evidences() if str(ev.get('id')) in {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706', '707', '708'}]
                if {'707', '708'} & set(yuan_ids):
                    break
            if not ({'707', '708'} & set(yuan_ids)):
                for source_id in post706_targets[:6]:
                    resp = chat_visible_or_probe(g, source_id, g.npcs() or npcs, q2, yuan_ids)
                    yuan_replies[source_id] = yuan_replies.get(source_id, '') + '\\n' + response_text(resp)
                    yuan_ids = [str(ev.get('id')) for ev in g.evidences() if str(ev.get('id')) in {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706', '707', '708'}]
                    if {'707', '708'} & set(yuan_ids):
                        break
            yuan_evidences = g.evidences()
            yuan_ids = [str(ev.get('id')) for ev in yuan_evidences if str(ev.get('id')) in {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706', '707', '708'}]
"""
    if old not in out:
        raise RuntimeError("n617c post-706 anchor not found")
    return out.replace(old, new, 1)


def build_n617d(src: str) -> str:
    out = retitle(src, "n617d")
    start = out.index("def n612_follow_yuan_contact_exchange(")
    end = out.index("\ndef n612_follow_yuan_usb(", start)
    replacement = r'''def n612_follow_yuan_contact_exchange(g: Game, current_npcs: list[str], yuan_replies: dict[str, str], yuan_ids: list[str]) -> list[str]:
    allowed = {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706', '707', '708'}
    if '707' not in set(yuan_ids) or '708' in set(yuan_ids):
        return yuan_ids
    yuan_evidences = g.evidences()
    ev707 = next((ev for ev in yuan_evidences if str(ev.get('id')) == '707'), None)
    ev707_text = str(ev707.get('name', '')) + '\n' + str(ev707.get('content', '')) if isinstance(ev707, dict) else ''
    contact_name = ''
    exchange_name = ''
    m = re.search(r'物证07：([一-龥]{1,4})的联系方式', ev707_text)
    if m:
        contact_name = m.group(1)
    for pattern in (
        r'可用于与([一-龥]{1,4})交换情报',
        r'与([一-龥]{1,4})交换情报',
        r'([一-龥]{1,4})曾表示如果能帮',
    ):
        m = re.search(pattern, ev707_text)
        if m:
            exchange_name = m.group(1)
            break
    targets: list[str] = []

    def add(npc_id: str) -> None:
        if npc_id and npc_id not in targets:
            targets.append(npc_id)

    for name in (exchange_name, contact_name):
        for npc_id in global_name_ids(name, current_npcs) if name else []:
            add(npc_id)
    combined = ev707_text + '\n' + '\n'.join(yuan_replies.values())
    runner_name = exchange_name
    for pattern in (
        r'看见([一-龥]{2,4}).{0,20}从生物馆',
        r'([一-龥]{2,4}).{0,20}从生物馆.{0,12}跑出来',
        r'([一-龥]{2,4}).{0,12}学生会副会长',
    ):
        m = re.search(pattern, combined)
        if m:
            runner_name = m.group(1)
            break
    for name in (runner_name, exchange_name, contact_name):
        for npc_id in global_name_ids(name, current_npcs) if name else []:
            add(npc_id)
    for npc_id in story_target_ids(combined, current_npcs, max_ids=10):
        add(npc_id)
    for npc_id in current_npcs:
        add(npc_id)
    contact_label = contact_name or '运动少女'
    exchange_label = exchange_name or runner_name or '生物馆跑出者'
    q_exchange = (
        f'707的交换已经完成：我把{contact_label}的联系方式交给你。不要再说“交换”或“找人”，直接兑现你承诺的杀手秘密。'
        '你上周六22:30为什么从生物馆慌张跑出，看见或处理了什么；秘密对应的实物记录是什么：'
        '生物馆门禁/监控、学生会办公室材料、李海天U盘、袁樱瞳手机原图、保卫处登记、QQ微信电话记录。若这就是物证08/708，请直接交出。'
    )
    q_contact = (
        f'你作为{contact_label}，已经提供联系方式。请回忆{exchange_label}向你要联系方式时的异常：他从生物馆跑出时手里是否有手机、U盘、血迹、背包/海豚挂件、行李箱；'
        '他说过什么，后来是否联系你；哪份门禁、监控、电话或微信记录能证明他的杀手秘密。'
    )
    q_locator = (
        f'现在只找{exchange_label}本人和记录：学生会办公室、宿舍、电子系楼、生物馆门禁、保卫处监控、QQ/微信/电话记录。'
        '请直接给能调取708的唯一持有人或证据原件。'
    )
    for npc_id in targets[:10]:
        name = cn_name(npc_id)
        if exchange_name and name == exchange_name:
            q = q_exchange
        elif runner_name and name == runner_name:
            q = q_exchange
        elif contact_name and name == contact_name:
            q = q_contact
        else:
            q = q_locator
        resp = chat_visible_or_probe(g, npc_id, g.npcs() or current_npcs, q, yuan_ids)
        yuan_replies[npc_id] = yuan_replies.get(npc_id, '') + '\n' + response_text(resp)
        yuan_ids = n612_refresh_ids(g, allowed)
        if '708' in set(yuan_ids):
            break
    return yuan_ids
'''
    return out[:start] + replacement + out[end:]


def build_n617e(src: str) -> str:
    out = retitle(src, "n617e")
    old = """        if forensic_target_id and '703' in set(yuan_ids):
            resp = g.chat(forensic_target_id, '703手机不是口供问题。请只说袁樱瞳手机是谁捡到、谁清空、凌晨1点照片的拍摄/发送时间、定位、EXIF元数据、删除记录、最后操作和账号登录记录；哪一份数字取证报告能打开物证06/706？', yuan_ids)
            yuan_replies[forensic_target_id] = yuan_replies.get(forensic_target_id, '') + '\\n' + response_text(resp)
            yuan_evidences = g.evidences()
            yuan_ids = [str(ev.get('id')) for ev in yuan_evidences if str(ev.get('id')) in {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706', '707', '708'}]
        if teacher_id and '704' in set(yuan_ids):
            resp = g.chat(teacher_id, '704投票纸只查原件 custody：票箱谁保管、谁能接触原始票、笔迹比对、废票/补票、课堂录像、教师办公室监控和行政系统日志在哪里？如果这能打开物证06/706，请给证据编号和持有人。', yuan_ids)
            yuan_replies[teacher_id] = yuan_replies.get(teacher_id, '') + '\\n' + response_text(resp)
            yuan_evidences = g.evidences()
            yuan_ids = [str(ev.get('id')) for ev in yuan_evidences if str(ev.get('id')) in {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706', '707', '708'}]
"""
    new = """        if teacher_id and '704' in set(yuan_ids):
            resp = g.chat(teacher_id, '先只核对课堂投票原件，不问警方编号：票箱从教室到办公室具体由谁保管，谁能接触原始票，全班49人、展示2人不投、缺席者未到场时为什么还能多出一票；那一票的笔迹和其他票哪里不同。如果投票异常连接到李海天随身U盘、失物招领、电子系保研名单或不雅视频，请直接说是哪份实物和谁发现的。', yuan_ids)
            yuan_replies[teacher_id] = yuan_replies.get(teacher_id, '') + '\\n' + response_text(resp)
            yuan_evidences = g.evidences()
            yuan_ids = [str(ev.get('id')) for ev in yuan_evidences if str(ev.get('id')) in {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706', '707', '708'}]
        if teacher_id and '704' in set(yuan_ids) and '706' not in set(yuan_ids):
            resp = g.chat(teacher_id, '继续只看原始票和行政链：多出的异笔迹票是谁写的，缺席者是谁，点名册、座位表、办公室监控、行政系统日志在哪里。如果老师没有U盘，请指出失物招领处、李海天、保研名单、不雅视频照片这条线的第一个可见持有人。', yuan_ids)
            yuan_replies[teacher_id] = yuan_replies.get(teacher_id, '') + '\\n' + response_text(resp)
            yuan_evidences = g.evidences()
            yuan_ids = [str(ev.get('id')) for ev in yuan_evidences if str(ev.get('id')) in {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706', '707', '708'}]
        if forensic_target_id and '703' in set(yuan_ids) and '706' not in set(yuan_ids):
            resp = g.chat(forensic_target_id, '先不问尸检和编号。你捡到袁樱瞳手机或竞争名额：请只说明手机是谁清空、她说“等到周五”要揭发什么、李海天随身U盘是否在失物招领、U盘里的保研名单和不雅视频照片谁见过。', yuan_ids)
            yuan_replies[forensic_target_id] = yuan_replies.get(forensic_target_id, '') + '\\n' + response_text(resp)
            yuan_evidences = g.evidences()
            yuan_ids = [str(ev.get('id')) for ev in yuan_evidences if str(ev.get('id')) in {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706', '707', '708'}]
"""
    if old not in out:
        raise RuntimeError("n617e yuan anchor not found")
    return out.replace(old, new, 1)


def write_candidate(label: str, text: str) -> None:
    target = OUT / label
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    (target / "ai.py").write_text(text, encoding="utf-8")


def main() -> int:
    write_candidate("n617a", build_n617a(BASE_N614A.read_text(encoding="utf-8")))
    write_candidate("n617b", build_n617b(BASE_N614A.read_text(encoding="utf-8")))
    write_candidate("n617c", build_n617c(BASE_N606A.read_text(encoding="utf-8")))
    write_candidate("n617d", build_n617d(BASE_N612B.read_text(encoding="utf-8")))
    write_candidate("n617e", build_n617e(BASE_N606A.read_text(encoding="utf-8")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
