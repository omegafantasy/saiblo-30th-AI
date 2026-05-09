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

COMMON_HELPERS = """                        poker_after_ids = [str(ev.get('id')) for ev in g.evidences()]
                        rich_ids = [
                            eid for eid in poker_after_ids
                            if eid in {'101', '102', '103', '104', '201', '202', '203', '204', '205', '401', '402', '404', '501'}
                        ]
                        current_npcs = g.npcs() or follow_npcs
                        true_club_name = ''
                        for pattern in (
                            r'现在的([一-龥]{2,4})就是她',
                            r'([一-龥]{2,4})就是她',
                            r'真正的梅花\\s*5[，,就是\\s]*([一-龥]{2,4})',
                            r'真正的梅花五[，,就是\\s]*([一-龥]{2,4})',
                        ):
                            m = re.search(pattern, reply)
                            if m:
                                true_club_name = m.group(1)
                                break
                        true_club_id = id_for_name(true_club_name, current_npcs) if true_club_name else ''
"""

POLICE_DOSSIER_BLOCK = COMMON_HELPERS + """                        if info_id:
                            dossier_q = '你既然掌握林渝植、Joker和人口贩卖集团线索，请不要复述推理，直接交出官方卷宗或下一证据：林渝植失踪案、Joker人口贩卖案、死者DNA/指纹、面具撬痕、车牌高清监控、银行流水和于书华看诊记录。'
                            if '景观' in reply or '刑警' in reply or '证据在我这' in reply:
                                g.chat(info_id, dossier_q, rich_ids)
                            else:
                                g.chat(info_id, '按警方证据链继续：林渝植失踪、Joker身份、人口贩卖、车辆高清监控、DNA/指纹和银行流水分别由哪份证据证明？', rich_ids)
                        if true_club_id and true_club_id != info_id:
                            g.chat(true_club_id, '你被指认为真正的梅花5或林渝植。请直接确认Joker、人口贩卖集团、7:20车辆、匿名转账、面具身份和警方卷宗之间的证据链。', rich_ids)
                if g.stage < 3 and ev_ids:
"""

TRUE_CLUB_BLOCK = COMMON_HELPERS + """                        if true_club_id and true_club_id != info_id:
                            g.chat(true_club_id, '不要再让信息源转述。你是否是真正的梅花5/林渝植？Joker为什么死，7:30提前入馆、8:20离开、12:00餐厅梅花5、衣帽间尸体和人口贩卖线索分别如何对应？', rich_ids)
                            g.chat(true_club_id, '如果你还活着且死者是Joker，请给出能进入下一阶段的物证：DNA/指纹、手机、隐藏房间、车牌、银行转账或人口贩卖名单。', rich_ids)
                        elif info_id:
                            g.chat(info_id, '请直接说真正梅花5/林渝植现在使用的身份，并说明应该向谁索取DNA/指纹、手机、隐藏房间、车牌、银行转账或人口贩卖名单。', rich_ids)
                if g.stage < 3 and ev_ids:
"""

VEHICLE_BANK_BLOCK = COMMON_HELPERS + """                        if info_id:
                            if '404' in poker_after_ids:
                                g.chat(info_id, '404车牌已经对上7:20车辆。下一证据应是车主、司机、后院窗户、后备箱血迹、轮胎痕、行车记录或移尸路线，请直接给出证据名和保管人。', rich_ids)
                            if '501' in poker_after_ids:
                                g.chat(info_id, '501匿名转账已经出现。下一证据应是转账源账户、于书华看诊记录、女儿胁迫、Joker勒索、林渝植失踪和人口贩卖名单，请直接给出证据名和保管人。', rich_ids)
                            if '404' not in poker_after_ids and '501' not in poker_after_ids:
                                g.chat(info_id, '时间线和密码已确认。请直接给出404车辆或501匿名转账之后的官方证据，不要重复401/402：车主、银行流水、医疗记录、DNA/指纹或人口贩卖名单。', rich_ids)
                if g.stage < 3 and ev_ids:
"""

COMBINED_BLOCK = COMMON_HELPERS + """                        if info_id:
                            g.chat(info_id, '按最高层卷宗继续，不要复述已知监控：林渝植失踪、Joker人口贩卖、真正梅花5身份、死者DNA/指纹、404车辆、501银行流水和于书华看诊记录中哪一项能打开下一阶段？', rich_ids)
                            if '404' in poker_after_ids or '501' in poker_after_ids:
                                g.chat(info_id, '已出现404或501。请只给下一份官方证据：车主/司机/后备箱血迹/行车记录，或转账源账户/女儿胁迫/人口贩卖名单/医疗档案。', rich_ids)
                        if true_club_id and true_club_id != info_id:
                            g.chat(true_club_id, '你被指认为真正的梅花5/林渝植。请直接说明Joker死亡、人口贩卖集团、车辆、转账、DNA/指纹和警方卷宗的关系，并交出下一证据。', rich_ids)
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
        'n585a': insert_block(iso, POLICE_DOSSIER_BLOCK),
        'n585b': insert_block(iso, TRUE_CLUB_BLOCK),
        'n585c': insert_block(iso, VEHICLE_BANK_BLOCK),
        'n585d': insert_block(full, COMBINED_BLOCK),
    }
    for label, text in specs.items():
        write_candidate(label, text)
    print('\\n'.join(sorted(specs)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
