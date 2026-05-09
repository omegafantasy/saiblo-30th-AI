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

Y_PREFIX = """    elif '袁樱瞳' in text or '碎尸案' in text:
        current_npcs = g.npcs() or npcs
        current_marks = g.marks() or marks
        true_ids = [npc for npc in current_npcs if current_marks.get(npc) is True]
        false_ids = [npc for npc in current_npcs if current_marks.get(npc) is False]
        competitor = true_ids[0] if true_ids else (current_npcs[0] if current_npcs else '')
        teacher = true_ids[1] if len(true_ids) > 1 else (true_ids[0] if true_ids else '')
        witness = false_ids[0] if false_ids else (current_npcs[-1] if current_npcs else '')

        if competitor:
            g.chat(competitor, '只说可核验事实：袁樱瞳手机、凌晨1点照片、lo裙栗色假发、黄色行李箱、相似外貌、出国名额竞争分别是什么。')
        if teacher:
            g.chat(teacher, '只说课程展示投票：49人、展示者不投、实际票数、多出笔迹不同票、24比23、一票之差和获利者。')
        if witness:
            g.chat(witness, '只说十点半生物馆、1919黑车、保安奇怪网站、世纪林尸块、李海天尸检报告和蓝色背包海豚挂件的亲眼或物证事实。')
        yuan_ids = [str(ev.get('id')) for ev in g.evidences() if str(ev.get('id')) in {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706', '707', '708'}]
"""

Y_705_SOURCE = Y_PREFIX + """        target_ids = yuan_ids
        if witness:
            g.chat(witness, '围绕705李海天尸检报告继续：这份官方报告从哪里来，谁保管，蓝色背包海豚挂件属于谁，和袁樱瞳尸块有什么同源证据？', target_ids)
            g.chat(witness, '如果还有下一份证据，请直接说证据来源：尸检原件、DNA比对、海豚挂件购买记录、蓝色背包主人或生物馆监控。', target_ids)
        for ynpc in (g.npcs() or current_npcs):
            if ynpc != witness:
                g.chat(ynpc, '你能否确认705尸检报告、海豚挂件、袁樱瞳手机和课程投票之间的下一项物证来源？', target_ids)
        g.answer(murderer='无名氏', motivation='无', method='无')
        return
"""

Y_DNA_DEATH = Y_PREFIX + """        target_ids = yuan_ids
        for ynpc in (g.npcs() or current_npcs):
            g.chat(ynpc, '只围绕法医问题回答：袁樱瞳尸块DNA、真实死因、死亡时间、是否背刺失血、是否断肢、凌晨照片女性和李海天尸检报告有何差异？', target_ids)
        if witness:
            g.chat(witness, '请直接指出能打开下一阶段的法医物证：袁樱瞳DNA报告、李海天尸检差异、海豚挂件来源、尸块二次利用或死亡时间伪造。', target_ids)
        g.answer(murderer='无名氏', motivation='无', method='无')
        return
"""

Y_SECURITY_MONITOR = Y_PREFIX + """        target_ids = yuan_ids
        if witness:
            g.chat(witness, '只围绕监控和路线继续：生物馆十点半、1919黑车、保安奇怪网站、世纪林岗位缺失、尸块转移路线分别有哪些监控或日志能调取？', target_ids)
        for ynpc in (g.npcs() or current_npcs):
            g.chat(ynpc, '如果你知道保安网站日志、生物馆监控、1919黑车行车记录、世纪林监控或宿舍楼梯监控，请直接说可调取的证据。', target_ids)
        g.answer(murderer='无名氏', motivation='无', method='无')
        return
"""

Y_TRAFFICKING_CROSS = Y_PREFIX + """        target_ids = yuan_ids
        for ynpc in (g.npcs() or current_npcs):
            g.chat(ynpc, '不要猜凶手，只说李海天、袁樱瞳、Joker、人口贩卖、匿名转账、1919黑车、生物馆和海豚挂件是否可能来自同一条旧案线索。', target_ids)
        if witness:
            g.chat(witness, '如果李海天尸检和袁樱瞳案背后有同源旧案，请给出下一项证据：转账记录、校内失踪记录、人口贩卖线索、车辆记录或尸检档案。', target_ids)
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
        'n582a': isolate_yuan(replace_yuan_branch(base, Y_705_SOURCE)),
        'n582b': isolate_yuan(replace_yuan_branch(base, Y_DNA_DEATH)),
        'n582c': isolate_yuan(replace_yuan_branch(base, Y_SECURITY_MONITOR)),
        'n582d': isolate_yuan(replace_yuan_branch(base, Y_TRAFFICKING_CROSS)),
    }
    for label, text in specs.items():
        write_candidate(label, text)
    print('\\n'.join(sorted(specs)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
