#!/usr/bin/env python3
from __future__ import annotations

import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'Game2' / 'deepclue_ai'
BASE = OUT / 'n596h' / 'ai.py'


HELPERS = r'''

def clean_cn_fragment(raw: str) -> str:
    value = re.sub(r'[^一-龥]', '', str(raw or ''))
    if value.startswith('保安'):
        value = value[2:]
    for suffix in ('大叔', '老师', '同学', '先生', '女士', '学长', '学姐', '处', '本人', '队长'):
        if value.endswith(suffix):
            value = value[:-len(suffix)]
    return value


def global_name_ids(raw: str, current_npcs: list[str] | None = None, max_ids: int = 8) -> list[str]:
    """Resolve full names and mixed forms like 江大叔/许老师 to possible npc ids."""
    fragment = clean_cn_fragment(raw)
    if not fragment:
        return []
    current = list(current_npcs or [])
    ids: list[str] = []

    def add(npc_id: str) -> None:
        if npc_id and npc_id not in ids:
            ids.append(npc_id)

    add(id_for_name(fragment, current))
    add(CN_TO_PINYIN.get(fragment, ''))
    for cn, npc_id in CN_TO_PINYIN.items():
        if cn == fragment:
            add(npc_id)
        elif len(fragment) == 1 and cn.startswith(fragment):
            add(npc_id)
        elif len(fragment) >= 2 and (cn.startswith(fragment) or fragment.startswith(cn)):
            add(npc_id)
        if len(ids) >= max_ids:
            break
    return ids[:max_ids]


def extract_story_names(text: str) -> list[str]:
    names: list[str] = []

    def add(name: str) -> None:
        name = clean_cn_fragment(name)
        if name and name not in names:
            names.append(name)

    for cn in CN_TO_PINYIN:
        if cn in text:
            add(cn)
    for pattern in (
        r'保安([一-龥]{1,4}(?:大叔|老师)?)',
        r'([一-龥]{1,4}(?:大叔|老师)?)[^。；\n]{0,20}奇怪网站',
        r'看到([一-龥]{1,4})[^。；\n]{0,30}从生物馆',
        r'([一-龥]{1,4})[^。；\n]{0,30}从生物馆跑',
        r'([一-龥]{1,4})处获得',
        r'([一-龥]{1,4})老师的出国',
        r'([一-龥]{1,4})[^。；\n]{0,16}以\s*24\s*票',
        r'([一-龥]{1,4})[^。；\n]{0,16}险胜袁樱瞳',
        r'([一-龥]{1,4})[^。；\n]{0,20}给了我密码',
        r'真正的梅花\s*5[^。；\n]{0,32}([一-龥]{1,4})',
        r'林渝植[^。；\n]{0,24}(?:就是|现在叫|现在是)([一-龥]{1,4})',
        r'([一-龥]{1,4})[^。；\n]{0,20}(?:车主|司机|转账|看诊|银行流水)',
    ):
        for match in re.finditer(pattern, text):
            add(match.group(1))
    return names
'''


POKER_GLOBAL_SWEEP = r'''                if 'poker_after_ids' in locals():
                    global_targets: list[str] = []

                    def add_global_target(npc_id: str) -> None:
                        if npc_id and npc_id not in global_targets:
                            global_targets.append(npc_id)

                    global_text = str(locals().get('combined_late_text', ''))
                    local_current_npcs = list(locals().get('current_npcs', follow_npcs) or follow_npcs)
                    for name in extract_story_names(global_text):
                        for npc_id in global_name_ids(name, local_current_npcs):
                            add_global_target(npc_id)
                    if globals().get('N597_POKER_ALL_GLOBAL'):
                        for npc_id in CN_TO_PINYIN.values():
                            add_global_target(npc_id)
                    for npc_id in local_current_npcs:
                        add_global_target(npc_id)
                    local_rich_ids = list(locals().get('rich_ids', []))
                    sweep_limit = 32 if globals().get('N597_POKER_ALL_GLOBAL') else 18
                    for npc_id in global_targets[:sweep_limit]:
                        if npc_id:
                            g.probe_chat_once(
                                npc_id,
                                '全局stage4 holder排查。若你关联林渝植、Joker、景观警方、车辆、转账、医生、人口贩卖、真实杀害地点或移尸，请直接交出405/502或下一份官方证据编号和保管链。',
                                local_rich_ids,
                            )
                    poker_after_ids = [str(ev.get('id')) for ev in g.evidences()]
'''


