#!/usr/bin/env python3
from __future__ import annotations

import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "Game2" / "deepclue_ai"
BASE = OUT / "n622b" / "ai.py"

FORENSIC_ANCHOR = "        forensic_target_name = yuan_candidate_from_replies(yuan_replies, g.npcs() or npcs, g.marks() or marks)\n"
POST706_ANCHOR = "        if '707' in set(yuan_ids):\n            ev707 = next((ev for ev in yuan_evidences if str(ev.get('id')) == '707'), None)\n"
N622_START = "        if '707' in set(yuan_ids) and '708' not in set(yuan_ids):\n            n622_yuan_evidences = g.evidences()\n"
N622_END = "        if '707' in set(yuan_ids) and '708' not in set(yuan_ids):\n            yuan_ids = n612_follow_yuan_contact_exchange(g, current_npcs, yuan_replies, yuan_ids)\n"


def retitle(src: str, label: str) -> str:
    return src.replace('"""Game2 DeepClue AI n622b.', f'"""Game2 DeepClue AI {label}.', 1)


def refresh_yuan_ids_expr() -> str:
    return "[str(ev.get('id')) for ev in yuan_evidences if str(ev.get('id')) in {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706', '707', '708'}]"


def early_combo_block() -> str:
    return f"""        if '707' in set(yuan_ids) and '708' not in set(yuan_ids):
            n623_combo_ids = [str(ev.get('id')) for ev in g.evidences() if str(ev.get('id')) in {{'001', '002', '003', '004', '701', '702', '703', '704', '705', '706', '707', '708'}}]
            ask_all(
                '现在不谈隐私交换和编号，只核对三条你本人能确认的事实：'
                '上周六22:30谁从生物馆慌张跑出以及他手里是否有手机/U盘；'
                '保安是谁、为什么总看奇怪网站、周日为何离岗、我口袋里的模糊网页截图是否与他有关；'
                '袁樱瞳坐过的1919黑车、世纪林尸块和凌晨1点尸体照片如何连到一起。'
                '如果这些会唤起我关于雇主邮件、白色浴缸、手套和刀的记忆，请直接说明。',
                n623_combo_ids,
            )
            yuan_evidences = g.evidences()
            yuan_ids = {refresh_yuan_ids_expr()}
"""


def contact_holder_block() -> str:
    return f"""        if '707' in set(yuan_ids) and '708' not in set(yuan_ids):
            n623_ev707 = next((ev for ev in yuan_evidences if str(ev.get('id')) == '707'), None)
            n623_ev707_text = str(n623_ev707.get('name', '')) + '\\n' + str(n623_ev707.get('content', '')) if isinstance(n623_ev707, dict) else ''
            n623_contact_name = ''
            n623_exchange_name = ''
            m = re.search(r'物证07：([一-龥]{{1,4}})的联系方式', n623_ev707_text)
            if m:
                n623_contact_name = m.group(1)
            for pattern in (
                r'可用于与([一-龥]{{1,4}})交换情报',
                r'与([一-龥]{{1,4}})交换情报',
                r'([一-龥]{{1,4}})曾表示[^。\\n]{{0,30}}联系方式',
                r'([一-龥]{{1,4}})曾表示[^。\\n]{{0,30}}杀手',
            ):
                m = re.search(pattern, n623_ev707_text)
                if m:
                    n623_exchange_name = m.group(1)
                    break
            n623_contact_targets: list[str] = []

            def n623_add_contact_target(npc_id: str) -> None:
                if npc_id and npc_id not in n623_contact_targets:
                    n623_contact_targets.append(npc_id)

            for npc_id in global_name_ids(n623_contact_name, current_npcs, max_ids=4) if n623_contact_name else []:
                n623_add_contact_target(npc_id)
            for npc_id in story_target_ids(n623_ev707_text + '\\n' + '\\n'.join(yuan_replies.values()), current_npcs, max_ids=8):
                if n623_contact_name and cn_name(npc_id) == n623_contact_name:
                    n623_add_contact_target(npc_id)
            for npc_id in current_npcs:
                if n623_contact_name and cn_name(npc_id) == n623_contact_name:
                    n623_add_contact_target(npc_id)
            for contact_id in n623_contact_targets[:3]:
                resp = chat_visible_or_probe(
                    g,
                    contact_id,
                    g.npcs() or current_npcs,
                    f'现在不要求你把号码交给{{n623_exchange_name or \"那个人\"}}，也不问物证编号。请只按你亲眼所见回忆：{{n623_exchange_name or \"那个人\"}}上周六22:30为什么从生物馆慌张跑出来、有没有拿手机/U盘/血迹/背包、他后来为何想要你的联系方式；同时确认你是否也知道保安奇怪网站、周日离岗、1919黑车和世纪林尸块这些线索。若这些事实能让我想起雇主邮件、白色浴缸、手套和刀，请直接说出来。',
                    yuan_ids,
                )
                yuan_replies[contact_id] = yuan_replies.get(contact_id, '') + '\\n' + response_text(resp)
                yuan_evidences = g.evidences()
                yuan_ids = {refresh_yuan_ids_expr()}
                if '708' in set(yuan_ids):
                    break
"""


