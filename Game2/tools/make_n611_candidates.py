#!/usr/bin/env python3
from __future__ import annotations

import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'Game2' / 'deepclue_ai'


POKER_INIT_MARKER = "                if 'poker_after_ids' in locals():\n"
POKER_INIT_BLOCK = """                poker_after_snapshot = g.evidences()
                poker_after_ids = [str(ev.get('id')) for ev in poker_after_snapshot]
                combined_late_text = '\\n'.join(
                    [
                        str(locals().get('reply', '')),
                        str(response_text(locals().get('password_resp', {})) if 'password_resp' in locals() else ''),
                        str(response_text(locals().get('proof_resp', {})) if 'proof_resp' in locals() else ''),
                    ]
                    + [str(ev.get('name', '')) + str(ev.get('content', '')) for ev in poker_after_snapshot]
                )
                if {'404', '501', '502', '503', '504', '601', '602', '603', '604', '606'} & set(poker_after_ids):
                    globals()['POKER_HAS_LATE'] = True
"""


POST707_INSERT_MARKER = "            dynamic_exchange_targets: list[str] = []\n"
POST707_NATURAL_BLOCK = """            relay_text = ev707_text + '\\n' + '\\n'.join(yuan_replies.values())
            runner_name = ''
            for pattern in (
                r'([一-龥]{2,4})从生物馆[^。\\n]{0,18}(?:跑|出来)',
                r'看到([一-龥]{2,4})[^。\\n]{0,24}从(?:生物馆|里面)',
                r'([一-龥]{2,4})[^。\\n]{0,24}问我要(?:了)?(?:电话|联系方式)',
                r'([一-龥]{2,4})[^。\\n]{0,16}副会长',
            ):
                m = re.search(pattern, relay_text)
                if m:
                    runner_name = m.group(1)
                    break
            contact_id = id_for_name_any(contact_name, current_npcs) if contact_name else ''
            runner_id = id_for_name_any(runner_name, current_npcs) if runner_name else ''
            if contact_id and '708' not in set(yuan_ids):
                resp = chat_visible_or_probe(
                    g,
                    contact_id,
                    g.npcs() or npcs,
                    f'你刚才说{runner_name or \"那个人\"}从生物馆慌张出来，还向你要电话。现在不要讲物证编号，也不要说交换条件；只回忆他当时为什么慌张、手上有没有U盘/手机/血迹/背包/海豚挂件/行李箱、后来是否约你见面，以及怎样能找到他本人。',
                    yuan_ids,
                )
                yuan_replies[contact_id] = yuan_replies.get(contact_id, '') + '\\n' + response_text(resp)
                yuan_evidences = g.evidences()
                yuan_ids = [str(ev.get('id')) for ev in yuan_evidences if str(ev.get('id')) in {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706', '707', '708'}]
            if runner_id and '708' not in set(yuan_ids):
                resp = chat_visible_or_probe(
                    g,
                    runner_id,
                    g.npcs() or npcs,
                    f'我已经拿到{contact_name or \"运动少女\"}的联系方式。你上周六从生物馆慌张跑出后向她要电话；现在直接说明你在生物馆看见或做了什么，李海天U盘/袁樱瞳手机照片/世纪林尸块/保安网站/1919黑车和真正杀人者之间有什么秘密。',
                    yuan_ids,
                )
                yuan_replies[runner_id] = yuan_replies.get(runner_id, '') + '\\n' + response_text(resp)
                yuan_evidences = g.evidences()
                yuan_ids = [str(ev.get('id')) for ev in yuan_evidences if str(ev.get('id')) in {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706', '707', '708'}]
            if runner_name and runner_id not in set(g.npcs() or npcs) and '708' not in set(yuan_ids):
                ask_all(
                    f'现在不谈编号，先找人：谁能联系或带我找到{runner_name}，也就是上周六从生物馆慌张跑出来、向{contact_name or \"运动少女\"}要联系方式的人？请说他的完整身份、宿舍/学生会/联系方式，以及他从生物馆带出的秘密。',
                    yuan_ids,
                )
                yuan_evidences = g.evidences()
                yuan_ids = [str(ev.get('id')) for ev in yuan_evidences if str(ev.get('id')) in {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706', '707', '708'}]
            if '708' not in set(yuan_ids):
                natural_targets: list[str] = []
                for npc_id in (runner_id, contact_id, forensic_target_id, teacher_id if 'teacher_id' in locals() else ''):
                    if npc_id and npc_id not in natural_targets:
                        natural_targets.append(npc_id)
                for npc_id in story_target_ids(relay_text + '\\n' + '\\n'.join(yuan_replies.values()), current_npcs, max_ids=8):
                    if npc_id and npc_id not in natural_targets:
                        natural_targets.append(npc_id)
                for npc_id in natural_targets[:4]:
                    resp = chat_visible_or_probe(
                        g,
                        npc_id,
                        g.npcs() or npcs,
                        f'沿生物馆跑出者和联系方式继续查：{runner_name or \"那个人\"}为什么要接近{contact_name or \"运动少女\"}，他知道的“杀手秘密”是什么，秘密对应的实物、监控、网页后台、U盘或手机原图在哪里？如果这就是下一证据，请直接交出。',
                        yuan_ids,
                    )
                    yuan_replies[npc_id] = yuan_replies.get(npc_id, '') + '\\n' + response_text(resp)
                    yuan_evidences = g.evidences()
                    yuan_ids = [str(ev.get('id')) for ev in yuan_evidences if str(ev.get('id')) in {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706', '707', '708'}]
                    if '708' in set(yuan_ids):
                        break
"""


