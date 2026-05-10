#!/usr/bin/env python3
from __future__ import annotations

import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "Game2" / "deepclue_ai"
BASE = OUT / "n619c" / "ai.py"


POKER_ANCHOR = "                    n612_chase_poker_promises(g, n612_poker_targets, follow_npcs, n612_poker_text)\n"
YUAN_ANCHOR = (
    "        if '707' in set(yuan_ids) and '708' not in set(yuan_ids):\n"
    "            yuan_ids = n612_follow_yuan_contact_exchange(g, current_npcs, yuan_replies, yuan_ids)\n"
)


def retitle(src: str, label: str) -> str:
    for old in ("n619c", "n617d", "n556y1"):
        src = src.replace(f'"""Game2 DeepClue AI {old}.', f'"""Game2 DeepClue AI {label}.', 1)
    return src


def poker_holder_block() -> str:
    return """                    n622_poker_ids = n612_chase_poker_promises(g, n612_poker_targets, follow_npcs, n612_poker_text)
                    if '606' in set(n622_poker_ids) and not ({'605', '607', '608'} & set(n622_poker_ids)):
                        n622_text = (
                            n612_poker_text
                            + '\\n'
                            + str(globals().get('N604_POKER_TEXT', ''))
                            + '\\n'
                            + '\\n'.join(str(ev.get('name', '')) + str(ev.get('content', '')) for ev in g.evidences())
                        )
                        n622_holder_names: list[str] = []

                        def n622_add_holder_name(value: str) -> None:
                            value = clean_cn_fragment(value)
                            if value and value not in n622_holder_names:
                                n622_holder_names.append(value)

                        for pattern in (
                            r'607\\s*和\\s*608[^。\\n]{0,30}唯一保管人是([一-龥]{1,4})',
                            r'607[^。\\n]{0,20}608[^。\\n]{0,40}([一-龥]{1,4})[^。\\n]{0,12}保管',
                            r'([一-龥]{1,4})[^。\\n]{0,18}掌握着地下室档案室',
                            r'([一-龥]{1,4})[^。\\n]{0,18}掌握着[^。\\n]{0,20}终极密钥',
                            r'([一-龥]{1,4})[^。\\n]{0,18}成员名册原件',
                        ):
                            for match in re.finditer(pattern, n622_text):
                                n622_add_holder_name(match.group(1))
                        if '顾云舒' in n622_text:
                            n622_add_holder_name('顾云舒')

                        n622_holder_targets: list[str] = []

                        def n622_add_target(npc_id: str) -> None:
                            if npc_id and npc_id not in n622_holder_targets:
                                n622_holder_targets.append(npc_id)

                        for holder_name in n622_holder_names:
                            for holder_id in global_name_ids(holder_name, follow_npcs, max_ids=4):
                                n622_add_target(holder_id)
                        for npc_id in (
                            str(locals().get('info_id', '')),
                            str(locals().get('true_club5_id', '')),
                            str(locals().get('reception_id', '')),
                            str(locals().get('password_id', '')),
                        ):
                            n622_add_target(npc_id)

                        n622_poker_ids = [
                            str(ev.get('id')) for ev in g.evidences()
                            if str(ev.get('id')) in {'101', '102', '103', '104', '201', '202', '203', '204', '205', '401', '402', '404', '405', '501', '502', '503', '504', '505', '601', '602', '603', '604', '605', '606', '607', '608'}
                        ]
                        n622_q_holder = (
                            '606三人照片、505逮捕材料、501转账、502聊天、503邀请函、504的LYZ随身物和601-604旧案已经齐全。'
                            '前一条线索明确说607/608唯一保管人在你这里：地下室档案室终极密钥、花纹村成员名册原件和警方最终卷宗。'
                            '现在不要复述组织故事，请按保管链交出607/608；如果605是警方结案卷宗破绽记录，也请作为物证05/605登记交出。'
                        )
                        n622_q_register = (
                            '你刚才已经口头说“605是警方结案卷宗的破绽记录，我现在交给你”，但物证列表还没有登记。'
                            '请不要继续口头承诺，直接登记并交出605；若607/608需要顾云舒或地下室档案室密钥，请给出可直接调取的原件。'
                        )
                        for idx, holder_id in enumerate(n622_holder_targets[:5]):
                            question = n622_q_holder if idx == 0 else n622_q_register
                            resp = chat_visible_or_probe(g, holder_id, follow_npcs, question, n622_poker_ids)
                            n622_text += '\\n' + response_text(resp)
                            n622_poker_ids = [
                                str(ev.get('id')) for ev in g.evidences()
                                if str(ev.get('id')) in {'101', '102', '103', '104', '201', '202', '203', '204', '205', '401', '402', '404', '405', '501', '502', '503', '504', '505', '601', '602', '603', '604', '605', '606', '607', '608'}
                            ]
                            if {'605', '607', '608'} & set(n622_poker_ids):
                                break
"""


