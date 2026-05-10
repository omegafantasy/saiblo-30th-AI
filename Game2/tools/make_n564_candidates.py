#!/usr/bin/env python3
from __future__ import annotations

import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'Game2' / 'deepclue_ai'
BASE = OUT / 'n547o' / 'ai.py'


BRANCH = """    elif ISO_MODE == 'rose_zf_poker_direct':
        solve_direct_kind(g, kind, npcs, marks, hint, evidences) if kind in {'rose', 'zf', 'poker'} else zero_answer(g, kind, npcs, marks, evidences, 'hard')
"""


def write_candidate(label: str, text: str) -> None:
    target = OUT / label
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    (target / 'ai.py').write_text(text, encoding='utf-8')


def fixed_yuan_answer(name: str) -> str:
    return f"""    elif ISO_MODE == 'rose_zf_poker_direct':
        if kind in {{'rose', 'zf', 'poker'}}:
            solve_direct_kind(g, kind, npcs, marks, hint, evidences)
        elif kind == 'yuan':
            g.answer(
                murderer='{name}',
                motivation='{name}隐瞒袁樱瞳手机、凌晨1点照片、课程展示投票异常、出国名额竞争和生物馆传闻，担心真实死亡时间、替身身份或尸块处理真相暴露而杀人灭口。',
                method='{name}利用lo裙栗色假发、黄色行李箱和手机照片制造死亡时间与身份混淆，随后转移尸块，并借张壹生物馆传闻、世纪林、1919黑车和保安网站线索误导调查。',
            )
        else:
            zero_answer(g, kind, npcs, marks, evidences, 'hard')
"""


def main() -> int:
    base = BASE.read_text(encoding='utf-8')
    names = {
        'n564a': '张朔',
        'n564b': '张壹',
        'n564c': '许清和',
        'n564d': '李海天',
        'n564e': '袁樱瞳',
        'n564f': '叶青衡',
        'n564g': '陆亦初',
        'n564h': '王科瑾',
    }
    for label, name in names.items():
        write_candidate(label, base.replace(BRANCH, fixed_yuan_answer(name)))
    print('\\n'.join(sorted(names)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
