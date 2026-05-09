#!/usr/bin/env python3
from __future__ import annotations

import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'Game2' / 'deepclue_ai'
FULL_BASE = OUT / 'n559a' / 'ai.py'
POKER_BASE = OUT / 'n597a' / 'ai.py'

SOLVE_CASE_BRANCH = """    if 'Rose' in text:
        solve_rose(g, npcs, marks, evidences)
    elif 'Z失踪' in text or 'F无法联络' in text:
        solve_z_script(g, npcs, evidences)
    else:
        solve_unknown(g, npcs, marks, hint, evidences)
"""


def write_candidate(label: str, text: str) -> None:
    target = OUT / label
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    (target / 'ai.py').write_text(text, encoding='utf-8')


def replace_yuan_branch(text: str, branch: str) -> str:
    start = text.index("    elif '袁樱瞳' in text or '碎尸案' in text:\n")
    end = text.index("    else:\n        method = '未知'\n", start)
    return text[:start] + branch + text[end:]


def isolate_yuan(text: str) -> str:
    replacement = """    if '袁樱瞳' in text or '碎尸案' in text:
        solve_unknown(g, npcs, marks, hint, evidences)
    else:
        g.answer(murderer='无名氏', motivation='无', method='无')
"""
    if SOLVE_CASE_BRANCH not in text:
        raise RuntimeError('solve_case branch missing')
    return text.replace(SOLVE_CASE_BRANCH, replacement, 1)


