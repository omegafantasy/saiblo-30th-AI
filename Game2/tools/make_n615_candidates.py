#!/usr/bin/env python3
from __future__ import annotations

import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "Game2" / "deepclue_ai"
BASE_N614A = OUT / "n614a" / "ai.py"
BASE_N614B = OUT / "n614b" / "ai.py"
BASE_N606A = OUT / "n606a" / "ai.py"


def retitle(src: str, label: str) -> str:
    for old in ("n614a", "n614b", "n606a", "n556y1"):
        src = src.replace(f'"""Game2 DeepClue AI {old}.', f'"""Game2 DeepClue AI {label}.', 1)
    return src


def widen_505_ids(src: str) -> str:
    return src.replace(
        "'502', '503', '504', '601'",
        "'502', '503', '504', '505', '601'",
    ).replace(
        "'503', '504', '601'",
        "'503', '504', '505', '601'",
    )


def build_n615a(src: str) -> str:
    out = retitle(widen_505_ids(src), "n615a")
    old_follow = """                                follow_q = (
                                    '你刚才已经明确确认照片原件在你这里、Joker手机和云端数据已经提取，'
                                    '并且605在你手上、607/608是警方最终卷宗。现在不是让你复述案情，而是做证据登记：'
                                    '请先把已经掌握的605交出，说明证据名、内容、保管链和它如何证明谁把Joker引入衣帽间、谁杀了Joker。'
                                    '如果607/608暂不能公开，请只说唯一公开条件和当前哪个可见持有人能满足。'
                                )
"""
    new_follow = """                                follow_q = (
                                    '你刚才已经确认照片原件、Joker手机云端、605和607/608卷宗都不是传闻，而是已经进入你或警方掌握。'
                                    '现在先满足你说的公开条件：504的LYZ随身物、601失踪少女特征、603/604刘丽雯身份和606三人POKER纹身照片，'
                                    '已经能说明林渝植仍在案中且Joker/于书华/红桃Q属于同一组织。'
                                    '如果你是景观或刑警信息源，请用警局授权把可公开的605登记成物证；'
                                    '如果还差林渝植本人确认，请说当前可见的梅花5/林渝植应向谁确认。'
                                    '请直接给证据名、内容、保管链、公开条件和下一持有人。'
                                )
"""
    if old_follow not in out:
        raise RuntimeError("n615a follow_q anchor not found")
    out = out.replace(old_follow, new_follow, 1)
    old_targets = """                    for npc_id in [
                        str(locals().get('info_id', '')),
                        str(locals().get('password_id', '')),
                        str(locals().get('reception_id', '')),
                    ]:
                        n601_add(npc_id)
"""
    new_targets = """                    for npc_id in [
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
    if old_targets not in out:
        raise RuntimeError("n615a target anchor not found")
    out = out.replace(old_targets, new_targets, 1)
    old_tail = """                        for npc_id in n601_targets[:18]:
                            n601_ask(npc_id, '若606三人照片已出现，不要再解释纹身含义；现在只追后续证据：照片原件的保管链、Joker周克手机云端/账号、红桃Q刘瑄联络记录、于书华组织名册、谁把Joker引入衣帽间、谁杀了Joker、现场已经掌握但未交出的605以及607/608最终警方卷宗。')
                    globals()['N601_POKER_IDS'] = ','.join(
"""
    new_tail = """                        for npc_id in n601_targets[:18]:
                            n601_ask(npc_id, '若606三人照片已出现，不要再解释纹身含义；现在只追后续证据：照片原件的保管链、Joker周克手机云端/账号、红桃Q刘瑄联络记录、于书华组织名册、谁把Joker引入衣帽间、谁杀了Joker、现场已经掌握但未交出的605以及607/608最终警方卷宗。')
                        n601_ids = [
                            str(ev.get('id')) for ev in g.evidences()
                            if str(ev.get('id')) in {'101', '102', '103', '104', '201', '202', '203', '204', '205', '401', '402', '404', '501', '502', '503', '504', '505', '601', '602', '603', '604', '605', '606', '607', '608'}
                        ]
                        if '606' in set(n601_ids) and not ({'605', '607', '608'} & set(n601_ids)):
                            for npc_id in n601_targets[:10]:
                                n601_ask(npc_id, '现在不再询问“有没有最终卷宗”，而是执行公开条件闭环：由林渝植/真正梅花5确认身份，由景观/刑警把照片原件、Joker手机云端、组织名册或衣帽间现场未交原件登记为可提交物证。请只回答哪一份已经可以公开、谁能签字、证据原件在哪里。')
                                n601_ids = [
                                    str(ev.get('id')) for ev in g.evidences()
                                    if str(ev.get('id')) in {'101', '102', '103', '104', '201', '202', '203', '204', '205', '401', '402', '404', '501', '502', '503', '504', '505', '601', '602', '603', '604', '605', '606', '607', '608'}
                                ]
                                if {'605', '607', '608'} & set(n601_ids):
                                    break
                    globals()['N601_POKER_IDS'] = ','.join(
"""
    if old_tail not in out:
        raise RuntimeError("n615a tail anchor not found")
    return out.replace(old_tail, new_tail, 1)


def build_n615b(src: str) -> str:
    out = retitle(widen_505_ids(src), "n615b")
    old_tail = """                        for npc_id in n601_targets[:18]:
                            n601_ask(npc_id, '若606三人照片已出现，不要再解释纹身含义；现在只追后续证据：照片原件的保管链、Joker周克手机云端/账号、红桃Q刘瑄联络记录、于书华组织名册、谁把Joker引入衣帽间、谁杀了Joker、现场已经掌握但未交出的605以及607/608最终警方卷宗。')
                    globals()['N601_POKER_IDS'] = ','.join(
"""
    new_tail = """                        for npc_id in n601_targets[:18]:
                            n601_ask(npc_id, '若606三人照片已出现，不要再解释纹身含义；现在只追后续证据：照片原件的保管链、Joker周克手机云端/账号、红桃Q刘瑄联络记录、于书华组织名册、谁把Joker引入衣帽间、谁杀了Joker、现场已经掌握但未交出的605以及607/608最终警方卷宗。')
                        n601_ids = [
                            str(ev.get('id')) for ev in g.evidences()
                            if str(ev.get('id')) in {'101', '102', '103', '104', '201', '202', '203', '204', '205', '401', '402', '404', '501', '502', '503', '504', '505', '601', '602', '603', '604', '605', '606', '607', '608'}
                        ]
                        if not ({'605', '607', '608'} & set(n601_ids)):
                            for npc_id in n601_targets[:12]:
                                n601_ask(npc_id, '换一个方向查，不问纹身含义。沿现场未交物和空间证据追：衣帽间暗格、地下室入口、花纹村账本、5年前逮捕令后续、凶器/血衣/指纹、窗户逃离路线、Joker手机原件和谁把Joker引到衣帽间。请直接给当前可公开的现场原件、账本或警方登记物。')
                                n601_ids = [
                                    str(ev.get('id')) for ev in g.evidences()
                                    if str(ev.get('id')) in {'101', '102', '103', '104', '201', '202', '203', '204', '205', '401', '402', '404', '501', '502', '503', '504', '505', '601', '602', '603', '604', '605', '606', '607', '608'}
                                ]
                                if {'605', '607', '608'} & set(n601_ids):
                                    break
                    globals()['N601_POKER_IDS'] = ','.join(
"""
    if old_tail not in out:
        raise RuntimeError("n615b tail anchor not found")
    return out.replace(old_tail, new_tail, 1)


def build_n615c(src: str) -> str:
    out = retitle(src, "n615c")
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
            for name in ('李海天', '袁樱瞳', '楚戎臻', '王科瑾', '沈知遥', '赵一橙', '王泽', '张壹', '张子韩'):
                for npc_id in global_name_ids(name, current_npcs):
                    add_post706_target(npc_id)
            for npc_id in current_npcs:
                add_post706_target(npc_id)
            q1 = (
                '706 U盘已经出现，现在不要回到投票细节。请直接打开U盘文件目录和元数据：'
                '电子系保研名单是谁导出的，李海天侵犯女生的视频照片里有哪些受害者，袁樱瞳周五准备揭发谁，'
                '谁拿走或隐藏U盘，谁清空袁樱瞳手机，谁用保研名单或视频威胁杀人。'
                '如果下一步是运动少女联系方式、赵一橙交换情报、生物馆监控或手机原图，请直接交出707/708的证据名和持有人。'
            )
            q2 = (
                '沿706 U盘继续查现实证据源：失物招领登记、U盘序列号/文件修改时间、李海天电脑或学生会办公室、'
                '袁樱瞳手机原图、保卫处门禁、生物馆22:30监控和聊天记录。哪一项能直接成为下一份物证？'
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
        raise RuntimeError("n615c post706 anchor not found")
    return out.replace(old, new, 1)


def build_n615d(src: str) -> str:
    out = retitle(src, "n615d")
    old_direct = """    direct_exchange_question = (
        f'我已经拿到{contact_label}主动给出的联系方式。你之前说只要拿到这个不认识的运动少女联系方式，就告诉我关于杀手的秘密。'
        '现在请按交换条件兑现：你知道的杀手秘密是什么，谁杀了袁樱瞳，秘密对应的手机原图、U盘视频、网页截图、生物馆监控、1919车辆记录或最终物证在哪里？'
    )
    relay_question = (
        f'这是{contact_label}的联系方式。请你现在当场打电话、发消息或带我去找{exchange_label}，把联系方式交给他，让他兑现“杀手秘密”。'
        '如果他不在当前现场，请说明他的完整身份、学生会/宿舍/办公室位置，以及怎样取得他掌握的最终证据。'
    )
"""
    new_direct = """    direct_exchange_question = (
        f'我已经拿到{contact_label}主动给出的联系方式，现在把它交给你。不要再讨论交换条件本身，直接兑现你承诺的杀手秘密：'
        '上周六22:30你为什么从生物馆慌张跑出，是否看见李海天U盘、袁樱瞳手机原图、尸块、背包/海豚挂件或真正凶手。'
        '请说出可调取的实物记录：生物馆门禁、走廊/实验室监控、学生会办公室文件、QQ/微信/电话记录、保卫处登记；若这就是708，请直接交出证据名、内容和持有人。'
    )
    relay_question = (
        f'这是{contact_label}的联系方式。请不要抽象说“交换秘密”，直接带我找到{exchange_label}或调出他的位置记录：'
        '学生会办公室、宿舍、电子系楼、生物馆门禁、保卫处监控、QQ/微信/电话记录。'
        '如果他掌握物证08/708，请直接说证据原件在哪里、谁能调取。'
    )
"""
    if old_direct not in out:
        raise RuntimeError("n615d contact question anchor not found")
    out = out.replace(old_direct, new_direct, 1)
    old_tail = """    for npc_id in relay_targets[:5]:
        resp = chat_visible_or_probe(
            g,
            npc_id,
            g.npcs() or current_npcs,
            f'不要再讨论物证07编号。现在只做一件事：谁能立刻联系或带我找到{exchange_label}，让他用{contact_label}的联系方式交换杀手秘密？请说可执行的找人路径、完整身份和他手里那份最终证据。',
            yuan_ids,
        )
        yuan_replies[npc_id] = yuan_replies.get(npc_id, '') + '\\n' + response_text(resp)
        yuan_ids = n612_refresh_ids(g, allowed)
        if '708' in set(yuan_ids):
            break
    return yuan_ids
"""
    new_tail = """    for npc_id in relay_targets[:5]:
        resp = chat_visible_or_probe(
            g,
            npc_id,
            g.npcs() or current_npcs,
            f'不要再讨论物证07编号。现在只做一件事：谁能立刻联系或带我找到{exchange_label}，让他用{contact_label}的联系方式交换杀手秘密？请说可执行的找人路径、完整身份和他手里那份最终证据。',
            yuan_ids,
        )
        yuan_replies[npc_id] = yuan_replies.get(npc_id, '') + '\\n' + response_text(resp)
        yuan_ids = n612_refresh_ids(g, allowed)
        if '708' in set(yuan_ids):
            break
    if '708' not in set(yuan_ids):
        hard_targets: list[str] = []
        for name in (exchange_name, contact_name, '赵一橙', '李海天', '王泽', '楚戎臻'):
            for npc_id in global_name_ids(name, current_npcs):
                n612_add_unique(hard_targets, npc_id)
        for npc_id in hard_targets[:6]:
            resp = chat_visible_or_probe(
                g,
                npc_id,
                g.npcs() or current_npcs,
                f'按707文本推进：{contact_label}的联系方式已经给到{exchange_label}。现在追可验证记录而不是口头秘密：生物馆22:30门禁/监控、学生会办公室、李海天U盘、袁樱瞳手机原图、保卫处登记、QQ微信电话记录。请直接交出物证08/708或说明唯一持有人。',
                yuan_ids,
            )
            yuan_replies[npc_id] = yuan_replies.get(npc_id, '') + '\\n' + response_text(resp)
            yuan_ids = n612_refresh_ids(g, allowed)
            if '708' in set(yuan_ids):
                break
    return yuan_ids
"""
    if old_tail not in out:
        raise RuntimeError("n615d contact tail anchor not found")
    return out.replace(old_tail, new_tail, 1)


def write_candidate(label: str, text: str) -> None:
    target = OUT / label
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    (target / "ai.py").write_text(text, encoding="utf-8")


def main() -> int:
    write_candidate("n615a", build_n615a(BASE_N614A.read_text(encoding="utf-8")))
    write_candidate("n615b", build_n615b(BASE_N614A.read_text(encoding="utf-8")))
    write_candidate("n615c", build_n615c(BASE_N606A.read_text(encoding="utf-8")))
    write_candidate("n615d", build_n615d(BASE_N614B.read_text(encoding="utf-8")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
