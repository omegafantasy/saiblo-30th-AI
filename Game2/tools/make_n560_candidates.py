#!/usr/bin/env python3
from __future__ import annotations

import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'Game2' / 'deepclue_ai' / 'n559a' / 'ai.py'
OUT = ROOT / 'Game2' / 'deepclue_ai'


POKER_METHOD_LINE = "        method = '凶手利用扑克公馆全员戴面具、身份混淆和场馆密室条件，在衣帽间用刀杀害并伪装死者。'\n"
YUAN_ZERO_BLOCK = "        g.answer(murderer='无名氏', motivation='无', method='无')\n        return\n"


def write_candidate(label: str, text: str) -> None:
    target = OUT / label
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    (target / 'ai.py').write_text(text, encoding='utf-8')


def isolate(text: str, target: str) -> str:
    old = """    if 'Rose' in text:
        solve_rose(g, npcs, marks, evidences)
    elif 'Z失踪' in text or 'F无法联络' in text:
        solve_z_script(g, npcs, evidences)
    else:
        solve_unknown(g, npcs, marks, hint, evidences)
"""
    if target == 'poker':
        new = """    if '扑克公馆' in text:
        solve_unknown(g, npcs, marks, hint, evidences)
    else:
        g.answer(murderer='无名氏', motivation='无', method='无')
"""
    elif target == 'yuan':
        new = """    if '袁樱瞳' in text or '碎尸案' in text:
        solve_unknown(g, npcs, marks, hint, evidences)
    else:
        g.answer(murderer='无名氏', motivation='无', method='无')
"""
    else:
        raise ValueError(target)
    return text.replace(old, new)


def poker_answer(text: str, mode: str) -> str:
    if mode == 'lin_self':
        repl = """        suspect = '林渝植'
        method = '林渝植利用扑克公馆全员戴面具造成身份混淆，提前用方形塑料盒冻住三把厨房刀的刀柄，借冰块固定刀具刺入自己背部；冰融化后留下无指纹刀具、塑料盒、稀释血水和厨房缺刀，伪装成他杀。'
"""
    elif mode == 'joker':
        repl = """        suspect = 'Joker'
        method = 'Joker利用邀请函、聊天记录和宾客到达时间表操控全员戴面具入场，安排梅花5身份混淆，在衣帽间借厨房缺失刀具和电脑浏览记录制造死者真实身份误导。'
"""
    elif mode == 'info_self':
        repl = """        method = f'{suspect}围绕Joker聊天记录、宾客到达表、梅花5面具和林渝植身份混淆隐瞒真相；死者实际用方形塑料盒冻住三把厨房刀的刀柄，借冰块固定刀具刺入背部，冰融化后留下无指纹刀具和稀释血水，伪装成他杀。'
"""
    elif mode == 'reception_self':
        insert = """                if 'reception_id' in locals() and reception_id:
                    suspect = cn_name(reception_id)
"""
        text = text.replace("                    g.evidences()\n        method = ", "                    g.evidences()\n" + insert + "        method = ")
        repl = """        method = f'{suspect}作为接待者或核心知情人掌握Joker聊天记录和到达时间表，隐瞒梅花5与林渝植身份混淆；死者借冰块固定厨房刀具刺入背部伪装他杀，{suspect}利用电脑浏览记录、冰柜塑料盒和缺刀线索误导调查。'
"""
    else:
        raise ValueError(mode)
    if POKER_METHOD_LINE not in text:
        raise RuntimeError('poker method anchor not found')
    return text.replace(POKER_METHOD_LINE, repl)


