#!/usr/bin/env python3
from __future__ import annotations

import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'Game2' / 'deepclue_ai'


FIXED_POST707_PREFIX = """            for exchange_id in (id_for_name_any('楚戎臻', current_npcs), id_for_name_any('许清和', current_npcs), forensic_target_id):
                if not exchange_id:
                    continue
                resp = chat_visible_or_probe(g, exchange_id, g.npcs() or npcs, '707联系方式已经拿到。现在不是继续索要联系方式，而是完成交换条件：许清和承诺用“运动少女”楚戎臻的联系方式换关于杀手的秘密。请直接说这个杀手秘密、对应人物、物证08/708或最终证据的编号、名称和持有人。', yuan_ids)
                yuan_replies[exchange_id] = yuan_replies.get(exchange_id, '') + '\\n' + response_text(resp)
                yuan_evidences = g.evidences()
                yuan_ids = [str(ev.get('id')) for ev in yuan_evidences if str(ev.get('id')) in {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706', '707', '708'}]
                if '708' in set(yuan_ids):
                    break
            ev707 = next((ev for ev in yuan_evidences if str(ev.get('id')) == '707'), None)
            ev707_text = str(ev707.get('name', '')) + '\\n' + str(ev707.get('content', '')) if isinstance(ev707, dict) else ''
"""


DYNAMIC_POST707_PREFIX = """            contact_name = ''
            exchange_name = ''
            m = re.search(r'物证07：([一-龥]{2,4})的联系方式', ev707_text)
            if m:
                contact_name = m.group(1)
            for pattern in (
                r'可用于与([一-龥]{2,4})交换情报',
                r'([一-龥]{2,4})曾表示[^。\\n]{0,30}联系方式',
                r'([一-龥]{2,4})曾表示[^。\\n]{0,30}杀手',
            ):
                m = re.search(pattern, ev707_text)
                if m:
                    exchange_name = m.group(1)
                    break
            dynamic_exchange_targets: list[str] = []

            def add_exchange_target(npc_id: str) -> None:
                if npc_id and npc_id not in dynamic_exchange_targets:
                    dynamic_exchange_targets.append(npc_id)

            add_exchange_target(id_for_name_any(exchange_name, current_npcs))
            add_exchange_target(id_for_name_any(contact_name, current_npcs))
            add_exchange_target(forensic_target_id)
            for npc_id in story_target_ids(ev707_text + '\\n' + '\\n'.join(yuan_replies.values()), current_npcs, max_ids=8):
                add_exchange_target(npc_id)
            for exchange_id in dynamic_exchange_targets[:5]:
                resp = chat_visible_or_probe(g, exchange_id, g.npcs() or npcs, f'707联系方式已经拿到，文本显示“{contact_name}的联系方式”可用于和“{exchange_name}”交换情报。现在请直接完成交换：把{contact_name}的联系方式交给{exchange_name}，要求他说出关于杀手的秘密；这个秘密对应谁、物证08/708或最终证据的编号、名称和持有人是什么。', yuan_ids)
                yuan_replies[exchange_id] = yuan_replies.get(exchange_id, '') + '\\n' + response_text(resp)
                yuan_evidences = g.evidences()
                yuan_ids = [str(ev.get('id')) for ev in yuan_evidences if str(ev.get('id')) in {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706', '707', '708'}]
                if '708' in set(yuan_ids):
                    break
            ev707 = next((ev for ev in yuan_evidences if str(ev.get('id')) == '707'), None)
            ev707_text = str(ev707.get('name', '')) + '\\n' + str(ev707.get('content', '')) if isinstance(ev707, dict) else ''
"""


FIXED_POST707_QUESTION = "707联系方式已经拿到。现在按交换条件推进：把楚戎臻的联系方式交给许清和，要求他说出关于“杀手”的秘密；这个秘密对应谁、什么证据、是否能打开708或最终物证？直接给证据编号、证据名、持有人。"
DYNAMIC_POST707_QUESTION = "707联系方式已经拿到。不要使用固定姓名，按物证07文本中的联系方式持有人和交换对象推进：用该联系方式交换关于杀手的秘密；这个秘密对应谁、什么证据、是否能打开708或最终物证？直接给证据编号、证据名、持有人。"


FIXED_POST707_FALLBACK = "707已经出现。不要总结碎尸案，只执行联系方式交换：许清和用“运动少女”楚戎臻的联系方式换来的杀手秘密是什么，下一份物证08/708在哪里，谁持有？"
DYNAMIC_POST707_FALLBACK = "707已经出现。不要总结碎尸案，只执行物证07写明的联系方式交换：联系方式持有人、交换对象、杀手秘密、下一份物证08/708在哪里，谁持有？"

FIXED_PRE707_LINE = "单独确认联系方式交换线：许清和是否说过想要那个不认识的“运动少女”的联系方式，运动少女是否是楚戎臻；如果能给707或708，请直接给证据编号、证据名和持有人。"
DYNAMIC_PRE707_LINE = "单独确认联系方式交换线：是否有人想要那个不认识的“运动少女”的联系方式，运动少女是谁，谁愿意用联系方式交换关于杀手的秘密；如果能给707或708，请直接给证据编号、证据名和持有人。"

FIXED_NAME_LOOP = "for name in ('许清和', '楚戎臻'):"
DYNAMIC_NAME_LOOP = "for name in (exchange_name, contact_name):"


def write_candidate(label: str, text: str) -> None:
    target = OUT / label
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    (target / 'ai.py').write_text(text, encoding='utf-8')


def dynamic_post707(src: str) -> str:
    out = src
    if FIXED_POST707_PREFIX in out:
        out = out.replace(FIXED_POST707_PREFIX, DYNAMIC_POST707_PREFIX, 1)
    else:
        raise RuntimeError('fixed post707 prefix not found')
    out = out.replace(FIXED_POST707_QUESTION, DYNAMIC_POST707_QUESTION)
    out = out.replace(FIXED_POST707_FALLBACK, DYNAMIC_POST707_FALLBACK)
    out = out.replace(FIXED_PRE707_LINE, DYNAMIC_PRE707_LINE)
    out = out.replace(FIXED_NAME_LOOP, DYNAMIC_NAME_LOOP)
    return out


def main() -> int:
    n609b = (OUT / 'n609b' / 'ai.py').read_text(encoding='utf-8')
    n609c = (OUT / 'n609c' / 'ai.py').read_text(encoding='utf-8')
    write_candidate('n610b', dynamic_post707(n609b))
    write_candidate('n610c', dynamic_post707(n609c))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
