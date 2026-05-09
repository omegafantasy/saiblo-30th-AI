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

SPACE_ACCESS_BLOCK = """                        poker_after_ids = [str(ev.get('id')) for ev in g.evidences()]
                        rich_ids = [eid for eid in poker_after_ids if eid in {'101', '102', '103', '104', '201', '202', '203', '204', '205', '401', '402', '404', '501'}]
                        if reception_id:
                            g.chat(reception_id, '只围绕公馆空间和权限回答：衣帽间密码、死者房间门锁、窗户/后院、厨房冰柜、垃圾桶、清洁路线、门禁日志和谁能从厨房把尸体移到衣帽间。', rich_ids)
                            g.chat(reception_id, '下一阶段证据若不是车辆或转账，应是门禁/清洁/空间复原：房门开关记录、窗户痕迹、后院脚印、厨房监控、清洁记录或密码使用记录。', rich_ids)
                        if info_id:
                            g.chat(info_id, '按空间复原继续：真实死亡地点、厨房到衣帽间动线、后院窗户、停车点、尸体搬运路径、门锁和密码权限分别由哪项证据证明？', rich_ids)
                if g.stage < 3 and ev_ids:
"""

PASSWORD_PERMISSION_BLOCK = """                        poker_after_ids = [str(ev.get('id')) for ev in g.evidences()]
                        rich_ids = [eid for eid in poker_after_ids if eid in {'101', '102', '103', '104', '201', '202', '203', '204', '205', '401', '402', '404', '501'}]
                        if password_id:
                            g.chat(password_id, '你掌握0512或衣帽间密码。请直接说明密码来源、谁知道密码、谁开过衣帽间、死者手机/隐藏房间、公馆门禁和下一份权限记录。', rich_ids)
                            g.chat(password_id, '不要重复血迹破绽。请给出密码使用记录、门锁痕迹、房间访问日志、手机解锁记录或隐藏房间入口。', rich_ids)
                        elif info_id:
                            g.chat(info_id, '当前缺密码/权限层。请指出0512是谁给的、谁知道衣帽间密码、谁能开死者房间、是否有手机解锁或隐藏房间访问记录。', rich_ids)
                if g.stage < 3 and ev_ids:
"""

TOOLMARK_BLOCK = """                        poker_after_ids = [str(ev.get('id')) for ev in g.evidences()]
                        rich_ids = [eid for eid in poker_after_ids if eid in {'101', '102', '103', '104', '201', '202', '203', '204', '205', '401', '402', '404', '501'}]
                        current_npcs = g.npcs() or follow_npcs
                        if info_id:
                            g.chat(info_id, '只围绕法医和刀具回答：背后三刀、刀柄无指纹、手臂烧伤、血水稀释、冰冻刀柄、厨房缺刀、刀痕比对和真实死亡时间能否打开下一阶段证据。', rich_ids)
                        if reception_id and reception_id != info_id:
                            g.chat(reception_id, '厨房缺失三刀、冰柜塑料盒、死者烧伤和血水稀释之间是否有刀具/冰块/清洁记录可查？请直接给证据来源。', rich_ids)
                        for npc_id in current_npcs:
                            if npc_id not in {info_id, reception_id}:
                                g.chat(npc_id, '你是否见过刀具、冰柜、塑料盒、清洁血迹或手臂烧伤相关异常？只给可验证物证来源。', rich_ids)
                                break
                if g.stage < 3 and ev_ids:
"""

COMBINED_SPACE_TOOL_BLOCK = """                        poker_after_ids = [str(ev.get('id')) for ev in g.evidences()]
                        rich_ids = [eid for eid in poker_after_ids if eid in {'101', '102', '103', '104', '201', '202', '203', '204', '205', '401', '402', '404', '501'}]
                        if reception_id:
                            g.chat(reception_id, '把空间权限和刀具物证合并复原：门锁/密码、厨房冰柜、后院窗户、清洁路线、背后三刀、冰冻刀柄、血水稀释和移尸路径分别缺哪份证据。', rich_ids)
                        if password_id:
                            g.chat(password_id, '你掌握密码。请给出密码使用记录、死者手机/隐藏房间入口、房间访问日志、刀具来源和真实死亡地点。', rich_ids)
                        if info_id:
                            g.chat(info_id, '不要再复述401/402。下一阶段若存在，应是空间权限、刀痕比对、门禁/清洁记录、手机/隐藏房间或真实死亡地点，请直接交出证据名。', rich_ids)
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
        'n589a': insert_block(iso, SPACE_ACCESS_BLOCK),
        'n589b': insert_block(iso, PASSWORD_PERMISSION_BLOCK),
        'n589c': insert_block(iso, TOOLMARK_BLOCK),
        'n589d': insert_block(full, COMBINED_SPACE_TOOL_BLOCK),
    }
    for label, text in specs.items():
        write_candidate(label, text)
    print('\\n'.join(sorted(specs)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
