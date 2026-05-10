#!/usr/bin/env python3
from __future__ import annotations

import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'Game2' / 'deepclue_ai'


POST_706_BLOCK = """        if '706' in set(yuan_ids):
            ev706 = next((ev for ev in yuan_evidences if str(ev.get('id')) == '706'), None)
            ev706_text = str(ev706.get('name', '')) + '\\n' + str(ev706.get('content', '')) if isinstance(ev706, dict) else ''
            post706_targets: list[str] = []
            for npc_id in story_target_ids(ev706_text + '\\n' + '\\n'.join(yuan_replies.values()), current_npcs, max_ids=8):
                if npc_id and npc_id not in post706_targets:
                    post706_targets.append(npc_id)
            for npc_id in (forensic_target_id, teacher_id, runner_id if 'runner_id' in locals() else '', guard_id if 'guard_id' in locals() else ''):
                if npc_id and npc_id not in post706_targets:
                    post706_targets.append(npc_id)
            for source_id in post706_targets[:5]:
                resp = chat_visible_or_probe(g, source_id, g.npcs() or npcs, '706 U盘已经说明李海天随身U盘、电子系保研名单、袁樱瞳/楚戎臻保研成功、王科瑾未保研以及李海天侵犯女生视频照片。现在只追下一阶段：谁拿走/隐藏U盘，谁清空袁樱瞳手机，谁利用视频或保研名单杀人，707/708的证据编号、证据名和持有人是什么。', yuan_ids)
                yuan_replies[source_id] = yuan_replies.get(source_id, '') + '\\n' + response_text(resp)
                yuan_evidences = g.evidences()
                yuan_ids = [str(ev.get('id')) for ev in yuan_evidences if str(ev.get('id')) in {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706', '707', '708'}]
                if {'707', '708'} & set(yuan_ids):
                    break
            if not ({'707', '708'} & set(yuan_ids)):
                ask_all('706已经出现。不要回到投票细节，沿U盘内容追707/708：李海天侵犯袁樱瞳等女生的视频照片、电子系保研名单、王科瑾未保研、手机清空、凌晨尸体照片、生物馆和世纪林尸块之间，下一份官方物证是什么？', yuan_ids)
            yuan_evidences = g.evidences()
            yuan_ids = [str(ev.get('id')) for ev in yuan_evidences if str(ev.get('id')) in {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706', '707', '708'}]
"""

POST_707_BLOCK = POST_706_BLOCK + """        if '707' in set(yuan_ids):
            ev707 = next((ev for ev in yuan_evidences if str(ev.get('id')) == '707'), None)
            ev707_text = str(ev707.get('name', '')) + '\\n' + str(ev707.get('content', '')) if isinstance(ev707, dict) else ''
            post707_targets: list[str] = []
            for name in ('许清和', '楚戎臻'):
                npc_id = id_for_name_any(name, current_npcs)
                if npc_id and npc_id not in post707_targets:
                    post707_targets.append(npc_id)
            for npc_id in story_target_ids(ev707_text + '\\n' + '\\n'.join(yuan_replies.values()), current_npcs, max_ids=8):
                if npc_id and npc_id not in post707_targets:
                    post707_targets.append(npc_id)
            for source_id in post707_targets[:5]:
                resp = chat_visible_or_probe(g, source_id, g.npcs() or npcs, '707联系方式已经拿到。现在按交换条件推进：把楚戎臻的联系方式交给许清和，要求他说出关于“杀手”的秘密；这个秘密对应谁、什么证据、是否能打开708或最终物证？直接给证据编号、证据名、持有人。', yuan_ids)
                yuan_replies[source_id] = yuan_replies.get(source_id, '') + '\\n' + response_text(resp)
                yuan_evidences = g.evidences()
                yuan_ids = [str(ev.get('id')) for ev in yuan_evidences if str(ev.get('id')) in {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706', '707', '708'}]
                if '708' in set(yuan_ids):
                    break
            if '708' not in set(yuan_ids):
                ask_all('707已经出现。不要总结碎尸案，只执行联系方式交换：许清和用“运动少女”楚戎臻的联系方式换来的杀手秘密是什么，下一份物证08/708在哪里，谁持有？', yuan_ids)
            yuan_evidences = g.evidences()
            yuan_ids = [str(ev.get('id')) for ev in yuan_evidences if str(ev.get('id')) in {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706', '707', '708'}]
"""

YUAN_USB_AFTER_TEACHER = """        if teacher_id and '704' in set(yuan_ids) and '706' not in set(yuan_ids):
            resp = g.chat(teacher_id, '不要泛问物证编号，只沿投票异常和电子系材料查：多出的异笔迹票、票箱锁入办公室、失物招领处李海天随身U盘、电子系保研名单、不雅视频照片、谁能接触U盘和原始票；如果这是物证06/706请直接交出。', yuan_ids)
            yuan_replies[teacher_id] = yuan_replies.get(teacher_id, '') + '\\n' + response_text(resp)
            yuan_evidences = g.evidences()
            yuan_ids = [str(ev.get('id')) for ev in yuan_evidences if str(ev.get('id')) in {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706', '707', '708'}]
"""

YUAN_ORIGINAL_BALLOT = YUAN_USB_AFTER_TEACHER + """        if teacher_id and '704' in set(yuan_ids) and '706' not in set(yuan_ids):
            resp = g.chat(teacher_id, '你刚才已经确认多出一张异笔迹票，且原始票在办公室或票箱中。现在不要讨论推理，请直接交出那张多出的原始票、签到/缺席记录、票箱钥匙流转、失物招领处李海天U盘；如果这些对应706或708，请直接给证据。', yuan_ids)
            yuan_replies[teacher_id] = yuan_replies.get(teacher_id, '') + '\\n' + response_text(resp)
            yuan_evidences = g.evidences()
            yuan_ids = [str(ev.get('id')) for ev in yuan_evidences if str(ev.get('id')) in {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706', '707', '708'}]
"""


def add_post707(src: str) -> str:
    if POST_706_BLOCK not in src:
        raise RuntimeError('post 706 block not found')
    return src.replace(POST_706_BLOCK, POST_707_BLOCK, 1)


def add_original_ballot(src: str) -> str:
    if YUAN_USB_AFTER_TEACHER not in src:
        raise RuntimeError('teacher usb block not found')
    return src.replace(YUAN_USB_AFTER_TEACHER, YUAN_ORIGINAL_BALLOT, 1)


def write_candidate(label: str, text: str) -> None:
    target = OUT / label
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    (target / 'ai.py').write_text(text, encoding='utf-8')


def main() -> int:
    n607a = (OUT / 'n607a' / 'ai.py').read_text(encoding='utf-8')
    n607b = (OUT / 'n607b' / 'ai.py').read_text(encoding='utf-8')
    write_candidate('n608a', add_post707(n607a))
    write_candidate('n608b', add_post707(n607b))
    write_candidate('n608c', add_original_ballot(add_post707(n607a)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
