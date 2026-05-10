#!/usr/bin/env python3
from __future__ import annotations

import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'Game2' / 'deepclue_ai'


POKER_ANCHOR = """                    if {'601', '602', '603', '604', '606'} & set(n604_ids):
                        for npc_id in n604_targets[:8]:
"""

POKER_INSERT = """                    if {'601', '602', '603', '604', '606'} & set(n604_ids):
                        poker_ceiling_sources: list[str] = []

                        def add_poker_ceiling_source(npc_id: str) -> None:
                            if npc_id and npc_id not in poker_ceiling_sources:
                                poker_ceiling_sources.append(npc_id)

                        for npc_id in [
                            str(locals().get('info_id', '')),
                            id_for_name_any('张朔', n604_current),
                            id_for_name_any('刘瑄', n604_current),
                            str(locals().get('target_id', '')),
                            str(locals().get('wang_id', '')),
                            str(locals().get('reception_id', '')),
                            str(locals().get('password_id', '')),
                            str(locals().get('true_club5_id', '')),
                        ]:
                            add_poker_ceiling_source(npc_id)
                        for npc_id in n604_targets:
                            add_poker_ceiling_source(npc_id)

                        if not ({'605', '606', '607', '608'} & set(n604_ids)):
                            for npc_id in poker_ceiling_sources[:5]:
                                n604_ask(npc_id, '601-604已经证明失踪少女、花纹村组织、刘丽雯/林渝植身份。现在不要再问亲子鉴定，直接查606三人照片和左臂POKER纹身：Joker周克、于书华、红桃Q/刘瑄、照片原件、组织名册、现场未交605由谁掌握。')
                                n604_ids = [
                                    str(ev.get('id')) for ev in g.evidences()
                                    if str(ev.get('id')) in {'101', '102', '103', '104', '201', '202', '203', '204', '205', '401', '402', '404', '405', '501', '502', '503', '504', '601', '602', '603', '604', '605', '606', '607', '608'}
                                ]
                                if {'605', '606', '607', '608'} & set(n604_ids):
                                    break

                        if '606' in set(n604_ids) and not ({'605', '607', '608'} & set(n604_ids)):
                            for npc_id in poker_ceiling_sources[:6]:
                                n604_ask(npc_id, '606三人照片已经出现，照片中Joker周克、于书华、红桃Q/刘瑄都有POKER纹身。现在只追下一阶段：你刚说605已在现场掌握，请立刻交出605；如果605不是你持有，就给607/608、最终警方卷宗、组织名册或刘瑄/张朔密码来源的持有人。')
                                n604_ids = [
                                    str(ev.get('id')) for ev in g.evidences()
                                    if str(ev.get('id')) in {'101', '102', '103', '104', '201', '202', '203', '204', '205', '401', '402', '404', '405', '501', '502', '503', '504', '601', '602', '603', '604', '605', '606', '607', '608'}
                                ]
                                if {'605', '607', '608'} & set(n604_ids):
                                    break

                        for npc_id in n604_targets[:8]:
"""


POST_706_START = """        if '706' in set(yuan_ids):
            ev706 = next((ev for ev in yuan_evidences if str(ev.get('id')) == '706'), None)
            ev706_text = str(ev706.get('name', '')) + '\\n' + str(ev706.get('content', '')) if isinstance(ev706, dict) else ''
            post706_targets: list[str] = []
            for npc_id in story_target_ids(ev706_text + '\\n' + '\\n'.join(yuan_replies.values()), current_npcs, max_ids=8):
                if npc_id and npc_id not in post706_targets:
                    post706_targets.append(npc_id)
            for npc_id in (forensic_target_id, teacher_id, runner_id if 'runner_id' in locals() else '', guard_id if 'guard_id' in locals() else ''):
                if npc_id and npc_id not in post706_targets:
                    post706_targets.append(npc_id)
"""

POST_706_START_REPLACEMENT = """        if '706' in set(yuan_ids):
            ev706 = next((ev for ev in yuan_evidences if str(ev.get('id')) == '706'), None)
            ev706_text = str(ev706.get('name', '')) + '\\n' + str(ev706.get('content', '')) if isinstance(ev706, dict) else ''
            post706_targets: list[str] = []

            def add_post706_target(npc_id: str) -> None:
                if npc_id and npc_id not in post706_targets:
                    post706_targets.append(npc_id)

            for pattern in (
                r'([一-龥]{2,4}).{0,12}失物招领',
                r'([一-龥]{2,4}).{0,12}找到.*?U盘',
                r'袁樱瞳、([一-龥]{2,4})保研成功',
                r'([一-龥]{2,4})未能保研',
            ):
                m = re.search(pattern, ev706_text)
                if m:
                    add_post706_target(id_for_name_any(m.group(1), current_npcs))
            for name in ('王科瑾', '楚戎臻', '沈知遥', '许清和'):
                add_post706_target(id_for_name_any(name, current_npcs))
            for npc_id in story_target_ids(ev706_text + '\\n' + '\\n'.join(yuan_replies.values()), current_npcs, max_ids=8):
                add_post706_target(npc_id)
            for npc_id in (forensic_target_id, teacher_id, runner_id if 'runner_id' in locals() else '', guard_id if 'guard_id' in locals() else ''):
                add_post706_target(npc_id)
"""


