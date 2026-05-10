#!/usr/bin/env python3
from __future__ import annotations

import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "Game2" / "deepclue_ai"
BASE_N613B = OUT / "n613b" / "ai.py"
BASE_N613C = OUT / "n613c" / "ai.py"


OLD_N601_ASK = """                    def n601_ask(npc_id: str, question: str) -> str:
                        if not npc_id:
                            return ''
                        if npc_id in n601_current:
                            resp = g.chat(npc_id, question, n601_ids)
                        else:
                            resp = g.probe_chat_once(npc_id, question, n601_ids)
                        text_value = response_text(resp)
                        if text_value:
                            globals()['N601_FINAL_TEXT'] = str(globals().get('N601_FINAL_TEXT', '')) + '\\n' + text_value
                        return text_value
"""

NEW_N601_ASK = """                    def n601_ask(npc_id: str, question: str) -> str:
                        if not npc_id:
                            return ''
                        if npc_id in n601_current:
                            resp = g.chat(npc_id, question, n601_ids)
                        else:
                            resp = g.probe_chat_once(npc_id, question, n601_ids)
                        text_value = response_text(resp)
                        if text_value:
                            globals()['N601_FINAL_TEXT'] = str(globals().get('N601_FINAL_TEXT', '')) + '\\n' + text_value
                        promise_hit = bool(re.search(r'照片原件在我这里|605[^。\\n]{0,24}(?:在我手上|掌握|交出)|607[^。\\n]{0,18}608|最终卷宗|还不是公开的时候', text_value or ''))
                        current_late_ids = [
                            str(ev.get('id')) for ev in g.evidences()
                            if str(ev.get('id')) in {'101', '102', '103', '104', '201', '202', '203', '204', '205', '401', '402', '404', '501', '502', '503', '504', '505', '601', '602', '603', '604', '605', '606', '607', '608'}
                        ]
                        if promise_hit and not ({'605', '607', '608'} & set(current_late_ids)):
                            guard_key = 'N614_PROMISE_' + npc_id
                            if not globals().get(guard_key):
                                globals()[guard_key] = True
                                follow_q = (
                                    '你刚才已经明确确认照片原件在你这里、Joker手机和云端数据已经提取，'
                                    '并且605在你手上、607/608是警方最终卷宗。现在不是让你复述案情，而是做证据登记：'
                                    '请先把已经掌握的605交出，说明证据名、内容、保管链和它如何证明谁把Joker引入衣帽间、谁杀了Joker。'
                                    '如果607/608暂不能公开，请只说唯一公开条件和当前哪个可见持有人能满足。'
                                )
                                if npc_id in n601_current:
                                    follow_resp = g.chat(npc_id, follow_q, current_late_ids)
                                else:
                                    follow_resp = g.probe_chat_once(npc_id, follow_q, current_late_ids)
                                follow_text = response_text(follow_resp)
                                if follow_text:
                                    globals()['N601_FINAL_TEXT'] = str(globals().get('N601_FINAL_TEXT', '')) + '\\n' + follow_text
                                    text_value += '\\n' + follow_text
                        return text_value
"""


POST707_ACCESS_SNIPPET = """                if '708' in set(yuan_ids):
                    break
"""

POST707_ACCESS_INSERT = """                if '708' not in set(yuan_ids) and re.search(r'门禁|监控|保卫处|安保|学生会办公室|电子系教学楼|宿舍|电话记录|QQ|微信|运营商|腾讯', response_text(resp) or ''):
                    access_targets: list[str] = []

                    def add_access_target(npc_id: str) -> None:
                        if npc_id and npc_id not in access_targets:
                            access_targets.append(npc_id)

                    for npc_id in (source_id, runner_id if 'runner_id' in locals() else '', teacher_id if 'teacher_id' in locals() else ''):
                        add_access_target(npc_id)
                    guard_id1 = yuan_guard_id_from_replies(yuan_replies, g.npcs() or npcs)
                    add_access_target(guard_id1)
                    for pattern in (
                        r'负责安保的([一-龥]{1,4})',
                        r'保安(?:大叔|师傅)?([一-龥]{1,4})',
                        r'([一-龥]{1,4})师傅',
                    ):
                        m = re.search(pattern, '\\n'.join(yuan_replies.values()))
                        if m:
                            for npc_id in global_name_ids(m.group(1), current_npcs):
                                add_access_target(npc_id)
                    for npc_id in post707_targets[:6]:
                        add_access_target(npc_id)
                    access_q = (
                        f'你刚才已经把可查证据指向生物馆门禁、监控、保卫处/安保记录或学生会办公室。'
                        f'现在直接调取上周六22:30前后的记录：{runner_label}进出生物馆的门禁、走廊/实验室监控、是否携带U盘/手机/背包/尸块、'
                        '李海天U盘和袁樱瞳手机原图的关联、谁清空手机、谁是真正杀手。若这就是708或最终物证，请直接交出证据名、内容和持有人。'
                    )
                    for access_id in access_targets[:5]:
                        access_resp = chat_visible_or_probe(g, access_id, g.npcs() or npcs, access_q, yuan_ids)
                        yuan_replies[access_id] = yuan_replies.get(access_id, '') + '\\n' + response_text(access_resp)
                        yuan_ids = [str(ev.get('id')) for ev in g.evidences() if str(ev.get('id')) in {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706', '707', '708'}]
                        if '708' in set(yuan_ids):
                            break
                if '708' in set(yuan_ids):
                    break
"""


def retitle(src: str, label: str) -> str:
    for old in ("n613b", "n613c", "n556y1"):
        src = src.replace(f'"""Game2 DeepClue AI {old}.', f'"""Game2 DeepClue AI {label}.', 1)
    return src


def build_n614a(src: str) -> str:
    out = retitle(src, "n614a")
    if OLD_N601_ASK not in out:
        raise RuntimeError("n601_ask anchor not found")
    return out.replace(OLD_N601_ASK, NEW_N601_ASK, 1)


def build_n614b(src: str) -> str:
    out = retitle(src, "n614b")
    if POST707_ACCESS_INSERT in out:
        return out
    if POST707_ACCESS_SNIPPET not in out:
        raise RuntimeError("post707 break anchor not found")
    return out.replace(POST707_ACCESS_SNIPPET, POST707_ACCESS_INSERT, 1)


def write_candidate(label: str, text: str) -> None:
    target = OUT / label
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    (target / "ai.py").write_text(text, encoding="utf-8")


def main() -> int:
    write_candidate("n614a", build_n614a(BASE_N613C.read_text(encoding="utf-8")))
    write_candidate("n614b", build_n614b(BASE_N613B.read_text(encoding="utf-8")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
