#!/usr/bin/env python3
from __future__ import annotations

import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "Game2" / "deepclue_ai"


COMMON_HELPERS = r'''
def n612_refresh_ids(g: Game, allowed: set[str]) -> list[str]:
    return [
        str(ev.get('id'))
        for ev in g.evidences()
        if str(ev.get('id')) in allowed
    ]


def n612_add_unique(bucket: list[str], value: str) -> None:
    if value and value not in bucket:
        bucket.append(value)


def n612_chase_poker_promises(g: Game, target_ids: list[str], visible_npcs: list[str], seen_text: str, max_targets: int = 6) -> list[str]:
    allowed = {'101', '102', '103', '104', '201', '202', '203', '204', '205', '401', '402', '404', '405', '501', '502', '503', '504', '505', '601', '602', '603', '604', '605', '606', '607', '608'}
    current_ids = n612_refresh_ids(g, allowed)
    current_set = set(current_ids)
    wanted: list[str] = []
    for eid in ('405', '605', '607', '608'):
        if eid not in current_set and re.search(rf'(?<!\d){eid}(?!\d)', seen_text or ''):
            wanted.append(eid)
    if '605' not in current_set and ('606' in current_set or 'POKER' in (seen_text or '')):
        if any(key in (seen_text or '') for key in ('现场掌握', '警方手里', '保管', '还不是交出', '时机未到', '最终卷宗', '成员名册')):
            n612_add_unique(wanted, '605')
    if not wanted:
        return current_ids

    targets: list[str] = []
    for npc_id in target_ids:
        n612_add_unique(targets, npc_id)
    for npc_id in story_target_ids(seen_text or '', visible_npcs, max_ids=8):
        n612_add_unique(targets, npc_id)
    if not targets:
        targets = list(visible_npcs)

    want_text = '、'.join(wanted)
    question = (
        f'你刚才已经明确提到或暗示了{want_text}，而且说由你保管、现场/警方已经掌握或只是时机未到。'
        '现在不要复述剧情，也不要再说编号听不懂；请按保管链直接交出对应实物。'
        '如果它是LYZ挂件、凶器/血衣、死者手机云端名单、花纹村成员名册、POKER组织照片原件、DNA/指纹报告、车内血迹/行车记录或警方最终卷宗，请直接说证据名、内容和持有人。'
    )
    asked = 0
    for npc_id in targets:
        if not npc_id:
            continue
        resp = chat_visible_or_probe(g, npc_id, visible_npcs, question, current_ids)
        seen_text += '\n' + response_text(resp)
        current_ids = n612_refresh_ids(g, allowed)
        current_set = set(current_ids)
        asked += 1
        if current_set & {'405', '605', '607', '608'}:
            break
        if asked >= max_targets:
            break
    return current_ids


def n612_follow_yuan_contact_exchange(g: Game, current_npcs: list[str], yuan_replies: dict[str, str], yuan_ids: list[str]) -> list[str]:
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

    contact_ids: list[str] = []
    exchange_ids: list[str] = []
    for npc_id in global_name_ids(contact_name, current_npcs) if contact_name else []:
        n612_add_unique(contact_ids, npc_id)
    for npc_id in global_name_ids(exchange_name, current_npcs) if exchange_name else []:
        n612_add_unique(exchange_ids, npc_id)

    relay_targets: list[str] = []
    for npc_id in contact_ids + exchange_ids:
        n612_add_unique(relay_targets, npc_id)
    for npc_id in story_target_ids(ev707_text + '\n' + '\n'.join(yuan_replies.values()), current_npcs, max_ids=8):
        n612_add_unique(relay_targets, npc_id)
    for npc_id in current_npcs:
        n612_add_unique(relay_targets, npc_id)

    contact_label = contact_name or '运动少女'
    exchange_label = exchange_name or '想交换秘密的人'
    direct_exchange_question = (
        f'我已经拿到{contact_label}主动给出的联系方式。你之前说只要拿到这个不认识的运动少女联系方式，就告诉我关于杀手的秘密。'
        '现在请按交换条件兑现：你知道的杀手秘密是什么，谁杀了袁樱瞳，秘密对应的手机原图、U盘视频、网页截图、生物馆监控、1919车辆记录或最终物证在哪里？'
    )
    relay_question = (
        f'这是{contact_label}的联系方式。请你现在当场打电话、发消息或带我去找{exchange_label}，把联系方式交给他，让他兑现“杀手秘密”。'
        '如果他不在当前现场，请说明他的完整身份、学生会/宿舍/办公室位置，以及怎样取得他掌握的最终证据。'
    )
    for npc_id in exchange_ids + contact_ids:
        if not npc_id:
            continue
        question = direct_exchange_question if npc_id in exchange_ids else relay_question
        resp = chat_visible_or_probe(g, npc_id, g.npcs() or current_npcs, question, yuan_ids)
        yuan_replies[npc_id] = yuan_replies.get(npc_id, '') + '\n' + response_text(resp)
        yuan_ids = n612_refresh_ids(g, allowed)
        if '708' in set(yuan_ids):
            return yuan_ids
    for npc_id in relay_targets[:5]:
        resp = chat_visible_or_probe(
            g,
            npc_id,
            g.npcs() or current_npcs,
            f'不要再讨论物证07编号。现在只做一件事：谁能立刻联系或带我找到{exchange_label}，让他用{contact_label}的联系方式交换杀手秘密？请说可执行的找人路径、完整身份和他手里那份最终证据。',
            yuan_ids,
        )
        yuan_replies[npc_id] = yuan_replies.get(npc_id, '') + '\n' + response_text(resp)
        yuan_ids = n612_refresh_ids(g, allowed)
        if '708' in set(yuan_ids):
            break
    return yuan_ids


def n612_follow_yuan_usb(g: Game, current_npcs: list[str], yuan_replies: dict[str, str], yuan_ids: list[str]) -> list[str]:
    allowed = {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706', '707', '708'}
    if '706' not in set(yuan_ids) or {'707', '708'} & set(yuan_ids):
        return yuan_ids
    yuan_evidences = g.evidences()
    ev706 = next((ev for ev in yuan_evidences if str(ev.get('id')) == '706'), None)
    ev706_text = str(ev706.get('name', '')) + '\n' + str(ev706.get('content', '')) if isinstance(ev706, dict) else ''
    targets: list[str] = []
    for npc_id in story_target_ids(ev706_text + '\n' + '\n'.join(yuan_replies.values()), current_npcs, max_ids=10):
        n612_add_unique(targets, npc_id)
    for name in ('张子韩', '李海天', '袁樱瞳', '王科瑾', '江沐青', '叶青衡', '楚戎臻', '沈知遥', '陆亦初'):
        for npc_id in global_name_ids(name, current_npcs):
            n612_add_unique(targets, npc_id)
    for npc_id in current_npcs:
        n612_add_unique(targets, npc_id)

    question = (
        '706 U盘不是终点。请直接打开U盘内容继续查：电子系保研名单里谁获利、谁未保研，李海天侵犯女生的视频照片里出现了哪些人，'
        '袁樱瞳周五要揭发谁，谁因此清空她手机或伪造凌晨照片。下一步如果需要受害女生/运动少女联系方式、交换杀手秘密、手机原图元数据、生物馆监控或最终物证，请直接给707/708的证据名和持有人。'
    )
    for npc_id in targets[:8]:
        resp = chat_visible_or_probe(g, npc_id, g.npcs() or current_npcs, question, yuan_ids)
        yuan_replies[npc_id] = yuan_replies.get(npc_id, '') + '\n' + response_text(resp)
        yuan_ids = n612_refresh_ids(g, allowed)
        if {'707', '708'} & set(yuan_ids):
            break
    return yuan_ids

'''


