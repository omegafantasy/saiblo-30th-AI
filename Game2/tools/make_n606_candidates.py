#!/usr/bin/env python3
from __future__ import annotations

import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'Game2' / 'deepclue_ai'
BASE = OUT / 'n604f' / 'ai.py'


OLD_FIRST = (
    '现在只查身份原件：刘丽雯女儿失踪报案、亲子鉴定、心形胎记医疗记录、林渝植档案、'
    'LYZ项链来源、张子韩复学和Joker人口贩卖名单。请说明哪份原件在现场已经掌握但还没有交出。'
)
OLD_SECOND = (
    '如果林渝植就是刘丽雯女儿或真正梅花5，请直接给DNA/亲子/医疗/报案/警方卷宗的证据名、'
    '持有人和内容，并说明它如何闭环Joker周克、于书华和最终凶手。'
)
OLD_PRE = (
    '不要停在车牌、转账或邀请函。沿着身份原件链继续查：Joker真实姓名、死者手机、LYZ随身物、'
    '刘丽雯女儿、花纹村组织、POKER纹身照片和现场未交原件分别由谁保管。'
)


def variant(src: str, mode: str) -> str:
    if mode == 'tattoo':
        first = (
            '601-604已经出现，先不要追亲子鉴定。现在只问左臂POKER纹身和606三人照片：'
            'Joker、于书华、红桃Q/接待者是否同属花纹村组织，照片原件、组织成员名单和现场未交证据由谁保管。'
        )
        second = (
            '如果你知道左臂POKER纹身，就直接说照片中三人的真实姓名、纹身含义、花纹村组织分工，'
            '并交出606；若606已出现，则继续交出605、607/608或最终警方卷宗。'
        )
        pre = (
            '501/502/503/504已经出现。下一层不要泛问身份原件，只沿POKER纹身照片查：'
            '三人照片、左臂纹身、Joker周克、于书华、红桃Q/接待者、组织名单和606/605由谁掌握。'
        )
    elif mode == 'n601':
        first = (
            '601-604或606若已出现，停止复述案情，只按官方材料追缺口：605、刘丽雯女儿失踪/报案/亲子鉴定、'
            '林渝植档案、心形胎记医疗记录、Joker人口贩卖名册、花纹村余党、密码来源和警方结案证据。'
        )
        second = (
            '若606三人照片已出现，请解释照片来源、三人的真实姓名和POKER纹身组织含义，并直接交出缺失的605或下一份卷宗。'
            '若606未出现，请先交出606三人照片。'
        )
        pre = (
            '501-504已经出现或即将出现。请直接给后续证据601/602/603/604/605/606：人口失踪案、人口贩卖集团、'
            '医生刘丽雯旧身份、失踪女儿、心形胎记、LYZ项链、特殊邀请函、Joker真实身份、三人照片和最终凶手。'
        )
    else:
        first = (
            '从“时机未到”的缺口继续。601-604已经证明失踪少女和花纹村组织，'
            '请把现场已掌握但未交出的605/606交出来：三人照片、左臂POKER纹身、组织名册、'
            '红桃Q/刘瑄、密码来源、谁把Joker引入衣帽间。'
        )
        second = (
            '不要再说等时机。条件已经满足：501转账、502聊天、503邀请函、504随身物、601-604旧案都在。'
            '请直接交出605/606/607/608，或说明唯一还缺的条件和持有人。'
        )
        pre = (
            '501/502打开后不要分散问DNA。只查时机条件：还缺哪一项才能公开三人照片、POKER纹身、'
            '组织名册、红桃Q/刘瑄、最终凶手和605/606/607/608。'
        )

    out = src
    for old, new in ((OLD_FIRST, first), (OLD_SECOND, second), (OLD_PRE, pre)):
        if old not in out:
            raise RuntimeError(f'missing anchor: {old[:20]}')
        out = out.replace(old, new)
    if mode == 'tattoo':
        out = out.replace('n604_targets[:14]', 'n604_targets[:10]')
        out = out.replace('n604_targets[:10]', 'n604_targets[:8]')
    return out


def write_candidate(label: str, text: str) -> None:
    target = OUT / label
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    (target / 'ai.py').write_text(text, encoding='utf-8')


def main() -> int:
    src = BASE.read_text(encoding='utf-8')
    specs = {
        'n606a': variant(src, 'tattoo'),
        'n606b': variant(src, 'n601'),
        'n606c': variant(src, 'condition'),
    }
    for label, text in specs.items():
        write_candidate(label, text)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
