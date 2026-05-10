#!/usr/bin/env python3
from __future__ import annotations

import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'Game2' / 'deepclue_ai'
FULL = OUT / 'n559a' / 'ai.py'
DIRECT = OUT / 'n549e' / 'ai.py'


POKER_METHOD = "        method = '凶手利用扑克公馆全员戴面具、身份混淆和场馆密室条件，在衣帽间用刀杀害并伪装死者。'\n"
YUAN_ZERO = "    zero_answer(g)\n\n\ndef solve_case(g: Game) -> bool:\n"


def write_candidate(label: str, text: str) -> None:
    target = OUT / label
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    (target / 'ai.py').write_text(text, encoding='utf-8')


def add_before_poker_method(text: str, block: str) -> str:
    if POKER_METHOD not in text:
        raise RuntimeError('poker method anchor missing')
    return text.replace(POKER_METHOD, block + POKER_METHOD)


def replace_yuan_questions(text: str, questions: list[str]) -> str:
    start = text.index("        ask_all('袁樱瞳碎尸案请完整说明：")
    end_anchor = "        ask_all('如果你知道凶手或关键隐瞒者，请直接给出名字、动机、作案过程和证据链。', yuan_ids)\n"
    end = text.index(end_anchor, start) + len(end_anchor)
    lines = []
    for i, q in enumerate(questions):
        if i < 2:
            lines.append(f"        ask_all('{q}')\n")
        else:
            if i == 2:
                lines.append("        yuan_ids = [str(ev.get('id')) for ev in g.evidences() if str(ev.get('id')) in {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706'}]\n")
            lines.append(f"        ask_all('{q}', yuan_ids)\n")
    return text[:start] + ''.join(lines) + text[end:]


def direct_yuan_answer(text: str, mode: str) -> str:
    if mode == 'marks_short':
        block = """    suspect = false_name
    g.answer(
        suspect,
        f'{suspect}与袁樱瞳存在出国名额或投票结果冲突，担心手机照片、替身身份和尸块处理真相暴露而灭口。',
        f'{suspect}利用手机、凌晨1点女性尸体照片、lo裙栗色假发和黄色行李箱制造袁樱瞳死亡时间与身份混淆，随后分尸转移并借生物馆、世纪林和1919黑车线索误导调查。',
    )


def solve_case(g: Game) -> bool:
"""
    elif mode == 'split_death':
        block = """    suspect = false_name
    g.answer(
        suspect,
        f'{suspect}不是单纯因投票杀人，而是利用袁樱瞳已被误认或死亡时间被伪造这一点，隐瞒手机、行李箱和尸块转移真相。',
        f'袁樱瞳的死亡、凌晨1点照片、lo裙栗色假发、黄色行李箱和世纪林尸块不是同一时间线；{suspect}二次处理尸体、清空手机并制造张壹生物馆传闻，把真正死亡时间和尸块来源掩盖起来。',
    )


def solve_case(g: Game) -> bool:
"""
    elif mode == 'unknown_murderer':
        block = """    g.answer(
        '无名氏',
        '凶手利用课程展示投票异常、出国名额竞争、袁樱瞳手机和凌晨1点尸体照片制造时间线混乱，借张壹生物馆传闻转移嫌疑。',
        '凶手用lo裙栗色假发、黄色行李箱和手机照片伪造袁樱瞳仍然存活或死亡时间错误的假象，随后分尸并通过世纪林、1919黑车和保安网站线索转移尸块来源。',
    )


def solve_case(g: Game) -> bool:
"""
    else:
        raise ValueError(mode)
    if YUAN_ZERO not in text:
        raise RuntimeError('direct yuan zero anchor missing')
    return text.replace(YUAN_ZERO, block)


