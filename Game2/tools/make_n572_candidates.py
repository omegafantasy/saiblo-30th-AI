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

Y_TEN30_ALL = """    elif '袁樱瞳' in text or '碎尸案' in text:
        def ask_all(question: str, evidences_arg: list[str] | None = None) -> None:
            for ynpc in (g.npcs() or npcs):
                g.chat(ynpc, question, evidences_arg)
        ask_all('请只围绕周六晚上十点半回答：谁在生物馆附近看到有人慌张跑出来，看到的人是不是张壹，保安当时在看什么奇怪网站，1919黑车和世纪林尸块有什么联系？')
        ask_all('请只围绕袁樱瞳本人回答：手机、凌晨1点照片、lo裙栗色假发、黄色行李箱、周五课程展示投票异常和出国名额分别是什么线索？')
        yuan_ids = [str(ev.get('id')) for ev in g.evidences() if str(ev.get('id')) in {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706', '707', '708'}]
        ask_all('结合手机和投票证据，重新核对十点半生物馆目击、保安网站、1919黑车、世纪林尸块和李海天旧案：哪一环是亲眼所见，哪一环只是传闻？', yuan_ids)
        ask_all('不要给凶手结论，只说能核验的证据链：袁樱瞳说等到周五、投票多出一张、凌晨照片、十点半生物馆跑出、张壹传闻之间是否同一人制造？', yuan_ids)
        g.answer(murderer='无名氏', motivation='无', method='无')
        return
"""

Y_TEN30_WITNESS_FIRST = """    elif '袁樱瞳' in text or '碎尸案' in text:
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
        for ynpc in (g.npcs() or current_npcs):
            g.chat(ynpc, '如果你知道十点半生物馆目击和袁樱瞳手机、投票异常之间的联系，请只说可核验证据，不要猜凶手。', yuan_ids)
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
    witness_full = replace_yuan_branch(base, Y_TEN30_WITNESS_FIRST)
    specs = {
        'n572a': isolate_yuan(replace_yuan_branch(base, Y_TEN30_ALL)),
        'n572b': isolate_yuan(witness_full),
        'n572c': witness_full,
    }
    for label, text in specs.items():
        write_candidate(label, text)
    print('\\n'.join(sorted(specs)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