POST_706_QUESTION = "706 U盘已经说明李海天随身U盘、电子系保研名单、袁樱瞳/楚戎臻保研成功、王科瑾未保研以及李海天侵犯女生视频照片。现在只追下一阶段：谁拿走/隐藏U盘，谁清空袁樱瞳手机，谁利用视频或保研名单杀人，707/708的证据编号、证据名和持有人是什么。"
POST_706_QUESTION_NEW = "706 U盘已经出现。不要回到投票细节，只追名单和视频的后续：王科瑾未保研、楚戎臻保研成功、李海天侵犯女生视频、谁拿走U盘、谁清空袁樱瞳手机、谁用这些材料灭口；如果下一步是707联系方式/杀手秘密或708最终物证，请直接交出编号、证据名和持有人。"


POST_707_ANCHOR = """        if '707' in set(yuan_ids):
            ev707 = next((ev for ev in yuan_evidences if str(ev.get('id')) == '707'), None)
            ev707_text = str(ev707.get('name', '')) + '\\n' + str(ev707.get('content', '')) if isinstance(ev707, dict) else ''
            post707_targets: list[str] = []
"""

POST_707_INSERT = """        if '707' in set(yuan_ids):
            ev707 = next((ev for ev in yuan_evidences if str(ev.get('id')) == '707'), None)
            ev707_text = str(ev707.get('name', '')) + '\\n' + str(ev707.get('content', '')) if isinstance(ev707, dict) else ''
            for exchange_id in (id_for_name_any('楚戎臻', current_npcs), id_for_name_any('许清和', current_npcs), forensic_target_id):
                if not exchange_id:
                    continue
                resp = chat_visible_or_probe(g, exchange_id, g.npcs() or npcs, '707联系方式已经拿到。现在不是继续索要联系方式，而是完成交换条件：许清和承诺用“运动少女”楚戎臻的联系方式换关于杀手的秘密。请直接说这个杀手秘密、对应人物、物证08/708或最终证据的编号、名称和持有人。', yuan_ids)
                yuan_replies[exchange_id] = yuan_replies.get(exchange_id, '') + '\\n' + response_text(resp)
                yuan_evidences = g.evidences()
                yuan_ids = [str(ev.get('id')) for ev in yuan_evidences if str(ev.get('id')) in {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706', '707', '708'}]
                if '708' in set(yuan_ids):
                    break
            ev707 = next((ev for ev in yuan_evidences if str(ev.get('id')) == '707'), None)
            ev707_text = str(ev707.get('name', '')) + '\\n' + str(ev707.get('content', '')) if isinstance(ev707, dict) else ''
            post707_targets: list[str] = []
"""


YUAN_PERSONAL_LINE = """        ask_all('不要只讲传闻。请说明你本人看到或确认了什么：谁从生物馆出来，谁接触尸块或行李箱，谁清空手机，谁伪造死亡时间，谁从投票中获利？')
"""

YUAN_707_LINE = """        ask_all('不要只讲传闻。请说明你本人看到或确认了什么：谁从生物馆出来，谁接触尸块或行李箱，谁清空手机，谁伪造死亡时间，谁从投票中获利？')
        ask_all('单独确认联系方式交换线：许清和是否说过想要那个不认识的“运动少女”的联系方式，运动少女是否是楚戎臻；如果能给707或708，请直接给证据编号、证据名和持有人。')
"""


def write_candidate(label: str, text: str) -> None:
    target = OUT / label
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    (target / 'ai.py').write_text(text, encoding='utf-8')


def poker_ceiling(src: str) -> str:
    if POKER_ANCHOR not in src:
        raise RuntimeError('poker n604 anchor not found')
    return src.replace(POKER_ANCHOR, POKER_INSERT, 1)


def yuan_usb_ceiling(src: str) -> str:
    out = src
    if POST_706_START not in out:
        raise RuntimeError('post706 start not found')
    out = out.replace(POST_706_START, POST_706_START_REPLACEMENT, 1)
    if POST_706_QUESTION not in out:
        raise RuntimeError('post706 question not found')
    out = out.replace(POST_706_QUESTION, POST_706_QUESTION_NEW, 1)
    if POST_707_ANCHOR not in out:
        raise RuntimeError('post707 anchor not found')
    out = out.replace(POST_707_ANCHOR, POST_707_INSERT, 1)
    return out


def yuan_contact_ceiling(src: str) -> str:
    out = src
    if YUAN_PERSONAL_LINE not in out:
        raise RuntimeError('yuan personal line not found')
    out = out.replace(YUAN_PERSONAL_LINE, YUAN_707_LINE, 1)
    if POST_707_ANCHOR in out:
        out = out.replace(POST_707_ANCHOR, POST_707_INSERT, 1)
    return out


def main() -> int:
    n607a = (OUT / 'n607a' / 'ai.py').read_text(encoding='utf-8')
    n608a = (OUT / 'n608a' / 'ai.py').read_text(encoding='utf-8')
    n608b = (OUT / 'n608b' / 'ai.py').read_text(encoding='utf-8')
    write_candidate('n609a', poker_ceiling(n607a))
    write_candidate('n609b', yuan_usb_ceiling(n608a))
    write_candidate('n609c', yuan_contact_ceiling(n608b))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
