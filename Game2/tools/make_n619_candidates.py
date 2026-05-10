#!/usr/bin/env python3
from __future__ import annotations

import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "Game2" / "deepclue_ai"
BASE = OUT / "n617d" / "ai.py"

INITIAL_IDS = """        yuan_evidences = g.evidences()
        yuan_ids = [str(ev.get('id')) for ev in yuan_evidences if str(ev.get('id')) in {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706', '707', '708'}]
"""


def retitle(src: str, label: str) -> str:
    for old in ("n617d", "n556y1"):
        src = src.replace(f'"""Game2 DeepClue AI {old}.', f'"""Game2 DeepClue AI {label}.', 1)
    return src


EARLY_QAS_BLOCK = r'''        if '707' in set(yuan_ids) and '708' not in set(yuan_ids):
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
            for pattern in (r'用于与([一-龥]{1,4})交换', r'与([一-龥]{1,4})交换情报', r'([一-龥]{1,4})曾表示'):
                for exchange_name in re.findall(pattern, ev707_text):
                    for npc_id in global_name_ids(exchange_name, g.npcs() or npcs):
                        if npc_id and npc_id not in exchange_targets:
                            exchange_targets.append(npc_id)
            for exchange_id in exchange_targets[:3]:
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
                    for exchange_id in exchange_targets[:3]:
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
'''


CONTACT_FIRST_BLOCK = r'''        if '707' in set(yuan_ids) and '708' not in set(yuan_ids):
            ev707 = next((ev for ev in yuan_evidences if str(ev.get('id')) == '707'), None)
            ev707_text = str(ev707.get('name', '')) + '\n' + str(ev707.get('content', '')) if isinstance(ev707, dict) else ''
            contact_match = re.search(r'物证07：([一-龥]{1,4})的联系方式', ev707_text)
            contact_name = contact_match.group(1) if contact_match else ''
            exchange_name_hint = ''
            for pattern in (r'可用于与([一-龥]{1,4})交换情报', r'用于与([一-龥]{1,4})交换', r'与([一-龥]{1,4})交换情报', r'([一-龥]{1,4})曾表示'):
                exchange_match = re.search(pattern, ev707_text)
                if exchange_match:
                    exchange_name_hint = exchange_match.group(1)
                    break
            exchange_targets: list[str] = []
            if exchange_name_hint:
                for npc_id in global_name_ids(exchange_name_hint, g.npcs() or npcs):
                    if npc_id and npc_id not in exchange_targets:
                        exchange_targets.append(npc_id)
            contact_targets: list[str] = []
            if contact_name:
                for npc_id in global_name_ids(contact_name, g.npcs() or npcs):
                    if npc_id and npc_id not in contact_targets:
                        contact_targets.append(npc_id)
            for contact_id in contact_targets[:3]:
                resp = chat_visible_or_probe(
                    g,
                    contact_id,
                    g.npcs() or npcs,
                    f'707写的是你的联系方式，{exchange_name_hint or "那个人"}想拿到它来交换杀手秘密。请不要讲编号，只确认一件事：我能否把你的号码转交给{exchange_name_hint or "那个人"}，让他打给你并兑现秘密？如果可以，请直接说“把我的号码给他/她”。',
                    yuan_ids,
                )
                yuan_replies[contact_id] = yuan_replies.get(contact_id, '') + '\n' + response_text(resp)
                yuan_evidences = g.evidences()
                yuan_ids = [str(ev.get('id')) for ev in yuan_evidences if str(ev.get('id')) in {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706', '707', '708'}]
                if '708' in set(yuan_ids):
                    break
            if '708' not in set(yuan_ids):
                for exchange_id in exchange_targets[:4]:
                    resp = chat_visible_or_probe(
                        g,
                        exchange_id,
                        g.npcs() or npcs,
                        f'{contact_name or "运动少女"}已经明确授权我转交联系方式。你要的运动少女号码已经满足交换条件；现在请兑现杀手秘密，直接交出708或说明雇主邮件、白色浴缸、手套刀具和袁樱瞳死亡照片的下一份物证。',
                        yuan_ids,
                    )
                    yuan_replies[exchange_id] = yuan_replies.get(exchange_id, '') + '\n' + response_text(resp)
                    yuan_evidences = g.evidences()
                    yuan_ids = [str(ev.get('id')) for ev in yuan_evidences if str(ev.get('id')) in {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706', '707', '708'}]
                    if '708' in set(yuan_ids):
                        break
            if '708' not in set(yuan_ids):
                ask_all(f'707联系方式已经出现。现在只做授权转交：{contact_name or "联系方式持有人"}是否允许把号码给{exchange_name_hint or "交换对象"}，{exchange_name_hint or "交换对象"}拿到号码后应兑现的杀手秘密/708在哪里。不要讨论U盘或投票。', yuan_ids)
                yuan_evidences = g.evidences()
                yuan_ids = [str(ev.get('id')) for ev in yuan_evidences if str(ev.get('id')) in {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706', '707', '708'}]
'''


EARLY_HELPER_CALL = """        if '707' in set(yuan_ids) and '708' not in set(yuan_ids):
            yuan_ids = n612_follow_yuan_contact_exchange(g, current_npcs, yuan_replies, yuan_ids)
            yuan_evidences = g.evidences()
            yuan_ids = [str(ev.get('id')) for ev in yuan_evidences if str(ev.get('id')) in {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706', '707', '708'}]
"""


def insert_after_initial_ids(src: str, block: str, label: str) -> str:
    if INITIAL_IDS not in src:
        raise RuntimeError(f"{label}: initial ids anchor not found")
    return src.replace(INITIAL_IDS, INITIAL_IDS + block, 1)


def tune_initial_questions(src: str, label: str, contact_priority: bool) -> str:
    out = retitle(src, label)
    old = "        ask_all('单独确认联系方式交换线：是否有人想要那个不认识的“运动少女”的联系方式，运动少女是谁，谁愿意用联系方式交换关于杀手的秘密；如果能给707或708，请直接给证据编号、证据名和持有人。')\n"
    new = "        ask_all('优先确认联系方式交换线，不等U盘：谁想要那个不认识的运动少女联系方式，运动少女是谁，谁承诺拿到号码就说杀手秘密；如果能给707请直接交出，若号码已经给出请继续给708。')\n"
    if contact_priority and old in out:
        out = out.replace(old, new, 1)
    return out


def write_candidate(label: str, text: str) -> None:
    target = OUT / label
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    (target / "ai.py").write_text(text, encoding="utf-8")


def main() -> int:
    base = BASE.read_text(encoding="utf-8")
    write_candidate("n619a", insert_after_initial_ids(tune_initial_questions(base, "n619a", True), EARLY_QAS_BLOCK, "n619a"))
    write_candidate("n619b", insert_after_initial_ids(tune_initial_questions(base, "n619b", True), CONTACT_FIRST_BLOCK, "n619b"))
    write_candidate("n619c", insert_after_initial_ids(tune_initial_questions(base, "n619c", True), EARLY_HELPER_CALL, "n619c"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
