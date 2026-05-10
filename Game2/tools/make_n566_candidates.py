#!/usr/bin/env python3
from __future__ import annotations

import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'Game2' / 'deepclue_ai'
BASE = OUT / 'n559a' / 'ai.py'


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


def isolate_yuan(text: str) -> str:
    replacement = """    if '袁樱瞳' in text or '碎尸案' in text:
        solve_unknown(g, npcs, marks, hint, evidences)
    else:
        g.answer(murderer='无名氏', motivation='无', method='无')
"""
    if SOLVE_CASE_BRANCH not in text:
        raise RuntimeError('solve_case branch missing')
    return text.replace(SOLVE_CASE_BRANCH, replacement)


def yuan_answer_block(mode: str) -> str:
    if mode == 'runner':
        return """        runner = ''
        for reply in yuan_replies.values():
            for pattern in (
                r'亲眼看(?:到|见)([一-龥]{2,4})[^。；，]*从生物馆[^。；，]*跑出来',
                r'([一-龥]{2,4})[^。；，]*慌[^。；，]*从生物馆[^。；，]*跑出来',
                r'([一-龥]{2,4})[^。；，]*从生物馆[^。；，]*跑出',
            ):
                m = re.search(pattern, reply)
                if m:
                    runner = m.group(1)
                    break
            if runner:
                break
        suspect = runner or '无名氏'
        g.answer(
            murderer=suspect,
            motivation=f'{suspect}与李海天旧案、生物馆、蓝色背包海豚挂件或袁樱瞳掌握的真相有关，担心袁樱瞳在周五后揭露投票异常、手机照片、尸块处理和李海天案关联而杀人灭口。',
            method=f'{suspect}利用袁樱瞳手机、凌晨1点尸体照片、lo裙栗色假发和黄色行李箱制造死亡时间与身份混淆，处理尸块后借张壹生物馆传闻、1919黑车和保安网站转移视线；李海天尸检报告中的四肢被砍、背刺失血和海豚挂件说明两案有共同处理链条。',
        )
        return
"""
    if mode == 'runner_hidden':
        return """        runner = ''
        guard = ''
        for reply in yuan_replies.values():
            m = re.search(r'([一-龥]{2,4})[^。；，]*从生物馆[^。；，]*跑出', reply)
            if m:
                runner = m.group(1)
            gmatch = re.search(r'保安([一-龥]{2,4})[^。；，]*奇怪网站', reply)
            if gmatch:
                guard = gmatch.group(1)
        suspect = runner or guard or '无名氏'
        g.answer(
            murderer=suspect,
            motivation=f'{suspect}是生物馆或保安网站线索背后的关键隐瞒者，因李海天旧案、袁樱瞳手机照片和课程投票异常即将暴露而杀害袁樱瞳。',
            method=f'{suspect}先制造袁樱瞳死亡时间和身份混淆，再用黄色行李箱、lo裙栗色假发、手机清空、1919黑车和张壹传闻掩盖尸块来源，并把李海天案的相似死状嫁接到袁樱瞳案上。',
        )
        return
"""
    raise ValueError(mode)


def replace_yuan(text: str, deep: bool, answer_mode: str) -> str:
    start = text.index(YUAN_START)
    end = text.index(YUAN_END, start) + len(YUAN_END)
    if deep:
        questions = [
            '先只按人物和时间线说明：袁樱瞳周四聚会、周五展示、凌晨1点照片、周六世纪林尸块、李海天旧案、生物馆、1919黑车、保安网站各自是谁亲眼确认的？',
            '请每个人只说本人亲眼确认的事实：谁从生物馆慌张跑出来，谁在看奇怪网站，谁坐1919黑车，谁捡手机，谁推黄色行李箱，谁知道投票多出一票。',
            '重点追问李海天旧案：谁掌握尸检报告，蓝色背包海豚挂件是谁的，背刺失血和四肢被砍与袁樱瞳碎尸案有什么相同和不同？',
            '请给我能证明生物馆跑出者身份的物证或证词，并说明这个人和张壹传闻、李海天尸检、袁樱瞳手机照片之间的关系。',
            '结合袁樱瞳手机、投票纸、李海天尸检报告和目击证词，直接指出真正隐瞒者或凶手是谁，为什么不是只赢了一票的竞争者。',
        ]
    else:
        questions = [
            '袁樱瞳碎尸案请完整说明：手机、凌晨1点女性尸体照片、lo裙、栗色假发、黄色行李箱、投票异常、出国名额、张朔、张壹、生物馆、世纪林、李海天、1919黑车、保安奇怪网站分别是什么线索？',
            '不要只讲传闻。请说明你本人看到或确认了什么：谁从生物馆出来，谁接触尸块或行李箱，谁清空手机，谁伪造死亡时间，谁从投票中获利？',
            '结合现有证据重新推理袁樱瞳死亡：实际死者是谁，凌晨照片是谁，张壹传闻哪里错，生物馆和世纪林尸块如何连接？',
        ]
    lines: list[str] = []
    for index, question in enumerate(questions):
        if index < 2:
            lines.append(f"        ask_all('{question}')\n")
        else:
            if index == 2:
                lines.append("        yuan_ids = [str(ev.get('id')) for ev in g.evidences() if str(ev.get('id')) in {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706'}]\n")
            lines.append(f"        ask_all('{question}', yuan_ids)\n")
    lines.append(yuan_answer_block(answer_mode))
    return text[:start] + ''.join(lines) + text[end:]


def main() -> int:
    base = BASE.read_text(encoding='utf-8')
    specs = {
        'n566a': isolate_yuan(replace_yuan(base, deep=True, answer_mode='runner')),
        'n566b': replace_yuan(base, deep=True, answer_mode='runner'),
        'n566c': isolate_yuan(replace_yuan(base, deep=False, answer_mode='runner')),
        'n566d': replace_yuan(base, deep=False, answer_mode='runner_hidden'),
    }
    for label, text in specs.items():
        write_candidate(label, text)
    print('\\n'.join(sorted(specs)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
