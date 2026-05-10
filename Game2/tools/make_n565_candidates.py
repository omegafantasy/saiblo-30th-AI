#!/usr/bin/env python3
from __future__ import annotations

import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'Game2' / 'deepclue_ai'
BASE = OUT / 'n559a' / 'ai.py'


POKER_ANCHOR = """                poker_evidences = g.evidences()
                ev_ids = [str(ev.get('id')) for ev in poker_evidences if str(ev.get('id')) in {'101', '201', '202', '203'}]
                if g.stage < 3 and ev_ids:
                    g.chat(info_id, '结合邀请函、聊天记录、宾客到达表和电脑浏览记录，死者真实身份、林渝植、梅花5之间是什么关系？', ev_ids)
                    g.evidences()
"""

POKER_MONITOR_BLOCK = """                poker_evidences = g.evidences()
                ev_ids = [str(ev.get('id')) for ev in poker_evidences if str(ev.get('id')) in {'101', '201', '202', '203'}]
                if reception_id:
                    g.chat(reception_id, '请调取并直接给我扑克公馆餐厅11:00到13:00监控和大门口0:00到13:00监控；重点说明7:30不明身份人、8:20离开、8:50梅花5到达、12:00梅花5进餐厅和12:05离开。')
                    poker_evidences = g.evidences()
                    monitor_ids = [str(ev.get('id')) for ev in poker_evidences if str(ev.get('id')) in {'101', '102', '103', '104', '201', '202', '203', '204', '205', '301', '302', '303', '304', '305', '401', '402'}]
                    if monitor_ids:
                        g.chat(reception_id, '结合大门口监控、餐厅监控、Joker聊天记录、宾客到达表和梅花5面具，按时间线说明谁提前进出公馆、谁在12点伪装梅花5。', monitor_ids)
                        g.evidences()
                if g.stage < 3 and ev_ids:
                    g.chat(info_id, '结合邀请函、聊天记录、宾客到达表和电脑浏览记录，死者真实身份、林渝植、梅花5之间是什么关系？', ev_ids)
                    g.evidences()
"""

YUAN_START = "        ask_all('袁樱瞳碎尸案请完整说明："
YUAN_END = "        ask_all('如果你知道凶手或关键隐瞒者，请直接给出名字、动机、作案过程和证据链。', yuan_ids)\n"

SOLVE_CASE_BRANCH = """    if 'Rose' in text:
        solve_rose(g, npcs, marks, evidences)
    elif 'Z失踪' in text or 'F无法联络' in text:
        solve_z_script(g, npcs, evidences)
    else:
        solve_unknown(g, npcs, marks, hint, evidences)
"""


def write_candidate(label: str, text: str) -> None:
    target = OUT / label
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    (target / 'ai.py').write_text(text, encoding='utf-8')


def add_poker_monitor(text: str) -> str:
    if POKER_ANCHOR not in text:
        raise RuntimeError('poker anchor missing')
    return text.replace(POKER_ANCHOR, POKER_MONITOR_BLOCK)


def isolate(text: str, target: str) -> str:
    if target == 'poker':
        replacement = """    if '扑克公馆' in text:
        solve_unknown(g, npcs, marks, hint, evidences)
    else:
        g.answer(murderer='无名氏', motivation='无', method='无')
"""
    elif target == 'yuan':
        replacement = """    if '袁樱瞳' in text or '碎尸案' in text:
        solve_unknown(g, npcs, marks, hint, evidences)
    else:
        g.answer(murderer='无名氏', motivation='无', method='无')
"""
    else:
        raise ValueError(target)
    if SOLVE_CASE_BRANCH not in text:
        raise RuntimeError('solve_case branch missing')
    return text.replace(SOLVE_CASE_BRANCH, replacement)


