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


Y_PHONE_FORENSICS_DIRECT = """            current_npcs = g.npcs() or npcs
            current_marks = g.marks() or marks
            true_ids = [npc for npc in current_npcs if current_marks.get(npc) is True]
            false_ids = [npc for npc in current_npcs if current_marks.get(npc) is False]
            competitor = true_ids[0] if true_ids else (current_npcs[0] if current_npcs else '')
            teacher = true_ids[1] if len(true_ids) > 1 else (true_ids[0] if true_ids else '')
            witness = false_ids[0] if false_ids else (current_npcs[-1] if current_npcs else '')
            if competitor:
                g.chat(competitor, '手机不是口供问题。请只说袁樱瞳手机是谁捡到、谁清空、凌晨1点照片的拍摄/发送时间、定位、EXIF元数据、删除记录和最后操作。')
            if teacher:
                g.chat(teacher, '课程投票先放一边。袁樱瞳周五前反复说等到周五，是否和手机里被删除的证据、照片元数据、最后通话或定位有关？')
            if witness:
                g.chat(witness, '你看到的1919黑车、生物馆十点半、保安网站和世纪林尸块，哪一项能用手机定位、照片元数据或删除恢复来核验？')
            yuan_ids = [str(ev.get('id')) for ev in g.evidences() if str(ev.get('id')) in {'001', '703', '704', '705', '706', '707', '708'}]
            for ynpc in (g.npcs() or current_npcs):
                g.chat(ynpc, '下一阶段不要给传闻，只给数字取证来源：手机恢复报告、照片EXIF、定位轨迹、最后通话、删除记录、账号登录或监控时间戳。', yuan_ids)
            g.answer('无名氏', '无', '无')
"""

Y_BALLOT_CUSTODY_DIRECT = """            current_npcs = g.npcs() or npcs
            current_marks = g.marks() or marks
            true_ids = [npc for npc in current_npcs if current_marks.get(npc) is True]
            false_ids = [npc for npc in current_npcs if current_marks.get(npc) is False]
            competitor = true_ids[0] if true_ids else (current_npcs[0] if current_npcs else '')
            teacher = true_ids[1] if len(true_ids) > 1 else (true_ids[0] if true_ids else '')
            witness = false_ids[0] if false_ids else (current_npcs[-1] if current_npcs else '')
            if teacher:
                g.chat(teacher, '只围绕投票原件：票箱谁保管、谁能接触原始票、笔迹比对、废票/补票、行政记录、监考或课堂录像分别在哪里。')
                g.chat(teacher, '如果多出的一票不是凶杀本身，而是掩盖手机/死亡时间/替身线索，请说明投票原件能证明谁参与了掩护。')
            if competitor:
                g.chat(competitor, '你以一票之差获利。请只说明你是否接触过票箱、计票纸、原始票、老师办公室或行政系统记录。')
            if witness:
                g.chat(witness, '投票异常与生物馆/1919/保安网站是否同一条线？如果不是，请说哪份官方记录能把两条线连接起来。')
            yuan_ids = [str(ev.get('id')) for ev in g.evidences() if str(ev.get('id')) in {'001', '703', '704', '705', '706', '707', '708'}]
            for ynpc in (g.npcs() or current_npcs):
                g.chat(ynpc, '下一阶段只找投票 custody：原始票、笔迹鉴定、票箱接触人、课堂录像、教师办公室监控、行政系统日志或保管人证词。', yuan_ids)
            g.answer('无名氏', '无', '无')
"""

