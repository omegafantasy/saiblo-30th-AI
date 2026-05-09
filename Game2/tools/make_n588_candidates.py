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

VEHICLE_OWNER_BLOCK = """                        poker_after = g.evidences()
                        poker_after_ids = [str(ev.get('id')) for ev in poker_after]
                        rich_ids = [eid for eid in poker_after_ids if eid in {'101', '102', '103', '104', '201', '202', '203', '204', '205', '401', '402', '404', '501'}]
                        current_npcs = g.npcs() or follow_npcs
                        owner_name = ''
                        for ev in poker_after:
                            if str(ev.get('id')) == '404':
                                m = re.search(r'([一-龥]{2,4})车牌号', str(ev.get('name', '')) + str(ev.get('content', '')))
                                if m:
                                    owner_name = m.group(1)
                                    break
                        owner_id = id_for_name(owner_name, current_npcs) if owner_name else ''
                        if owner_id:
                            g.chat(owner_id, '你的车牌与7:20经过大门车辆吻合。请直接说明车是谁开、是否载过Joker/梅花5、后备箱血迹、行车记录、轮胎痕、后院窗户和移尸路线。', rich_ids)
                            g.chat(owner_id, '不要否认监控。请给出下一项证据：车钥匙、行车记录仪、后备箱血迹、车内DNA、停车记录或司机身份。', rich_ids)
                        elif info_id:
                            g.chat(info_id, '404车牌出现后，不要再重复时间线。请指出车主/司机是谁，并交出车钥匙、行车记录仪、后备箱血迹、车内DNA、停车记录或司机身份。', rich_ids)
                if g.stage < 3 and ev_ids:
"""

TRANSFER_RECIPIENT_BLOCK = """                        poker_after = g.evidences()
                        poker_after_ids = [str(ev.get('id')) for ev in poker_after]
                        rich_ids = [eid for eid in poker_after_ids if eid in {'101', '102', '103', '104', '201', '202', '203', '204', '205', '401', '402', '404', '501'}]
                        current_npcs = g.npcs() or follow_npcs
                        recipient_name = ''
                        for ev in poker_after:
                            if str(ev.get('id')) == '501':
                                m = re.search(r'([一-龥]{2,4})（?于书华', str(ev.get('content', '')))
                                if m:
                                    recipient_name = m.group(1)
                                    break
                        recipient_id = id_for_name(recipient_name, current_npcs) if recipient_name else ''
                        if recipient_id:
                            g.chat(recipient_id, '501显示你或于书华在看诊后收到50万匿名转账。请直接说明看诊对象、转账来源、女儿胁迫、Joker勒索、林渝植失踪和人口贩卖名单。', rich_ids)
                            g.chat(recipient_id, '下一项证据只可能是银行流水、转账源账户、医疗挂号记录、女儿定位、勒索聊天或人口贩卖名单，请直接给出。', rich_ids)
                        elif info_id:
                            g.chat(info_id, '501转账出现后，请不要复述身份线。请指出收款人/于书华、看诊对象、转账源账户、女儿胁迫、医疗档案、勒索聊天和人口贩卖名单。', rich_ids)
                if g.stage < 3 and ev_ids:
"""

HIDDEN_ROOM_BLOCK = """                        poker_after = g.evidences()
                        poker_after_ids = [str(ev.get('id')) for ev in poker_after]
                        rich_ids = [eid for eid in poker_after_ids if eid in {'101', '102', '103', '104', '201', '202', '203', '204', '205', '401', '402', '404', '501'}]
                        if info_id:
                            g.chat(info_id, '你提到密码或证据在你这里。请直接打开手机或隐藏房间，给出下一阶段物证：隐藏房间照片、手机内容、DNA/指纹、人口贩卖名单、银行流水、车牌高清监控。', rich_ids)
                            g.chat(info_id, '0512、死者手机、公馆隐藏房间和Joker人口贩卖资料之间是什么关系？请只给可交付物证，不要复述推理。', rich_ids)
                if g.stage < 3 and ev_ids:
"""

COMBINED_OWNER_RECIPIENT_BLOCK = """                        poker_after = g.evidences()
                        poker_after_ids = [str(ev.get('id')) for ev in poker_after]
                        rich_ids = [eid for eid in poker_after_ids if eid in {'101', '102', '103', '104', '201', '202', '203', '204', '205', '401', '402', '404', '501'}]
                        current_npcs = g.npcs() or follow_npcs
                        owner_name = ''
                        recipient_name = ''
                        for ev in poker_after:
                            if str(ev.get('id')) == '404':
                                m = re.search(r'([一-龥]{2,4})车牌号', str(ev.get('name', '')) + str(ev.get('content', '')))
                                if m:
                                    owner_name = m.group(1)
                            if str(ev.get('id')) == '501':
                                m = re.search(r'([一-龥]{2,4})（?于书华', str(ev.get('content', '')))
                                if m:
                                    recipient_name = m.group(1)
                        owner_id = id_for_name(owner_name, current_npcs) if owner_name else ''
                        recipient_id = id_for_name(recipient_name, current_npcs) if recipient_name else ''
                        if owner_id:
                            g.chat(owner_id, '404车牌指向你。请给车主、司机、后备箱血迹、行车记录、停车记录、后院窗户和移尸路线的直接证据。', rich_ids)
                        if recipient_id and recipient_id != owner_id:
                            g.chat(recipient_id, '501转账指向你或于书华。请给银行流水、转账源账户、看诊档案、女儿胁迫、Joker勒索和人口贩卖名单的直接证据。', rich_ids)
                        if info_id:
                            g.chat(info_id, '如果车主和收款人都不是最终答案，请直接交出手机/隐藏房间/官方卷宗中能连接404车辆、501转账、Joker、林渝植和人口贩卖的下一证据。', rich_ids)
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
        'n588a': insert_block(iso, VEHICLE_OWNER_BLOCK),
        'n588b': insert_block(iso, TRANSFER_RECIPIENT_BLOCK),
        'n588c': insert_block(iso, HIDDEN_ROOM_BLOCK),
        'n588d': insert_block(full, COMBINED_OWNER_RECIPIENT_BLOCK),
    }
    for label, text in specs.items():
        write_candidate(label, text)
    print('\\n'.join(sorted(specs)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
