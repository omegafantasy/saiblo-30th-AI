#!/usr/bin/env python3
from __future__ import annotations

import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "Game2" / "deepclue_ai"
BASE_N617A = OUT / "n617a" / "ai.py"
BASE_N617D = OUT / "n617d" / "ai.py"


def retitle(src: str, label: str) -> str:
    for old in ("n617a", "n617d", "n606a", "n556y1"):
        src = src.replace(f'"""Game2 DeepClue AI {old}.', f'"""Game2 DeepClue AI {label}.', 1)
    return src


def build_poker_final_accusation(src: str, label: str, mode: str) -> str:
    out = retitle(src, label)
    old_follow = """                                follow_q = (
                                    '你刚才确认照片原件、Joker手机云端、605和最终卷宗都已经在你或警方掌握。'
                                    '现在不索要内部卷宗，只做可公开登记：谁把Joker约进衣帽间、谁亲手杀死Joker、'
                                    '现场未交原件/自白笔录/凶器或手机云端中哪一份可以作为605公开。'
                                    '请直接给证据名、内容、保管链、签字人；如果需要林渝植或景观授权，只说当前应该找谁签字。'
                                )
"""
    if mode == "accuse":
        new_follow = """                                follow_q = (
                                    '我现在正式给出最终指控并要求登记公开摘要：Joker周克不是梅花5，他被POKER组织内部成员引入衣帽间后杀害，'
                                    '林渝植/真正梅花5只是身份混淆核心，606三人照片已经证明组织关系。'
                                    '请按办案流程公开一份不涉密的定案材料：凶手姓名、约见Joker的手机云端记录、现场未交原件/供述/凶器痕迹中哪一份作为605。'
                                    '如果还差授权，请直接说由林渝植、景观刑警还是照片原件持有人签字。'
                                )
"""
    else:
        new_follow = """                                follow_q = (
                                    '不要再把605/607/608当内部卷宗处理。请先只做授权条件核验：'
                                    '504的LYZ项链、601失踪少女、603/604刘丽雯身份、606三人POKER纹身照片是否已经足以让林渝植本人或景观刑警授权公开。'
                                    '若足够，请给公开摘要物证605；若不足，请说唯一缺少的前置材料和当前可见签字人。'
                                )
"""
    if old_follow not in out:
        raise RuntimeError(f"{label}: follow anchor not found")
    out = out.replace(old_follow, new_follow, 1)

    replacements = {
        "accuse": (
            "601-604或606若已出现，停止复述案情，先按POKER组织最终材料追缺口：606三人照片、605现场未交原件、Joker周克/于书华/红桃Q刘瑄组织名册、密码来源、衣帽间约见记录、死者手机云端和警方结案证据。",
            "601-604或606若已出现，直接进入最终指控核验：Joker周克被谁约进衣帽间，谁亲手杀死Joker，606三人照片中于书华和红桃Q/联络人分别承担什么角色；请给可公开的605摘要、供述或手机云端约见记录。",
        ),
        "auth": (
            "601-604或606若已出现，停止复述案情，先按POKER组织最终材料追缺口：606三人照片、605现场未交原件、Joker周克/于书华/红桃Q刘瑄组织名册、密码来源、衣帽间约见记录、死者手机云端和警方结案证据。",
            "601-604或606若已出现，先别问凶手口供，只问公开权限：照片原件、Joker手机云端、林渝植失踪档案、张子韩女儿身份和景观警方卷宗分别由谁保管；当前哪一个人可以授权公开605摘要。",
        ),
    }
    old_q, new_q = replacements[mode]
    if old_q not in out:
        raise RuntimeError(f"{label}: first post-606 question not found")
    out = out.replace(old_q, new_q, 1)

    old_q2 = "若606三人照片已出现，不要再解释纹身含义；现在只追后续证据：照片原件的保管链、Joker周克手机云端/账号、红桃Q刘瑄联络记录、于书华组织名册、谁把Joker引入衣帽间、谁杀了Joker、现场已经掌握但未交出的605以及607/608最终警方卷宗。"
    if mode == "accuse":
        new_q2 = "若606三人照片已出现，现在我只要求兑现最终指控后的公开材料：谁诱导Joker周克进入衣帽间、凶手是否为照片中的POKER成员、凶手供述/约见聊天/手机云端/现场原件哪一份能作为605公开登记。"
    else:
        new_q2 = "若606三人照片已出现，请只回答授权链：照片原件在谁手中，605公开摘要需要谁签字，607/608最终卷宗为什么不能公开；如果林渝植本人确认或景观刑警授权即可公开，请指出当前应问的可见NPC。"
    if old_q2 not in out:
        raise RuntimeError(f"{label}: second post-606 question not found")
    out = out.replace(old_q2, new_q2, 1)

    old_q3 = "现在先不问组织名册和最终卷宗，只问凶手闭环：你是否亲眼知道或参与把Joker周克引入衣帽间并杀死他？若知道，请给可登记的供述、凶器/血迹/指纹、入室时间、手机云端约见记录或现场未交605；这份材料谁签字、谁保管？"
    if mode == "accuse":
        new_q3 = "最终指控已经明确：请不要再说时机未到，只确认这份605公开摘要是否成立。摘要应包含凶手姓名、Joker周克约见记录、杀害地点、凶器/血迹/指纹或照片原件编号；若你不能交出，请说唯一保管人。"
    else:
        new_q3 = "请只回答授权缺口：605公开摘要缺的是林渝植本人确认、景观刑警签字、Joker手机云端提取记录、照片原件登记，还是最终卷宗解密时间？当前哪位可见人物能补齐。"
    if old_q3 not in out:
        raise RuntimeError(f"{label}: third post-606 question not found")
    out = out.replace(old_q3, new_q3, 1)
    return out


