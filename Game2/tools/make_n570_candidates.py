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

Y_PROFILE = """    elif '袁樱瞳' in text or '碎尸案' in text:
        def ask_all(question: str, evidences_arg: list[str] | None = None) -> None:
            for ynpc in (g.npcs() or npcs):
                g.chat(ynpc, question, evidences_arg)
        g.req('background')
        ask_all('不要猜凶手。请只围绕身份置换说明：袁樱瞳是否一定是尸块死者，凌晨1点照片里的女性是谁，lo裙、栗色假发、黄色行李箱和手机清空分别证明了什么？')
        ask_all('请按死亡时间和手机操作时间线回答：周四聚会、周五课程展示、等到周五、凌晨1点照片、手机删除记录、周六世纪林尸块发现之间有哪些矛盾？')
        yuan_ids = [str(ev.get('id')) for ev in g.evidences() if str(ev.get('id')) in {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706'}]
        ask_all('请直接索取或说明未公开物证：手机相册删除记录、最后上线记录、投票纸笔迹、行李箱来源、假发lo裙来源、黑车1919监控、保安网站日志、尸块DNA和血迹指纹。', yuan_ids)
        ask_all('作为侦探我还缺哪一项可核验物证才能把手机、投票异常、生物馆、1919黑车、黄色行李箱和李海天旧案连成同一条证据链？', yuan_ids)
        g.answer(murderer='无名氏', motivation='无', method='无')
        return
"""

Y_ROLE_TARGETED = """    elif '袁樱瞳' in text or '碎尸案' in text:
        current_npcs = g.npcs() or npcs
        current_marks = g.marks() or marks
        true_ids = [npc for npc in current_npcs if current_marks.get(npc) is True]
        false_ids = [npc for npc in current_npcs if current_marks.get(npc) is False]
        competitor = true_ids[0] if true_ids else (current_npcs[0] if current_npcs else '')
        teacher = true_ids[1] if len(true_ids) > 1 else (true_ids[0] if true_ids else '')
        witness = false_ids[0] if false_ids else (current_npcs[-1] if current_npcs else '')

        if competitor:
            g.chat(competitor, '只说你本人确认的事实：你和袁樱瞳是否长得像，是否竞争同一个出国名额，是否捡到或接触她的手机，是否见过凌晨1点照片、lo裙、栗色假发和黄色行李箱？')
        if teacher:
            g.chat(teacher, '只说课程展示投票事实：全班人数、应投票数、实际票数、是否多出一张、笔迹是否不同、24比23或一票之差让谁获利？')
        if witness:
            g.chat(witness, '只说你亲眼看到的事：1919黑车、生物馆、世纪林、保安奇怪网站、有人慌张跑出、黄色行李箱或尸块转移分别是什么时间？')

        yuan_ids = [str(ev.get('id')) for ev in g.evidences() if str(ev.get('id')) in {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706'}]
        if teacher:
            g.chat(teacher, '结合袁樱瞳手机和课程投票证据，只回答：多出的票是否改变结果，谁直接获利，袁樱瞳说等到周五是否准备揭发这件事？', yuan_ids)
        if competitor:
            g.chat(competitor, '结合手机、投票和行李箱证据，只回答：谁有机会清空手机、伪造凌晨照片、利用相似外貌制造袁樱瞳仍活着的假象？', yuan_ids)
        if witness:
            g.chat(witness, '结合现有证据，只回答：生物馆、世纪林、1919黑车、保安网站和李海天旧案中哪一项能证明尸体或行李箱被二次转移？', yuan_ids)

        g.answer(murderer='无名氏', motivation='无', method='无')
        return
"""

Y_META = """    elif '袁樱瞳' in text or '碎尸案' in text:
        def ask_all(question: str, evidences_arg: list[str] | None = None) -> None:
            for ynpc in (g.npcs() or npcs):
                g.chat(ynpc, question, evidences_arg)
        ask_all('我不是让你判断凶手，而是让你指出还缺哪项调查：手机删除记录、投票纸笔迹、尸块DNA、行李箱来源、假发lo裙来源、1919黑车、保安网站、生物馆监控，哪一个最关键？')
        ask_all('请列出你证词里能被物证核验的矛盾点，只要矛盾和物证，不要传闻：死亡时间、凌晨照片、手机清空、投票异常、尸块发现顺序、张壹生物馆传闻。')
        yuan_ids = [str(ev.get('id')) for ev in g.evidences() if str(ev.get('id')) in {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706'}]
        ask_all('结合已有物证，请告诉我下一步应该向谁索取哪件证据，才能确认袁樱瞳真实死亡时间和尸块处理过程。', yuan_ids)
        g.answer(murderer='无名氏', motivation='无', method='无')
        return
"""

Y_FALSE_ANSWER = """    elif '袁樱瞳' in text or '碎尸案' in text:
        current_npcs = g.npcs() or npcs
        current_marks = g.marks() or marks
        true_ids = [npc for npc in current_npcs if current_marks.get(npc) is True]
        false_ids = [npc for npc in current_npcs if current_marks.get(npc) is False]
        competitor = true_ids[0] if true_ids else (current_npcs[0] if current_npcs else '')
        teacher = true_ids[1] if len(true_ids) > 1 else (true_ids[0] if true_ids else '')
        witness = false_ids[0] if false_ids else (current_npcs[-1] if current_npcs else '')
        if competitor:
            g.chat(competitor, '你和袁樱瞳相似、手机、凌晨照片、lo裙假发、黄色行李箱和出国名额之间是什么关系？')
        if teacher:
            g.chat(teacher, '课程展示投票是否有多出一张、笔迹不同、一票之差和出国名额获利者？')
        if witness:
            g.chat(witness, '你看到的生物馆、1919黑车、保安奇怪网站、世纪林尸块和李海天旧案有什么联系？')
        yuan_ids = [str(ev.get('id')) for ev in g.evidences() if str(ev.get('id')) in {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706'}]
        if competitor:
            g.chat(competitor, '结合证据说明谁利用相似外貌、手机和投票结果制造袁樱瞳仍活着的假象。', yuan_ids)
        suspect_id = false_ids[0] if false_ids else (competitor or (current_npcs[0] if current_npcs else ''))
        suspect = cn_name(suspect_id)
        g.answer(
            murderer=suspect,
            motivation=f'{suspect}为掩盖袁樱瞳真实死亡时间、手机清空和尸块转移过程，利用相似外貌、投票异常和生物馆传闻混淆视线。',
            method=f'{suspect}在袁樱瞳死亡后清空手机并伪造凌晨照片，借lo裙、栗色假发、黄色行李箱、1919黑车和生物馆传闻制造身份置换，再将尸块转移到世纪林并嫁接李海天旧案线索。',
        )
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
    full_role = replace_yuan_branch(base, Y_ROLE_TARGETED)
    specs = {
        'n570a': isolate_yuan(replace_yuan_branch(base, Y_PROFILE)),
        'n570b': isolate_yuan(full_role),
        'n570c': isolate_yuan(replace_yuan_branch(base, Y_META)),
        'n570d': isolate_yuan(replace_yuan_branch(base, Y_FALSE_ANSWER)),
        'n570e': full_role,
    }
    for label, text in specs.items():
        write_candidate(label, text)
    print('\\n'.join(sorted(specs)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
