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


Y_AMNESIA_WEB_DIRECT = """            current_npcs = g.npcs() or npcs
            current_marks = g.marks() or marks
            true_ids = [npc for npc in current_npcs if current_marks.get(npc) is True]
            false_ids = [npc for npc in current_npcs if current_marks.get(npc) is False]
            ordered = true_ids + false_ids + [npc for npc in current_npcs if npc not in true_ids + false_ids]
            for ynpc in ordered:
                g.chat(ynpc, '开场里保安认识失忆侦探，侦探口袋有模糊网页截图。请只说明这个网页、保安为什么认识我、我的身份、世纪林命案和袁樱瞳/李海天旧案的关系。')
            yuan_ids = [str(ev.get('id')) for ev in g.evidences() if str(ev.get('id')) in {'001', '703', '704', '705', '706', '707', '708'}]
            for ynpc in ordered:
                g.chat(ynpc, '下一阶段证据是否是网页截图复原、保安电脑/浏览记录、侦探身份档案、旧案卷宗、学校安保记录或报警记录？请只说来源。', yuan_ids)
            g.answer('无名氏', '无', '无')
"""

Y_BODY_SPLIT_DIRECT = """            current_npcs = g.npcs() or npcs
            current_marks = g.marks() or marks
            true_ids = [npc for npc in current_npcs if current_marks.get(npc) is True]
            false_ids = [npc for npc in current_npcs if current_marks.get(npc) is False]
            ordered = true_ids + false_ids + [npc for npc in current_npcs if npc not in true_ids + false_ids]
            for ynpc in ordered:
                g.chat(ynpc, '不要默认死者就是袁樱瞳。请只按身份排除：袁樱瞳本人、凌晨照片女尸、世纪林尸块、李海天尸体、替身/相似者分别有什么DNA或身份物证。')
            yuan_ids = [str(ev.get('id')) for ev in g.evidences() if str(ev.get('id')) in {'001', '703', '704', '705', '706', '707', '708'}]
            for ynpc in ordered:
                g.chat(ynpc, '如果袁樱瞳可能未死或尸源混合，下一证据应是DNA比对、照片元数据、尸检原件、手机定位、监控还是失踪记录？', yuan_ids)
            g.answer('无名氏', '无', '无')
"""

Y_ADMIN_QUOTA_DIRECT = """            current_npcs = g.npcs() or npcs
            current_marks = g.marks() or marks
            true_ids = [npc for npc in current_npcs if current_marks.get(npc) is True]
            false_ids = [npc for npc in current_npcs if current_marks.get(npc) is False]
            competitor = true_ids[0] if true_ids else (current_npcs[0] if current_npcs else '')
            teacher = true_ids[1] if len(true_ids) > 1 else (true_ids[0] if true_ids else '')
            witness = false_ids[0] if false_ids else (current_npcs[-1] if current_npcs else '')
            if teacher:
                g.chat(teacher, '不要只说投票纸。出国名额的行政流程、推荐材料、学院系统、办公室记录、名单变更、谁能改结果、谁会被袁樱瞳周五揭发？')
            if competitor:
                g.chat(competitor, '你竞争出国名额。请只说明行政名单、推荐材料、老师办公室、学院系统、投票后名单变更和袁樱瞳周五揭发之间的证据。')
            if witness:
                g.chat(witness, '出国名额/行政名单和生物馆、保安网站、1919黑车是否同线？如果不是，请说哪份学校记录能排除。')
            yuan_ids = [str(ev.get('id')) for ev in g.evidences() if str(ev.get('id')) in {'001', '703', '704', '705', '706', '707', '708'}]
            for ynpc in (g.npcs() or current_npcs):
                g.chat(ynpc, '下一阶段只找出国名额官方记录：行政名单、推荐表、学院系统日志、办公室监控、邮件、导师签字或名单变更记录。', yuan_ids)
            g.answer('无名氏', '无', '无')
"""

Y_FULL_AMNESIA_WEB = """    elif '袁樱瞳' in text or '碎尸案' in text:
        current_npcs = g.npcs() or npcs
        current_marks = g.marks() or marks
        true_ids = [npc for npc in current_npcs if current_marks.get(npc) is True]
        false_ids = [npc for npc in current_npcs if current_marks.get(npc) is False]
        ordered = true_ids + false_ids + [npc for npc in current_npcs if npc not in true_ids + false_ids]
        def ask_all(question: str, evidences_arg: list[str] | None = None) -> None:
            for ynpc in (g.npcs() or current_npcs):
                g.chat(ynpc, question, evidences_arg)
        ask_all('开场保安认识失忆侦探，侦探口袋有模糊网页截图。请按证据来源说明网页内容、保安身份、侦探身份、世纪林尸块、李海天和袁樱瞳之间的连接。')
        ask_all('不要猜凶手。只说下一阶段证据是否在网页截图复原、保安电脑、学校安保系统、旧案卷宗、报警记录、手机照片元数据或DNA比对。')
        yuan_ids = [str(ev.get('id')) for ev in g.evidences() if str(ev.get('id')) in {'001', '703', '704', '705', '706', '707', '708'}]
        ask_all('结合现有证据，失忆侦探和保安为什么会卷入本案？请只给官方档案、网页记录、安保记录或旧案材料来源。', yuan_ids)
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
        'n591a': direct.replace(DIRECT_BRANCH, direct_yuan_branch(Y_AMNESIA_WEB_DIRECT)),
        'n591b': direct.replace(DIRECT_BRANCH, direct_yuan_branch(Y_BODY_SPLIT_DIRECT)),
        'n591c': direct.replace(DIRECT_BRANCH, direct_yuan_branch(Y_ADMIN_QUOTA_DIRECT)),
        'n591d': isolate_yuan(replace_yuan_branch(full, Y_FULL_AMNESIA_WEB)),
    }
    for label, text in specs.items():
        write_candidate(label, text)
    print('\\n'.join(sorted(specs)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
