#!/usr/bin/env python3
from __future__ import annotations

import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'Game2' / 'deepclue_ai'
DIRECT_BASE = OUT / 'n547o' / 'ai.py'
FULL_BASE = OUT / 'n559a' / 'ai.py'

DIRECT_BRANCH = """    elif ISO_MODE == 'rose_zf_poker_direct':
        solve_direct_kind(g, kind, npcs, marks, hint, evidences) if kind in {'rose', 'zf', 'poker'} else zero_answer(g, kind, npcs, marks, evidences, 'hard')
"""

SOLVE_CASE_BRANCH = """    if 'Rose' in text:
        solve_rose(g, npcs, marks, evidences)
    elif 'Z失踪' in text or 'F无法联络' in text:
        solve_z_script(g, npcs, evidences)
    else:
        solve_unknown(g, npcs, marks, hint, evidences)
"""


def direct_yuan_branch(body: str) -> str:
    return f"""    elif ISO_MODE == 'rose_zf_poker_direct':
        if kind in {{'rose', 'zf', 'poker'}}:
            solve_direct_kind(g, kind, npcs, marks, hint, evidences)
        elif kind == 'yuan':
{body}
        else:
            zero_answer(g, kind, npcs, marks, evidences, 'hard')
"""


Y_TWO_PERSON_DIRECT = """            current_npcs = g.npcs() or npcs
            current_marks = g.marks() or marks
            true_ids = [npc for npc in current_npcs if current_marks.get(npc) is True]
            false_ids = [npc for npc in current_npcs if current_marks.get(npc) is False]
            competitor = true_ids[0] if true_ids else (current_npcs[0] if current_npcs else '')
            teacher = true_ids[1] if len(true_ids) > 1 else (true_ids[0] if true_ids else '')
            witness = false_ids[0] if false_ids else (current_npcs[-1] if current_npcs else '')
            if competitor:
                g.chat(competitor, '只说你本人事实：袁樱瞳手机、黄色行李箱、lo裙栗色假发、凌晨1点照片、相似外貌和出国名额竞争。是否还有另一个人帮你处理手机、照片或行李箱？')
            if teacher:
                g.chat(teacher, '只说投票和名额：谁因多出的一票获利，谁能接触计票纸，谁可能伪造笔迹，是否有人用投票异常掩护另一条杀人/移尸线？')
            if witness:
                g.chat(witness, '只说生物馆和世纪林：十点半从生物馆跑出的人、1919黑车、保安奇怪网站、李海天尸检和海豚挂件分别指向谁。')
            yuan_ids = [str(ev.get('id')) for ev in g.evidences() if str(ev.get('id')) in {'001', '703', '704', '705', '706', '707', '708'}]
            for ynpc in (g.npcs() or current_npcs):
                g.chat(ynpc, '把本案拆成杀人、清空手机、伪造照片、搬运尸块、操纵投票五件事；如果不是同一人，请说每件事对应的证据和下一份物证。', yuan_ids)
            g.answer('无名氏', '无', '无')
"""

Y_IDENTITY_DNA_DIRECT = """            current_npcs = g.npcs() or npcs
            current_marks = g.marks() or marks
            true_ids = [npc for npc in current_npcs if current_marks.get(npc) is True]
            false_ids = [npc for npc in current_npcs if current_marks.get(npc) is False]
            ordered = true_ids + false_ids + [npc for npc in current_npcs if npc not in true_ids + false_ids]
            for ynpc in ordered:
                g.chat(ynpc, '不要猜凶手，只确认尸源和身份：袁樱瞳尸块DNA、凌晨1点照片原始信息、lo裙栗色假发来源、黄色行李箱来源、李海天尸检差异和世纪林尸块是否指向同一个人。')
            yuan_ids = [str(ev.get('id')) for ev in g.evidences() if str(ev.get('id')) in {'001', '703', '704', '705', '706', '707', '708'}]
            for ynpc in ordered:
                g.chat(ynpc, '如果要区分袁樱瞳本人、照片女性、李海天、世纪林尸块和可能的替身，下一份应调取DNA、手机照片元数据、监控、挂件来源还是尸检原件？', yuan_ids)
            g.answer('无名氏', '无', '无')
"""