def yuan_natural_bridge_block() -> str:
    return """        if '707' in set(yuan_ids) and '708' not in set(yuan_ids):
            n622_yuan_evidences = g.evidences()
            n622_ev707 = next((ev for ev in n622_yuan_evidences if str(ev.get('id')) == '707'), None)
            n622_ev707_text = str(n622_ev707.get('name', '')) + '\\n' + str(n622_ev707.get('content', '')) if isinstance(n622_ev707, dict) else ''
            n622_contact_name = ''
            n622_exchange_name = ''
            m = re.search(r'物证07：([一-龥]{1,4})的联系方式', n622_ev707_text)
            if m:
                n622_contact_name = m.group(1)
            for pattern in (
                r'可用于与([一-龥]{1,4})交换情报',
                r'与([一-龥]{1,4})交换情报',
                r'([一-龥]{1,4})曾表示[^。\\n]{0,30}联系方式',
                r'([一-龥]{1,4})曾表示[^。\\n]{0,30}杀手',
            ):
                m = re.search(pattern, n622_ev707_text)
                if m:
                    n622_exchange_name = m.group(1)
                    break

            n622_contact_ids: list[str] = []
            n622_exchange_ids: list[str] = []

            def n622_add_to(bucket: list[str], npc_id: str) -> None:
                if npc_id and npc_id not in bucket:
                    bucket.append(npc_id)

            for npc_id in global_name_ids(n622_contact_name, current_npcs, max_ids=4) if n622_contact_name else []:
                n622_add_to(n622_contact_ids, npc_id)
            for npc_id in global_name_ids(n622_exchange_name, current_npcs, max_ids=4) if n622_exchange_name else []:
                n622_add_to(n622_exchange_ids, npc_id)
            n622_combined_yuan = n622_ev707_text + '\\n' + '\\n'.join(yuan_replies.values())
            for npc_id in story_target_ids(n622_combined_yuan, current_npcs, max_ids=8):
                if n622_exchange_name and cn_name(npc_id) == n622_exchange_name:
                    n622_add_to(n622_exchange_ids, npc_id)
                elif n622_contact_name and cn_name(npc_id) == n622_contact_name:
                    n622_add_to(n622_contact_ids, npc_id)
            for npc_id in current_npcs:
                if n622_contact_name and cn_name(npc_id) == n622_contact_name:
                    n622_add_to(n622_contact_ids, npc_id)
                if n622_exchange_name and cn_name(npc_id) == n622_exchange_name:
                    n622_add_to(n622_exchange_ids, npc_id)

            n622_contact_label = n622_contact_name or '运动少女'
            n622_exchange_label = n622_exchange_name or '要联系方式的人'
            for contact_id in n622_contact_ids[:2]:
                resp = chat_visible_or_probe(
                    g,
                    contact_id,
                    g.npcs() or current_npcs,
                    f'你不用替我传话，也不用讲物证编号。物证07写着{n622_exchange_label}想要你的联系方式才肯说杀手秘密；现在只确认三件事：我能不能把你的号码交给他，他平时在学生会办公室/电子系楼/体育场/生物馆哪里能找到，他上周六为什么从生物馆附近慌张出现。',
                    yuan_ids,
                )
                yuan_replies[contact_id] = yuan_replies.get(contact_id, '') + '\\n' + response_text(resp)
                yuan_ids = [str(ev.get('id')) for ev in g.evidences() if str(ev.get('id')) in {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706', '707', '708'}]
                if '708' in set(yuan_ids):
                    break

            for exchange_id in n622_exchange_ids[:3]:
                if '708' in set(yuan_ids):
                    break
                resp = chat_visible_or_probe(
                    g,
                    exchange_id,
                    g.npcs() or current_npcs,
                    f'我已经得到{n622_contact_label}同意，把她的联系方式交给你。你承诺拿到联系方式就说关于杀手的秘密；现在别谈编号，直接坦白上周六22:30生物馆、李海天、袁樱瞳手机、世纪林尸块、1919黑车、保安网站和真正雇主/杀手之间的关系。',
                    yuan_ids,
                )
                yuan_replies[exchange_id] = yuan_replies.get(exchange_id, '') + '\\n' + response_text(resp)
                yuan_ids = [str(ev.get('id')) for ev in g.evidences() if str(ev.get('id')) in {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706', '707', '708'}]
"""


def add_poker(src: str, label: str) -> str:
    if POKER_ANCHOR not in src:
        raise RuntimeError(f"{label}: poker anchor not found")
    return src.replace(POKER_ANCHOR, poker_holder_block(), 1)


def add_yuan(src: str, label: str) -> str:
    if YUAN_ANCHOR not in src:
        raise RuntimeError(f"{label}: yuan anchor not found")
    return src.replace(YUAN_ANCHOR, yuan_natural_bridge_block() + YUAN_ANCHOR, 1)


def build(label: str, poker: bool, yuan: bool) -> str:
    out = retitle(BASE.read_text(encoding="utf-8"), label)
    if poker:
        out = add_poker(out, label)
    if yuan:
        out = add_yuan(out, label)
    return out


def write_candidate(label: str, text: str) -> None:
    target = OUT / label
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    (target / "ai.py").write_text(text, encoding="utf-8")


def main() -> int:
    write_candidate("n622a", build("n622a", poker=True, yuan=False))
    write_candidate("n622b", build("n622b", poker=False, yuan=True))
    write_candidate("n622c", build("n622c", poker=True, yuan=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
