#!/usr/bin/env python3
from __future__ import annotations

import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'Game2' / 'deepclue_ai'
BASE = OUT / 'n559a' / 'ai.py'

YUAN_ZERO_BLOCK = "        g.answer(murderer='无名氏', motivation='无', method='无')\n        return\n"
SOLVE_CASE_BRANCH = """    if 'Rose' in text:
        solve_rose(g, npcs, marks, evidences)
    elif 'Z失踪' in text or 'F无法联络' in text:
        solve_z_script(g, npcs, evidences)
    else:
        solve_unknown(g, npcs, marks, hint, evidences)
"""


ROLE_SELECTORS = {
    'competitor': """        suspect = ''
        for ynpc, reply in yuan_replies.items():
            if any(key in reply for key in ('捡到', '手机', '黄色行李箱', '行李箱', '险胜', '一票之差')) and any(key in reply for key in ('长得', '出国名额', '竞争')):
                suspect = cn_name(ynpc)
                break
""",
    'teacher': """        suspect = ''
        for ynpc, reply in yuan_replies.items():
            if any(key in reply for key in ('教师', '老师', '课堂', '投票箱', '课程展示', '无线电')):
                suspect = cn_name(ynpc)
                break
""",
    'witness': """        suspect = ''
        for ynpc, reply in yuan_replies.items():
            if any(key in reply for key in ('夜跑', '1919', '奇怪网站', '生物馆')):
                suspect = cn_name(ynpc)
                break
""",
    'runner': """        suspect = ''
        for reply in yuan_replies.values():
            for pattern in (
                r'亲眼看(?:到|见)([一-龥]{2,4})[^。；，]*从生物馆[^。；，]*跑出来',
                r'([一-龥]{2,4})[^。；，]*慌[^。；，]*从生物馆[^。；，]*跑出来',
                r'([一-龥]{2,4})[^。；，]*从生物馆[^。；，]*跑出',
            ):
                m = re.search(pattern, reply)
                if m:
                    suspect = m.group(1)
                    break
            if suspect:
                break
""",
    'guard': """        suspect = ''
        for reply in yuan_replies.values():
            for pattern in (
                r'保安([一-龥]{2,4})[^。；，]*奇怪网站',
                r'保安([一-龥]{2,4})[^。；，]*网站',
            ):
                m = re.search(pattern, reply)
                if m:
                    suspect = m.group(1)
                    break
            if suspect:
                break
""",
    'absent': """        suspect = ''
        for reply in yuan_replies.values():
            for pattern in (
                r'实到[^。；，]*[（(]([一-龥]{2,4})(?:缺席|翘课)',
                r'([一-龥]{2,4})(?:缺席|翘课)[^。；，]*实际',
                r'([一-龥]{2,4})那天翘课',
            ):
                m = re.search(pattern, reply)
                if m:
                    suspect = m.group(1)
                    break
            if suspect:
                break
""",
}


def write_candidate(label: str, text: str) -> None:
    target = OUT / label
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    (target / 'ai.py').write_text(text, encoding='utf-8')


def isolate_yuan(text: str) -> str:
    replacement = """    if '袁樱瞳' in text or '碎尸案' in text:
        solve_unknown(g, npcs, marks, hint, evidences)
    else:
        g.answer(murderer='无名氏', motivation='无', method='无')
"""
    if SOLVE_CASE_BRANCH not in text:
        raise RuntimeError('solve_case branch missing')
    return text.replace(SOLVE_CASE_BRANCH, replacement)


def apply_role_answer(text: str, selector: str) -> str:
    block = ROLE_SELECTORS[selector] + """        if not suspect:
            suspect = '无名氏'
        g.answer(
            murderer=suspect,
            motivation=f'{suspect}因袁樱瞳掌握出国名额投票异常、手机照片、李海天旧案或生物馆线索，担心真相暴露而杀人灭口。',
            method=f'{suspect}利用袁樱瞳手机、凌晨1点尸体照片、lo裙栗色假发、黄色行李箱、1919黑车、生物馆传闻和保安网站制造死亡时间、身份和尸块来源混淆。',
        )
        return
"""
    if YUAN_ZERO_BLOCK not in text:
        raise RuntimeError('yuan zero block missing')
    return text.replace(YUAN_ZERO_BLOCK, block)


def main() -> int:
    base = BASE.read_text(encoding='utf-8')
    specs = {
        'n567a': isolate_yuan(apply_role_answer(base, 'competitor')),
        'n567b': isolate_yuan(apply_role_answer(base, 'teacher')),
        'n567c': isolate_yuan(apply_role_answer(base, 'witness')),
        'n567d': isolate_yuan(apply_role_answer(base, 'runner')),
        'n567e': isolate_yuan(apply_role_answer(base, 'guard')),
        'n567f': isolate_yuan(apply_role_answer(base, 'absent')),
    }
    for label, text in specs.items():
        write_candidate(label, text)
    print('\\n'.join(sorted(specs)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
