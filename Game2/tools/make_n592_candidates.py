#!/usr/bin/env python3
from __future__ import annotations

import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'Game2' / 'deepclue_ai'
ISO_BASE = OUT / 'n579a' / 'ai.py'
FULL_BASE = OUT / 'n579b' / 'ai.py'

ANCHOR = """                        g.evidences()
                if g.stage < 3 and ev_ids:
"""

JOKER_ACCOUNT_BLOCK = """                        poker_after_ids = [str(ev.get('id')) for ev in g.evidences()]
                        rich_ids = [eid for eid in poker_after_ids if eid in {'101', '102', '103', '104', '201', '202', '203', '204', '205', '401', '402', '404', '501'}]
                        if reception_id:
                            g.chat(reception_id, '不要只给聊天截图。Joker账号的登录IP、设备、付款账户、转账定金、邀请函地址表来源、快递/寄送记录和账号实名分别在哪里查？', rich_ids)
                            g.chat(reception_id, '下一阶段若是Joker数字取证，请直接给证据：账号实名、IP日志、设备指纹、付款账户、快递单、地址表原文件或转账源。', rich_ids)
                        if info_id:
                            g.chat(info_id, 'Joker账号、人口贩卖集团和真正梅花5之间缺数字证据。请直接给账号实名、IP、设备、付款账户、地址表来源或快递记录。', rich_ids)
                if g.stage < 3 and ev_ids:
"""

INVITATION_MAPPING_BLOCK = """                        poker_after_ids = [str(ev.get('id')) for ev in g.evidences()]
                        rich_ids = [eid for eid in poker_after_ids if eid in {'101', '102', '103', '104', '201', '202', '203', '204', '205', '401', '402', '404', '501'}]
                        current_npcs = g.npcs() or follow_npcs
                        for npc_id in current_npcs:
                            g.chat(npc_id, '只核对邀请函/面具/地址表：你收到的牌面、到达时间、真实地址、是否见过梅花5、是否换过面具、是否知道谁拿走梅花5身份。', rich_ids)
                        if info_id:
                            g.chat(info_id, '202地址表没有梅花5。请直接说明梅花5邀请函、面具、地址、替身、Joker和真正林渝植身份如何被伪造。', rich_ids)
                if g.stage < 3 and ev_ids:
"""

RECEPTION_PAYMENT_BLOCK = """                        poker_after_ids = [str(ev.get('id')) for ev in g.evidences()]
                        rich_ids = [eid for eid in poker_after_ids if eid in {'101', '102', '103', '104', '201', '202', '203', '204', '205', '401', '402', '404', '501'}]
                        if reception_id:
                            g.chat(reception_id, '你从Joker处收到十万定金并被承诺事后五十万。请只说付款账户、收款记录、任务清单、清洁范围、是否被要求处理血迹/刀具/房间/车辆。', rich_ids)
                            g.chat(reception_id, '501也是五十万转账。你的承诺付款、501匿名转账、Joker账号和人口贩卖集团是否同源？请给银行流水或账户证据。', rich_ids)
                        if info_id:
                            g.chat(info_id, '接待者的十万定金和五十万承诺是否是下一证据入口？请给付款账户、银行流水、任务清单、清洁记录和Joker实名。', rich_ids)
                if g.stage < 3 and ev_ids:
"""

COMBINED_DIGITAL_BLOCK = """                        poker_after_ids = [str(ev.get('id')) for ev in g.evidences()]
                        rich_ids = [eid for eid in poker_after_ids if eid in {'101', '102', '103', '104', '201', '202', '203', '204', '205', '401', '402', '404', '501'}]
                        if reception_id:
                            g.chat(reception_id, '综合数字链：Joker账号实名/IP/设备、定金和五十万承诺、地址表原文件、邀请函快递、面具分发、清洁任务和银行流水分别缺哪份证据。', rich_ids)
                        if info_id:
                            g.chat(info_id, '不要复述时间线。下一阶段若存在，应是Joker账号数字取证、邀请函地址表来源、接待付款流水、快递记录或面具替换记录，请直接给证据名。', rich_ids)
                if g.stage < 3 and ev_ids:
"""


def insert_block(text: str, block: str) -> str:
    if ANCHOR not in text:
        raise RuntimeError('post-monitor anchor missing')
    return text.replace(ANCHOR, block)


def write_candidate(label: str, text: str) -> None:
    target = OUT / label
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    (target / 'ai.py').write_text(text, encoding='utf-8')


def main() -> int:
    iso = ISO_BASE.read_text(encoding='utf-8')
    full = FULL_BASE.read_text(encoding='utf-8')
    specs = {
        'n592a': insert_block(iso, JOKER_ACCOUNT_BLOCK),
        'n592b': insert_block(iso, INVITATION_MAPPING_BLOCK),
        'n592c': insert_block(iso, RECEPTION_PAYMENT_BLOCK),
        'n592d': insert_block(full, COMBINED_DIGITAL_BLOCK),
    }
    for label, text in specs.items():
        write_candidate(label, text)
    print('\\n'.join(sorted(specs)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
