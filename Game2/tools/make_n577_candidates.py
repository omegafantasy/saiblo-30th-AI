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

Y_IDENTITY_FORENSIC = """    elif '袁樱瞳' in text or '碎尸案' in text:
        def ask_all(question: str, evidences_arg: list[str] | None = None) -> None:
            for ynpc in (g.npcs() or npcs):
                g.chat(ynpc, question, evidences_arg)

        ask_all('不要判断凶手，只做身份确认：袁樱瞳是否一定是尸块死者，凌晨1点lo裙栗色假发女性是谁，李海天尸检、蓝色背包海豚挂件、尸块DNA和黄色行李箱分别指向谁？')
        ask_all('按时间轴说明：袁樱瞳等到周五、课程展示投票、手机被清空、凌晨1点照片、周六十点半生物馆、1919黑车、世纪林尸块发现之间有哪些矛盾？')
        yuan_ids = [str(ev.get('id')) for ev in g.evidences() if str(ev.get('id')) in {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706', '707', '708'}]
        ask_all('请直接索取或说明可核验物证：尸块DNA、李海天尸检原件、海豚挂件来源、手机相册删除记录、最后上线记录、行李箱血迹指纹、假发lo裙来源、1919黑车和生物馆监控。', yuan_ids)
        ask_all('如果尸块身份、照片女性和袁樱瞳本人不是同一层问题，请只说明哪项证据能区分真实死者、替身、分尸转移和死亡时间伪造。', yuan_ids)
        g.answer(murderer='无名氏', motivation='无', method='无')
        return
"""

Y_VOTE_BIOLOGY_INTERACTION = """    elif '袁樱瞳' in text or '碎尸案' in text:
        current_npcs = g.npcs() or npcs
        current_marks = g.marks() or marks
        true_ids = [npc for npc in current_npcs if current_marks.get(npc) is True]
        false_ids = [npc for npc in current_npcs if current_marks.get(npc) is False]
        competitor = true_ids[0] if true_ids else (current_npcs[0] if current_npcs else '')
        teacher = true_ids[1] if len(true_ids) > 1 else (true_ids[0] if true_ids else '')
        witness = false_ids[0] if false_ids else (current_npcs[-1] if current_npcs else '')

        if teacher:
            g.chat(teacher, '先只说课程展示投票：全班人数、应投票数、实际票数、多出一张、笔迹不同、24比23或一票之差、最终获利者分别是什么。')
            g.chat(teacher, '袁樱瞳说等到周五是否与投票异常有关？如果多出的票改变了出国名额，请说明谁因此获利，谁会害怕她公开。')
        yuan_ids = [str(ev.get('id')) for ev in g.evidences() if str(ev.get('id')) in {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706', '707', '708'}]
        if witness:
            g.chat(witness, '现在只说周六十点半生物馆：谁跑出来，保安在看什么奇怪网站，1919黑车何时出现，世纪林尸块和李海天旧案如何被你亲眼或物证连接。', yuan_ids)
        if competitor:
            g.chat(competitor, '结合投票异常和生物馆目击，只说袁樱瞳手机、凌晨1点照片、lo裙栗色假发、黄色行李箱和相似外貌能证明谁在制造她仍活着的假象。', yuan_ids)
        if witness:
            g.chat(witness, '不要猜凶手。请把投票异常、生物馆跑出者、1919黑车、保安网站、世纪林尸块按可核验证据排成一条时间线。', yuan_ids)
        g.answer(murderer='无名氏', motivation='无', method='无')
        return
"""

Y_LIHAITIAN_SPLIT_META = """    elif '袁樱瞳' in text or '碎尸案' in text:
        current_npcs = g.npcs() or npcs
        current_marks = g.marks() or marks
        false_ids = [npc for npc in current_npcs if current_marks.get(npc) is False]
        witness = false_ids[0] if false_ids else (current_npcs[-1] if current_npcs else '')

        if witness:
            g.chat(witness, '先不要说张壹。只说李海天旧案、学生会会长、蓝色背包海豚挂件、尸检报告和世纪林尸块之间有什么能被物证证明的联系。')
            g.chat(witness, '现在只说十点半生物馆：你亲眼看到谁跑出来，看到的地点、时间、衣着、行李箱、车辆和保安网站分别是什么。')
        for ynpc in (g.npcs() or current_npcs):
            if ynpc == witness:
                continue
            g.chat(ynpc, '请只补充能核验的物证缺口：手机删除记录、投票纸笔迹、尸块DNA、行李箱来源、1919黑车、生物馆监控、保安网站日志。')
        yuan_ids = [str(ev.get('id')) for ev in g.evidences() if str(ev.get('id')) in {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706', '707', '708'}]
        if witness:
            g.chat(witness, '结合已有物证，只回答下一步应查哪一件证据才能区分张壹传闻、李海天旧案和袁樱瞳碎尸案。', yuan_ids)
        g.answer(murderer='无名氏', motivation='无', method='无')
        return
"""

