#!/usr/bin/env python3
from __future__ import annotations

import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'Game2' / 'deepclue_ai'
FULL = OUT / 'n559a' / 'ai.py'

POKER_METHOD = "        method = '凶手利用扑克公馆全员戴面具、身份混淆和场馆密室条件，在衣帽间用刀杀害并伪装死者。'\n"
YUAN_START = "        ask_all('袁樱瞳碎尸案请完整说明："
YUAN_END = "        ask_all('如果你知道凶手或关键隐瞒者，请直接给出名字、动机、作案过程和证据链。', yuan_ids)\n"


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


def poker_field(text: str, mode: str) -> str:
    if mode == 'method_unknown':
        return text.replace(POKER_METHOD, "        method = '未知'\n")
    if mode == 'murderer_zero':
        return text.replace(POKER_METHOD, "        suspect = '无名氏'\n        method = '凶手利用Joker聊天记录、宾客到达表、梅花5、林渝植、电脑浏览记录、冰柜塑料盒和厨房缺刀制造身份与死亡方式误导。'\n")
    if mode == 'answer_zero':
        old = "    log(f'[n556y1] unknown hint={compact(hint, 50)} suspect={suspect}')\n    g.answer(murderer=suspect, motivation='未知', method=method)\n"
        new = "    log(f'[n556y1] unknown hint={compact(hint, 50)} suspect={suspect}')\n    if '扑克公馆' in text:\n        g.answer(murderer='无名氏', motivation='无', method='无')\n    else:\n        g.answer(murderer=suspect, motivation='未知', method=method)\n"
        return text.replace(old, new)
    raise ValueError(mode)


def yuan_questions(text: str, questions: list[str]) -> str:
    start = text.index(YUAN_START)
    end = text.index(YUAN_END, start) + len(YUAN_END)
    lines = []
    for i, q in enumerate(questions):
        if i < 2:
            lines.append(f"        ask_all('{q}')\n")
        else:
            if i == 2:
                lines.append("        yuan_ids = [str(ev.get('id')) for ev in g.evidences() if str(ev.get('id')) in {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706'}]\n")
            lines.append(f"        ask_all('{q}', yuan_ids)\n")
    return text[:start] + ''.join(lines) + text[end:]


def main() -> int:
    full = FULL.read_text(encoding='utf-8')
    specs = {
        'n563a': isolate(poker_field(full, 'method_unknown'), 'poker'),
        'n563b': isolate(poker_field(full, 'murderer_zero'), 'poker'),
        'n563c': isolate(poker_field(full, 'answer_zero'), 'poker'),
        'n563d': poker_field(full, 'answer_zero'),
        'n563e': isolate(yuan_questions(full, [
            '请确认真实死者和身份置换：袁樱瞳、凌晨1点照片女性、lo裙栗色假发女性、黄色行李箱和世纪林尸块分别是谁？',
            '谁利用长相相似、假发、手机照片或行李箱制造袁樱瞳仍存活或死亡时间错误的假象？',
            '结合现有证据，哪一个身份判断是错的？请给出能核验的物证和证词矛盾。',
            '还有哪些未公开证据能确认尸块真实身份、死亡时间和替身链条？',
        ]), 'yuan'),
        'n563f': isolate(yuan_questions(full, [
            '请只按时间线说：袁樱瞳最后出现、手机被捡到或清空、凌晨1点照片、课程投票、尸块发现、生物馆和1919黑车先后顺序。',
            '谁能在这些时间点接触手机、行李箱、尸块、假发或照片？谁的不在场证明最矛盾？',
            '结合现有证据，死亡时间被伪造在哪里？请指出手机、照片、假发和尸块的先后矛盾。',
            '我还缺哪项关键调查才能锁定死亡时间？请说未公开证词或物证。',
        ]), 'yuan'),
        'n563g': isolate(yuan_questions(full, [
            '请只索取物证：手机相册删除记录、行李箱来源、假发购买记录、血迹指纹DNA、监控、1919黑车记录和保安网站日志在哪里？',
            '谁接触过这些物证？不要讲张壹传闻，只讲能核验的证据。',
            '结合现有证据，哪件物证能直接排除传闻并指向处理尸体的人？',
            '还有哪些未公开物证或证词能补完整案情？请列出物证名。',
        ]), 'yuan'),
        'n563h': isolate(yuan_questions(full, [
            '这起案子里谁不是凶手但在替凶手掩护？谁清空手机、搬运行李箱、伪造照片、转移尸块或制造张壹传闻？',
            '谁知道真相却只说传闻？请指出每个人隐瞒的具体事实和保护对象。',
            '结合现有证据，掩护链条如何连接投票异常、手机照片、生物馆、世纪林和1919黑车？',
            '请给出关键隐瞒者、被隐瞒的事实、凶手或真实处理尸体者以及证据链。',
        ]), 'yuan'),
    }
    for label, text in specs.items():
        write_candidate(label, text)
    print('\\n'.join(sorted(specs)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
