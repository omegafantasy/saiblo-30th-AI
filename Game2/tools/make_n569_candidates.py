#!/usr/bin/env python3
from __future__ import annotations

import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'Game2' / 'deepclue_ai'
BASE = OUT / 'n568b' / 'ai.py'

POKER_METHOD_LINE = "        method = '凶手利用扑克公馆全员戴面具、身份混淆和场馆密室条件，在衣帽间用刀杀害并伪装死者。'\n"
ANSWER_LINE = "    g.answer(murderer=suspect, motivation='未知', method=method)\n"


def write_candidate(label: str, text: str) -> None:
    target = OUT / label
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    (target / 'ai.py').write_text(text, encoding='utf-8')


def replace_answer(text: str, mode: str) -> str:
    method = {
        'timeline_self': "        method = '死者或凶手利用扑克公馆面具规则、Joker接待表和监控盲区制造身份混淆：7:30不明身份人进门、8:20离开、8:50梅花5到达，11:30浏览冰冻刀柄伪装自杀视频，12:00到12:05梅花5短暂进餐厅；随后用冰块固定三把厨房刀刺入背部，冰融化后留下方形塑料盒、稀释血水、无指纹刀具和厨房缺刀，伪装成他杀。'\n",
        'timeline_murder': "        method = '凶手提前利用Joker聊天记录和宾客到达表进入扑克公馆，再借全员戴面具与梅花5身份混淆制造不在场证明；监控中的7:30不明身份人、8:20离开、8:50梅花5到达、12:00到12:05梅花5进餐厅说明有人伪装死者行动，之后用冰冻刀柄、方形塑料盒和厨房缺刀完成衣帽间杀害并伪装现场。'\n",
        'lin_yuzhi': "        suspect = '林渝植'\n        method = '林渝植利用梅花5代号、Joker聊天记录、公馆面具规则和监控时间线制造身份混淆；通过冰冻刀柄、三把厨房刀、方形塑料盒和电脑浏览记录把真实死亡方式伪装成他杀或自杀难辨的现场。'\n",
        'joker': "        suspect = 'Joker'\n        method = 'Joker提前安排邀请函、到达表和接待者，利用7:30不明身份人、8:20离开、8:50梅花5到达以及12:00餐厅监控制造替身时间线，再用冰冻刀柄、方形塑料盒、厨房缺刀和电脑浏览记录完成身份与死亡方式误导。'\n",
        'unknown': "        suspect = '无名氏'\n        method = '凶手围绕Joker聊天记录、宾客到达表、梅花5面具、7:30与8:20大门口监控、12:00到12:05餐厅监控、电脑冰冻刀柄视频、方形塑料盒和厨房缺刀制造身份混淆与死亡方式误导。'\n",
    }[mode]
    if POKER_METHOD_LINE not in text:
        raise RuntimeError('method anchor missing')
    text = text.replace(POKER_METHOD_LINE, method)
    if ANSWER_LINE not in text:
        raise RuntimeError('answer anchor missing')
    if mode in {'timeline_self', 'timeline_murder'}:
        return text.replace(
            ANSWER_LINE,
            "    g.answer(murderer=suspect, motivation='利用Joker身份、梅花5面具和公馆监控时间线掩盖真实身份与死亡方式。', method=method)\n",
        )
    return text.replace(
        ANSWER_LINE,
        "    g.answer(murderer=suspect, motivation='利用Joker身份、梅花5面具和公馆监控时间线掩盖真实身份与死亡方式。', method=method)\n",
    )


def main() -> int:
    base = BASE.read_text(encoding='utf-8')
    specs = {
        'n569a': replace_answer(base, 'timeline_self'),
        'n569b': replace_answer(base, 'timeline_murder'),
        'n569c': replace_answer(base, 'lin_yuzhi'),
        'n569d': replace_answer(base, 'joker'),
        'n569e': replace_answer(base, 'unknown'),
    }
    for label, text in specs.items():
        write_candidate(label, text)
    print('\\n'.join(sorted(specs)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