def main() -> int:
    full = FULL.read_text(encoding='utf-8')
    direct = DIRECT.read_text(encoding='utf-8')
    specs: dict[str, str] = {}

    specs['n562a'] = add_before_poker_method(full, """                deep_ids = [str(ev.get('id')) for ev in g.evidences() if str(ev.get('id')) in {'101', '102', '103', '104', '201', '202', '203', '204', '205'}]
                for doctor in (g.npcs() or npcs):
                    g.chat(doctor, '只谈尸检和死亡方式：背部刀伤、死亡时间、冰块融化、方形塑料盒、厨房缺刀、无指纹刀具和稀释血水分别说明什么？', deep_ids)
                    if g.stage >= 4:
                        break
""")
    specs['n562b'] = add_before_poker_method(full, """                deep_ids = [str(ev.get('id')) for ev in g.evidences() if str(ev.get('id')) in {'101', '102', '103', '104', '201', '202', '203', '204', '205'}]
                if 'reception_id' in locals() and reception_id:
                    g.chat(reception_id, '你为什么隐瞒或延迟公开Joker聊天记录和宾客到达时间表？谁让你负责接待，谁能从身份混淆中获利？', deep_ids)
""")
    specs['n562c'] = add_before_poker_method(full, """                deep_ids = [str(ev.get('id')) for ev in g.evidences() if str(ev.get('id')) in {'101', '102', '103', '104', '201', '202', '203', '204', '205'}]
                if info_id:
                    g.chat(info_id, '你最初为什么说信息不能全部公开？还缺哪项证据才能确认Joker、林渝植、梅花5和真实死者身份？', deep_ids)
""")
    specs['n562d'] = full.replace(POKER_METHOD, "        method = '未知'\n")
    specs['n562e'] = full.replace(POKER_METHOD, "        suspect = '无名氏'\n        method = '凶手利用扑克公馆全员戴面具造成身份混淆，围绕Joker聊天记录、宾客到达表、梅花5、林渝植、电脑浏览记录、冰柜塑料盒和厨房缺刀制造死者身份与死亡方式误导。'\n")

    specs['n562f'] = replace_yuan_questions(full, [
        '不要先判断凶手。请确认真实死者是谁：袁樱瞳、凌晨1点照片女性、lo裙栗色假发女性、黄色行李箱尸块和世纪林尸块是否是同一人？',
        '逐一说明手机、行李箱、假发、照片、尸块发现地点、张壹生物馆传闻中哪些是身份置换，哪些是真实死亡线索。',
        '结合现有证据，死者身份是否被替换或误认？袁樱瞳真正死亡时间、照片女性身份和尸块来源分别是什么？',
        '如果有人利用替身或误认掩护凶手，请说出掩护者、被掩护者、证据链和可核验物证。',
    ])
    specs['n562g'] = replace_yuan_questions(full, [
        '请按时间线说明袁樱瞳最后出现、手机被捡到或清空、凌晨1点照片、周五揭穿、尸块发现和1919黑车每一步发生时间。',
        '谁能操作袁樱瞳手机，谁知道手机照片，谁有时间搬运行李箱或尸块，谁的时间线最矛盾？',
        '结合现有证据，哪一个时间点能证明死亡时间被伪造？请给出手机、照片、假发、行李箱和尸块的先后顺序。',
        '我还缺哪项关键证据才能确认凶手？请指出未公开证词、矛盾证词和可核验物证。',
    ])
    specs['n562h'] = replace_yuan_questions(full, [
        '请只索取物证：袁樱瞳手机相册和删除记录、黄色行李箱来源、lo裙和栗色假发来源、血迹指纹DNA、监控和1919黑车记录分别在哪里？',
        '谁接触过手机、行李箱、假发、尸块、保安网站和黑车？请不要讲传闻，只说可验证证据。',
        '结合现有证据，哪些物证能排除张壹传闻并确认真实处理尸体的人？',
        '还有哪些未公开证据或证词能补完整案情？请按证据编号或物证名称列出。',
    ])

    specs['n562i'] = direct_yuan_answer(direct, 'marks_short')
    specs['n562j'] = direct_yuan_answer(direct, 'split_death')
    specs['n562k'] = direct_yuan_answer(direct, 'unknown_murderer')

    for label, text in specs.items():
        write_candidate(label, text)
    print('\\n'.join(sorted(specs)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