def replace_yuan_questions(text: str, questions: list[str], answer_dynamic: bool = False) -> str:
    start = text.index(YUAN_START)
    end = text.index(YUAN_END, start) + len(YUAN_END)
    lines: list[str] = []
    for index, question in enumerate(questions):
        if index == 0:
            lines.append("        g.req('background')\n")
        if index < 3:
            lines.append(f"        ask_all('{question}')\n")
        else:
            if index == 3:
                lines.append("        yuan_ids = [str(ev.get('id')) for ev in g.evidences() if str(ev.get('id')) in {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706'}]\n")
            lines.append(f"        ask_all('{question}', yuan_ids)\n")
    if answer_dynamic:
        lines.append("""        suspect_id = ''
        best_score = -1
        for ynpc, reply in yuan_replies.items():
            score = 0
            for key in ('一票', '险胜', '出国名额', '手机', '行李箱', '假发', 'lo裙', '清空', '凌晨1点', '李海天', '海豚', '生物馆', '1919', '尸检'):
                if key in reply:
                    score += 1
            if score > best_score:
                best_score = score
                suspect_id = ynpc
        suspect = cn_name(suspect_id) if suspect_id else '无名氏'
        g.answer(
            murderer=suspect,
            motivation=f'{suspect}围绕袁樱瞳的出国名额、投票异常、手机照片和李海天旧案隐瞒真相，担心替身、死亡时间或尸块处理暴露而杀人灭口。',
            method=f'{suspect}利用长相相似、lo裙栗色假发、黄色行李箱和清空手机制造袁樱瞳死亡时间与身份混淆，处理尸块后借张壹生物馆传闻、1919黑车、保安网站和李海天尸检报告转移视线。',
        )
        return
""")
    else:
        lines.append("        g.answer(murderer='无名氏', motivation='无', method='无')\n        return\n")
    return text[:start] + ''.join(lines) + text[end:]


def main() -> int:
    base = BASE.read_text(encoding='utf-8')
    yuan_questions = [
        '先不要猜凶手。请按完整剧情说明袁樱瞳碎尸案：周四聚会、周五课程展示、凌晨1点照片、周六世纪林尸块、黄色行李箱、手机清空、lo裙栗色假发、1919黑车、保安网站、生物馆、李海天旧案分别怎么连接？',
        '逐人说明你本人确认的事实：谁和袁樱瞳长得像并竞争出国名额，谁捡到或清空手机，谁推黄色行李箱，谁知道投票异常，谁看到生物馆和1919黑车，谁掌握李海天尸检或蓝色背包海豚挂件？',
        '把袁樱瞳案和李海天案并排比较：死亡时间、背刺、大量失血、四肢被砍、尸块位置、海豚挂件、蓝色背包、生物馆、世纪林、张壹传闻中哪些相同哪些不同？',
        '请优先给我未公开物证：袁樱瞳手机、课程展示投票纸、李海天尸检报告、监控、黑车记录、保安网站日志、行李箱来源、假发lo裙来源和尸块DNA。缺哪一个就说明谁持有。',
        '结合现有证据重建真实时间线：袁樱瞳何时死亡，凌晨1点照片是谁发的，照片女性是谁，谁伪装她活着，谁处理尸块，谁制造张壹从生物馆跑出的传闻？',
        '最后只回答证据链，不讲传闻：哪件物证能把手机、投票异常、李海天尸检、生物馆、1919黑车和黄色行李箱连到同一个隐瞒者或凶手？',
    ]

    specs = {
        'n565a': add_poker_monitor(base),
        'n565b': isolate(add_poker_monitor(base), 'poker'),
        'n565c': isolate(replace_yuan_questions(base, yuan_questions, answer_dynamic=True), 'yuan'),
        'n565d': replace_yuan_questions(base, yuan_questions, answer_dynamic=False),
        'n565e': add_poker_monitor(replace_yuan_questions(base, yuan_questions, answer_dynamic=False)),
    }
    for label, text in specs.items():
        write_candidate(label, text)
    print('\\n'.join(sorted(specs)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