POKER_PROMISE_CALL = r'''                if 'follow_npcs' in locals():
                    n612_poker_text = '\n'.join([
                        str(locals().get('reply', '')),
                        str(response_text(locals().get('password_resp', {})) if 'password_resp' in locals() else ''),
                        str(response_text(locals().get('proof_resp', {})) if 'proof_resp' in locals() else ''),
                        str(locals().get('gate_text', '')),
                        str(locals().get('deep_text', '')),
                        str(locals().get('n601_text', '')),
                        str(locals().get('n604_text', '')),
                        str(globals().get('N600_DEEP_TEXT', '')),
                        str(globals().get('N601_FINAL_TEXT', '')),
                        str(globals().get('N604_POKER_TEXT', '')),
                        '\n'.join(str(ev.get('name', '')) + str(ev.get('content', '')) for ev in g.evidences()),
                    ])
                    n612_poker_targets: list[str] = []
                    for _npc in (
                        str(locals().get('info_id', '')),
                        str(locals().get('password_id', '')),
                        str(locals().get('reception_id', '')),
                        str(locals().get('true_club5_id', '')),
                        str(locals().get('target_id', '')),
                        str(locals().get('wang_id', '')),
                        str(locals().get('luo_id', '')),
                    ):
                        n612_add_unique(n612_poker_targets, _npc)
                    for _npc in story_target_ids(n612_poker_text, follow_npcs, max_ids=10):
                        n612_add_unique(n612_poker_targets, _npc)
                    n612_chase_poker_promises(g, n612_poker_targets, follow_npcs, n612_poker_text)
'''


YUAN_FOLLOW_CALL_N607 = r'''        yuan_ids = n612_follow_yuan_usb(g, current_npcs, yuan_replies, yuan_ids)
        yuan_ids = n612_follow_yuan_contact_exchange(g, current_npcs, yuan_replies, yuan_ids)
'''


