#!/usr/bin/env python3
from __future__ import annotations

import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "Game2" / "deepclue_ai"
BASE_N614A = OUT / "n614a" / "ai.py"
BASE_N606A = OUT / "n606a" / "ai.py"


def retitle(src: str, label: str) -> str:
    for old in ("n614a", "n606a", "n556y1"):
        src = src.replace(f'"""Game2 DeepClue AI {old}.', f'"""Game2 DeepClue AI {label}.', 1)
    return src


def build_n616a(src: str) -> str:
    out = retitle(src, "n616a")
    anchor = """                                if follow_text:
                                    globals()['N601_FINAL_TEXT'] = str(globals().get('N601_FINAL_TEXT', '')) + '\\n' + follow_text
                                    text_value += '\\n' + follow_text
                        return text_value
"""
    insert = """                                if follow_text:
                                    globals()['N601_FINAL_TEXT'] = str(globals().get('N601_FINAL_TEXT', '')) + '\\n' + follow_text
                                    text_value += '\\n' + follow_text
                                    if re.search(r'警局授权|刑警队的证件|林渝植的下落|个人的调查笔记|不能交给你登记|最终卷宗|现在根本不存在|时机未到', follow_text):
                                        auth_ids = [
                                            str(ev.get('id')) for ev in g.evidences()
                                            if str(ev.get('id')) in {'101', '102', '103', '104', '201', '202', '203', '204', '205', '401', '402', '404', '501', '502', '503', '504', '505', '601', '602', '603', '604', '605', '606', '607', '608'}
                                        ]
                                        auth_q = (
                                            '你提出的条件现在逐项满足：504的LYZ随身物、601右眼角心形胎记、603/604刘丽雯身份和606三人POKER纹身照片，'
                                            '已经足够定位林渝植/真正梅花5；而你本人若是景观或刑警信息源，本身具备警局授权。'
                                            '不要交内部最终卷宗；只先把能公开的部分转成证据登记：个人调查笔记的可公开摘录、现场扣押清单、照片原件登记、Joker手机云端提取记录、'
                                            '或林渝植本人确认笔录。请直接给当前可以提交的证据名、内容、持有人。'
                                        )
                                        if npc_id in n601_current:
                                            auth_resp = g.chat(npc_id, auth_q, auth_ids)
                                        else:
                                            auth_resp = g.probe_chat_once(npc_id, auth_q, auth_ids)
                                        auth_text = response_text(auth_resp)
                                        if auth_text:
                                            globals()['N601_FINAL_TEXT'] = str(globals().get('N601_FINAL_TEXT', '')) + '\\n' + auth_text
                                            text_value += '\\n' + auth_text
                        return text_value
"""
    if anchor not in out:
        raise RuntimeError("n616a auth anchor not found")
    return out.replace(anchor, insert, 1)


def build_n616b(src: str) -> str:
    out = retitle(src, "n616b")
    start = out.index("        if forensic_target_id and '703' in set(yuan_ids):")
    end = out.index("        if forensic_target_id and '704' in set(yuan_ids) and '706' not in set(yuan_ids):", start)
    replacement = """        if teacher_id and '704' in set(yuan_ids):
            clean_vote_q = (
                '先只核对课堂投票原件，不问警方编号：票箱从教室到办公室具体由谁保管，谁能接触原始票，'
                '全班49人、展示2人不投、缺席者未到场时为什么还能多出一票；那一票的笔迹和其他票哪里不同。'
                '如果投票异常连接到李海天随身U盘、失物招领、电子系保研名单或不雅视频，请直接说是哪份实物和谁发现的。'
            )
            resp = g.chat(teacher_id, clean_vote_q, yuan_ids)
            yuan_replies[teacher_id] = yuan_replies.get(teacher_id, '') + '\\n' + response_text(resp)
            yuan_evidences = g.evidences()
            yuan_ids = [str(ev.get('id')) for ev in yuan_evidences if str(ev.get('id')) in {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706', '707', '708'}]
        if teacher_id and '704' in set(yuan_ids) and '706' not in set(yuan_ids):
            clean_vote_q2 = (
                '继续只看原始票和行政链：多出的异笔迹票是谁写的，缺席者是谁，点名册、座位表、办公室监控、行政系统日志在哪里。'
                '如果老师没有U盘，请指出失物招领处、李海天、保研名单、不雅视频照片这条线的第一个可见持有人。'
            )
            resp = g.chat(teacher_id, clean_vote_q2, yuan_ids)
            yuan_replies[teacher_id] = yuan_replies.get(teacher_id, '') + '\\n' + response_text(resp)
            yuan_evidences = g.evidences()
            yuan_ids = [str(ev.get('id')) for ev in yuan_evidences if str(ev.get('id')) in {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706', '707', '708'}]
        if forensic_target_id and '703' in set(yuan_ids) and '706' not in set(yuan_ids):
            resp = g.chat(forensic_target_id, '先不问尸检和编号。你捡到袁樱瞳手机或竞争名额：请只说明手机是谁清空、她说“等到周五”要揭发什么、李海天随身U盘是否在失物招领、U盘里的保研名单和不雅视频照片谁见过。', yuan_ids)
            yuan_replies[forensic_target_id] = yuan_replies.get(forensic_target_id, '') + '\\n' + response_text(resp)
            yuan_evidences = g.evidences()
            yuan_ids = [str(ev.get('id')) for ev in yuan_evidences if str(ev.get('id')) in {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706', '707', '708'}]
"""
    return out[:start] + replacement + out[end:]


def write_candidate(label: str, text: str) -> None:
    target = OUT / label
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    (target / "ai.py").write_text(text, encoding="utf-8")


def main() -> int:
    write_candidate("n616a", build_n616a(BASE_N614A.read_text(encoding="utf-8")))
    write_candidate("n616b", build_n616b(BASE_N606A.read_text(encoding="utf-8")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