def yuan_branch(mode: str) -> str:
    if mode == 'identity':
        first = (
            '先查开场身份链：失忆侦探是谁、保安为什么眼熟、口袋网页截图来自哪个网站、保安上周日缺岗、奇怪网站后台、世纪林旧案和李海天尸检分别由谁保管。'
        )
        second = (
            '不要重复投票传闻。只给能打开706/707/708的系统来源：保卫处值班表、网站后台、警方旧案卷宗、法医DNA、手机云端、1919车辆登记、蓝色背包海豚挂件。'
        )
    elif mode == 'cross':
        first = (
            '跨案官方链排查：Joker人口贩卖、林渝植失踪、匿名转账、1919黑车、李海天、袁樱瞳、保安网页、生物馆、蓝色背包和手机照片是否同案；下一证据在哪。'
        )
        second = (
            '按系统而不是口供追：警方旧案卷宗、人口贩卖名单、银行流水、车辆登记、保卫处监控、网站后台、手机云端、DNA/尸检原件分别谁能调取。'
        )
    else:
        first = (
            'Yuan上限排查，只建证据来源图：703手机、704投票、705李海天尸检、706/707/708、1919黑车、生物馆、保安奇怪网站、网页截图、蓝色背包分别谁保管。'
        )
        second = (
            '解析所有半名和外部来源：保安X大叔、十点半生物馆跑出者、尸检报告X处获得、竞争者/老师/跑步者各对应哪份官方物证或系统。'
        )

    return f'''    elif '袁樱瞳' in text or '碎尸案' in text:
        current_npcs = g.npcs() or npcs
        current_marks = g.marks() or marks
        true_ids = [npc for npc in current_npcs if current_marks.get(npc) is True]
        false_ids = [npc for npc in current_npcs if current_marks.get(npc) is False]
        ordered = true_ids + false_ids + [npc for npc in current_npcs if npc not in true_ids + false_ids]
        replies: dict[str, str] = {{}}

        def ask_visible(npc: str, question: str, evidences_arg: list[str] | None = None) -> None:
            resp = g.chat(npc, question, evidences_arg)
            replies[npc] = replies.get(npc, '') + '\\n' + response_text(resp)

        def ask_target(npc: str, question: str, evidences_arg: list[str] | None = None) -> None:
            if npc in current_npcs:
                resp = g.chat(npc, question, evidences_arg)
            else:
                resp = g.probe_chat_once(npc, question, evidences_arg)
            replies[npc] = replies.get(npc, '') + '\\n' + response_text(resp)

        for ynpc in ordered:
            ask_visible(ynpc, '{first}')
        yuan_evidences = g.evidences()
        yuan_ids = [str(ev.get('id')) for ev in yuan_evidences if str(ev.get('id')) in {{'001', '703', '704', '705', '706', '707', '708'}}]
        for ynpc in ordered:
            ask_visible(ynpc, '{second}', yuan_ids)

        yuan_evidences = g.evidences()
        yuan_ids = [str(ev.get('id')) for ev in yuan_evidences if str(ev.get('id')) in {{'001', '703', '704', '705', '706', '707', '708'}}]
        combined = '\\n'.join(replies.values()) + '\\n' + '\\n'.join(
            str(ev.get('name', '')) + str(ev.get('content', '')) for ev in yuan_evidences
        )
        target_ids: list[str] = []

        def add_target_id(npc_id: str) -> None:
            if npc_id and npc_id not in target_ids:
                target_ids.append(npc_id)

        for name in extract_story_names(combined):
            for npc_id in global_name_ids(name, current_npcs):
                add_target_id(npc_id)
        for npc_id in ordered:
            add_target_id(npc_id)

        for npc_id in target_ids[:14]:
            ask_target(
                npc_id,
                '你被指向隐藏来源或系统代理。请直接给706/707/708或其来源：DNA比对、手机元数据、票箱原件、课堂/生物馆监控、保安网页后台、1919车辆、尸检档案、蓝色背包海豚挂件、警方旧案卷宗。',
                yuan_ids,
            )
        yuan_evidences = g.evidences()
        yuan_ids = [str(ev.get('id')) for ev in yuan_evidences if str(ev.get('id')) in {{'001', '703', '704', '705', '706', '707', '708'}}]

        if '705' in yuan_ids:
            for npc_id in target_ids[:12]:
                ask_target(
                    npc_id,
                    '705李海天尸检已出现。继续追下一层：报告原始保管人、李海天与袁樱瞳死状差异、蓝色背包海豚挂件主人、尸块DNA、1919车辆、保安网页和生物馆监控对应的706/707/708。',
                    yuan_ids,
                )
        else:
            for ynpc in ordered:
                ask_visible(
                    ynpc,
                    '若705或706不在你手里，请不要猜测；只说明应该找哪个完整姓名、哪个保安、哪位老师、警方/法医/保卫处/车辆/网站/手机云端系统来调取。',
                    yuan_ids,
                )
        yuan_ids = [str(ev.get('id')) for ev in g.evidences() if str(ev.get('id')) in {{'001', '703', '704', '705', '706', '707', '708'}}]
        if '706' in yuan_ids or '707' in yuan_ids or '708' in yuan_ids:
            for ynpc in ordered:
                ask_visible(ynpc, '后续证据已经出现。请闭环真实死者、旧案同源、网页截图、凶手、动机、分尸/移尸/嫁祸过程和最终可提交答案。', yuan_ids)
        g.answer(murderer='无名氏', motivation='无', method='无')
        return
'''