Y_FULL_PHONE_BALLOT = """    elif '袁樱瞳' in text or '碎尸案' in text:
        current_npcs = g.npcs() or npcs
        current_marks = g.marks() or marks
        true_ids = [npc for npc in current_npcs if current_marks.get(npc) is True]
        false_ids = [npc for npc in current_npcs if current_marks.get(npc) is False]
        ordered = true_ids + false_ids + [npc for npc in current_npcs if npc not in true_ids + false_ids]
        def ask_all(question: str, evidences_arg: list[str] | None = None) -> None:
            for ynpc in (g.npcs() or current_npcs):
                g.chat(ynpc, question, evidences_arg)
        ask_all('袁樱瞳案只按官方来源拆：手机恢复报告、照片EXIF/定位、最后通话、删除记录、原始投票纸、笔迹鉴定、票箱接触人、课堂录像分别在哪里。')
        ask_all('不要先猜凶手。请说明手机数字取证和投票原件能否证明同一个人参与清空手机、伪造照片、操纵投票或掩盖死亡时间。')
        yuan_ids = [str(ev.get('id')) for ev in g.evidences() if str(ev.get('id')) in {'001', '703', '704', '705', '706', '707', '708'}]
        ask_all('结合现有证据，只给下一项可调取的官方材料：手机恢复、照片元数据、定位轨迹、笔迹鉴定、课堂录像、生物馆门禁、保安网页日志或尸检档案。', yuan_ids)
        g.answer(murderer='无名氏', motivation='无', method='无')
        return
"""

Y_FULL_CROSS = """    elif '袁樱瞳' in text or '碎尸案' in text:
        current_npcs = g.npcs() or npcs
        current_marks = g.marks() or marks
        true_ids = [npc for npc in current_npcs if current_marks.get(npc) is True]
        false_ids = [npc for npc in current_npcs if current_marks.get(npc) is False]
        ordered = true_ids + false_ids + [npc for npc in current_npcs if npc not in true_ids + false_ids]
        cross = globals().get('POKER_HAS_501') or globals().get('POKER_HAS_404')
        def ask_all(question: str, evidences_arg: list[str] | None = None) -> None:
            for ynpc in (g.npcs() or current_npcs):
                g.chat(ynpc, question, evidences_arg)
        if cross:
            ask_all('另一案已经出现车辆或匿名转账证据。请只判断袁樱瞳、李海天、1919黑车、生物馆、保安网站、Joker、人口贩卖、匿名转账是否同源，以及哪份官方证据能连接。')
        else:
            ask_all('袁樱瞳案请优先说明是否存在旧案同源：李海天、1919黑车、生物馆、保安网站、世纪林尸块、手机照片和投票异常各自对应什么来源。')
        ask_all('不要给凶手结论。请拆分证据来源：谁掌握手机/投票纸/尸检报告/门禁监控/1919车辆登记/保安网页日志/海豚挂件。')
        yuan_ids = [str(ev.get('id')) for ev in g.evidences() if str(ev.get('id')) in {'001', '703', '704', '705', '706', '707', '708'}]
        ask_all('如果要打开下一阶段，最应该调取哪份官方材料：人口贩卖名单、转账源账户、1919车辆档案、手机元数据、DNA比对、尸检原件或保安网页日志？', yuan_ids)
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


def mark_poker_late(text: str) -> str:
    mark = """                        poker_after_ids = [str(ev.get('id')) for ev in g.evidences()]
                        if '501' in poker_after_ids:
                            globals()['POKER_HAS_501'] = True
                        if '404' in poker_after_ids:
                            globals()['POKER_HAS_404'] = True
                if g.stage < 3 and ev_ids:
"""
    if POST_ANCHOR not in text:
        raise RuntimeError('post anchor missing')
    return text.replace(POST_ANCHOR, mark)


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
    post = POST_BASE.read_text(encoding='utf-8')
    specs = {
        'n587a': direct.replace(DIRECT_BRANCH, direct_yuan_branch(Y_PHONE_FORENSICS_DIRECT)),
        'n587b': direct.replace(DIRECT_BRANCH, direct_yuan_branch(Y_BALLOT_CUSTODY_DIRECT)),
        'n587c': isolate_yuan(replace_yuan_branch(full, Y_FULL_PHONE_BALLOT)),
        'n587d': replace_yuan_branch(mark_poker_late(post), Y_FULL_CROSS),
    }
    for label, text in specs.items():
        write_candidate(label, text)
    print('\\n'.join(sorted(specs)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