POST707_INSERT = r'''        if '707' in set(yuan_ids) and '708' not in set(yuan_ids):
            ev707 = next((ev for ev in yuan_evidences if str(ev.get('id')) == '707'), None)
            ev707_text = str(ev707.get('name', '')) + '\n' + str(ev707.get('content', '')) if isinstance(ev707, dict) else ''
            contact_match = re.search(r'物证07：([一-龥]{1,4})的联系方式', ev707_text)
            contact_name = contact_match.group(1) if contact_match else ''
            exchange_name_hint = ''
            for pattern in (r'用于与([一-龥]{1,4})交换', r'与([一-龥]{1,4})交换情报', r'([一-龥]{1,4})曾表示'):
                exchange_match = re.search(pattern, ev707_text)
                if exchange_match:
                    exchange_name_hint = exchange_match.group(1)
                    break
            exchange_targets: list[str] = []
            for name in (exchange_name_hint,):
                for npc_id in global_name_ids(name, g.npcs() or npcs) if name else []:
                    if npc_id and npc_id not in exchange_targets:
                        exchange_targets.append(npc_id)
            for npc_id in story_target_ids(ev707_text + '\n' + '\n'.join(yuan_replies.values()), g.npcs() or npcs, max_ids=8):
                if npc_id and npc_id not in exchange_targets:
                    exchange_targets.append(npc_id)
            for exchange_id in exchange_targets[:4]:
                resp = chat_visible_or_probe(g, exchange_id, g.npcs() or npcs, f'我已经把{contact_name or "那个运动少女"}的联系方式给你了。你之前说拿到这个不认识的运动少女联系方式，就告诉我关于杀手的秘密；现在请兑现交换：杀手秘密是什么，谁杀了袁樱瞳，物证08/708或下一份最终证据在哪里？', yuan_ids)
                yuan_replies[exchange_id] = yuan_replies.get(exchange_id, '') + '\n' + response_text(resp)
                yuan_evidences = g.evidences()
                yuan_ids = [str(ev.get('id')) for ev in yuan_evidences if str(ev.get('id')) in {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706', '707', '708'}]
                if '708' in set(yuan_ids):
                    break
            if '708' not in set(yuan_ids) and contact_name:
                contact_targets: list[str] = []
                for npc_id in global_name_ids(contact_name, g.npcs() or npcs):
                    if npc_id and npc_id not in contact_targets:
                        contact_targets.append(npc_id)
                for contact_id in contact_targets[:3]:
                    resp = chat_visible_or_probe(g, contact_id, g.npcs() or npcs, f'物证07写明这是你的联系方式，{exchange_name_hint or "交换对象"}想要那个不认识的运动少女联系方式。我现在正式征求你本人授权：能不能把你的号码交给{exchange_name_hint or "交换对象"}，让他联系你，从而换出关于杀手的秘密？请直接确认能转交，或给出应该转交的号码。', yuan_ids)
                    yuan_replies[contact_id] = yuan_replies.get(contact_id, '') + '\n' + response_text(resp)
                    yuan_evidences = g.evidences()
                    yuan_ids = [str(ev.get('id')) for ev in yuan_evidences if str(ev.get('id')) in {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706', '707', '708'}]
                    if '708' in set(yuan_ids):
                        break
                if '708' not in set(yuan_ids):
                    for exchange_id in exchange_targets[:4]:
                        resp = chat_visible_or_probe(g, exchange_id, g.npcs() or npcs, f'{contact_name}本人已经授权我把号码交给你，让你直接联系她。现在交换条件已经满足：请兑现你说的杀手秘密，交出物证08/708，或说明雇主邮件、白色浴缸、手套和刀具的下一份证据在哪里。', yuan_ids)
                        yuan_replies[exchange_id] = yuan_replies.get(exchange_id, '') + '\n' + response_text(resp)
                        yuan_evidences = g.evidences()
                        yuan_ids = [str(ev.get('id')) for ev in yuan_evidences if str(ev.get('id')) in {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706', '707', '708'}]
                        if '708' in set(yuan_ids):
                            break
            if '708' not in set(yuan_ids):
                ask_all(f'707已经出现，交换对象是{exchange_name_hint or "物证07写明的人"}。现在不要解释编号：请直接告诉我如何找到或解锁{exchange_name_hint or "这个交换对象"}，他/她是否是学生会副会长、生物馆跑出者、体育场夜跑遇到的人或要联系方式的人；谁能带我去宿舍/学生会/电子系/体育场见他/她，谁能代为转交{contact_name or "运动少女"}的联系方式并换出杀手秘密/708。', yuan_ids)
                yuan_evidences = g.evidences()
                yuan_ids = [str(ev.get('id')) for ev in yuan_evidences if str(ev.get('id')) in {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706', '707', '708'}]
            if '707' in set(yuan_ids) and '708' not in set(yuan_ids):
                ask_all(f'你刚才要求我证明有资格知道。现在资格链已经给出：703袁樱瞳手机、704投票异常、707的{contact_name or "联系方式"}，以及开场保安认出我这个失忆侦探、口袋里的网页截图/保安奇怪网站。请按正式调查协助处理，把联系方式转交给{exchange_name_hint or "交换对象"}，兑现杀手秘密；若仍缺资格，请直接说缺侦探身份证明、警方授权、学生会登记、保卫处网页截图、705还是706，若已满足请交出708。', yuan_ids)
                yuan_evidences = g.evidences()
                yuan_ids = [str(ev.get('id')) for ev in yuan_evidences if str(ev.get('id')) in {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706', '707', '708'}]
        if '708' in set(yuan_ids):
            post708_targets: list[str] = []
            for npc_id in (forensic_target_id if 'forensic_target_id' in locals() else '', teacher_id if 'teacher_id' in locals() else '', absent_vote_id if 'absent_vote_id' in locals() else ''):
                if npc_id and npc_id not in post708_targets:
                    post708_targets.append(npc_id)
            for npc_id in story_target_ids('\n'.join(yuan_replies.values()), g.npcs() or npcs, max_ids=8):
                if npc_id and npc_id not in post708_targets:
                    post708_targets.append(npc_id)
            for npc_id in (g.npcs() or npcs):
                if npc_id not in post708_targets:
                    post708_targets.append(npc_id)
            for source_id in post708_targets[:6]:
                resp = chat_visible_or_probe(g, source_id, g.npcs() or npcs, '708略微复苏的记忆已经出现：雇主邮件要求杀死目标后拍照发邮箱，画面里有沾血白色浴缸、戴手套握刀的手。现在只追下一层：雇主是谁、邮箱账号/IP/付款记录在哪里、浴缸地点是哪间房、刀和手套是谁处理的、物证09/709或最终记忆由谁持有？', yuan_ids)
                yuan_replies[source_id] = yuan_replies.get(source_id, '') + '\n' + response_text(resp)
                yuan_evidences = g.evidences()
                yuan_ids = [str(ev.get('id')) for ev in yuan_evidences if str(ev.get('id')) in {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706', '707', '708', '709'}]
                if '709' in set(yuan_ids):
                    break
'''