def yuan_branch(mode: str) -> str:
    if mode == 'source_first':
        opener = '袁樱瞳碎尸案只查证据保管链：手机、投票、李海天尸检、蓝色背包海豚挂件、1919黑车、生物馆监控、保安网站后台分别在哪个完整姓名或系统。'
        second = '不要猜凶手。请说你本人能调取或知道来源的官方物证：705尸检报告、706/707/708、保卫处、法医、警方旧案、车辆登记、网站后台、手机云端。'
        follow = '705李海天尸检已出现。你作为报告来源或被报告指向的人，只回答下一份官方材料：报告原件编号、DNA比对、蓝色背包主人、海豚挂件来源、1919车、保安网页日志、生物馆监控、警方旧案卷宗。'
        missing = '当前还缺705/706。请只给官方来源完整名称：哪位老师、哪名保安、哪名学生、法医/警方/保卫处/车辆/网站/手机云端系统能调取。'
    elif mode == 'identity_custody':
        opener = '袁樱瞳案按身份法医链重建：袁樱瞳、凌晨1点照片女性、lo裙栗色假发、黄色行李箱尸块、世纪林尸块、李海天分别如何比对。'
        second = '只查能证明身份互换或死亡时间的物证：DNA、照片EXIF、手机云备份、蓝色背包海豚挂件、尸检原件、行李箱血迹指纹纤维、1919车辆轨迹。'
        follow = '705尸检已出现。继续比较李海天和袁樱瞳：死状差异、四肢切断、背刺失血、蓝色背包海豚挂件、尸块DNA、照片女尸身份和下一份706/707/708法医物证。'
        missing = '若没有705，请指出谁能证明尸源身份：法医、警方旧案、手机照片来源、行李箱主人、蓝色背包主人、1919车主、保安网站后台。'
    else:
        opener = '袁樱瞳碎尸案请完整说明：手机、凌晨1点女性尸体照片、lo裙、栗色假发、黄色行李箱、投票异常、出国名额、张朔、张壹、生物馆、世纪林、李海天、1919黑车、保安奇怪网站分别是什么线索？'
        second = '不要只讲传闻。请说明你本人看到或确认了什么：谁从生物馆出来，谁接触尸块或行李箱，谁清空手机，谁伪造死亡时间，谁从投票中获利？'
        follow = '705李海天尸检已出现。不要复述已知报告，只追706/707/708：报告原始保管人、蓝色背包海豚挂件主人、尸块DNA、1919车辆、保安网页后台、生物馆监控、手机元数据和警方旧案卷宗。'
        missing = '如果你不知道凶手，请只说明缺哪份官方物证才能得到705或706：尸检原件、DNA、手机云端、投票原件、保卫处监控、网站后台、车辆登记或旧案卷宗。'

    return f"""    elif '袁樱瞳' in text or '碎尸案' in text:
        current_npcs = g.npcs() or npcs
        current_marks = g.marks() or marks
        true_ids = [npc for npc in current_npcs if current_marks.get(npc) is True]
        false_ids = [npc for npc in current_npcs if current_marks.get(npc) is False]
        ordered = true_ids + false_ids + [npc for npc in current_npcs if npc not in true_ids + false_ids]
        replies: dict[str, str] = {{}}

        def ask(npc: str, question: str, evidences_arg: list[str] | None = None) -> None:
            if not npc:
                return
            if npc in current_npcs:
                resp = g.chat(npc, question, evidences_arg)
            else:
                resp = g.probe_chat_once(npc, question, evidences_arg)
            replies[npc] = replies.get(npc, '') + '\\n' + response_text(resp)

        def ask_all(question: str, evidences_arg: list[str] | None = None) -> None:
            for ynpc in ordered:
                ask(ynpc, question, evidences_arg)

        def add_id(bucket: list[str], npc_id: str) -> None:
            if npc_id and npc_id not in bucket:
                bucket.append(npc_id)

        def resolve_name(raw: str, max_ids: int = 6) -> list[str]:
            fragment = re.sub(r'[^一-龥]', '', str(raw or ''))
            if fragment.startswith('保安'):
                fragment = fragment[2:]
            for suffix in ('大叔', '老师', '同学', '先生', '女士', '本人', '处'):
                if fragment.endswith(suffix):
                    fragment = fragment[:-len(suffix)]
            ids: list[str] = []
            add_id(ids, id_for_name(fragment, current_npcs))
            add_id(ids, CN_TO_PINYIN.get(fragment, ''))
            for cn, npc_id in CN_TO_PINYIN.items():
                if cn == fragment:
                    add_id(ids, npc_id)
                elif len(fragment) == 1 and cn.startswith(fragment):
                    add_id(ids, npc_id)
                elif len(fragment) >= 2 and (cn.startswith(fragment) or fragment.startswith(cn)):
                    add_id(ids, npc_id)
                if len(ids) >= max_ids:
                    break
            return ids[:max_ids]

        ask_all('{opener}')
        ask_all('{second}')
        yuan_ids = [str(ev.get('id')) for ev in g.evidences() if str(ev.get('id')) in {{'001', '002', '003', '004', '701', '702', '703', '704', '705', '706', '707', '708'}}]
        ask_all('结合现有证据，按证据编号说明下一份隐藏物证应该由谁保管；如果出现705，请立刻指向706/707/708，不要停在案情复述。', yuan_ids)

        yuan_evidences = g.evidences()
        yuan_ids = [str(ev.get('id')) for ev in yuan_evidences if str(ev.get('id')) in {{'001', '002', '003', '004', '701', '702', '703', '704', '705', '706', '707', '708'}}]
        combined = '\\n'.join(replies.values()) + '\\n' + '\\n'.join(
            str(ev.get('name', '')) + str(ev.get('content', '')) for ev in yuan_evidences
        )
        target_ids: list[str] = []
        for cn, npc_id in CN_TO_PINYIN.items():
            if cn in combined:
                add_id(target_ids, npc_id)
        for pattern in (
            r'([一-龥]{{1,4}})处获得[^。；\\n]{{0,20}}尸检报告',
            r'([一-龥]{{1,4}})[^。；\\n]{{0,20}}处获得的官方尸检报告',
            r'保安([一-龥]{{1,4}}(?:大叔|老师)?)',
            r'([一-龥]{{1,4}}(?:大叔|老师)?)[^。；\\n]{{0,24}}奇怪网站',
            r'看到([一-龥]{{1,4}})[^。；\\n]{{0,32}}从生物馆',
            r'([一-龥]{{1,4}})[^。；\\n]{{0,32}}从生物馆跑',
            r'([一-龥]{{1,4}})[^。；\\n]{{0,20}}蓝色背包',
            r'([一-龥]{{1,4}})[^。；\\n]{{0,20}}1919',
        ):
            for match in re.finditer(pattern, combined):
                for npc_id in resolve_name(match.group(1)):
                    add_id(target_ids, npc_id)
        for npc_id in ordered:
            add_id(target_ids, npc_id)

        if '705' in yuan_ids:
            for npc_id in target_ids[:12]:
                ask(npc_id, '{follow}', yuan_ids)
        else:
            for npc_id in target_ids[:10]:
                ask(npc_id, '{missing}', yuan_ids)

        yuan_ids = [str(ev.get('id')) for ev in g.evidences() if str(ev.get('id')) in {{'001', '002', '003', '004', '701', '702', '703', '704', '705', '706', '707', '708'}}]
        if '706' in yuan_ids or '707' in yuan_ids or '708' in yuan_ids:
            ask_all('后续隐藏证据已经出现。请闭环真实死者、旧案同源、保安网页截图、凶手、动机、分尸/移尸/嫁祸过程和最终可提交答案。', yuan_ids)
        g.answer(murderer='无名氏', motivation='无', method='无')
        return
"""