Y_FALSE_SHORT_ANSWER = """    elif '袁樱瞳' in text or '碎尸案' in text:
        current_npcs = g.npcs() or npcs
        current_marks = g.marks() or marks
        true_ids = [npc for npc in current_npcs if current_marks.get(npc) is True]
        false_ids = [npc for npc in current_npcs if current_marks.get(npc) is False]
        competitor = true_ids[0] if true_ids else (current_npcs[0] if current_npcs else '')
        teacher = true_ids[1] if len(true_ids) > 1 else (true_ids[0] if true_ids else '')
        witness = false_ids[0] if false_ids else (current_npcs[-1] if current_npcs else '')

        if competitor:
            g.chat(competitor, '你与袁樱瞳相似、捡到手机、凌晨1点照片、lo裙栗色假发、黄色行李箱和出国名额竞争之间是什么事实？')
        if teacher:
            g.chat(teacher, '课程展示投票是否多出一张、笔迹不同、一票之差，袁樱瞳等到周五是否准备揭发投票问题？')
        if witness:
            g.chat(witness, '生物馆十点半目击、1919黑车、保安奇怪网站、世纪林尸块和李海天旧案之间哪部分是亲眼事实？')
        yuan_ids = [str(ev.get('id')) for ev in g.evidences() if str(ev.get('id')) in {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706', '707', '708'}]
        if competitor:
            g.chat(competitor, '结合手机、投票和行李箱证据，说明谁利用相似外貌和凌晨照片制造袁樱瞳仍活着的假象。', yuan_ids)

        suspect_id = false_ids[0] if false_ids else (competitor or (current_npcs[0] if current_npcs else ''))
        suspect = cn_name(suspect_id)
        g.answer(
            murderer=suspect,
            motivation=f'{suspect}为掩盖袁樱瞳真实死亡时间和手机、投票、尸块转移证据，利用相似外貌与生物馆传闻混淆视线。',
            method=f'{suspect}清空手机并伪造凌晨照片，借lo裙栗色假发、黄色行李箱、1919黑车和生物馆传闻制造身份置换，再把尸块转移到世纪林。'
        )
        return
"""

Y_CONDITIONAL_705_FULL = """    elif '袁樱瞳' in text or '碎尸案' in text:
        yuan_replies: dict[str, str] = {}
        def ask_all(question: str, evidences_arg: list[str] | None = None) -> None:
            for ynpc in (g.npcs() or npcs):
                resp = g.chat(ynpc, question, evidences_arg)
                yuan_replies[ynpc] = yuan_replies.get(ynpc, '') + '\\n' + response_text(resp)
        ask_all('袁樱瞳碎尸案请完整说明：手机、凌晨1点女性尸体照片、lo裙、栗色假发、黄色行李箱、投票异常、出国名额、张朔、张壹、生物馆、世纪林、李海天、1919黑车、保安奇怪网站分别是什么线索？')
        ask_all('不要只讲传闻。请说明你本人看到或确认了什么：谁从生物馆出来，谁接触尸块或行李箱，谁清空手机，谁伪造死亡时间，谁从投票中获利？')
        yuan_ids = [str(ev.get('id')) for ev in g.evidences() if str(ev.get('id')) in {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706', '707', '708'}]
        ask_all('结合现有证据重新推理袁樱瞳死亡：实际死者是谁，凌晨照片是谁，张壹传闻哪里错，生物馆和世纪林尸块如何连接？', yuan_ids)
        yuan_ids = [str(ev.get('id')) for ev in g.evidences() if str(ev.get('id')) in {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706', '707', '708'}]
        if '705' in yuan_ids:
            ask_all('现在只围绕李海天尸检报告回答：蓝色背包海豚挂件、背部刀伤、失血死亡、肢体分离和袁樱瞳碎尸案之间哪项证据能继续打开旧案关系？', yuan_ids)
        else:
            ask_all('请只说下一项应查的物证，不要猜凶手：尸块DNA、手机删除记录、投票纸笔迹、行李箱来源、假发lo裙来源、1919黑车或生物馆监控哪一个最关键？', yuan_ids)
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
        'n577a': isolate_yuan(replace_yuan_branch(base, Y_IDENTITY_FORENSIC)),
        'n577b': isolate_yuan(replace_yuan_branch(base, Y_VOTE_BIOLOGY_INTERACTION)),
        'n577c': isolate_yuan(replace_yuan_branch(base, Y_LIHAITIAN_SPLIT_META)),
        'n577d': isolate_yuan(replace_yuan_branch(base, Y_FALSE_SHORT_ANSWER)),
        'n577e': replace_yuan_branch(base, Y_CONDITIONAL_705_FULL),
    }
    for label, text in specs.items():
        write_candidate(label, text)
    print('\\n'.join(sorted(specs)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
