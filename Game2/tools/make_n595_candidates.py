#!/usr/bin/env python3
from __future__ import annotations

import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'Game2' / 'deepclue_ai'
POKER_BASE = OUT / 'n593a' / 'ai.py'
YUAN_BASE = OUT / 'n594c' / 'ai.py'

POKER_TRUE_ANCHOR = "                        true_club_id = id_for_name(true_club_name, current_npcs) if true_club_name else ''\n"
POKER_OWNER_ANCHOR = "                        owner_id = id_for_name(owner_name, current_npcs) if owner_name else ''\n                        recipient_id = id_for_name(recipient_name, current_npcs) if recipient_name else ''\n"
ANSWER_LINE = "    g.answer(murderer=suspect, motivation='未知', method=method)\n"
YUAN_ZERO_ANSWER = "        g.answer(murderer='无名氏', motivation='无', method='无')\n        return\n"


def write_candidate(label: str, text: str) -> None:
    target = OUT / label
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    (target / 'ai.py').write_text(text, encoding='utf-8')


def poker_with_globals(text: str) -> str:
    if POKER_TRUE_ANCHOR not in text or POKER_OWNER_ANCHOR not in text:
        raise RuntimeError('poker answer anchors missing')
    text = text.replace(
        POKER_TRUE_ANCHOR,
        POKER_TRUE_ANCHOR + "                        if true_club_name:\n                            globals()['POKER_TRUE_CLUB_NAME'] = true_club_name\n",
    )
    text = text.replace(
        POKER_OWNER_ANCHOR,
        POKER_OWNER_ANCHOR + "                        if owner_name:\n                            globals()['POKER_OWNER_NAME'] = owner_name\n                        if recipient_name:\n                            globals()['POKER_RECIPIENT_NAME'] = recipient_name\n",
    )
    return text


def poker_true_club_answer(text: str) -> str:
    text = poker_with_globals(text)
    if ANSWER_LINE not in text:
        raise RuntimeError('answer line missing')
    return text.replace(
        ANSWER_LINE,
        """    if '扑克公馆' in text:
        final_murderer = str(globals().get('POKER_TRUE_CLUB_NAME') or suspect)
        g.answer(
            murderer=final_murderer,
            motivation='Joker掌握人口贩卖集团和林渝植身份秘密，真梅花5为夺回身份、切断Joker威胁并隐藏失踪案真相而杀死Joker。',
            method='真梅花5利用扑克公馆面具规则和监控盲区，在衣帽间外先杀死Joker，再借密码、面具、移尸、厨房缺刀、冰冻刀柄和监控时间差伪装成梅花5死在衣帽间。'
        )
    else:
        g.answer(murderer=suspect, motivation='未知', method=method)
""",
    )


def poker_late_holder_answer(text: str) -> str:
    text = poker_with_globals(text)
    if ANSWER_LINE not in text:
        raise RuntimeError('answer line missing')
    return text.replace(
        ANSWER_LINE,
        """    if '扑克公馆' in text:
        final_murderer = str(globals().get('POKER_RECIPIENT_NAME') or globals().get('POKER_OWNER_NAME') or suspect)
        g.answer(
            murderer=final_murderer,
            motivation='凶手被Joker的人口贩卖、医疗看诊、匿名转账或车辆移尸链胁迫，为保护自己和相关人员而参与杀害并处理Joker。',
            method='凶手与Joker约定或配合进入公馆，利用车辆、衣帽间密码、接待清洁、厨房刀具和面具身份混淆完成杀人或移尸，并用匿名转账/车辆证据掩盖真实链路。'
        )
    else:
        g.answer(murderer=suspect, motivation='未知', method=method)
""",
    )


def yuan_competitor_answer(text: str) -> str:
    if YUAN_ZERO_ANSWER not in text:
        raise RuntimeError('yuan answer anchor missing')
    return text.replace(
        YUAN_ZERO_ANSWER,
        """        final_id = true_ids[0] if true_ids else (current_npcs[0] if current_npcs else '')
        final_name = cn_name(final_id) if final_id else '无名氏'
        g.answer(
            murderer=final_name,
            motivation=f'{final_name}与袁樱瞳外貌相似并竞争出国名额，害怕袁樱瞳周五揭发手机、投票、照片或旧案线索，遂借身份混淆和投票异常掩盖杀人动机。',
            method=f'{final_name}利用捡到或控制的袁樱瞳手机、凌晨照片、lo裙栗色假发、黄色行李箱和死亡时间混淆调查，并借投票原件异常制造竞争者获利的表面解释。'
        )
        return
""",
    )


def yuan_hidden_holder_answer(text: str) -> str:
    if YUAN_ZERO_ANSWER not in text:
        raise RuntimeError('yuan answer anchor missing')
    return text.replace(
        YUAN_ZERO_ANSWER,
        """        final_id = target_ids[0] if target_ids else (false_ids[0] if false_ids else (current_npcs[0] if current_npcs else ''))
        final_name = cn_name(final_id) if final_id else '无名氏'
        g.answer(
            murderer=final_name,
            motivation=f'{final_name}与生物馆、保安网页、1919黑车、李海天尸检或旧案卷宗关联最深，为阻止袁樱瞳周五揭发旧案链路而杀人或协助转移尸体。',
            method=f'{final_name}利用学校安保/生物馆/车辆/手机/投票原件中的一环隐藏真实死亡时间和尸源，并通过清空手机、伪造照片、处理行李箱或转移尸块切断袁樱瞳与李海天旧案的联系。'
        )
        return
""",
    )


def main() -> int:
    poker = POKER_BASE.read_text(encoding='utf-8')
    yuan = YUAN_BASE.read_text(encoding='utf-8')
    specs = {
        'n595a': poker_true_club_answer(poker),
        'n595b': poker_late_holder_answer(poker),
        'n595c': yuan_competitor_answer(yuan),
        'n595d': yuan_hidden_holder_answer(yuan),
    }
    for label, text in specs.items():
        write_candidate(label, text)
    print('\\n'.join(sorted(specs)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