POKER_PRECISE_BLOCK = r'''                if 'poker_after_ids' in locals():
                    exact_evs = [
                        eid for eid in list(locals().get('poker_after_ids', []))
                        if eid in {'101', '102', '103', '104', '201', '202', '203', '204', '205', '401', '402', '404', '405', '501', '502'}
                    ]
                    exact_current = list(locals().get('current_npcs', follow_npcs) or follow_npcs)
                    exact_targets: list[str] = []

                    def add_exact(npc_id: str) -> None:
                        if npc_id and npc_id not in exact_targets:
                            exact_targets.append(npc_id)

                    for npc_id in [
                        str(locals().get('info_id', '')),
                        str(locals().get('password_id', '')),
                        str(locals().get('reception_id', '')),
                    ]:
                        add_exact(npc_id)
                    for cn in ('罗方琛', '王泽', '于书华', '叶青衡', '楚戎臻', '许清和', '陆亦初', '林晚舟', '张壹'):
                        for npc_id in global_name_ids(cn, exact_current):
                            add_exact(npc_id)
                    for npc_id in exact_current:
                        add_exact(npc_id)

                    def exact_ask(npc_id: str, question: str) -> None:
                        if not npc_id:
                            return
                        if npc_id in exact_current:
                            g.chat(npc_id, question, exact_evs)
                        else:
                            g.probe_chat_once(npc_id, question, exact_evs)

                    for npc_id in exact_targets[:14]:
                        exact_ask(
                            npc_id,
                            'Poker后续车辆链。只回答是否能给404之后的405：京F车辆原始登记、车主/司机、行车记录仪、停车场原片、后备箱血迹、轮胎痕、车内DNA/指纹、真实移尸路线和下一证据编号。',
                        )
                    poker_after_ids = [str(ev.get('id')) for ev in g.evidences()]
                    exact_evs = [
                        eid for eid in poker_after_ids
                        if eid in {'101', '102', '103', '104', '201', '202', '203', '204', '205', '401', '402', '404', '405', '501', '502'}
                    ]
                    for npc_id in exact_targets[:14]:
                        exact_ask(
                            npc_id,
                            'Poker后续资金医疗链。只回答是否能给501之后的502：匿名五十万源账户、于书华/王泽看诊原档、女儿胁迫、Joker勒索、人口贩卖资金流、银行流水和下一证据编号。',
                        )
                    poker_after_ids = [str(ev.get('id')) for ev in g.evidences()]
                    exact_evs = [
                        eid for eid in poker_after_ids
                        if eid in {'101', '102', '103', '104', '201', '202', '203', '204', '205', '401', '402', '404', '405', '501', '502'}
                    ]
                    for npc_id in exact_targets[:10]:
                        exact_ask(
                            npc_id,
                            'Poker后续官方数字链。只回答景观警方卷宗、林渝植失踪案、Joker账号实名/IP/设备、邀请函地址表源文件、面具寄送记录、人口贩卖名单、DNA/指纹和结案证据编号。',
                        )
                    poker_after_ids = [str(ev.get('id')) for ev in g.evidences()]
'''


def add_poker_precise_block(text: str) -> str:
    marker = "                if g.stage < 3 and ev_ids:\n"
    idx = text.rfind(marker)
    if idx < 0:
        raise RuntimeError('poker insertion marker missing')
    return text[:idx] + POKER_PRECISE_BLOCK + text[idx:]


def main() -> int:
    full = FULL_BASE.read_text(encoding='utf-8')
    poker = POKER_BASE.read_text(encoding='utf-8')
    specs = {
        'n599a': isolate_yuan(replace_yuan_branch(full, yuan_branch('old_followup'))),
        'n599b': isolate_yuan(replace_yuan_branch(full, yuan_branch('source_first'))),
        'n599c': isolate_yuan(replace_yuan_branch(full, yuan_branch('identity_custody'))),
        'n599d': replace_yuan_branch(full, yuan_branch('old_followup')),
        'n599e': add_poker_precise_block(poker),
        'n599f': replace_yuan_branch(add_poker_precise_block(poker), yuan_branch('source_first')),
    }
    for label, text in specs.items():
        write_candidate(label, text)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