def post706_combo_block() -> str:
    return f"""        if '706' in set(yuan_ids) and '707' in set(yuan_ids) and '708' not in set(yuan_ids):
            n623_post706_ids = [str(ev.get('id')) for ev in g.evidences() if str(ev.get('id')) in {{'001', '002', '003', '004', '701', '702', '703', '704', '705', '706', '707', '708'}}]
            ask_all(
                '706 U盘和707联系方式已经同时出现。现在不要回到投票，也不要抽象说交换：'
                '请把李海天U盘里的保研名单/不雅视频、王科瑾未保研、袁樱瞳手机清空、'
                '生物馆慌张跑出者、运动少女联系方式、保安奇怪网站/网页截图、1919黑车、世纪林尸块串成一条实物链。'
                '如果这条链能触发物证08或我关于雇主邮件、白色浴缸、手套刀具的记忆，请直接说明。',
                n623_post706_ids,
            )
            yuan_evidences = g.evidences()
            yuan_ids = {refresh_yuan_ids_expr()}
"""


def remove_n622_natural_bridge(src: str, label: str) -> str:
    start = src.find(N622_START)
    end = src.find(N622_END, start)
    if start < 0 or end < 0:
        raise RuntimeError(f"{label}: n622 natural bridge not found")
    return src[:start] + src[end:]


def insert_before_forensic(src: str, block: str, label: str) -> str:
    if FORENSIC_ANCHOR not in src:
        raise RuntimeError(f"{label}: forensic anchor not found")
    return src.replace(FORENSIC_ANCHOR, block + FORENSIC_ANCHOR, 1)


def insert_before_post706_707(src: str, block: str, label: str) -> str:
    idx = src.rfind(POST706_ANCHOR)
    if idx < 0:
        raise RuntimeError(f"{label}: post706/post707 anchor not found")
    return src[:idx] + block + src[idx:]


def build(label: str, variant: str) -> str:
    src = retitle(BASE.read_text(encoding="utf-8"), label)
    if variant == "early_combo":
        return insert_before_forensic(src, early_combo_block(), label)
    if variant == "contact_holder":
        return insert_before_forensic(src, contact_holder_block(), label)
    if variant == "post706_combo":
        return insert_before_post706_707(src, post706_combo_block(), label)
    if variant == "early_combo_no_n622":
        src = remove_n622_natural_bridge(src, label)
        return insert_before_forensic(src, early_combo_block(), label)
    raise ValueError(variant)


def write_candidate(label: str, text: str) -> None:
    target = OUT / label
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    (target / "ai.py").write_text(text, encoding="utf-8")


def main() -> int:
    write_candidate("n623a", build("n623a", "early_combo"))
    write_candidate("n623b", build("n623b", "contact_holder"))
    write_candidate("n623c", build("n623c", "post706_combo"))
    write_candidate("n623d", build("n623d", "early_combo_no_n622"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