POST606_MARKER = "                    globals()['N601_POKER_IDS'] = ','.join(\n"
POST606_BLOCK = """                    post606_ids = [
                        str(ev.get('id')) for ev in g.evidences()
                        if str(ev.get('id')) in {'101', '102', '103', '104', '201', '202', '203', '204', '205', '401', '402', '404', '405', '501', '502', '503', '504', '505', '601', '602', '603', '604', '605', '606', '607', '608'}
                    ]
                    if '606' in set(post606_ids) and not ({'605', '607', '608'} & set(post606_ids)):
                        ev606_text = '\\n'.join(
                            str(ev.get('name', '')) + str(ev.get('content', ''))
                            for ev in g.evidences()
                            if str(ev.get('id')) == '606'
                        )
                        post606_targets: list[str] = []

                        def add_post606_target(npc_id: str) -> None:
                            if npc_id and npc_id not in post606_targets:
                                post606_targets.append(npc_id)

                        for npc_id in n601_targets:
                            add_post606_target(npc_id)
                        for name in extract_story_names(ev606_text + '\\n' + str(globals().get('N601_FINAL_TEXT', ''))):
                            for npc_id in global_name_ids(name, n601_current):
                                add_post606_target(npc_id)
                        for cn in ('周克', '刘瑄', '红桃Q', '于书华', '张朔', '陆亦初', '张子韩', '王科瑾', '林渝植'):
                            for npc_id in global_name_ids(cn, n601_current):
                                add_post606_target(npc_id)
                        for npc_id in post606_targets[:12]:
                            n601_ask(
                                npc_id,
                                '606三人照片已经出现。现在不要再解释纹身含义，只追照片的来源和下一份实物：花纹村组织成员名册、Joker/周克真实身份、红桃Q/刘瑄接待联络记录、于书华组织分工、警方已掌握但未交出的605，以及607/608最终卷宗分别由谁保管。',
                            )
                        post606_ids = [
                            str(ev.get('id')) for ev in g.evidences()
                            if str(ev.get('id')) in {'101', '102', '103', '104', '201', '202', '203', '204', '205', '401', '402', '404', '405', '501', '502', '503', '504', '505', '601', '602', '603', '604', '605', '606', '607', '608'}
                        ]
                    if '606' in set(post606_ids) and not ({'605', '607', '608'} & set(post606_ids)):
                        for npc_id in post606_targets[:8] if 'post606_targets' in locals() else []:
                            n601_ask(
                                npc_id,
                                '你刚才说605已经在现场或警方手里。请不要等时机，直接把605交出来；如果605是花纹村逮捕令、组织名册、死者手机云端名单、照片原件、DNA/指纹结案报告或最终凶手证据，请直接说证据名和持有人。',
                            )
"""

