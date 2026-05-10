#!/usr/bin/env python3
from __future__ import annotations

import shutil
from pathlib import Path

from make_n600_candidates import add_deep_block


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'Game2' / 'deepclue_ai'
POKER_BASE = OUT / 'n600a' / 'ai.py'
YUAN_BASE = OUT / 'n597b' / 'ai.py'
FULL_BASE = OUT / 'n597e' / 'ai.py'


def poker_extra_block(mode: str) -> str:
    if mode == 'official':
        first = (
            '601-604或606若已出现，停止复述案情，只按官方材料追缺口：605、刘丽雯女儿失踪/报案/亲子鉴定、林渝植档案、'
            '心形胎记医疗记录、Joker人口贩卖名册、花纹村余党、张子韩密码来源和警方结案证据。'
        )
        second = (
            '若606三人照片已出现，请解释照片来源、三人的真实姓名和POKER纹身组织含义，并直接交出缺失的605或下一份卷宗。'
        )
    elif mode == 'final':
        first = (
            '601-604或606若已出现，直接闭环最终层：谁把Joker引入衣帽间，谁实际杀死Joker，谁给密码，'
            '林渝植/真正梅花5、刘丽雯/张壹、于书华、张子韩、景观警方各自分工和可提交答案。'
        )
        second = (
            '不要再列证据编号。请按作案链回答：8:50聊天、特殊邀请函、LYZ项链、衣帽间密码、刀具/移尸、POKER组织、最终凶手和动机。'
        )
    else:
        first = (
            '601-604或606若已出现，请直接问左臂POKER纹身：Joker、于书华、张子韩是否同属花纹村组织，'
            '三人照片、组织成员、Joker真实身份、林渝植心形胎记和刘丽雯女儿线索分别对应哪份下一证据。'
        )
        second = (
            '若有人提示左臂纹身，就不要问泛化案情；只追POKER纹身、花纹村入场券、三人照片原件、组织名单、605和最终凶手。'
        )

    return f'''                if 'poker_after_ids' in locals():
                    n601_current = list(locals().get('current_npcs', follow_npcs) or follow_npcs)
                    n601_ids = [
                        eid for eid in list(locals().get('poker_after_ids', []))
                        if eid in {{'101', '102', '103', '104', '201', '202', '203', '204', '205', '401', '402', '404', '501', '502', '503', '504', '601', '602', '603', '604', '605', '606', '607', '608'}}
                    ]
                    n601_text = str(globals().get('N600_DEEP_TEXT', '')) + '\\n' + str(locals().get('combined_late_text', ''))
                    n601_text += '\\n' + '\\n'.join(
                        str(ev.get('name', '')) + str(ev.get('content', '')) for ev in g.evidences()
                    )
                    n601_targets: list[str] = []

                    def n601_add(npc_id: str) -> None:
                        if npc_id and npc_id not in n601_targets:
                            n601_targets.append(npc_id)

                    def n601_ask(npc_id: str, question: str) -> str:
                        if not npc_id:
                            return ''
                        if npc_id in n601_current:
                            resp = g.chat(npc_id, question, n601_ids)
                        else:
                            resp = g.probe_chat_once(npc_id, question, n601_ids)
                        text_value = response_text(resp)
                        if text_value:
                            globals()['N601_FINAL_TEXT'] = str(globals().get('N601_FINAL_TEXT', '')) + '\\n' + text_value
                        return text_value

                    for npc_id in [
                        str(locals().get('info_id', '')),
                        str(locals().get('password_id', '')),
                        str(locals().get('reception_id', '')),
                    ]:
                        n601_add(npc_id)
                    for name in extract_story_names(n601_text):
                        for npc_id in global_name_ids(name, n601_current):
                            n601_add(npc_id)
                    for cn in ('张子韩', '张壹', '刘丽雯', '于书华', '王科瑾', '王泽', '林渝植', '许清和', '江沐青', '沈知遥'):
                        for npc_id in global_name_ids(cn, n601_current):
                            n601_add(npc_id)
                    for npc_id in n601_current:
                        n601_add(npc_id)

                    if {{'601', '602', '603', '604'}} & set(n601_ids) or '606' in n601_ids:
                        for npc_id in n601_targets[:18]:
                            n601_ask(npc_id, '{first}')
                        n601_ids = [
                            str(ev.get('id')) for ev in g.evidences()
                            if str(ev.get('id')) in {{'101', '102', '103', '104', '201', '202', '203', '204', '205', '401', '402', '404', '501', '502', '503', '504', '601', '602', '603', '604', '605', '606', '607', '608'}}
                        ]
                        for npc_id in n601_targets[:18]:
                            n601_ask(npc_id, '{second}')
                    globals()['N601_POKER_IDS'] = ','.join(
                        str(ev.get('id')) for ev in g.evidences()
                    )
                    poker_after_ids = [str(ev.get('id')) for ev in g.evidences()]
'''


