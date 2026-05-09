#!/usr/bin/env python3
from __future__ import annotations

import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'Game2' / 'deepclue_ai'
BASE = OUT / 'n559a' / 'ai.py'

FIRST_ASK = "        ask_all('袁樱瞳碎尸案请完整说明：手机、凌晨1点女性尸体照片、lo裙、栗色假发、黄色行李箱、投票异常、出国名额、张朔、张壹、生物馆、世纪林、李海天、1919黑车、保安奇怪网站分别是什么线索？')\n"
SECOND_ASK = "        ask_all('不要只讲传闻。请说明你本人看到或确认了什么：谁从生物馆出来，谁接触尸块或行李箱，谁清空手机，谁伪造死亡时间，谁从投票中获利？')\n"

WITNESS_SETUP = """        current_npcs = g.npcs() or npcs
        current_marks = g.marks() or marks
        false_ids = [npc for npc in current_npcs if current_marks.get(npc) is False]
        witness = false_ids[0] if false_ids else (current_npcs[-1] if current_npcs else '')
        if witness:
            g.chat(witness, '你在周六晚上十点半到底看到了什么？请直接说明生物馆、张壹、1919黑车、保安奇怪网站、世纪林尸块和李海天旧案之间的亲眼事实。')
"""


def write_candidate(label: str, text: str) -> None:
    target = OUT / label
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    (target / 'ai.py').write_text(text, encoding='utf-8')


def insert_before_first(text: str) -> str:
    if FIRST_ASK not in text:
        raise RuntimeError('first Yuan ask anchor missing')
    return text.replace(FIRST_ASK, WITNESS_SETUP + FIRST_ASK)


def replace_second(text: str) -> str:
    if SECOND_ASK not in text:
        raise RuntimeError('second Yuan ask anchor missing')
    return text.replace(SECOND_ASK, WITNESS_SETUP)


def after_first_replace_second(text: str) -> str:
    if FIRST_ASK not in text or SECOND_ASK not in text:
        raise RuntimeError('Yuan anchors missing')
    text = text.replace(SECOND_ASK, '')
    return text.replace(FIRST_ASK, FIRST_ASK + WITNESS_SETUP)


def main() -> int:
    base = BASE.read_text(encoding='utf-8')
    specs = {
        'n573a': insert_before_first(base),
        'n573b': replace_second(base),
        'n573c': after_first_replace_second(base),
    }
    for label, text in specs.items():
        write_candidate(label, text)
    print('\\n'.join(sorted(specs)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