def yuan_answer(text: str, mode: str) -> str:
    if mode == 'zhao':
        repl = """        g.answer(
            murderer='赵一橙',
            motivation='赵一橙与袁樱瞳竞争出国名额，利用课程展示投票异常和手机照片制造时间线混乱，担心作弊和替身真相暴露而杀害袁樱瞳。',
            method='赵一橙利用袁樱瞳手机、凌晨1点女性尸体照片、lo裙栗色假发和黄色行李箱制造死亡时间与身份混淆，杀害袁樱瞳后分尸，并借张壹生物馆传闻、世纪林尸块和1919黑车转移视线。',
        )
        return
"""
    elif mode == 'lin':
        repl = """        g.answer(
            murderer='林晚舟',
            motivation='林晚舟与袁樱瞳长相相似并牵涉出国名额和投票异常，利用替身、手机照片和生物馆传闻掩盖真实死亡时间，担心真相暴露而杀人。',
            method='林晚舟利用lo裙、栗色假发、黄色行李箱和凌晨1点女性尸体照片伪造袁樱瞳仍然活着的假象，杀害袁樱瞳后分尸，将线索引向张壹、生物馆、世纪林尸块和1919黑车。',
        )
        return
"""
    elif mode == 'gu':
        repl = """        g.answer(
            murderer='顾云舒',
            motivation='顾云舒在出国名额和课程展示投票中获利，利用袁樱瞳手机、投票异常和张壹传闻转移嫌疑，担心作弊与尸体处理真相暴露而杀人灭口。',
            method='顾云舒先用手机照片、lo裙栗色假发和黄色行李箱制造死亡时间及身份混淆，再处理袁樱瞳尸体并抛尸，以生物馆、世纪林、张壹和1919黑车线索误导调查。',
        )
        return
"""
    elif mode == 'dynamic':
        repl = """        scores: dict[str, int] = {}
        for ynpc, reply in yuan_replies.items():
            score = 0
            for key in ('出国名额', '获利', '投票', '24', '23', '多出', '笔迹', '手机', '凌晨1点', '尸体照片', '假发', '行李箱', '清空手机', '生物馆', '世纪林', '1919'):
                if key in reply:
                    score += 1
            scores[ynpc] = score
        ynpcs = g.npcs() or npcs
        marked_false = [ynpc for ynpc in ynpcs if g.marks().get(ynpc) is False]
        suspect_id = max(scores, key=scores.get) if scores else (marked_false[0] if marked_false else (ynpcs[0] if ynpcs else ''))
        if marked_false and scores.get(suspect_id, 0) < 4:
            suspect_id = marked_false[0]
        suspect = cn_name(suspect_id)
        g.answer(
            murderer=suspect,
            motivation=f'{suspect}与袁樱瞳竞争出国名额或隐瞒课程展示投票异常，担心手机照片、替身和尸块处理真相暴露而杀害袁樱瞳。',
            method=f'{suspect}利用袁樱瞳手机、凌晨1点女性尸体照片、lo裙栗色假发和黄色行李箱制造死亡时间与身份混淆，杀害袁樱瞳后分尸，并借张壹生物馆传闻、世纪林尸块、1919黑车和保安网站转移视线。',
        )
        return
"""
    else:
        raise ValueError(mode)
    if YUAN_ZERO_BLOCK not in text:
        raise RuntimeError('yuan zero anchor not found')
    return text.replace(YUAN_ZERO_BLOCK, repl)


def main() -> int:
    base = BASE.read_text(encoding='utf-8')
    specs = {
        'n560a': poker_answer(base, 'lin_self'),
        'n560b': poker_answer(base, 'joker'),
        'n560c': poker_answer(base, 'info_self'),
        'n560d': poker_answer(base, 'reception_self'),
        'n560e': yuan_answer(base, 'zhao'),
        'n560f': yuan_answer(base, 'lin'),
        'n560g': yuan_answer(base, 'gu'),
        'n560h': yuan_answer(base, 'dynamic'),
        'n560i': isolate(poker_answer(base, 'lin_self'), 'poker'),
        'n560j': isolate(yuan_answer(base, 'dynamic'), 'yuan'),
    }
    for label, text in specs.items():
        write_candidate(label, text)
    print('\\n'.join(sorted(specs)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