PASSWORD_HOLDER_ANSWER_PATCH = """    final_mode = str(globals().get('N601_ANSWER_MODE', ''))
    if final_mode == 'password_holder':
        final_text = str(globals().get('N601_FINAL_TEXT', '')) + '\\n' + str(globals().get('N600_DEEP_TEXT', ''))
        final_ids = str(globals().get('N601_POKER_IDS', '')) + ',' + str(globals().get('N600_POKER_IDS', ''))
        password_holder = ''
        for pattern in (
            r'([一-龥]{2,4})给了我密码',
            r'密码[^。\\n]{0,20}([一-龥]{2,4})',
            r'接待(?:员|者)?([一-龥]{2,4})',
        ):
            match = re.search(pattern, final_text)
            if match:
                password_holder = match.group(1)
                break
        if password_holder and ('601' in final_ids or '606' in final_ids):
            g.answer(
                murderer=password_holder,
                motivation=f'{password_holder}掌握衣帽间密码并卷入Joker、POKER纹身、花纹村人口贩卖、林渝植失踪和刘丽雯女儿线索，为揭露或切断组织而杀死Joker。',
                method=f'{password_holder}利用接待权限、8:50梅花5与Joker聊天、特殊邀请函、LYZ项链和0512衣帽间密码把Joker引入衣帽间，再用面具身份混淆、刀具和移尸痕迹制造梅花5死亡假象。'
            )
            return
    g.answer(murderer=suspect, motivation='未知', method=method)
"""


def add_poker_extra(src: str, mode: str) -> str:
    marker = "                if g.stage < 3 and ev_ids:\n"
    idx = src.rfind(marker)
    if idx < 0:
        raise RuntimeError('poker insertion marker missing')
    return src[:idx] + poker_extra_block(mode) + src[idx:]


def add_password_holder_answer(src: str) -> str:
    src = src.replace('DEBUG = False\n', "DEBUG = False\nN601_ANSWER_MODE = 'password_holder'\n", 1)
    old = "    g.answer(murderer=suspect, motivation='未知', method=method)\n"
    if old not in src:
        raise RuntimeError('answer anchor missing')
    return src.replace(old, PASSWORD_HOLDER_ANSWER_PATCH, 1)


