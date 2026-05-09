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

Y_TEMPLATE = """    elif '袁樱瞳' in text or '碎尸案' in text:
        current_npcs = g.npcs() or npcs
        current_marks = g.marks() or marks
        true_ids = [npc for npc in current_npcs if current_marks.get(npc) is True]
        false_ids = [npc for npc in current_npcs if current_marks.get(npc) is False]
        competitor = true_ids[0] if true_ids else (current_npcs[0] if current_npcs else '')
        teacher = true_ids[1] if len(true_ids) > 1 else (true_ids[0] if true_ids else '')
        witness = false_ids[0] if false_ids else (current_npcs[-1] if current_npcs else '')
        if witness:
            g.chat(witness, '你在周六晚上十点半到底看到了什么？请直接说明生物馆、张壹、1919黑车、保安奇怪网站、世纪林尸块和李海天旧案之间的亲眼事实。')
        if competitor:
            g.chat(competitor, '袁樱瞳手机、凌晨1点照片、lo裙栗色假发、黄色行李箱、相似外貌和出国名额竞争分别是什么事实？')
        if teacher:
            g.chat(teacher, '周五课程展示投票异常请给出完整数字：应投票数、实际票数、多出一张、笔迹不同、24比23或一票之差，以及谁获利。')
        yuan_ids = [str(ev.get('id')) for ev in g.evidences() if str(ev.get('id')) in {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706', '707', '708'}]
        if witness:
            g.chat(witness, '结合现有证据，只核对十点半生物馆跑出者、保安网站、1919黑车、世纪林尸块和张壹传闻哪一个可以被物证证明。', yuan_ids)
        {answer_block}
        return
"""

ANSWER_ZERO = "g.answer(murderer='无名氏', motivation='无', method='无')"
ANSWER_COMPETITOR = """suspect = cn_name(competitor)
        g.answer(
            murderer=suspect,
            motivation=f'{suspect}为争夺出国名额并掩盖投票作弊，利用与袁樱瞳相似的外貌、手机照片和黄色行李箱制造死亡时间与身份混淆。',
            method=f'{suspect}清空袁樱瞳手机并伪造凌晨1点照片，借lo裙栗色假发和黄色行李箱制造袁樱瞳仍活着的假象，再用张壹十点半生物馆传闻、1919黑车和世纪林尸块转移线索混淆视听。',
        )"""
ANSWER_FALSE = """suspect = cn_name(witness)
        g.answer(
            murderer=suspect,
            motivation=f'{suspect}为掩盖十点半生物馆目击、1919黑车和世纪林尸块转移真相，制造张壹传闻并混淆袁樱瞳死亡时间。',
            method=f'{suspect}利用保安网站、生物馆目击和张壹传闻转移视线，配合手机清空、凌晨照片、黄色行李箱和投票异常，把袁樱瞳案伪装成旧案重演。',
        )"""
ANSWER_TEACHER = """suspect = cn_name(teacher)
        g.answer(
            murderer=suspect,
            motivation=f'{suspect}为维护课程投票和出国名额结果，隐瞒多出一张票、笔迹不同和袁樱瞳准备周五揭发的事实。',
            method=f'{suspect}利用投票异常诱发冲突，再借手机清空、凌晨照片、黄色行李箱、生物馆十点半传闻和1919黑车线索混淆袁樱瞳死亡时间。',
        )"""


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


def branch(answer_block: str) -> str:
    return Y_TEMPLATE.replace('{answer_block}', answer_block)


def main() -> int:
    base = BASE.read_text(encoding='utf-8')
    specs = {
        'n575a': isolate_yuan(replace_yuan_branch(base, branch(ANSWER_COMPETITOR))),
        'n575b': isolate_yuan(replace_yuan_branch(base, branch(ANSWER_FALSE))),
        'n575c': isolate_yuan(replace_yuan_branch(base, branch(ANSWER_TEACHER))),
        'n575d': isolate_yuan(replace_yuan_branch(base, branch(ANSWER_ZERO))),
    }
    for label, text in specs.items():
        write_candidate(label, text)
    print('\\n'.join(sorted(specs)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
