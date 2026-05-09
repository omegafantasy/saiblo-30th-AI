#!/usr/bin/env python3
from __future__ import annotations

import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'Game2' / 'deepclue_ai'
DIRECT_BASE = OUT / 'n547o' / 'ai.py'
FULL_BASE = OUT / 'n559a' / 'ai.py'
POST_BASE = OUT / 'n579b' / 'ai.py'

DIRECT_BRANCH = """    elif ISO_MODE == 'rose_zf_poker_direct':
        solve_direct_kind(g, kind, npcs, marks, hint, evidences) if kind in {'rose', 'zf', 'poker'} else zero_answer(g, kind, npcs, marks, evidences, 'hard')
"""

POST_ANCHOR = """                        g.evidences()
                if g.stage < 3 and ev_ids:
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


Y_FRIDAY_CACHE_DIRECT = """            current_npcs = g.npcs() or npcs
            current_marks = g.marks() or marks
            true_ids = [npc for npc in current_npcs if current_marks.get(npc) is True]
            false_ids = [npc for npc in current_npcs if current_marks.get(npc) is False]
            competitor = true_ids[0] if true_ids else (current_npcs[0] if current_npcs else '')
            teacher = true_ids[1] if len(true_ids) > 1 else (true_ids[0] if true_ids else '')
            witness = false_ids[0] if false_ids else (current_npcs[-1] if current_npcs else '')
            if competitor:
                g.chat(competitor, '袁樱瞳反复说等到周五。她准备揭发什么、交给谁、证据藏在手机/云端/纸质材料/老师处/保安处哪一处？')
            if teacher:
                g.chat(teacher, '袁樱瞳周五前是否要向你提交投票作弊、出国名额、手机照片、张壹传闻或旧案证据？请只说证据缓存位置。')
            if witness:
                g.chat(witness, '如果袁樱瞳准备周五揭发旧案，她可能把1919黑车、生物馆、保安网站、李海天或世纪林证据交给谁？')
            yuan_ids = [str(ev.get('id')) for ev in g.evidences() if str(ev.get('id')) in {'001', '703', '704', '705', '706', '707', '708'}]
            for ynpc in (g.npcs() or current_npcs):
                g.chat(ynpc, '下一阶段只找周五揭发缓存：草稿、云盘、邮件、聊天记录、纸质备份、老师收件、保安记录或手机恢复报告。', yuan_ids)
            g.answer('无名氏', '无', '无')
"""

Y_RUMOR_SOURCE_DIRECT = """            current_npcs = g.npcs() or npcs
            current_marks = g.marks() or marks
            true_ids = [npc for npc in current_npcs if current_marks.get(npc) is True]
            false_ids = [npc for npc in current_npcs if current_marks.get(npc) is False]
            zhang_ids = [npc for npc in (id_for_name('张壹', current_npcs), id_for_name('张朔', current_npcs)) if npc]
            for npc_id in zhang_ids:
                g.chat(npc_id, '只说传闻源头：你与袁樱瞳、照片女尸、替身、周五揭发、生物馆跑出者、1919黑车和李海天旧案分别有什么关系？')
            if not zhang_ids:
                for ynpc in current_npcs:
                    g.chat(ynpc, '张壹/张朔相关传闻从哪里来？请只说明真实失踪、替身传闻、照片女尸、生物馆跑出者和袁樱瞳死亡之间的源头。')
            yuan_ids = [str(ev.get('id')) for ev in g.evidences() if str(ev.get('id')) in {'001', '703', '704', '705', '706', '707', '708'}]
            for ynpc in (g.npcs() or current_npcs):
                g.chat(ynpc, '如果张壹/张朔传闻是误导，下一项官方证据应是身份档案、失踪记录、DNA、监控、聊天记录还是手机恢复？', yuan_ids)
            g.answer('无名氏', '无', '无')
