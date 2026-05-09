#!/usr/bin/env python3
from __future__ import annotations

import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'Game2' / 'deepclue_ai'
POKER_ISO_BASE = OUT / 'n579a' / 'ai.py'
POKER_FULL_BASE = OUT / 'n579b' / 'ai.py'
YUAN_FULL_BASE = OUT / 'n559a' / 'ai.py'

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


POKER_ALL_NPC_STAGE4 = """                        poker_after = g.evidences()
                        poker_after_ids = [str(ev.get('id')) for ev in poker_after]
                        rich_ids = [
                            eid for eid in poker_after_ids
                            if eid in {'101', '102', '103', '104', '201', '202', '203', '204', '205', '401', '402', '404', '405', '501', '502'}
                        ]
                        current_npcs = g.npcs() or follow_npcs
                        asked_stage4: set[str] = set()
                        for npc_id in [info_id, password_id, reception_id]:
                            if npc_id and npc_id not in asked_stage4:
                                asked_stage4.add(npc_id)
                                g.chat(npc_id, '不要复述已知时间线。现在只回答最高层角色分配：你是否掌握405/502、真实杀害地点、移尸车辆、Joker手机、死者DNA/指纹、人口贩卖名单、转账源账户、于书华看诊档案或林渝植失踪案卷宗。', rich_ids)
                        for npc_id in current_npcs:
                            if npc_id in asked_stage4:
                                continue
                            asked_stage4.add(npc_id)
                            g.chat(npc_id, '只做stage4排查：你是否是真梅花5/林渝植、Joker同伙、车主/司机、医生/收款人、接待/清洁、密码知情者或警方线人？如果是，请交出下一份物证。', rich_ids)
                        poker_after_ids = [str(ev.get('id')) for ev in g.evidences()]
                        if '404' in poker_after_ids:
                            globals()['POKER_HAS_404'] = True
                        if '501' in poker_after_ids:
                            globals()['POKER_HAS_501'] = True
                if g.stage < 3 and ev_ids:
"""


YUAN_BFS = """    elif '袁樱瞳' in text or '碎尸案' in text:
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
            ask(ynpc, '按703到708逐项排查：手机、投票原件、李海天尸检、下一份706、707、708分别是什么，谁保管，在哪个系统或案卷里，能证明什么矛盾？')
        yuan_evidences = g.evidences()
        yuan_ids = [str(ev.get('id')) for ev in yuan_evidences if str(ev.get('id')) in {'001', '703', '704', '705', '706', '707', '708'}]
        for ynpc in (g.npcs() or current_npcs):
            ask(ynpc, '不要猜凶手。只给官方来源：手机恢复/EXIF/定位、原始票箱/笔迹/课堂录像、生物馆门禁/监控、保安网页日志、1919车辆登记、尸检原件、海豚挂件来源、警方旧案卷宗。', yuan_ids)
        yuan_evidences = g.evidences()
        yuan_ids = [str(ev.get('id')) for ev in yuan_evidences if str(ev.get('id')) in {'001', '703', '704', '705', '706', '707', '708'}]
        combined = '\\n'.join(replies.values())
        target_names: list[str] = []
        for pattern in (
            r'看到([一-龥]{2,4})[^。；\\n]{0,24}从生物馆',
            r'([一-龥]{2,4})[^。；\\n]{0,24}从生物馆跑出来',
            r'保安([一-龥]{2,4})',
            r'([一-龥]{2,4})[^。；\\n]{0,12}奇怪网站',
            r'([一-龥]{2,4})[^。；\\n]{0,12}以\\s*24\\s*票',
            r'([一-龥]{2,4})[^。；\\n]{0,12}险胜袁樱瞳',
        ):
            for m in re.finditer(pattern, combined):
                name = m.group(1)
                if name not in target_names:
                    target_names.append(name)
        for ev in yuan_evidences:
            if str(ev.get('id')) == '705':
                m = re.search(r'([一-龥]{2,4})处获得的官方尸检报告', str(ev.get('content', '')))
                if m and m.group(1) not in target_names:
                    target_names.append(m.group(1))
        target_ids: list[str] = []
        for name in target_names:
            npc_id = id_for_name(name, current_npcs)
            if npc_id and npc_id not in target_ids:
                target_ids.append(npc_id)
        for npc_id in target_ids:
            ask(npc_id, '你被解析为隐藏链关键人。请直接交出下一项物证或系统来源：706/707/708、DNA、手机元数据、票箱原件、生物馆监控、保安网页日志、1919车辆、尸检档案、海豚挂件、旧案卷宗。', yuan_ids)
        if not target_ids:
            for ynpc in ordered:
                ask(ynpc, '如果可见三人都不是706来源，请说明应该找哪个保安、老师、警方、安保系统、车辆系统、法医档案或网站后台，而不是继续讲口供。', yuan_ids)
        g.answer(murderer='无名氏', motivation='无', method='无')
        return
"""