POKER_ONLY_SOLVE_CASE = r'''def solve_case(g: Game, case_idx: int) -> bool:
    npcs = g.npcs()
    if not npcs:
        return False
    marks = g.marks()
    hint = g.hint()
    evidences = g.evidences()
    text = all_text(hint, evidences)
    log(f'[n597] case={case_idx} npcs={sorted(npcs)} marks={marks} hint={compact(hint, 60)}')
    if '扑克公馆' in text:
        solve_unknown(g, npcs, marks, hint, evidences)
    else:
        g.answer(murderer='无名氏', motivation='无', method='无')
    return True


'''


YUAN_ONLY_SOLVE_CASE = r'''def solve_case(g: Game, case_idx: int) -> bool:
    npcs = g.npcs()
    if not npcs:
        return False
    marks = g.marks()
    hint = g.hint()
    evidences = g.evidences()
    text = all_text(hint, evidences)
    log(f'[n597] case={case_idx} npcs={sorted(npcs)} marks={marks} hint={compact(hint, 60)}')
    if '袁樱瞳' in text or '碎尸案' in text:
        solve_unknown(g, npcs, marks, hint, evidences)
    else:
        g.answer(murderer='无名氏', motivation='无', method='无')
    return True


'''


def insert_helpers(src: str) -> str:
    marker = "def rose_roles(npcs: list[str], marks: dict[str, bool], evidences: list[dict[str, Any]]) -> dict[str, tuple[str, str]]:\n"
    if HELPERS.strip() in src:
        return src
    return src.replace(marker, HELPERS + "\n" + marker, 1)


def add_poker_sweep(src: str) -> str:
    marker = "                if g.stage < 3 and ev_ids:\n"
    if POKER_GLOBAL_SWEEP.strip() in src:
        return src
    return src.replace(marker, POKER_GLOBAL_SWEEP + marker, 1)


def replace_yuan(src: str, mode: str) -> str:
    start = src.index("    elif '袁樱瞳' in text or '碎尸案' in text:\n")
    end = src.index("    else:\n        method = '未知'\n", start)
    return src[:start] + yuan_branch(mode) + src[end:]


def replace_solve_case(src: str, replacement: str) -> str:
    start = src.index('def solve_case(g: Game, case_idx: int) -> bool:\n')
    end = src.index('def main() -> int:\n', start)
    return src[:start] + replacement + src[end:]


def write_candidate(label: str, *, yuan_mode: str | None = None, isolate: str | None = None, poker_all_global: bool = False) -> None:
    src = BASE.read_text(encoding='utf-8')
    src = insert_helpers(src)
    src = add_poker_sweep(src)
    if yuan_mode:
        src = replace_yuan(src, yuan_mode)
    if poker_all_global:
        src = src.replace('DEBUG = False\n', 'DEBUG = False\nN597_POKER_ALL_GLOBAL = True\n', 1)
    if isolate == 'poker':
        src = replace_solve_case(src, POKER_ONLY_SOLVE_CASE)
    elif isolate == 'yuan':
        src = replace_solve_case(src, YUAN_ONLY_SOLVE_CASE)

    target = OUT / label
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    (target / 'ai.py').write_text(src, encoding='utf-8')


def main() -> int:
    write_candidate('n597a', isolate='poker', poker_all_global=True)
    write_candidate('n597b', yuan_mode='holder', isolate='yuan')
    write_candidate('n597c', yuan_mode='identity', isolate='yuan')
    write_candidate('n597d', yuan_mode='holder')
    write_candidate('n597e', yuan_mode='cross')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
