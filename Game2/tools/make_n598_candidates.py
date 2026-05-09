#!/usr/bin/env python3
from __future__ import annotations

import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'Game2' / 'deepclue_ai'
YUAN_HOLDER_BASE = OUT / 'n597b' / 'ai.py'
YUAN_IDENTITY_BASE = OUT / 'n597c' / 'ai.py'
FULL_CROSS_BASE = OUT / 'n597e' / 'ai.py'

ZERO_LINE = "        g.answer(murderer='无名氏', motivation='无', method='无')\n        return\n"


def write_candidate(label: str, text: str) -> None:
    target = OUT / label
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    (target / 'ai.py').write_text(text, encoding='utf-8')


def replace_answer(text: str, replacement: str) -> str:
    if ZERO_LINE not in text:
        raise RuntimeError('yuan zero answer anchor missing')
    return text.replace(ZERO_LINE, replacement, 1)


SELF_ANSWER = """        g.answer(
            murderer='侦探',
            motivation='失忆侦探与口袋网页截图、眼熟保安、世纪林旧案和李海天尸检存在直接关联，袁樱瞳周五要揭发的不是普通投票作弊，而是旧案与当前碎尸案的同源真相。',
            method='侦探在记忆缺失前后利用保安求救、网页截图、手机照片、1919黑车、生物馆和世纪林现场制造侦探身份伪装，并通过清空手机、转移尸块或嫁祸竞争者掩盖真实作案链。'
        )
        return
"""


GUARD_ANSWER = """        guard_ids: list[str] = []
        for pattern in (
            r'保安([一-龥]{1,4}(?:大叔|老师)?)',
            r'([一-龥]{1,4}(?:大叔|老师)?)[^。；\\n]{0,20}奇怪网站',
            r'([一-龥]{1,4}(?:大叔|老师)?)[^。；\\n]{0,20}上周日[^。；\\n]{0,12}不在',
        ):
            for match in re.finditer(pattern, combined):
                for npc_id in global_name_ids(match.group(1), current_npcs):
                    if npc_id and npc_id not in guard_ids:
                        guard_ids.append(npc_id)
        final_id = guard_ids[0] if guard_ids else (target_ids[0] if target_ids else (false_ids[0] if false_ids else ''))
        final_name = cn_name(final_id) if final_id else '保安'
        g.answer(
            murderer=final_name,
            motivation=f'{final_name}作为保安或网站来源掌握世纪林现场、网页后台、值班缺岗和旧案记录，担心袁樱瞳周五揭发李海天旧案与当前碎尸案同源而灭口。',
            method=f'{final_name}利用保安权限、奇怪网站后台、世纪林巡逻/监控、生物馆记录、1919车辆线索和手机照片控制信息流，清空或转移关键证据并伪装为竞争者投票动机。'
        )
        return
"""


RUNNER_ANSWER = """        runner_ids: list[str] = []
        for pattern in (
            r'看到([一-龥]{1,4})[^。；\\n]{0,30}从生物馆',
            r'([一-龥]{1,4})[^。；\\n]{0,30}从生物馆跑',
        ):
            for match in re.finditer(pattern, combined):
                for npc_id in global_name_ids(match.group(1), current_npcs):
                    if npc_id and npc_id not in runner_ids:
                        runner_ids.append(npc_id)
        final_id = runner_ids[0] if runner_ids else (target_ids[0] if target_ids else (false_ids[0] if false_ids else ''))
        final_name = cn_name(final_id) if final_id else '生物馆相关人'
        g.answer(
            murderer=final_name,
            motivation=f'{final_name}与周六十点半生物馆、尸块处理、李海天尸检和袁樱瞳旧案线索直接相关，为阻止周五揭发而杀人或协助分尸转移。',
            method=f'{final_name}在生物馆/世纪林链条中处理尸块、伪造死亡时间或转移手机照片，再借黄色行李箱、lo裙栗色假发、投票异常和1919黑车误导调查。'
        )
        return
"""


TEACHER_ANSWER = """        final_id = true_ids[1] if len(true_ids) > 1 else (true_ids[0] if true_ids else (current_npcs[0] if current_npcs else ''))
        final_name = cn_name(final_id) if final_id else '教师'
        g.answer(
            murderer=final_name,
            motivation=f'{final_name}掌握出国名额、课堂投票、原始票箱和行政系统记录，担心袁樱瞳周五揭发推荐名额/投票作弊与旧案线索相连而灭口。',
            method=f'{final_name}利用课堂投票和行政记录制造竞争者获利表象，同时通过手机、票箱原件、网页截图、保卫处记录或车辆线索隐藏真实死亡时间和尸源。'
        )
        return
"""


def main() -> int:
    holder = YUAN_HOLDER_BASE.read_text(encoding='utf-8')
    identity = YUAN_IDENTITY_BASE.read_text(encoding='utf-8')
    full = FULL_CROSS_BASE.read_text(encoding='utf-8')
    specs = {
        'n598a': replace_answer(identity, SELF_ANSWER),
        'n598b': replace_answer(identity, GUARD_ANSWER),
        'n598c': replace_answer(holder, RUNNER_ANSWER),
        'n598d': replace_answer(holder, TEACHER_ANSWER),
        'n598e': replace_answer(full, GUARD_ANSWER),
    }
    for label, text in specs.items():
        write_candidate(label, text)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