YUAN_BFS_CROSS = """    elif '袁樱瞳' in text or '碎尸案' in text:
        current_npcs = g.npcs() or npcs
        current_marks = g.marks() or marks
        true_ids = [npc for npc in current_npcs if current_marks.get(npc) is True]
        false_ids = [npc for npc in current_npcs if current_marks.get(npc) is False]
        ordered = true_ids + false_ids + [npc for npc in current_npcs if npc not in true_ids + false_ids]
        cross = bool(globals().get('POKER_HAS_404') or globals().get('POKER_HAS_501'))
        replies: dict[str, str] = {}
        def ask(npc: str, question: str, evidences_arg: list[str] | None = None) -> None:
            resp = g.chat(npc, question, evidences_arg)
            replies[npc] = replies.get(npc, '') + '\\n' + response_text(resp)
        first_question = (
            'Poker 已出现404车辆或501转账。按703到708逐项说明袁樱瞳、李海天、1919黑车、生物馆、保安网页、Joker、人口贩卖、匿名转账是否同源，下一份官方证据在哪里。'
            if cross else
            '按703到708逐项排查：手机、投票原件、李海天尸检、下一份706、707、708分别是什么，谁保管，在哪个系统或案卷里，能证明什么矛盾？'
        )
        for ynpc in ordered:
            ask(ynpc, first_question)
        yuan_evidences = g.evidences()
        yuan_ids = [str(ev.get('id')) for ev in yuan_evidences if str(ev.get('id')) in {'001', '703', '704', '705', '706', '707', '708'}]
        for ynpc in (g.npcs() or current_npcs):
            ask(ynpc, '只给下一份可调官方材料：人口贩卖名单、转账源账户、1919车辆档案、手机EXIF/定位、DNA比对、尸检原件、保安网页日志、生物馆监控、票箱原件或警方旧案卷宗。', yuan_ids)
        yuan_evidences = g.evidences()
        yuan_ids = [str(ev.get('id')) for ev in yuan_evidences if str(ev.get('id')) in {'001', '703', '704', '705', '706', '707', '708'}]
        combined = '\\n'.join(replies.values())
        target_names: list[str] = []
        for pattern in (
            r'看到([一-龥]{2,4})[^。；\\n]{0,24}从生物馆',
            r'([一-龥]{2,4})[^。；\\n]{0,24}从生物馆跑出来',
            r'保安([一-龥]{2,4})',
            r'([一-龥]{2,4})[^。；\\n]{0,12}奇怪网站',
            r'([一-龥]{2,4})[^。；\\n]{0,12}以\\s*24\\s*票',
            r'([一-龥]{2,4})[^。；\\n]{0,12}险胜袁樱瞳',
        ):
            for m in re.finditer(pattern, combined):
                name = m.group(1)
                if name not in target_names:
                    target_names.append(name)
        for ev in yuan_evidences:
            if str(ev.get('id')) == '705':
                m = re.search(r'([一-龥]{2,4})处获得的官方尸检报告', str(ev.get('content', '')))
                if m and m.group(1) not in target_names:
                    target_names.append(m.group(1))
        target_ids: list[str] = []
        for name in target_names:
            npc_id = id_for_name(name, current_npcs)
            if npc_id and npc_id not in target_ids:
                target_ids.append(npc_id)
        for npc_id in target_ids:
            ask(npc_id, '你被解析为隐藏链关键人。请直接交出706/707/708或跨案物证：DNA、手机元数据、票箱原件、生物馆监控、保安网页日志、1919车、尸检档案、海豚挂件、人口贩卖名单或转账源账户。', yuan_ids)
        if not target_ids:
            for ynpc in ordered:
                ask(ynpc, '如果可见三人都不是706来源，请说明应该找哪个保安、老师、警方、安保系统、车辆系统、法医档案、网站后台或跨案资金账户。', yuan_ids)
        g.answer(murderer='无名氏', motivation='无', method='无')
        return
"""


def write_candidate(label: str, text: str) -> None:
    target = OUT / label
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    (target / 'ai.py').write_text(text, encoding='utf-8')


def insert_poker_block(text: str, block: str) -> str:
    if POST_ANCHOR not in text:
        raise RuntimeError('post-monitor anchor missing')
    return text.replace(POST_ANCHOR, block)


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
    poker_iso = POKER_ISO_BASE.read_text(encoding='utf-8')
    poker_full = POKER_FULL_BASE.read_text(encoding='utf-8')
    yuan_full = YUAN_FULL_BASE.read_text(encoding='utf-8')
    specs = {
        'n594a': insert_poker_block(poker_iso, POKER_ALL_NPC_STAGE4),
        'n594b': insert_poker_block(poker_full, POKER_ALL_NPC_STAGE4),
        'n594c': isolate_yuan(replace_yuan_branch(yuan_full, YUAN_BFS)),
        'n594d': replace_yuan_branch(insert_poker_block(poker_full, POKER_ALL_NPC_STAGE4), YUAN_BFS_CROSS),
    }
    for label, text in specs.items():
        write_candidate(label, text)
    print('\\n'.join(sorted(specs)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