YUAN_SIMPLE_707_MARKER = "        n604_yuan_ids = [str(ev.get('id')) for ev in g.evidences() if str(ev.get('id')) in {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706', '707', '708'}]\n"
YUAN_SIMPLE_707_BLOCK = """        if '707' in set(yuan_ids):
            ev707 = next((ev for ev in yuan_evidences if str(ev.get('id')) == '707'), None)
            ev707_text = str(ev707.get('name', '')) + '\\n' + str(ev707.get('content', '')) if isinstance(ev707, dict) else ''
            contact_name = ''
            m = re.search(r'物证07：([一-龥]{2,4})的联系方式', ev707_text)
            if m:
                contact_name = m.group(1)
            relay_text = ev707_text + '\\n' + '\\n'.join(yuan_replies.values())
            runner_name = ''
            for pattern in (
                r'([一-龥]{2,4})从生物馆[^。\\n]{0,18}(?:跑|出来)',
                r'看到([一-龥]{2,4})[^。\\n]{0,24}从(?:生物馆|里面)',
                r'([一-龥]{2,4})[^。\\n]{0,24}问我要(?:了)?(?:电话|联系方式)',
                r'([一-龥]{2,4})[^。\\n]{0,16}副会长',
            ):
                m = re.search(pattern, relay_text)
                if m:
                    runner_name = m.group(1)
                    break
            natural_targets: list[str] = []
            for npc_id in (
                id_for_name_any(contact_name, current_npcs) if contact_name else '',
                id_for_name_any(runner_name, current_npcs) if runner_name else '',
                forensic_target_id,
                teacher_id if 'teacher_id' in locals() else '',
            ):
                if npc_id and npc_id not in natural_targets:
                    natural_targets.append(npc_id)
            for npc_id in story_target_ids(relay_text, current_npcs, max_ids=8):
                if npc_id and npc_id not in natural_targets:
                    natural_targets.append(npc_id)
            for npc_id in natural_targets[:6]:
                resp = chat_visible_or_probe(
                    g,
                    npc_id,
                    g.npcs() or npcs,
                    f'不要说物证编号，沿真实事件查：{runner_name or \"生物馆跑出者\"}为什么向{contact_name or \"运动少女\"}要联系方式，他当晚在生物馆看见或带走了什么，袁樱瞳手机照片、李海天U盘、保安网站、1919黑车和杀人者之间有什么秘密？如果有下一份实物证据，请直接交出。',
                    yuan_ids,
                )
                yuan_replies[npc_id] = yuan_replies.get(npc_id, '') + '\\n' + response_text(resp)
                yuan_evidences = g.evidences()
                yuan_ids = [str(ev.get('id')) for ev in yuan_evidences if str(ev.get('id')) in {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706', '707', '708'}]
                if '708' in set(yuan_ids):
                    break
"""


def write_candidate(label: str, text: str) -> None:
    target = OUT / label
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    (target / 'ai.py').write_text(text, encoding='utf-8')


def retitle(src: str, label: str) -> str:
    return src.replace('"""Game2 DeepClue AI n556y1.', f'"""Game2 DeepClue AI {label}.', 1)


def add_poker_init(src: str) -> str:
    if POKER_INIT_BLOCK in src:
        return src
    if POKER_INIT_MARKER not in src:
        raise RuntimeError('poker init marker not found')
    return src.replace(POKER_INIT_MARKER, POKER_INIT_BLOCK + POKER_INIT_MARKER, 1)


def add_natural_post707(src: str) -> str:
    if POST707_NATURAL_BLOCK in src:
        return src
    if POST707_INSERT_MARKER not in src:
        raise RuntimeError('post707 marker not found')
    return src.replace(POST707_INSERT_MARKER, POST707_NATURAL_BLOCK + POST707_INSERT_MARKER, 1)


def add_post606(src: str) -> str:
    if POST606_BLOCK in src:
        return src
    if POST606_MARKER not in src:
        raise RuntimeError('post606 marker not found')
    return src.replace(POST606_MARKER, POST606_BLOCK + POST606_MARKER, 1)


def add_simple_post707(src: str) -> str:
    if YUAN_SIMPLE_707_BLOCK in src:
        return src
    if YUAN_SIMPLE_707_MARKER not in src:
        raise RuntimeError('simple post707 marker not found')
    return src.replace(YUAN_SIMPLE_707_MARKER, YUAN_SIMPLE_707_BLOCK + YUAN_SIMPLE_707_MARKER, 1)


def main() -> int:
    n610c = (OUT / 'n610c' / 'ai.py').read_text(encoding='utf-8')
    n601f = (OUT / 'n601f' / 'ai.py').read_text(encoding='utf-8')
    n606a = (OUT / 'n606a' / 'ai.py').read_text(encoding='utf-8')

    write_candidate('n611a', add_natural_post707(add_poker_init(retitle(n610c, 'n611a'))))
    write_candidate('n611b', add_post606(retitle(n601f, 'n611b')))
    write_candidate('n611c', add_simple_post707(retitle(n606a, 'n611c')))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
