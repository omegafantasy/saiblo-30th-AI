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


def direct_yuan_branch(body: str) -> str:
    return f"""    elif ISO_MODE == 'rose_zf_poker_direct':
        if kind in {{'rose', 'zf', 'poker'}}:
            solve_direct_kind(g, kind, npcs, marks, hint, evidences)
        elif kind == 'yuan':
{body}
        else:
            zero_answer(g, kind, npcs, marks, evidences, 'hard')
"""


DIRECT_IDENTITY = """            current_npcs = g.npcs() or npcs
            current_marks = g.marks() or marks
            true_ids = [npc for npc in current_npcs if current_marks.get(npc) is True]
            false_ids = [npc for npc in current_npcs if current_marks.get(npc) is False]
            competitor = true_ids[0] if true_ids else (current_npcs[0] if current_npcs else '')
            teacher = true_ids[1] if len(true_ids) > 1 else (true_ids[0] if true_ids else '')
            witness = false_ids[0] if false_ids else (current_npcs[-1] if current_npcs else '')
            if competitor:
                g.chat(competitor, '只做身份置换和真实死者确认：袁樱瞳手机、凌晨1点照片、lo裙栗色假发、黄色行李箱、相似外貌、尸块DNA分别能证明谁不是谁？')
            if teacher:
                g.chat(teacher, '不要判断凶手，只说投票和死亡时间矛盾：袁樱瞳等到周五、课程展示异常、手机最后操作、凌晨照片和尸块发现顺序哪里冲突？')
            ids = [str(ev.get('id')) for ev in g.evidences() if str(ev.get('id')) in {'001', '703', '704', '705', '706', '707', '708'}]
            if witness:
                g.chat(witness, '只说可核验身份链：十点半生物馆跑出者、1919黑车、世纪林尸块、李海天尸检、海豚挂件和真实死者身份如何相互排除？', ids)
            ids = [str(ev.get('id')) for ev in g.evidences() if str(ev.get('id')) in {'001', '703', '704', '705', '706', '707', '708'}]
            for ynpc in (g.npcs() or current_npcs):
                g.chat(ynpc, '请只给下一项能区分真实死者、替身、分尸转移和死亡时间伪造的证据；不要重复传闻，不要猜凶手。', ids)
            g.answer('无名氏', '无', '无')
"""

DIRECT_META = """            current_npcs = g.npcs() or npcs
            current_marks = g.marks() or marks
            true_ids = [npc for npc in current_npcs if current_marks.get(npc) is True]
            false_ids = [npc for npc in current_npcs if current_marks.get(npc) is False]
            ordered = true_ids + false_ids + [npc for npc in current_npcs if npc not in true_ids + false_ids]
            for ynpc in ordered:
                g.chat(ynpc, '我不要求你判断凶手。请列出本案还没公开但可以调取的证据：手机删除记录、DNA、投票纸、行李箱来源、假发lo裙来源、生物馆监控、1919车辆、尸检档案。')
            ids = [str(ev.get('id')) for ev in g.evidences() if str(ev.get('id')) in {'001', '703', '704', '705', '706', '707', '708'}]
            for ynpc in ordered:
                g.chat(ynpc, '如果要继续推进到下一阶段，缺的是哪一份证据或哪一句证词？请直接说证据来源、保管人、编号线索和它能证明的矛盾。', ids)
            g.answer('无名氏', '无', '无')
"""

DIRECT_SHORT_ANSWER = """            current_npcs = g.npcs() or npcs
            current_marks = g.marks() or marks
            true_ids = [npc for npc in current_npcs if current_marks.get(npc) is True]
            false_ids = [npc for npc in current_npcs if current_marks.get(npc) is False]
            competitor = true_ids[0] if true_ids else (current_npcs[0] if current_npcs else '')
            teacher = true_ids[1] if len(true_ids) > 1 else (true_ids[0] if true_ids else '')
            witness = false_ids[0] if false_ids else (current_npcs[-1] if current_npcs else '')
            if competitor:
                g.chat(competitor, '你与袁樱瞳相似、手机、凌晨1点照片、lo裙栗色假发、黄色行李箱和出国名额竞争之间哪些是事实？')
            if teacher:
                g.chat(teacher, '课程展示投票是否异常，袁樱瞳是否准备揭发投票或名额问题，谁因此最怕真实时间线曝光？')
            ids = [str(ev.get('id')) for ev in g.evidences() if str(ev.get('id')) in {'001', '703', '704', '705'}]
            if witness:
                g.chat(witness, '生物馆十点半、1919黑车、世纪林尸块、李海天尸检和海豚挂件中，哪件事说明有人在替真正死亡时间打掩护？', ids)
            suspect_id = false_ids[0] if false_ids else (competitor or (current_npcs[0] if current_npcs else ''))
            suspect = cn_name(suspect_id) if suspect_id else '无名氏'
            g.answer(
                suspect,
                f'{suspect}为掩盖袁樱瞳真实死亡时间、手机操作和尸块转移链，借投票争议与身份相似者混淆调查。',
                f'{suspect}清空或利用手机，伪造凌晨照片和替身行踪，再借lo裙假发、黄色行李箱、生物馆传闻、1919黑车和世纪林尸块制造身份置换。'
            )
"""

FULL_YUAN_HELPER = """    elif '袁樱瞳' in text or '碎尸案' in text:
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
        ask_all('不要给最终凶手结论。只说谁在帮忙清空手机、搬行李箱、伪造照片、转移尸块或替人隐瞒；下一项应调取的证据是什么？', yuan_ids)
        g.answer(murderer='无名氏', motivation='无', method='无')
        return
"""


def replace_full_yuan(text: str, branch: str) -> str:
    start = text.index("    elif '袁樱瞳' in text or '碎尸案' in text:\n")
    end = text.index("    else:\n        method = '未知'\n", start)
    return text[:start] + branch + text[end:]


def write_candidate(label: str, text: str) -> None:
    target = OUT / label
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    (target / 'ai.py').write_text(text, encoding='utf-8')


def main() -> int:
    direct = DIRECT_BASE.read_text(encoding='utf-8')
    full = FULL_BASE.read_text(encoding='utf-8')
    specs = {
        'n583a': direct.replace(DIRECT_BRANCH, direct_yuan_branch(DIRECT_IDENTITY)),
        'n583b': direct.replace(DIRECT_BRANCH, direct_yuan_branch(DIRECT_META)),
        'n583c': direct.replace(DIRECT_BRANCH, direct_yuan_branch(DIRECT_SHORT_ANSWER)),
        'n583d': replace_full_yuan(full, FULL_YUAN_HELPER),
    }
    for label, text in specs.items():
        write_candidate(label, text)
    print('\\n'.join(sorted(specs)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