def build_yuan_contact(src: str, label: str, aggressive: bool) -> str:
    out = retitle(src, label)
    anchor = "        if '707' in set(yuan_ids):\n"
    if anchor not in out:
        raise RuntimeError(f"{label}: 707 anchor not found")
    out = out.replace(anchor, POST707_INSERT + anchor, 1)
    if aggressive:
        old = "        ask_all('单独确认联系方式交换线：是否有人想要那个不认识的“运动少女”的联系方式，运动少女是谁，谁愿意用联系方式交换关于杀手的秘密；如果能给707或708，请直接给证据编号、证据名和持有人。')\n"
        new = "        ask_all('优先确认联系方式交换线，不要等U盘：谁想要那个不认识的运动少女联系方式，运动少女是谁，谁承诺拿到号码就说杀手秘密；如果能给707请直接交出，若号码已经给出请继续给708。')\n"
        if old in out:
            out = out.replace(old, new, 1)
    return out


def build_yuan_usb(src: str, label: str) -> str:
    out = retitle(src, label)
    old = "        ask_all('先按物证06方向查，不等705：李海天随身U盘是否从失物招领出现，U盘里的电子系保研名单、不雅视频照片、袁樱瞳周五要揭发的内容、王科瑾未保研和手机清空之间有什么关系；若能给706/707/708请直接交出。')\n"
    new = "        ask_all('优先按物证06方向查，不等705也不总结尸检：李海天随身U盘是否从失物招领出现，谁今天找到，U盘里的电子系保研名单、不雅视频照片、袁樱瞳周五要揭发的内容、未保研者和手机清空之间是什么关系；若能给706请直接交出，若已给706请继续707/708。')\n"
    if old not in out:
        raise RuntimeError(f"{label}: usb question anchor not found")
    out = out.replace(old, new, 1)
    return build_yuan_contact(out, label, aggressive=False)


def write_candidate(label: str, text: str) -> None:
    target = OUT / label
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    (target / "ai.py").write_text(text, encoding="utf-8")


def main() -> int:
    write_candidate("n618a", build_poker_final_accusation(BASE_N617A.read_text(encoding="utf-8"), "n618a", "accuse"))
    write_candidate("n618b", build_poker_final_accusation(BASE_N617A.read_text(encoding="utf-8"), "n618b", "auth"))
    write_candidate("n618c", build_yuan_contact(BASE_N617D.read_text(encoding="utf-8"), "n618c", aggressive=True))
    write_candidate("n618d", build_yuan_usb(BASE_N617D.read_text(encoding="utf-8"), "n618d"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