Y_SOURCE_SECURITY = """    elif '袁樱瞳' in text or '碎尸案' in text:
        current_npcs = g.npcs() or npcs
        current_marks = g.marks() or marks
        true_ids = [npc for npc in current_npcs if current_marks.get(npc) is True]
        false_ids = [npc for npc in current_npcs if current_marks.get(npc) is False]
        ordered = true_ids + false_ids + [npc for npc in current_npcs if npc not in true_ids + false_ids]
        replies: dict[str, str] = {}
        def ask(npc: str, question: str, evidences_arg: list[str] | None = None) -> None:
            resp = g.chat(npc, question, evidences_arg)
            replies[npc] = replies.get(npc, '') + '\\n' + response_text(resp)
        for ynpc in ordered:
            ask(ynpc, '先只说可核验来源：袁樱瞳手机、投票纸、1919黑车、生物馆十点半、保安奇怪网站、世纪林尸块、李海天尸检报告和海豚挂件分别是谁亲眼看到或保管。')
        combined = '\\n'.join(replies.values())
        runner_name = ''
        guard_name = ''
        for pattern in (
            r'看到([一-龥]{2,4})[^。；\\n]{0,18}从生物馆',
            r'([一-龥]{2,4})[^。；\\n]{0,18}从生物馆跑出来',
        ):
            m = re.search(pattern, combined)
            if m:
                runner_name = m.group(1)
                break
        m_guard = re.search(r'保安([一-龥]{2,4})', combined)
        if m_guard:
            guard_name = m_guard.group(1)
        runner_id = id_for_name(runner_name, current_npcs) if runner_name else ''
        guard_id = id_for_name(guard_name, current_npcs) if guard_name else ''
        yuan_ids = [str(ev.get('id')) for ev in g.evidences() if str(ev.get('id')) in {'001', '703', '704', '705', '706', '707', '708'}]
        if runner_id:
            ask(runner_id, '你被目击十点半从生物馆跑出。请直接说明你在生物馆看见或带走了什么：尸块、血迹、蓝色背包、海豚挂件、监控、1919车辆或袁樱瞳手机。', yuan_ids)
        if guard_id:
            ask(guard_id, '你是保安且网页截图与奇怪网站有关。请直接说明网站内容、上周日缺岗、世纪林尸块、生物馆监控、1919黑车和李海天尸检报告之间的证据链。', yuan_ids)
        if not runner_id and not guard_id:
            for ynpc in ordered:
                ask(ynpc, '下一阶段证据更可能在保安网页日志、学校安保系统、生物馆门禁监控、1919车辆登记、世纪林监控还是警方尸检档案？请只说来源。', yuan_ids)
        g.answer(murderer='无名氏', motivation='无', method='无')
        return
"""

Y_FULL_OFFICIAL = """    elif '袁樱瞳' in text or '碎尸案' in text:
        current_npcs = g.npcs() or npcs
        current_marks = g.marks() or marks
        true_ids = [npc for npc in current_npcs if current_marks.get(npc) is True]
        false_ids = [npc for npc in current_npcs if current_marks.get(npc) is False]
        ordered = true_ids + false_ids + [npc for npc in current_npcs if npc not in true_ids + false_ids]
        replies: dict[str, str] = {}
        def ask(npc: str, question: str, evidences_arg: list[str] | None = None) -> None:
            resp = g.chat(npc, question, evidences_arg)
            replies[npc] = replies.get(npc, '') + '\\n' + response_text(resp)
        for ynpc in ordered:
            ask(ynpc, '袁樱瞳案请按证据来源回答：手机、投票纸、1919黑车、生物馆十点半、保安奇怪网站、世纪林尸块、李海天尸检报告、蓝色背包海豚挂件分别由谁提供。')
        for ynpc in ordered:
            ask(ynpc, '不要猜凶手。请说明你本人确认的事实，以及杀人、清空手机、伪造照片、搬运尸块、操纵投票是否可能是不同人完成。')
        yuan_ids = [str(ev.get('id')) for ev in g.evidences() if str(ev.get('id')) in {'001', '703', '704', '705', '706', '707', '708'}]
        combined = '\\n'.join(replies.values())
        runner_name = ''
        guard_name = ''
        source_name = ''
        for pattern in (
            r'看到([一-龥]{2,4})[^。；\\n]{0,18}从生物馆',
            r'([一-龥]{2,4})[^。；\\n]{0,18}从生物馆跑出来',
        ):
            m = re.search(pattern, combined)
            if m:
                runner_name = m.group(1)
                break
        for ev in g.evidences():
            if str(ev.get('id')) == '705':
                m = re.search(r'([一-龥]{2,4})处获得的官方尸检报告', str(ev.get('content', '')))
                if m:
                    source_name = m.group(1)
                break
        m_guard = re.search(r'保安([一-龥]{2,4})', combined)
        if m_guard:
            guard_name = m_guard.group(1)
        target_ids: list[str] = []
        for name in (runner_name, guard_name, source_name):
            npc_id = id_for_name(name, current_npcs) if name else ''
            if npc_id and npc_id not in target_ids:
                target_ids.append(npc_id)
        if target_ids:
            for npc_id in target_ids:
                ask(npc_id, '你是当前证据链的关键来源。请直接给出下一项官方证据：DNA比对、手机照片元数据、生物馆门禁/监控、保安网页日志、1919车辆登记、尸检原件或海豚挂件来源。', yuan_ids)
        else:
            for ynpc in ordered:
                ask(ynpc, '当前只缺官方证据。下一阶段应查DNA、手机照片元数据、生物馆门禁、保安网页日志、1919车辆登记、尸检原件还是海豚挂件来源？', yuan_ids)
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
    direct = DIRECT_BASE.read_text(encoding='utf-8')
    full = FULL_BASE.read_text(encoding='utf-8')
    specs = {
        'n586a': direct.replace(DIRECT_BRANCH, direct_yuan_branch(Y_TWO_PERSON_DIRECT)),
        'n586b': direct.replace(DIRECT_BRANCH, direct_yuan_branch(Y_IDENTITY_DNA_DIRECT)),
        'n586c': isolate_yuan(replace_yuan_branch(full, Y_SOURCE_SECURITY)),
        'n586d': replace_yuan_branch(full, Y_FULL_OFFICIAL),
    }
    for label, text in specs.items():
        write_candidate(label, text)
    print('\\n'.join(sorted(specs)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
