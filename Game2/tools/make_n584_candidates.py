#!/usr/bin/env python3
from __future__ import annotations

import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'Game2' / 'deepclue_ai'
BASE = OUT / 'n579a' / 'ai.py'
FULL_BASE = OUT / 'n579b' / 'ai.py'

ANCHOR = """                        g.evidences()
                if g.stage < 3 and ev_ids:
"""

DEEP_EVIDENCE_BLOCK = """                        poker_after_ids = [str(ev.get('id')) for ev in g.evidences()]
                        deep_ids = [
                            eid for eid in poker_after_ids
                            if eid in {'101', '102', '103', '104', '201', '202', '203', '204', '205', '401', '402', '404', '405', '501', '502'}
                        ]
                        if info_id:
                            if '404' in poker_after_ids or '501' in poker_after_ids:
                                g.chat(info_id, '你已经给出404或501。不要再等我确认，直接交代405或502下一阶段证据：7:20车辆、后院窗户、匿名转账、看诊记录、人口贩卖名单、林渝植身份和Joker幕后关系。', deep_ids)
                            else:
                                g.chat(info_id, '如果时间线推断正确，请直接给404车牌、501匿名转账、405/502下一阶段证据；如果不能给证据，请说明还缺哪个密码、人物或地点。', deep_ids)
                        if reception_id and reception_id != info_id:
                            g.chat(reception_id, '用接待记录、监控、衣帽间密码和面具血迹，说明是否还存在405或502下一阶段证据，尤其是车辆、后院窗户、转账和人口贩卖线索。', deep_ids)
                        g.evidences()
                if g.stage < 3 and ev_ids:
"""

POKER_METHOD_LINE = "        method = '凶手利用扑克公馆全员戴面具、身份混淆和场馆密室条件，在衣帽间用刀杀害并伪装死者。'\n"
ANSWER_LINE = "    g.answer(murderer=suspect, motivation='未知', method=method)\n"


def with_deep_evidence(text: str) -> str:
    if ANCHOR not in text:
        raise RuntimeError('post-monitor evidence anchor missing')
    return text.replace(ANCHOR, DEEP_EVIDENCE_BLOCK)


def with_dynamic_answer(text: str) -> str:
    if POKER_METHOD_LINE not in text or ANSWER_LINE not in text:
        raise RuntimeError('answer anchors missing')
    method = (
        "        method = '凶手利用梅花5与Joker身份错位、7:30/8:20/8:50/12:00监控矛盾、衣帽间密码、面具血迹、冰冻刀柄和厨房缺刀制造死亡地点与身份混淆。'\n"
    )
    text = text.replace(POKER_METHOD_LINE, method)
    return text.replace(
        ANSWER_LINE,
        "    g.answer(murderer=suspect, motivation='掩盖Joker、林渝植、梅花5真实身份和人口贩卖线索。', method=method)\n",
    )


def with_joker_answer(text: str) -> str:
    if POKER_METHOD_LINE not in text or ANSWER_LINE not in text:
        raise RuntimeError('answer anchors missing')
    method = (
        "        method = 'Joker借扑克公馆面具规则和梅花5身份错位布置骗局，利用监控盲区、衣帽间密码、面具血迹和移尸痕迹掩盖人口贩卖集团线索。'\n"
    )
    text = text.replace(POKER_METHOD_LINE, method)
    return text.replace(
        ANSWER_LINE,
        "    g.answer(murderer='Joker', motivation='隐藏人口贩卖集团、林渝植和真正梅花5身份，并切断匿名转账与看诊记录。', method=method)\n",
    )


def write_candidate(label: str, text: str) -> None:
    target = OUT / label
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    (target / 'ai.py').write_text(text, encoding='utf-8')


def main() -> int:
    isolate = with_deep_evidence(BASE.read_text(encoding='utf-8'))
    full = with_deep_evidence(FULL_BASE.read_text(encoding='utf-8'))
    specs = {
        'n584a': isolate,
        'n584b': with_dynamic_answer(isolate),
        'n584c': with_joker_answer(isolate),
        'n584d': full,
    }
    for label, text in specs.items():
        write_candidate(label, text)
    print('\\n'.join(sorted(specs)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