def yuan_branch(mode: str) -> str:
    if mode == 'identity':
        first = (
            '先查开场身份链，不猜凶手：失忆侦探是谁，眼熟保安为什么认识我，口袋模糊网页截图是什么网站，'
            '保安周日缺岗、奇怪网站后台、旧案系统、李海天和袁樱瞳之间由谁保管原始材料。'
        )
        second = (
            '只追网页/保安/身份系统来源：网站后台访问日志、保卫处值班表、警方旧案卷宗、法医DNA、手机云端、'
            '1919车辆、生物馆监控、蓝色背包海豚挂件和706/707/708。'
        )
        follow = (
            '705李海天尸检若已出现，继续追网页截图和保安线：报告原件来源、保安认识侦探的原因、奇怪网站后台、'
            '李海天/袁樱瞳/照片女尸DNA、蓝色背包主人和下一证据706/707/708。'
        )
    else:
        first = (
            '袁樱瞳案按官方custody拆分，不问泛化口供：703手机、704投票、705李海天尸检、706/707/708、'
            '周五揭发材料、票箱原件、尸源DNA、黄色行李箱、1919黑车、生物馆监控、保安网页分别由谁保管。'
        )
        second = (
            '请按系统而不是传闻回答：教务/办公室/票箱、保卫处、警方旧案、法医、车辆登记、网站后台、手机云端、'
            '行李箱物证、蓝色背包海豚挂件中哪一个能打开705之后的下一层。'
        )
        follow = (
            '705李海天尸检已出现时，不要复述背刺断肢；只追706/707/708：报告原件编号、DNA比对、蓝色背包主人、'
            '海豚挂件来源、1919车辆轨迹、生物馆监控、网页后台、手机照片元数据和警方旧案卷宗。'
        )

    return f'''    elif '袁樱瞳' in text or '碎尸案' in text:
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

        def add_id(bucket: list[str], npc_id: str) -> None:
            if npc_id and npc_id not in bucket:
                bucket.append(npc_id)

        for ynpc in ordered:
            ask(ynpc, '{first}')
        yuan_ids = [str(ev.get('id')) for ev in g.evidences() if str(ev.get('id')) in {{'001', '703', '704', '705', '706', '707', '708'}}]
        for ynpc in ordered:
            ask(ynpc, '{second}', yuan_ids)

        yuan_evidences = g.evidences()
        yuan_ids = [str(ev.get('id')) for ev in yuan_evidences if str(ev.get('id')) in {{'001', '703', '704', '705', '706', '707', '708'}}]
        combined = '\\n'.join(replies.values()) + '\\n' + '\\n'.join(
            str(ev.get('name', '')) + str(ev.get('content', '')) for ev in yuan_evidences
        )
        targets: list[str] = []
        for name in extract_story_names(combined):
            for npc_id in global_name_ids(name, current_npcs):
                add_id(targets, npc_id)
        for cn in ('袁樱瞳', '李海天', '张朔', '张壹', '保安', '许清和', '江沐青', '罗方琛', '沈知遥'):
            for npc_id in global_name_ids(cn, current_npcs):
                add_id(targets, npc_id)
        for npc_id in ordered:
            add_id(targets, npc_id)

        if '705' in yuan_ids:
            for npc_id in targets[:16]:
                ask(npc_id, '{follow}', yuan_ids)
        else:
            for npc_id in targets[:12]:
                ask(
                    npc_id,
                    '若705尚未出现，请只指出完整来源：哪位保安、哪位老师、哪名学生、警方/法医/保卫处/车辆/网站/手机云端系统能调取；若你知道706来源也直接说。',
                    yuan_ids,
                )
        yuan_ids = [str(ev.get('id')) for ev in g.evidences() if str(ev.get('id')) in {{'001', '703', '704', '705', '706', '707', '708'}}]
        if '706' in yuan_ids or '707' in yuan_ids or '708' in yuan_ids:
            for ynpc in ordered:
                ask(ynpc, '后续隐藏证据已经出现。闭环真实死者、照片来源、网页截图、旧案同源、凶手、动机、分尸/移尸/嫁祸过程和最终答案。', yuan_ids)
        g.answer(murderer='无名氏', motivation='无', method='无')
        return
'''


def replace_yuan_branch(src: str, mode: str) -> str:
    start = src.index("    elif '袁樱瞳' in text or '碎尸案' in text:\n")
    end = src.index("    else:\n        method = '未知'\n", start)
    return src[:start] + yuan_branch(mode) + src[end:]


def write_candidate(label: str, text: str) -> None:
    target = OUT / label
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    (target / 'ai.py').write_text(text, encoding='utf-8')


def main() -> int:
    poker = POKER_BASE.read_text(encoding='utf-8')
    yuan = YUAN_BASE.read_text(encoding='utf-8')
    full = add_deep_block(FULL_BASE.read_text(encoding='utf-8'))
    specs = {
        'n601a': add_poker_extra(poker, 'tattoo'),
        'n601b': add_poker_extra(poker, 'official'),
        'n601c': add_password_holder_answer(add_poker_extra(poker, 'final')),
        'n601d': replace_yuan_branch(yuan, 'custody'),
        'n601e': replace_yuan_branch(yuan, 'identity'),
        'n601f': replace_yuan_branch(add_poker_extra(full, 'official'), 'identity'),
    }
    for label, text in specs.items():
        write_candidate(label, text)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