YUAN_FOLLOW_CALL_N611B = r'''        yuan_ids = n612_follow_yuan_usb(g, current_npcs, replies, yuan_ids)
        yuan_ids = n612_follow_yuan_contact_exchange(g, current_npcs, replies, yuan_ids)
'''


def write_candidate(label: str, text: str) -> None:
    target = OUT / label
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    (target / "ai.py").write_text(text, encoding="utf-8")


def retitle(src: str, label: str) -> str:
    return src.replace('"""Game2 DeepClue AI n556y1.', f'"""Game2 DeepClue AI {label}.', 1).replace('"""Game2 DeepClue AI n611a.', f'"""Game2 DeepClue AI {label}.', 1)


def add_common_helpers(src: str) -> str:
    if "def n612_chase_poker_promises" in src:
        return src
    for marker in ("def poker_true_club5_name(text: str) -> str:\n", "def rose_roles(npcs: list[str], marks: dict[str, bool], evidences: list[dict[str, Any]]) -> dict[str, tuple[str, str]]:\n"):
        if marker in src:
            return src.replace(marker, COMMON_HELPERS + "\n" + marker, 1)
    raise RuntimeError("helper insertion marker not found")


def add_missing_general_helpers_for_simple_base(src: str) -> str:
    if "def id_for_name_any" not in src:
        src = src.replace(
            "def clean_cn_fragment(raw: str) -> str:\n",
            "def id_for_name_any(name: str, npcs: list[str]) -> str:\n"
            "    return id_for_name(name, npcs) or CN_TO_PINYIN.get(name, '')\n\n\n"
            "def clean_cn_fragment(raw: str) -> str:\n",
            1,
        )
    if "def story_target_ids" not in src:
        marker = "def rose_roles(npcs: list[str], marks: dict[str, bool], evidences: list[dict[str, Any]]) -> dict[str, tuple[str, str]]:\n"
        block = r'''
def story_target_ids(text: str, current_npcs: list[str], max_ids: int = 8) -> list[str]:
    ids: list[str] = []

    def add(npc_id: str) -> None:
        if npc_id and npc_id not in ids:
            ids.append(npc_id)

    for name in extract_story_names(text):
        for npc_id in global_name_ids(name, current_npcs):
            add(npc_id)
            if len(ids) >= max_ids:
                return ids
    return ids


def chat_visible_or_probe(g: Game, npc: str, visible_npcs: list[str], question: str, evidences: list[str] | None = None) -> dict[str, Any]:
    if npc in set(visible_npcs):
        return g.chat(npc, question, evidences)
    return g.probe_chat_once(npc, question, evidences)

'''
        src = src.replace(marker, block + marker, 1)
    return src


def add_poker_promise_call(src: str) -> str:
    if "n612_chase_poker_promises(g, n612_poker_targets" in src:
        return src
    marker = "                if g.stage < 3 and ev_ids:\n"
    if marker not in src:
        raise RuntimeError("poker promise call marker not found")
    return src.replace(marker, POKER_PROMISE_CALL + marker, 1)


def add_yuan_follow_call_n607_shape(src: str) -> str:
    if "n612_follow_yuan_contact_exchange(g, current_npcs, yuan_replies" in src:
        return src
    marker = "        ask_all('结合现有证据重新推理袁樱瞳死亡：实际死者是谁，凌晨照片是谁，张壹传闻哪里错，生物馆和世纪林尸块如何连接？', yuan_ids)\n"
    if marker not in src:
        raise RuntimeError("yuan follow marker n607 not found")
    return src.replace(marker, YUAN_FOLLOW_CALL_N607 + marker, 1)


def add_yuan_follow_call_n611b_shape(src: str) -> str:
    if "n612_follow_yuan_contact_exchange(g, current_npcs, replies" in src:
        return src
    marker = "        if '706' in yuan_ids or '707' in yuan_ids or '708' in yuan_ids:\n"
    if marker not in src:
        raise RuntimeError("yuan follow marker n611b not found")
    return src.replace(marker, YUAN_FOLLOW_CALL_N611B + marker, 1)


def main() -> int:
    n607a = (OUT / "n607a" / "ai.py").read_text(encoding="utf-8")
    n611a = (OUT / "n611a" / "ai.py").read_text(encoding="utf-8")
    n611b = (OUT / "n611b" / "ai.py").read_text(encoding="utf-8")

    n612a = add_yuan_follow_call_n607_shape(add_poker_promise_call(add_common_helpers(retitle(n607a, "n612a"))))
    n612b = add_yuan_follow_call_n607_shape(add_poker_promise_call(add_common_helpers(retitle(n611a, "n612b"))))
    n612c = add_yuan_follow_call_n611b_shape(add_poker_promise_call(add_common_helpers(add_missing_general_helpers_for_simple_base(retitle(n611b, "n612c")))))

    write_candidate("n612a", n612a)
    write_candidate("n612b", n612b)
    write_candidate("n612c", n612c)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
