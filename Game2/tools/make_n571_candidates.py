#!/usr/bin/env python3
from __future__ import annotations

import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'Game2' / 'deepclue_ai'
BASE = OUT / 'n559a' / 'ai.py'

SOLVE_CASE_BRANCH = """    if 'Rose' in text:
        solve_rose(g, npcs, marks, evidences)
    elif 'Z失踪' in text or 'F无法联络' in text:
        solve_z_script(g, npcs, evidences)
    else:
        solve_unknown(g, npcs, marks, hint, evidences)
"""

Y_EVIDENCE_MINE = """    elif '袁樱瞳' in text or '碎尸案' in text:
        def ask_all(question: str, evidences_arg: list[str] | None = None) -> None:
            for ynpc in (g.npcs() or npcs):
                g.chat(ynpc, question, evidences_arg)
        ask_all('请不要推理，只交出或指出你能提供的物证：袁樱瞳手机、课程展示投票纸、尸检或DNA、黄色行李箱来源、lo裙假发来源、黑车1919记录、保安网站日志、生物馆监控、世纪林尸块记录。')
        yuan_ids = [str(ev.get('id')) for ev in g.evidences() if str(ev.get('id')) in {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706', '707', '708'}]
        ask_all('结合已有物证，请继续补充还没公开的原始材料：删除的手机照片、投票笔迹、行李箱购买或维修记录、假发衣服购买记录、黑车车牌轨迹、楼道或生物馆监控。', yuan_ids)
        yuan_ids = [str(ev.get('id')) for ev in g.evidences() if str(ev.get('id')) in {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706', '707', '708'}]
        ask_all('如果你没有物证，请明确说谁持有；如果你有物证，请直接给我，不要复述传闻。重点是手机、投票、尸体身份、转移路线、张壹生物馆传闻的可核验证据。', yuan_ids)
        g.answer(murderer='无名氏', motivation='无', method='无')
        return
"""

Y_IDENTITY_DNA = """    elif '袁樱瞳' in text or '碎尸案' in text:
        def ask_all(question: str, evidences_arg: list[str] | None = None) -> None:
            for ynpc in (g.npcs() or npcs):
                g.chat(ynpc, question, evidences_arg)
        ask_all('请只确认尸体身份：世纪林尸块是否经DNA确认就是袁樱瞳，凌晨1点照片中的女性是谁，lo裙栗色假发是否用于替身或身份置换，谁最后见过真正的袁樱瞳？')
        ask_all('请只确认死亡时间：袁樱瞳最后一次真实出现、手机最后一次操作、照片拍摄时间、尸块出现时间、黄色行李箱移动时间分别是什么？')
        yuan_ids = [str(ev.get('id')) for ev in g.evidences() if str(ev.get('id')) in {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706', '707', '708'}]
        ask_all('结合手机和投票证据，请指出能证明身份置换或死亡时间伪造的可核验物证；不要判断凶手，只说证据和持有人。', yuan_ids)
        ask_all('李海天案与袁樱瞳案只比较法医事实：背刺、大量失血、四肢被砍、尸块位置、海豚挂件、蓝色背包、生物馆和世纪林是否有同一个物证连接？', yuan_ids)
        g.answer(murderer='无名氏', motivation='无', method='无')
        return
"""

Y_ROUTE_MONITOR = """    elif '袁樱瞳' in text or '碎尸案' in text:
        current_npcs = g.npcs() or npcs
        current_marks = g.marks() or marks
        true_ids = [npc for npc in current_npcs if current_marks.get(npc) is True]
        false_ids = [npc for npc in current_npcs if current_marks.get(npc) is False]
        competitor = true_ids[0] if true_ids else (current_npcs[0] if current_npcs else '')
        teacher = true_ids[1] if len(true_ids) > 1 else (true_ids[0] if true_ids else '')
        witness = false_ids[0] if false_ids else (current_npcs[-1] if current_npcs else '')
        if competitor:
            g.chat(competitor, '你手上有没有袁樱瞳手机、照片删除记录、黄色行李箱、lo裙假发或出国名额相关原始材料？有就直接交给我。')
        if teacher:
            g.chat(teacher, '你手上有没有课程展示评分表、投票纸、笔迹不同的多出票、出勤名单或最终票数原件？有就直接交给我。')
        if witness:
            g.chat(witness, '你手上有没有1919黑车、生物馆、世纪林、保安网站、楼道或校园监控、李海天旧案物证？有就直接交给我。')
        yuan_ids = [str(ev.get('id')) for ev in g.evidences() if str(ev.get('id')) in {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706', '707', '708'}]
        for ynpc in (g.npcs() or current_npcs):
            g.chat(ynpc, '根据你能核验的物证，请按路线重建：黑车1919到校、手机照片、投票异常、黄色行李箱、生物馆、世纪林尸块、张壹传闻分别由谁接触过。', yuan_ids)
        g.answer(murderer='无名氏', motivation='无', method='无')
        return
"""


def write_candidate(label: str, text: str) -> None:
    target = OUT / label
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    (target / 'ai.py').write_text(text, encoding='utf-8')


def replace_yuan_branch(text: str, branch: str) -> str:
    start = text.index("    elif '袁樱瞳' in text or '碎尸案' in text:\n")
    end = text.index("    else:\n        method = '未知'\n", start)
    return text[:start] + branch + text[end:]


def isolate_yuan(text: str) -> str:
    replacement = """    if '袁樱瞳' in text or '碎尸案' in text:
        solve_unknown(g, npcs, marks, hint, evidences)
    else:
        g.answer(murderer='无名氏', motivation='无', method='无')
"""
    if SOLVE_CASE_BRANCH not in text:
        raise RuntimeError('solve_case branch missing')
    return text.replace(SOLVE_CASE_BRANCH, replacement)


def main() -> int:
    base = BASE.read_text(encoding='utf-8')
    specs = {
        'n571a': isolate_yuan(replace_yuan_branch(base, Y_EVIDENCE_MINE)),
        'n571b': isolate_yuan(replace_yuan_branch(base, Y_IDENTITY_DNA)),
        'n571c': isolate_yuan(replace_yuan_branch(base, Y_ROUTE_MONITOR)),
    }
    for label, text in specs.items():
        write_candidate(label, text)
    print('\\n'.join(sorted(specs)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