"""

Y_SUITCASE_DIRECT = """            current_npcs = g.npcs() or npcs
            current_marks = g.marks() or marks
            true_ids = [npc for npc in current_npcs if current_marks.get(npc) is True]
            false_ids = [npc for npc in current_npcs if current_marks.get(npc) is False]
            competitor = true_ids[0] if true_ids else (current_npcs[0] if current_npcs else '')
            witness = false_ids[0] if false_ids else (current_npcs[-1] if current_npcs else '')
            if competitor:
                g.chat(competitor, '黄色行李箱不是背景。请只说购买/快递/维修记录、店铺监控、箱内血迹/纤维/指纹、谁搬运、修箱路线和袁樱瞳手机关系。')
                g.chat(competitor, '如果你只是修箱，维修店、路上监控、箱子来源、箱内痕迹和手机捡到位置分别能由哪份证据证明？')
            if witness:
                g.chat(witness, '你是否见过黄色行李箱、搬运路线、维修店、宿舍楼梯、1919黑车或生物馆之间的连接？只给物证来源。')
            yuan_ids = [str(ev.get('id')) for ev in g.evidences() if str(ev.get('id')) in {'001', '703', '704', '705', '706', '707', '708'}]
            for ynpc in (g.npcs() or current_npcs):
                g.chat(ynpc, '下一阶段只找行李箱 provenance：购买记录、快递、维修单、店铺监控、箱内血迹/纤维/指纹、宿舍监控或搬运人。', yuan_ids)
            g.answer('无名氏', '无', '无')
"""

Y_TOOLMARK_CROSS_FULL = """    elif '袁樱瞳' in text or '碎尸案' in text:
        current_npcs = g.npcs() or npcs
        current_marks = g.marks() or marks
        true_ids = [npc for npc in current_npcs if current_marks.get(npc) is True]
        false_ids = [npc for npc in current_npcs if current_marks.get(npc) is False]
        ordered = true_ids + false_ids + [npc for npc in current_npcs if npc not in true_ids + false_ids]
        def ask_all(question: str, evidences_arg: list[str] | None = None) -> None:
            for ynpc in (g.npcs() or current_npcs):
                g.chat(ynpc, question, evidences_arg)
        ask_all('不要猜凶手。只按法医物证回答：袁樱瞳尸块、李海天背刺失血、断肢、海豚挂件、刀痕比对、同一刀具/同一作案手法是否有关。')
        ask_all('如果旧案和本案有关，下一项证据应是刀痕比对、DNA、尸检原件、凶器来源、蓝色背包/海豚挂件来源、监控还是手机照片元数据。')
        yuan_ids = [str(ev.get('id')) for ev in g.evidences() if str(ev.get('id')) in {'001', '703', '704', '705', '706', '707', '708'}]
        ask_all('结合现有证据，李海天的背刺失血和袁樱瞳碎尸是否能由同一凶器、同一搬运人或同一旧案组织解释？只给下一份物证。', yuan_ids)
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


def mark_poker_tool(text: str) -> str:
    mark = """                        poker_after_ids = [str(ev.get('id')) for ev in g.evidences()]
                        if {'203', '204', '205'}.issubset(set(poker_after_ids)):
                            globals()['POKER_TOOLMARK_AXIS'] = True
                if g.stage < 3 and ev_ids:
"""
    if POST_ANCHOR not in text:
        raise RuntimeError('post anchor missing')
    return text.replace(POST_ANCHOR, mark)


def main() -> int:
    direct = DIRECT_BASE.read_text(encoding='utf-8')
    full = FULL_BASE.read_text(encoding='utf-8')
    post = POST_BASE.read_text(encoding='utf-8')
    specs = {
        'n590a': direct.replace(DIRECT_BRANCH, direct_yuan_branch(Y_FRIDAY_CACHE_DIRECT)),
        'n590b': direct.replace(DIRECT_BRANCH, direct_yuan_branch(Y_RUMOR_SOURCE_DIRECT)),
        'n590c': direct.replace(DIRECT_BRANCH, direct_yuan_branch(Y_SUITCASE_DIRECT)),
        'n590d': replace_yuan_branch(mark_poker_tool(post), Y_TOOLMARK_CROSS_FULL),
    }
    for label, text in specs.items():
        write_candidate(label, text)
    print('\\n'.join(sorted(specs)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
