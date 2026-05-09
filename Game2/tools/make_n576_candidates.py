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

FIRST_ASK = "        ask_all('袁樱瞳碎尸案请完整说明：手机、凌晨1点女性尸体照片、lo裙、栗色假发、黄色行李箱、投票异常、出国名额、张朔、张壹、生物馆、世纪林、李海天、1919黑车、保安奇怪网站分别是什么线索？')\n"
SECOND_ASK = "        ask_all('不要只讲传闻。请说明你本人看到或确认了什么：谁从生物馆出来，谁接触尸块或行李箱，谁清空手机，谁伪造死亡时间，谁从投票中获利？')\n"

WITNESS_DOUBLE = """        current_npcs = g.npcs() or npcs
        current_marks = g.marks() or marks
        false_ids = [npc for npc in current_npcs if current_marks.get(npc) is False]
        witness = false_ids[0] if false_ids else (current_npcs[-1] if current_npcs else '')
        if witness:
            g.chat(witness, '你在周六晚上十点半到底看到了什么？请直接说明生物馆、张壹、1919黑车、保安奇怪网站、世纪林尸块和李海天旧案之间的亲眼事实。')
            g.chat(witness, '不要复述别人说法，只按时间线说：10:30生物馆门口谁跑出来，保安当时在看什么网站，1919黑车何时出现，之后尸块为何在世纪林。')
"""

Y_ISOLATED_DOUBLE = """    elif '袁樱瞳' in text or '碎尸案' in text:
        current_npcs = g.npcs() or npcs
        current_marks = g.marks() or marks
        true_ids = [npc for npc in current_npcs if current_marks.get(npc) is True]
        false_ids = [npc for npc in current_npcs if current_marks.get(npc) is False]
        competitor = true_ids[0] if true_ids else (current_npcs[0] if current_npcs else '')
        teacher = true_ids[1] if len(true_ids) > 1 else (true_ids[0] if true_ids else '')
        witness = false_ids[0] if false_ids else (current_npcs[-1] if current_npcs else '')
        if witness:
            g.chat(witness, '你在周六晚上十点半到底看到了什么？请直接说明生物馆、张壹、1919黑车、保安奇怪网站、世纪林尸块和李海天旧案之间的亲眼事实。')
            g.chat(witness, '不要复述别人说法，只按时间线说：10:30生物馆门口谁跑出来，保安当时在看什么网站，1919黑车何时出现，之后尸块为何在世纪林。')
        if competitor:
            g.chat(competitor, '袁樱瞳手机、凌晨1点照片、lo裙栗色假发、黄色行李箱、相似外貌和出国名额竞争分别是什么事实？')
        if teacher:
            g.chat(teacher, '周五课程展示投票异常请给出完整数字：应投票数、实际票数、多出一张、笔迹不同、24比23或一票之差，以及谁获利。')
        yuan_ids = [str(ev.get('id')) for ev in g.evidences() if str(ev.get('id')) in {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706', '707', '708'}]
        if witness:
            g.chat(witness, '结合现有证据，只核对十点半生物馆跑出者、保安网站、1919黑车、世纪林尸块和张壹传闻哪一个可以被物证证明。', yuan_ids)
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
    return text.replace(SOLVE_CASE_BRANCH, replacement)


def replace_second(text: str) -> str:
    if SECOND_ASK not in text:
        raise RuntimeError('second Yuan ask anchor missing')
    return text.replace(SECOND_ASK, WITNESS_DOUBLE)


def after_first(text: str) -> str:
    if FIRST_ASK not in text:
        raise RuntimeError('first Yuan ask anchor missing')
    return text.replace(FIRST_ASK, FIRST_ASK + WITNESS_DOUBLE)


def main() -> int:
    base = BASE.read_text(encoding='utf-8')
    specs = {
        'n576a': isolate_yuan(replace_yuan_branch(base, Y_ISOLATED_DOUBLE)),
        'n576b': replace_second(base),
        'n576c': after_first(base),
    }
    for label, text in specs.items():
        write_candidate(label, text)
    print('\\n'.join(sorted(specs)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
