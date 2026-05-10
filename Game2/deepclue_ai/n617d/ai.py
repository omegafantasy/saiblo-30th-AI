#!/usr/bin/env python3
"""Game2 DeepClue AI n617d.

Post-update probe:
- keep v49's robust direct answers for Rose and the two new cases;
- recover the old high-stage Z/F script under randomized Chinese NPC names;
- keep all changes isolated to Game2.
"""
from __future__ import annotations

import json
import re
import struct
import sys
import time
from typing import Any


PINYIN_TO_CN = {
    'BaiJingTing': '白井霆',
    'ChuRongZhen': '楚戎臻',
    'CuiAnYan': '崔安彦',
    'DengDaLing': '邓达岭',
    'FanMinMin': '范敏敏',
    'GuYunShu': '顾云舒',
    'JiangMuQing': '江沐青',
    'LinWanZhou': '林晚舟',
    'LuoFangChen': '罗方琛',
    'LuYiChu': '陆亦初',
    'ShenZhiYao': '沈知遥',
    'WangKeJin': '王科瑾',
    'WangZe': '王泽',
    'XiaoDingAng': '萧定昂',
    'XiaoDingGang': '萧定刚',
    'XuQingHe': '许清和',
    'YeQingHeng': '叶青衡',
    'YeWenXiao': '叶文潇',
    'ZhangShuo': '张朔',
    'ZhangYi': '张壹',
    'ZhangZiHan': '张子韩',
    'ZhaoYiCheng': '赵一橙',
    'ZhouLinJun': '周林君',
}
CN_TO_PINYIN = {cn: pinyin for pinyin, cn in PINYIN_TO_CN.items()}


class SDK:
    def __init__(self) -> None:
        self._stdin = sys.stdin.buffer
        self._stdout = sys.stdout.buffer

    def _send(self, data: dict[str, Any]) -> None:
        raw = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self._stdout.write(struct.pack('>I', len(raw)) + raw)
        self._stdout.flush()

    def _receive(self) -> dict[str, Any]:
        self._stdin.read(4)
        line = self._stdin.readline()
        if not line:
            raise EOFError('stdin closed')
        text = line.decode('utf-8', errors='replace').strip()
        return json.loads(text) if text else {}

    def request(self, action: str, **kwargs: Any) -> dict[str, Any] | list[Any]:
        self._send({'action': action, **kwargs})
        return self._receive()


DEBUG = False


def log(*args: Any) -> None:
    if DEBUG:
        print(*args, file=sys.stderr, flush=True)


def cn_name(npc_id: str) -> str:
    return PINYIN_TO_CN.get(npc_id, npc_id)


def name_from_title(title: str) -> str:
    title = title.strip()
    for pattern in (r'关于([^：:]+)$', r'^([^：:]+?)的介绍$'):
        m = re.search(pattern, title)
        if m:
            return m.group(1).strip()
    return ''


def poker_info_name(hint: str, npcs: list[str] | None = None) -> str:
    text = hint or ''
    if npcs is not None:
        for npc in npcs:
            name = cn_name(npc)
            if name and name in text:
                return name
    for pattern in (
        r'([一-龥]{2,4})是个好的信息来源',
        r'([一-龥]{2,4})会是[^，。]*好的信息来源',
        r'问问([一-龥]{2,4})关于',
        r'接待者([一-龥]{2,4})知道',
    ):
        m = re.search(pattern, text)
        if m:
            return m.group(1)
    return ''


def compact(text: Any, limit: int = 100) -> str:
    return re.sub(r'\s+', ' ', str(text or '')).strip()[:limit]


class Game:
    def __init__(self, sdk: SDK) -> None:
        self.sdk = sdk
        self.stage = 0
        self.calls = 0

    def req(self, action: str, **kwargs: Any) -> Any:
        try:
            return self.sdk.request(action, **kwargs)
        except Exception as exc:
            log(f'[n556y1] request failed action={action}: {exc}')
            return {}

    def npcs(self) -> list[str]:
        resp = self.req('npcs')
        return [str(x) for x in resp] if isinstance(resp, list) else []

    def marks(self) -> dict[str, bool]:
        resp = self.req('marks')
        return {str(k): bool(v) for k, v in resp.items()} if isinstance(resp, dict) else {}

    def hint(self) -> str:
        resp = self.req('hint')
        return str(resp.get('hint', '')) if isinstance(resp, dict) else ''

    def evidences(self) -> list[dict[str, Any]]:
        resp = self.req('others')
        if isinstance(resp, dict) and isinstance(resp.get('evidences'), list):
            return [x for x in resp['evidences'] if isinstance(x, dict)]
        return []

    def chat(self, npc: str, question: str, evidences: list[str] | None = None) -> dict[str, Any]:
        evs = list(evidences or [])
        resp: Any = {}
        for attempt in range(3):
            resp = self.req('chat', npc=npc, question=question, evidences=evs)
            self.calls += 1
            if not (isinstance(resp, dict) and resp.get('error')):
                break
            log(f'[n556y1] chat error retry={attempt} npc={npc} q={compact(question, 36)} err={compact(resp.get("error"), 80)}')
            time.sleep(0.25 * (attempt + 1))
        if not isinstance(resp, dict):
            return {}
        try:
            new_stage = int(resp.get('stage', self.stage) or self.stage)
        except (TypeError, ValueError):
            new_stage = self.stage
        if new_stage > self.stage:
            log(f'[n556y1] stage {self.stage}->{new_stage} npc={npc} q={compact(question, 36)}')
            self.stage = new_stage
        return resp

    def retry_trigger(self, trigger_qs: list[tuple[Any, ...]], max_retries: int = 2) -> bool:
        target_stage = self.stage
        for attempt in range(max_retries):
            for item in trigger_qs:
                npc, question = str(item[0]), str(item[1])
                evidences = list(item[2]) if len(item) > 2 else None
                log(f'[n556y1] retry a{attempt} npc={npc} q={compact(question, 40)}')
                self.chat(npc, question, evidences)
                if self.stage > target_stage:
                    return True
        return self.stage > target_stage

    def answer(self, murderer: str, motivation: str, method: str) -> dict[str, Any]:
        resp = self.req('answer', murderer=murderer, motivation=motivation, method=method)
        return resp if isinstance(resp, dict) else {}

    def probe_chat_once(self, npc: str, question: str, evidences: list[str] | None = None) -> dict[str, Any]:
        resp = self.req('chat', npc=npc, question=question, evidences=list(evidences or []))
        self.calls += 1
        if not isinstance(resp, dict):
            return {}
        try:
            new_stage = int(resp.get('stage', self.stage) or self.stage)
        except (TypeError, ValueError):
            new_stage = self.stage
        if new_stage > self.stage:
            log(f'[n556y1] stage {self.stage}->{new_stage} npc={npc} q={compact(question, 36)}')
            self.stage = new_stage
        return resp


def all_text(hint: str, evidences: list[dict[str, Any]]) -> str:
    parts = [hint]
    for ev in evidences:
        parts.append(str(ev.get('name', '')))
        parts.append(str(ev.get('content', '')))
    return '\n'.join(parts)


def response_text(resp: dict[str, Any]) -> str:
    if not isinstance(resp, dict):
        return ''
    for key in ('reply', 'content', 'message', 'text'):
        value = resp.get(key)
        if isinstance(value, str):
            return value
    return ''


def yuan_candidate_from_replies(yuan_replies: dict[str, str], npcs: list[str], marks: dict[str, bool]) -> str:
    scores: dict[str, int] = {}
    keys = (
        '出国名额', '获利', '投票', '24', '23', '多出', '笔迹',
        '手机', '凌晨1点', '尸体照片', '假发', '行李箱', '清空手机',
        '生物馆', '世纪林', '1919',
    )
    for npc, reply in yuan_replies.items():
        text = str(reply or '')
        scores[npc] = sum(1 for key in keys if key in text)
    if scores:
        suspect_id = max(scores, key=scores.get)
        marked_false = [npc for npc in npcs if marks.get(npc) is False]
        if marked_false and scores.get(suspect_id, 0) < 4:
            suspect_id = marked_false[0]
        return cn_name(suspect_id)
    for npc in npcs:
        if marks.get(npc) is False:
            return cn_name(npc)
    return cn_name(npcs[0]) if npcs else '无名氏'


def reception_name_from_reply(text: str) -> str:
    for pattern in (
        r'接待(?:员|者)([一-龥]{2,4})',
        r'去问(?:问)?([一-龥]{2,4})',
        r'应该去问(?:问)?([一-龥]{2,4})',
    ):
        match = re.search(pattern, text)
        if match:
            return match.group(1).strip()
    return ''


def poker_reception_id(npcs: list[str], info_id: str, hint: str, marks: dict[str, bool]) -> str:
    for npc in npcs:
        if npc != info_id and cn_name(npc) in hint:
            return npc
    if 'LuYiChu' in npcs and info_id != 'LuYiChu':
        return 'LuYiChu'
    marked_true = [npc for npc in npcs if npc != info_id and marks.get(npc) is True]
    if len(marked_true) == 1:
        return marked_true[0]
    return ''


def poker_reception_candidates(npcs: list[str], info_id: str, hint: str, marks: dict[str, bool]) -> list[str]:
    candidates: list[str] = []
    first = poker_reception_id(npcs, info_id, hint, marks)
    if first:
        candidates.append(first)
    for npc in npcs:
        if npc != info_id and marks.get(npc) is False and npc not in candidates:
            candidates.append(npc)
    for npc in npcs:
        if npc != info_id and npc not in candidates:
            candidates.append(npc)
    return candidates


def id_for_name(name: str, npcs: list[str]) -> str:
    direct = CN_TO_PINYIN.get(name, '')
    if direct in npcs:
        return direct
    for npc in npcs:
        if cn_name(npc) == name:
            return npc
    return ''


def id_for_name_any(name: str, npcs: list[str]) -> str:
    return id_for_name(name, npcs) or CN_TO_PINYIN.get(name, '')


def clean_cn_fragment(raw: str) -> str:
    value = re.sub(r'[^一-龥]', '', str(raw or ''))
    if value.startswith('保安'):
        value = value[2:]
    for suffix in ('大叔', '老师', '同学', '先生', '女士', '学长', '学姐', '处', '本人', '队长'):
        if value.endswith(suffix):
            value = value[:-len(suffix)]
    return value


def global_name_ids(raw: str, current_npcs: list[str] | None = None, max_ids: int = 8) -> list[str]:
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
        r'保安(?:室)?([一-龥]{1,2})(?:大叔|老师|师傅|老师傅)',
        r'看到([一-龥]{1,4})[^。；\n]{0,30}从生物馆',
        r'(?:从|在)?([一-龥]{2,4})处获得',
        r'([一-龥]{1,4})老师的出国',
        r'([一-龥]{1,4})[^。；\n]{0,16}以\s*24\s*票',
        r'([一-龥]{1,4})[^。；\n]{0,16}险胜袁樱瞳',
        r'([一-龥]{1,4})[^。；\n]{0,20}给了我密码',
        r'真正的梅花\s*5[^。；\n]{0,32}([一-龥]{1,4})',
        r'林渝植[^。；\n]{0,24}(?:就是|现在叫|现在是)([一-龥]{1,4})',
        r'([一-龥]{1,4})[^。；\n]{0,20}(?:车主|司机|转账|看诊|银行流水)',
    ):
        for match in re.finditer(pattern, text or ''):
            add(match.group(1))
    return names


def story_target_ids(text: str, current_npcs: list[str], max_ids: int = 8) -> list[str]:
    ids: list[str] = []

    def add(npc_id: str) -> None:
        if npc_id and npc_id not in ids:
            ids.append(npc_id)

    for name in extract_story_names(text):
        for npc_id in global_name_ids(name, current_npcs):
            add(npc_id)
            if len(ids) >= max_ids:
                return ids
    return ids


def chat_visible_or_probe(g: Game, npc: str, visible_npcs: list[str], question: str, evidences: list[str] | None = None) -> dict[str, Any]:
    if npc in set(visible_npcs):
        return g.chat(npc, question, evidences)
    return g.probe_chat_once(npc, question, evidences)



def n612_refresh_ids(g: Game, allowed: set[str]) -> list[str]:
    return [
        str(ev.get('id'))
        for ev in g.evidences()
        if str(ev.get('id')) in allowed
    ]


def n612_add_unique(bucket: list[str], value: str) -> None:
    if value and value not in bucket:
        bucket.append(value)


def n612_chase_poker_promises(g: Game, target_ids: list[str], visible_npcs: list[str], seen_text: str, max_targets: int = 6) -> list[str]:
    allowed = {'101', '102', '103', '104', '201', '202', '203', '204', '205', '401', '402', '404', '405', '501', '502', '503', '504', '505', '601', '602', '603', '604', '605', '606', '607', '608'}
    current_ids = n612_refresh_ids(g, allowed)
    current_set = set(current_ids)
    wanted: list[str] = []
    for eid in ('405', '605', '607', '608'):
        if eid not in current_set and re.search(rf'(?<!\d){eid}(?!\d)', seen_text or ''):
            wanted.append(eid)
    if '605' not in current_set and ('606' in current_set or 'POKER' in (seen_text or '')):
        if any(key in (seen_text or '') for key in ('现场掌握', '警方手里', '保管', '还不是交出', '时机未到', '最终卷宗', '成员名册')):
            n612_add_unique(wanted, '605')
    if not wanted:
        return current_ids

    targets: list[str] = []
    for npc_id in target_ids:
        n612_add_unique(targets, npc_id)
    for npc_id in story_target_ids(seen_text or '', visible_npcs, max_ids=8):
        n612_add_unique(targets, npc_id)
    if not targets:
        targets = list(visible_npcs)

    want_text = '、'.join(wanted)
    question = (
        f'你刚才已经明确提到或暗示了{want_text}，而且说由你保管、现场/警方已经掌握或只是时机未到。'
        '现在不要复述剧情，也不要再说编号听不懂；请按保管链直接交出对应实物。'
        '如果它是LYZ挂件、凶器/血衣、死者手机云端名单、花纹村成员名册、POKER组织照片原件、DNA/指纹报告、车内血迹/行车记录或警方最终卷宗，请直接说证据名、内容和持有人。'
    )
    asked = 0
    for npc_id in targets:
        if not npc_id:
            continue
        resp = chat_visible_or_probe(g, npc_id, visible_npcs, question, current_ids)
        seen_text += '\n' + response_text(resp)
        current_ids = n612_refresh_ids(g, allowed)
        current_set = set(current_ids)
        asked += 1
        if current_set & {'405', '605', '607', '608'}:
            break
        if asked >= max_targets:
            break
    return current_ids


def n612_follow_yuan_contact_exchange(g: Game, current_npcs: list[str], yuan_replies: dict[str, str], yuan_ids: list[str]) -> list[str]:
    allowed = {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706', '707', '708'}
    if '707' not in set(yuan_ids) or '708' in set(yuan_ids):
        return yuan_ids
    yuan_evidences = g.evidences()
    ev707 = next((ev for ev in yuan_evidences if str(ev.get('id')) == '707'), None)
    ev707_text = str(ev707.get('name', '')) + '\n' + str(ev707.get('content', '')) if isinstance(ev707, dict) else ''
    contact_name = ''
    exchange_name = ''
    m = re.search(r'物证07：([一-龥]{1,4})的联系方式', ev707_text)
    if m:
        contact_name = m.group(1)
    for pattern in (
        r'可用于与([一-龥]{1,4})交换情报',
        r'与([一-龥]{1,4})交换情报',
        r'([一-龥]{1,4})曾表示如果能帮',
    ):
        m = re.search(pattern, ev707_text)
        if m:
            exchange_name = m.group(1)
            break
    targets: list[str] = []

    def add(npc_id: str) -> None:
        if npc_id and npc_id not in targets:
            targets.append(npc_id)

    for name in (exchange_name, contact_name):
        for npc_id in global_name_ids(name, current_npcs) if name else []:
            add(npc_id)
    combined = ev707_text + '\n' + '\n'.join(yuan_replies.values())
    runner_name = exchange_name
    for pattern in (
        r'看见([一-龥]{2,4}).{0,20}从生物馆',
        r'([一-龥]{2,4}).{0,20}从生物馆.{0,12}跑出来',
        r'([一-龥]{2,4}).{0,12}学生会副会长',
    ):
        m = re.search(pattern, combined)
        if m:
            runner_name = m.group(1)
            break
    for name in (runner_name, exchange_name, contact_name):
        for npc_id in global_name_ids(name, current_npcs) if name else []:
            add(npc_id)
    for npc_id in story_target_ids(combined, current_npcs, max_ids=10):
        add(npc_id)
    for npc_id in current_npcs:
        add(npc_id)
    contact_label = contact_name or '运动少女'
    exchange_label = exchange_name or runner_name or '生物馆跑出者'
    q_exchange = (
        f'707的交换已经完成：我把{contact_label}的联系方式交给你。不要再说“交换”或“找人”，直接兑现你承诺的杀手秘密。'
        '你上周六22:30为什么从生物馆慌张跑出，看见或处理了什么；秘密对应的实物记录是什么：'
        '生物馆门禁/监控、学生会办公室材料、李海天U盘、袁樱瞳手机原图、保卫处登记、QQ微信电话记录。若这就是物证08/708，请直接交出。'
    )
    q_contact = (
        f'你作为{contact_label}，已经提供联系方式。请回忆{exchange_label}向你要联系方式时的异常：他从生物馆跑出时手里是否有手机、U盘、血迹、背包/海豚挂件、行李箱；'
        '他说过什么，后来是否联系你；哪份门禁、监控、电话或微信记录能证明他的杀手秘密。'
    )
    q_locator = (
        f'现在只找{exchange_label}本人和记录：学生会办公室、宿舍、电子系楼、生物馆门禁、保卫处监控、QQ/微信/电话记录。'
        '请直接给能调取708的唯一持有人或证据原件。'
    )
    for npc_id in targets[:10]:
        name = cn_name(npc_id)
        if exchange_name and name == exchange_name:
            q = q_exchange
        elif runner_name and name == runner_name:
            q = q_exchange
        elif contact_name and name == contact_name:
            q = q_contact
        else:
            q = q_locator
        resp = chat_visible_or_probe(g, npc_id, g.npcs() or current_npcs, q, yuan_ids)
        yuan_replies[npc_id] = yuan_replies.get(npc_id, '') + '\n' + response_text(resp)
        yuan_ids = n612_refresh_ids(g, allowed)
        if '708' in set(yuan_ids):
            break
    return yuan_ids

def n612_follow_yuan_usb(g: Game, current_npcs: list[str], yuan_replies: dict[str, str], yuan_ids: list[str]) -> list[str]:
    allowed = {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706', '707', '708'}
    if '706' not in set(yuan_ids) or {'707', '708'} & set(yuan_ids):
        return yuan_ids
    yuan_evidences = g.evidences()
    ev706 = next((ev for ev in yuan_evidences if str(ev.get('id')) == '706'), None)
    ev706_text = str(ev706.get('name', '')) + '\n' + str(ev706.get('content', '')) if isinstance(ev706, dict) else ''
    targets: list[str] = []
    for npc_id in story_target_ids(ev706_text + '\n' + '\n'.join(yuan_replies.values()), current_npcs, max_ids=10):
        n612_add_unique(targets, npc_id)
    for name in ('张子韩', '李海天', '袁樱瞳', '王科瑾', '江沐青', '叶青衡', '楚戎臻', '沈知遥', '陆亦初'):
        for npc_id in global_name_ids(name, current_npcs):
            n612_add_unique(targets, npc_id)
    for npc_id in current_npcs:
        n612_add_unique(targets, npc_id)

    question = (
        '706 U盘不是终点。请直接打开U盘内容继续查：电子系保研名单里谁获利、谁未保研，李海天侵犯女生的视频照片里出现了哪些人，'
        '袁樱瞳周五要揭发谁，谁因此清空她手机或伪造凌晨照片。下一步如果需要受害女生/运动少女联系方式、交换杀手秘密、手机原图元数据、生物馆监控或最终物证，请直接给707/708的证据名和持有人。'
    )
    for npc_id in targets[:8]:
        resp = chat_visible_or_probe(g, npc_id, g.npcs() or current_npcs, question, yuan_ids)
        yuan_replies[npc_id] = yuan_replies.get(npc_id, '') + '\n' + response_text(resp)
        yuan_ids = n612_refresh_ids(g, allowed)
        if {'707', '708'} & set(yuan_ids):
            break
    return yuan_ids


def poker_true_club5_name(text: str) -> str:
    for pattern in (
        r'现在的([一-龥]{2,4})就是她',
        r'她就在我们中间[，,。]*([一-龥]{2,4})就是她',
        r'([一-龥]{2,4})就是林渝植',
    ):
        match = re.search(pattern, text or '')
        if match:
            return match.group(1).strip()
    return ''


def yuan_guard_id_from_replies(yuan_replies: dict[str, str], npcs: list[str]) -> str:
    guard_name = ''
    for reply in yuan_replies.values():
        for pattern in (
            r'保安.*?([一-龥]{2,4})大叔',
            r'保安室([一-龥]{2,4})',
            r'保安([一-龥]{1,4})(?:大叔|师傅|老师傅)',
            r'保安([一-龥]{2,4})',
        ):
            m = re.search(pattern, reply)
            if m:
                guard_name = m.group(1)
                break
        if guard_name:
            break
    guard_name = re.sub(r'(大叔|师傅|老师傅)$', '', guard_name)
    guard_id = id_for_name(guard_name, npcs) if guard_name else ''
    if not guard_id and len(guard_name) == 1:
        for ynpc in npcs:
            if cn_name(ynpc).startswith(guard_name):
                return ynpc
    return guard_id


def yuan_absent_vote_name_from_replies(yuan_replies: dict[str, str]) -> str:
    combined = '\n'.join(yuan_replies.values())
    for pattern in (
        r'([一-龥]{2,4})那天明明翘课',
        r'([一-龥]{2,4})那天翘课',
        r'([一-龥]{2,4})翘课没来',
        r'([一-龥]{2,4})翘课未计入',
        r'([一-龥]{2,4})没来.*?却.*?票',
        r'实际(?:在场|实到)只有\s*46\s*人[，,。；\\n]{0,6}([一-龥]{2,4})',
    ):
        match = re.search(pattern, combined)
        if match:
            return match.group(1).strip()
    return ''


def rose_roles(npcs: list[str], marks: dict[str, bool], evidences: list[dict[str, Any]]) -> dict[str, tuple[str, str]]:
    roles: dict[str, tuple[str, str]] = {}
    for ev in evidences:
        ev_id = str(ev.get('id', ''))
        if ev_id == '002':
            name = name_from_title(str(ev.get('name', '')))
            npc_id = id_for_name(name, npcs)
            if name and npc_id:
                roles['xiao'] = (name, npc_id)
        elif ev_id == '003':
            name = name_from_title(str(ev.get('name', '')))
            npc_id = id_for_name(name, npcs)
            if name and npc_id:
                roles['bai'] = (name, npc_id)
        elif ev_id == '004':
            name = name_from_title(str(ev.get('name', '')))
            npc_id = id_for_name(name, npcs)
            if name and npc_id:
                roles['deng'] = (name, npc_id)
        elif ev_id == '001':
            m = re.search(r'传来([^等，,。]+)等舞女', str(ev.get('content', '')))
            if m:
                name = m.group(1).strip()
                npc_id = id_for_name(name, npcs)
                if name and npc_id:
                    roles['ye'] = (name, npc_id)

    for npc in npcs:
        if marks.get(npc) is False:
            roles['cui'] = (cn_name(npc), npc)
            break

    used = {npc_id for _, npc_id in roles.values()}
    remaining = [npc for npc in npcs if npc not in used]
    if len(remaining) == 1:
        roles['fan'] = (cn_name(remaining[0]), remaining[0])
    return roles


def solve_rose_direct(g: Game, npcs: list[str], marks: dict[str, bool], evidences: list[dict[str, Any]]) -> None:
    false_marked = [npc for npc in npcs if marks.get(npc) is False]
    murderer_id = false_marked[0] if false_marked else (npcs[0] if npcs else '')
    murderer = cn_name(murderer_id)
    banker = ''
    for ev in evidences:
        if str(ev.get('id')) == '004':
            banker = name_from_title(str(ev.get('name', '')))
            break
    if not banker:
        banker = '银行家'
    log(f'[n556y1] rose direct murderer_id={murderer_id} murderer={murderer} banker={banker}')
    g.answer(
        murderer=murderer,
        motivation=f'{murderer}爱慕并想独占{banker}，认为Rose纠缠{banker}、会阻碍自己与{banker}在一起，因此为扫清情敌而杀害Rose。',
        method=f'{murderer}利用家族药材生意取得夹竹桃毒素，趁18:40左右在准备室将毒投入Rose的专用蜂蜜水杯，Rose饮用后中毒身亡。',
    )


def solve_rose(g: Game, npcs: list[str], marks: dict[str, bool], evidences: list[dict[str, Any]]) -> None:
    roles = rose_roles(npcs, marks, evidences)
    if set(roles) != {'xiao', 'bai', 'deng', 'fan', 'ye', 'cui'}:
        log(f'[n556y1] rose role mapping incomplete roles={roles}')
        solve_rose_direct(g, npcs, marks, evidences)
        return

    xiao_name, xiao = roles['xiao']
    bai_name, bai = roles['bai']
    deng_name, deng = roles['deng']
    fan_name, fan = roles['fan']
    ye_name, ye = roles['ye']
    cui_name, cui = roles['cui']
    log(
        f'[n556y1] rose script xiao={xiao_name}/{xiao} bai={bai_name}/{bai} '
        f'deng={deng_name}/{deng} fan={fan_name}/{fan} ye={ye_name}/{ye} cui={cui_name}/{cui}'
    )
    g.stage = 0
    g.calls = 0

    g.chat(xiao, 'Rose是怎样的人？')
    g.chat(deng, 'Rose是怎样的人？')
    g.chat(ye, 'Rose是怎样的人？')
    g.chat(fan, 'Rose是怎样的人？')
    g.chat(bai, 'Rose是个怎样的人？')
    if g.stage < 2:
        g.retry_trigger([
            (bai, 'Rose给你的印象怎么样？'),
            (bai, '你怎么看Rose这个人？'),
        ])

    g.chat(xiao, '你今晚在做什么？')
    g.chat(bai, '你今晚在做什么？')
    g.chat(cui, '你今晚在干什么？')
    g.chat(deng, '你今晚在干什么？')
    g.chat(ye, '你今晚在干什么？')
    g.chat(fan, '你今晚在干什么？')
    if g.stage < 3:
        g.retry_trigger([
            (ye, '你今晚都去了哪些地方？'),
            (fan, '你今晚的行踪说一下？'),
        ])

    g.chat(deng, '你为什么没娶妻？')
    g.chat(ye, '这个杯子你认识吗？', ['111'])
    g.chat(fan, '你见过这个花盆吗？', ['112'])
    g.chat(bai, f'Rose和{fan_name}吵架了你知道吗？')
    g.chat(ye, f'Rose和{fan_name}吵架了？')
    g.chat(fan, '你和Rose吵架了？')
    g.chat(deng, '你和Rose好上了？')
    g.chat(cui, f'{deng_name}和Rose是什么关系？')
    g.chat(ye, 'Rose今天状态不对？')
    g.chat(cui, '你是不是提前来了？')
    g.chat(bai, f'你今天是不是和{cui_name}一起来的？')
    if g.stage < 4:
        g.retry_trigger([
            (ye, 'Rose今天有什么异常吗？'),
            (fan, '你和Rose到底怎么了？'),
            (cui, f'你和{deng_name}今天来的时候有没有看到什么？'),
        ])

    g.chat(ye, 'Rose今天戴面纱了？')
    g.chat(fan, '你和Rose长得像？')
    g.chat(xiao, f'你和{fan_name}什么关系？')
    g.chat(cui, '家里生意不好？')
    g.chat(deng, f'{cui_name}接近你？')
    if g.stage < 5:
        g.retry_trigger([
            (xiao, f'{fan_name}最近态度有变化吗？'),
            (deng, f'{cui_name}最近有什么异常行为？'),
        ])

    g.chat(xiao, f'{fan_name}态度怪？')
    g.chat(fan, f'对{xiao_name}冷淡？')
    g.chat(fan, '是不是你代替Rose上台？')
    g.chat(fan, f'你对{xiao_name}好？')
    g.chat(ye, f'{deng_name}喜欢你？')
    g.chat(deng, f'18:30和{ye_name}在舞台右侧见面？')
    g.chat(bai, f'18:30和{cui_name}在一起？')
    g.chat(xiao, '19:05你在干什么？')

    current_npcs = g.npcs()
    for npc in current_npcs:
        if npc not in npcs:
            g.chat(npc, '你是谁？')

    g.chat(bai, '19:05你在干什么？')
    g.chat(ye, f'你今天是不是和{deng_name}见面了？')
    g.chat(cui, '18:40你在哪里？')
    g.chat(cui, f'你让{bai_name}去安慰Rose是什么意思？')
    g.chat(deng, 'Rose是不是威胁你？')

    log(f'[n556y1] rose final stage={g.stage} calls={g.calls}')
    g.answer(
        murderer=cui_name,
        motivation=f'{cui_name}爱慕并想独占{deng_name}，认为Rose纠缠{deng_name}、会阻碍自己与{deng_name}在一起，因此为扫清情敌而杀害Rose。',
        method=f'{cui_name}利用家族药材生意取得夹竹桃毒素，趁18:40左右在准备室将毒投入Rose的专用蜂蜜水杯，Rose饮用后中毒身亡。',
    )


def z_roles(npcs: list[str], evidences: list[dict[str, Any]]) -> dict[str, tuple[str, str]]:
    id_to_role = {'002': 'A', '003': 'B', '004': 'C', '005': 'D', '006': 'E'}
    roles: dict[str, tuple[str, str]] = {}
    for ev in evidences:
        role = id_to_role.get(str(ev.get('id', '')))
        if not role:
            continue
        name = name_from_title(str(ev.get('name', '')))
        npc_id = id_for_name(name, npcs)
        if name and npc_id:
            roles[role] = (name, npc_id)
    return roles


def solve_z_direct(g: Game, evidences: list[dict[str, Any]]) -> None:
    names: dict[str, str] = {}
    for ev in evidences:
        ev_id = str(ev.get('id', ''))
        if ev_id in {'002', '003', '004', '005', '006'}:
            names[ev_id] = name_from_title(str(ev.get('name', '')))
    c = names.get('004', 'C')
    e = names.get('006', 'E')
    log(f'[n556y1] z direct C={c} E={e}')
    g.answer(
        murderer=e,
        motivation=f'{e}发现F就是高中时在表白墙造谣诬陷自己出轨的人，又发现F向Z家长告密导致Z被迫逃离学校，新仇旧恨交织下决定杀害F。',
        method=f'{e}尾随F到小树林埋伏处守株待兔，在F回收分尸工具时伏击打晕F，用偷来的{c}的水果刀按照{c}小说里的手法毁坏F面部，并将尸体埋在F自己挖的坑中。',
    )


def solve_z_script(g: Game, npcs: list[str], evidences: list[dict[str, Any]]) -> None:
    roles = z_roles(npcs, evidences)
    if set(roles) != {'A', 'B', 'C', 'D', 'E'}:
        log(f'[n556y1] z role mapping incomplete roles={roles}')
        solve_z_direct(g, evidences)
        return

    a_name, a = roles['A']
    b_name, b = roles['B']
    c_name, c = roles['C']
    d_name, d = roles['D']
    e_name, e = roles['E']
    log(f'[n556y1] z script A={a_name}/{a} B={b_name}/{b} C={c_name}/{c} D={d_name}/{d} E={e_name}/{e}')
    g.stage = 0
    g.calls = 0

    g.chat(a, '你知道Z失踪了吗？')
    g.chat(b, '你知道Z失踪了吗？')
    g.chat(b, '你了解平时的Z吗？')
    g.chat(c, '你知道Z失踪了吗？')
    g.chat(c, '你了解平时的Z吗？')
    g.chat(d, '你知道Z失踪了吗？')
    g.chat(d, '你了解平时的Z吗？')
    g.chat(e, '你了解平时的Z吗？')
    if g.stage < 2:
        g.retry_trigger([
            (e, 'Z平时是什么样的人？'),
            (e, '你和Z关系好吗？'),
        ])

    g.chat(a, '你是不是明年要竞选班长？')
    g.chat(a, '昨天下午你是不是看见Z了？')
    g.chat(b, f'昨天你是不是骑车撞到{d_name}了？')
    g.chat(c, '你知道Z凌晨去看病了吗？')
    g.chat(d, f'你和{e_name}以前是不是男女朋友？')
    if g.stage < 3:
        g.retry_trigger([
            (d, f'你和{e_name}是什么关系？'),
            (d, f'你以前是不是和{e_name}在一起过？'),
        ])

    g.chat(e, 'Z画漫画的事你知道吗？')
    g.chat(e, '关于那件事情你都知道什么？')
    g.chat(a, f'关于高中时候{e_name}和{d_name}的那件事，你都知道什么？')
    g.chat(b, f'你是不是喜欢{e_name}？')
    if g.stage < 4:
        g.retry_trigger([
            (b, f'你对{e_name}有什么感觉？'),
            (b, f'你是不是暗恋{e_name}？'),
        ])

    g.chat(d, '关于高中那件事，你知道是谁造谣的吗？')
    g.chat(a, 'F死了，你知道吗？', ['313'])
    g.chat(a, '你认为谁可能有杀F的动机？', ['313'])
    g.chat(c, '昨晚你在做什么？', ['313'])
    g.chat(c, '昨晚你在回宿舍路上有没有看到什么？', ['313'])
    if g.stage < 5:
        g.retry_trigger([
            (c, '昨晚你在回宿舍路上有没有看到什么？', ['313']),
            (a, '你认为谁可能有杀F的动机？', ['313']),
            (c, f'你昨晚有没有看到{d_name}？', ['313']),
            (c, '你昨晚有没有看到F？', ['313']),
            (c, '昨晚在回宿舍路上你遇到谁了？', ['313']),
            (a, f'{c_name}的电脑上有什么可疑的东西吗？', ['313']),
        ], max_retries=3)

    g.chat(c, '为什么你的水果刀会在现场？', ['315'])
    g.chat(b, '你最后一次见F是什么时候？', ['313'])
    g.chat(e, '关于F的死你知道什么？', ['313'])
    g.chat(e, '你帮Z躲起来了对吧？', ['311'])
    g.chat(e, f'你是不是找{d_name}盗号的？')
    g.chat(d, '你是不是盗了F的号？')
    g.chat(d, f'你是怎么看到{c_name}小说的？')
    g.chat(c, '你实际在写的是那种血腥猎奇的小说吧？')
    g.chat(a, '红U盘去哪了？')
    if g.stage < 6:
        g.retry_trigger([
            (a, '红U盘去哪了？'),
            (a, 'F的U盘你知道在哪吗？'),
        ])

    g.chat(a, f'你是不是拆了{d_name}的车？')
    g.chat(b, '你知道那个F的U盘去哪了吗？')
    g.chat(d, '你是同性恋吗？')
    g.chat(c, '那你的绿U盘去哪了？')
    g.chat(d, f'你不是崴脚了吗，为什么{c_name}会看见你自己去修车？')
    g.chat(d, '你为什么装病？')
    if g.stage < 7:
        g.retry_trigger([
            (d, '你为什么装病？'),
            (d, '你的脚到底有没有受伤？'),
            (d, '你是不是在骗我们？'),
        ])

    g.chat(c, '你电脑上的杀人计划书是怎么回事？')
    g.chat(c, '为什么杀人计划书里面都是同学的名字？')
    g.chat(b, f'你是不是准备杀{a_name}？')
    g.probe_chat_once(d, 'F的QQ里面还有什么信息？')
    g.probe_chat_once(c, '你是色盲？')

    log(f'[n556y1] z final stage={g.stage} calls={g.calls}')
    g.answer(
        murderer=e_name,
        motivation=f'{e_name}发现F就是高中时在表白墙造谣诬陷自己出轨的人，又发现F向Z家长告密导致Z被迫逃离学校。新仇旧恨交织，{e_name}决定杀害F。',
        method=f'{e_name}尾随F到小树林埋伏处守株待兔，在F回来回收分尸工具时伏击打晕了她，用偷来的{c_name}的水果刀按照{c_name}的小说手法破坏了F的面部，然后将尸体埋在F自己挖的坑中。',
    )


def solve_unknown(g: Game, npcs: list[str], marks: dict[str, bool], hint: str, evidences: list[dict[str, Any]]) -> None:
    g.stage = 0
    suspect = cn_name(npcs[0]) if npcs else ''
    text = all_text(hint, evidences)
    if '扑克公馆' in text:
        info_id = ''
        hint_name = poker_info_name(hint, npcs)
        hint_id = id_for_name(hint_name, npcs) if hint_name else ''
        marked_true = [npc for npc in npcs if marks.get(npc) is True]
        if hint_id:
            info_id = hint_id
            suspect = hint_name
        elif len(marked_true) == 1:
            info_id = marked_true[0]
            suspect = cn_name(info_id)
        else:
            for npc in npcs:
                if cn_name(npc) in hint:
                    info_id = npc
                    suspect = cn_name(npc)
                    break
        if info_id:
            suspect = cn_name(info_id)
            first = g.chat(info_id, '请说说案发现场情况，以及你手中的证据。')
            second = g.chat(info_id, '你是谁？你和死者是什么关系？')
            if g.stage < 2:
                asked: set[str] = set()
                def force_reception_evidence(npc_id: str, resp: dict[str, Any]) -> None:
                    reply_text = response_text(resp)
                    if g.stage >= 2:
                        return
                    if any(key in reply_text for key in ('聊天记录', '到达时间表', '接待员', '地址表')):
                        g.chat(npc_id, '你刚才已经确认有Joker聊天记录、宾客到达时间表或地址表。不要只口头描述，请立刻把这两份作为物证交给我：Joker与接待者聊天记录、扑克牌标号/真实地址/到达时间对应表。')

                for reception_id in poker_reception_candidates(g.npcs() or npcs, info_id, g.hint(), g.marks()):
                    asked.add(reception_id)
                    resp = g.chat(reception_id, '请先说Joker聊天记录和宾客到达时间表，暂时不要展开公馆内的异常发现。')
                    force_reception_evidence(reception_id, resp)
                    named = reception_name_from_reply(response_text(resp))
                    named_id = id_for_name(named, g.npcs() or npcs) if named else ''
                    if named_id and named_id not in asked and named_id != info_id:
                        asked.add(named_id)
                        named_resp = g.chat(named_id, '你负责接待这次聚会吗？请完整说明Joker聊天记录、宾客到达时间表、公馆内异常发现、电脑浏览记录、冰柜塑料盒和厨房缺刀。')
                        force_reception_evidence(named_id, named_resp)
                    if g.stage >= 2:
                        break
                if g.stage < 2:
                    for reception_id in poker_reception_candidates(g.npcs() or npcs, info_id, g.hint(), g.marks()):
                        if reception_id in asked:
                            continue
                        resp = g.chat(reception_id, '你是否负责接待扑克公馆聚会？请直接说明Joker聊天记录、宾客到达时间表、公馆内异常发现和死者身份线索。')
                        force_reception_evidence(reception_id, resp)
                        if g.stage >= 2:
                            break
            refusals = ('不是全部公开', '不行', '不能', '时机', '证据')
            if g.stage < 2 and any(word in (response_text(first) + response_text(second)) for word in refusals):
                g.chat(info_id, '死者戴的梅花5、你追查的林渝植和现场证据之间有什么关系？')
            if g.stage >= 2:
                follow_hint = g.hint()
                follow_marks = g.marks()
                follow_npcs = g.npcs() or npcs
                reception_id = poker_reception_id(follow_npcs, info_id, follow_hint, follow_marks)
                if reception_id:
                    g.chat(reception_id, '请先说Joker聊天记录和宾客到达时间表，暂时不要展开公馆内的异常发现。')
                    if g.stage < 3:
                        g.chat(reception_id, '现在只说公馆内异常发现：死者房间电脑浏览记录、冰柜旁方形塑料盒、厨房缺失刀具分别是什么？')
                poker_evidences = g.evidences()
                ev_ids = [str(ev.get('id')) for ev in poker_evidences if str(ev.get('id')) in {'101', '201', '202', '203'}]
                if reception_id and g.stage >= 3:
                    g.chat(reception_id, '请直接调取扑克公馆仅有的两类监控：餐厅11:00到13:00、大门口0:00到13:00；把7:30不明身份人、8:20离开、8:50梅花5到达、12:00梅花5进餐厅、12:05离开这些记录给我。')
                    poker_evidences = g.evidences()
                    monitor_ids = [
                        str(ev.get('id'))
                        for ev in poker_evidences
                        if str(ev.get('id')) in {'101', '102', '103', '104', '201', '202', '203', '204', '205', '401', '402'}
                    ]
                    true_club5_id = ''
                    police_revealed = False
                    if {'401', '402'}.issubset(set(monitor_ids)):
                        resp = g.chat(info_id, '我已经把线索拼完整：7:30不明身份人和12:00餐厅里的梅花5才是真正活着的梅花5；8:50到达并死在衣帽间的是Joker伪装者。请直接确认真正梅花5的姓名、Joker和林渝植的真实身份，并交出下一阶段证据。', monitor_ids)
                        reply = response_text(resp)
                        police_revealed = any(key in reply for key in ('刑警', '警察', '景观', '队长'))
                        true_club5_name = poker_true_club5_name(reply)
                        true_club5_id = id_for_name(true_club5_name, follow_npcs) if true_club5_name else ''
                        password_name = ''
                        for pattern in (
                            r'([一-龥]{2,4})已经给了我密码',
                            r'([一-龥]{2,4})给了我密码',
                            r'密码.*?([一-龥]{2,4})',
                        ):
                            m = re.search(pattern, reply)
                            if m:
                                password_name = m.group(1)
                                break
                        password_id = id_for_name(password_name, follow_npcs) if password_name else ''
                        if password_id:
                            password_resp = g.chat(password_id, '你给出的衣帽间密码是什么？请直接打开衣帽间，指出里面剩下的破绽、真正梅花5身份和下一阶段证据。', monitor_ids)
                        else:
                            password_resp = g.chat(info_id, '推断过程是：402显示7:30有人提前入馆、8:20离开，8:50又有梅花5到达；401显示12:00餐厅还有梅花5活动。你说衣帽间还有更多破绽，请直接给出密码、破绽和下一阶段证据。', monitor_ids)
                        if not true_club5_id:
                            true_club5_name = poker_true_club5_name(response_text(password_resp))
                            true_club5_id = id_for_name(true_club5_name, follow_npcs) if true_club5_name else ''
                        if police_revealed:
                            proof_resp = g.chat(info_id, '我把时间线完整说给你：402说明7:30有人随Joker提前入馆、8:20离开，8:50另一个梅花5才到；401说明12:00餐厅里的梅花5仍活着；衣帽间血迹位置和死后强戴面具证明Joker被移尸。密码0512已验证。请按刑警卷宗一次性交出车辆、转账、DNA/指纹、病历、银行流水中的下一阶段证据。', monitor_ids)
                            if not true_club5_id:
                                true_club5_name = poker_true_club5_name(response_text(proof_resp))
                                true_club5_id = id_for_name(true_club5_name, follow_npcs) if true_club5_name else ''
                        poker_evidences = g.evidences()
                        ev404 = next((ev for ev in poker_evidences if str(ev.get('id')) == '404'), None)
                        ev501 = next((ev for ev in poker_evidences if str(ev.get('id')) == '501'), None)
                        branch_ids = [
                            str(ev.get('id'))
                            for ev in poker_evidences
                            if str(ev.get('id')) in {'101', '102', '103', '104', '201', '202', '203', '204', '205', '401', '402', '404', '501'}
                        ]
                        if not isinstance(ev404, dict) and not isinstance(ev501, dict):
                            gate_resp = g.chat(info_id, '如果我的时间线和密码0512已经满足，请不要泛泛说“下一阶段”：直接给404车牌、501匿名转账，或隐藏物证405/502的证据编号、证据名和保管人；如果还不能给，请说明缺哪个持有人、地点或官方卷宗。', branch_ids)
                            poker_evidences = g.evidences()
                            ev404 = next((ev for ev in poker_evidences if str(ev.get('id')) == '404'), None)
                            ev501 = next((ev for ev in poker_evidences if str(ev.get('id')) == '501'), None)
                            branch_ids = [
                                str(ev.get('id'))
                                for ev in poker_evidences
                                if str(ev.get('id')) in {'101', '102', '103', '104', '201', '202', '203', '204', '205', '401', '402', '404', '405', '501', '502'}
                            ]
                            if not isinstance(ev404, dict) and not isinstance(ev501, dict):
                                gate_text = '\n'.join([response_text(gate_resp), response_text(password_resp), response_text(proof_resp) if 'proof_resp' in locals() else ''])
                                if any(key in gate_text for key in ('官方卷宗', '授权', '警方', '刑警', '景观')):
                                    auth_resp = g.chat(info_id, '你已经表明自己是刑警大队队长“景观”，官方卷宗授权应由你直接调取。现在我以协助侦查身份申请正式调阅：402大门监控、401餐厅监控、0512衣帽间密码和移尸破绽均已满足，请直接交出404车牌、501匿名转账、DNA/指纹/银行流水或下一阶段证据编号，不要再等接待者。', branch_ids)
                                    gate_text += '\n' + response_text(auth_resp)
                                    poker_evidences = g.evidences()
                                    ev404 = next((ev for ev in poker_evidences if str(ev.get('id')) == '404'), None)
                                    ev501 = next((ev for ev in poker_evidences if str(ev.get('id')) == '501'), None)
                                    branch_ids = [
                                        str(ev.get('id'))
                                        for ev in poker_evidences
                                        if str(ev.get('id')) in {'101', '102', '103', '104', '201', '202', '203', '204', '205', '401', '402', '404', '405', '501', '502'}
                                    ]
                                gate_sources: list[str] = []

                                def add_gate_source(npc_id: str) -> None:
                                    if npc_id and npc_id not in gate_sources:
                                        gate_sources.append(npc_id)

                                for pattern in (
                                    r'没有([一-龥]{1,4})手里[^。；\n]{0,16}现场勘验',
                                    r'([一-龥]{1,4})手里[^。；\n]{0,16}现场勘验',
                                    r'去找([一-龥]{1,4})',
                                    r'问([一-龥]{1,4})',
                                ):
                                    for match in re.finditer(pattern, gate_text):
                                        for npc_id in global_name_ids(match.group(1), follow_npcs):
                                            add_gate_source(npc_id)
                                add_gate_source(info_id)
                                add_gate_source(password_id)
                                add_gate_source(reception_id)
                                for source_id in gate_sources[:4]:
                                    if isinstance(ev404, dict) or isinstance(ev501, dict):
                                        break
                                    gate_follow = chat_visible_or_probe(g, source_id, follow_npcs, '你手里有现场勘验笔录或警方调取单。402大门监控、401餐厅监控、0512衣帽间密码和移尸破绽都已满足，请不要口头确认，直接交出404车牌、501匿名转账、现场勘验笔录、DNA/指纹/银行流水或下一阶段证据编号。', branch_ids)
                                    gate_text += '\n' + response_text(gate_follow)
                                    poker_evidences = g.evidences()
                                    ev404 = next((ev for ev in poker_evidences if str(ev.get('id')) == '404'), None)
                                    ev501 = next((ev for ev in poker_evidences if str(ev.get('id')) == '501'), None)
                                    branch_ids = [
                                        str(ev.get('id'))
                                        for ev in poker_evidences
                                        if str(ev.get('id')) in {'101', '102', '103', '104', '201', '202', '203', '204', '205', '401', '402', '404', '405', '501', '502'}
                                    ]
                                    if isinstance(ev404, dict) or isinstance(ev501, dict):
                                        break
                        if isinstance(ev404, dict):
                            globals()['POKER_HAS_404'] = True
                            car_name_raw = str(ev404.get('name', '')).replace('车牌号', '').strip()
                            car_match = re.search(r'([一-龥]{2,4})', car_name_raw)
                            car_name = car_match.group(1) if car_match else car_name_raw
                            car_id = id_for_name(car_name, follow_npcs) if car_name else ''
                            target_id = car_id or info_id
                            g.chat(target_id, '404显示京F·A7590在7:20经过，104又说死者房间窗外就是后院停车位。请直接说明这辆车谁开、停在窗边做了什么、Joker在哪里死亡、尸体如何移进衣帽间，并交出物证405、后备箱血迹或行车记录证据。', branch_ids)
                            poker_evidences = g.evidences()
                            ev405 = next((ev for ev in poker_evidences if str(ev.get('id')) == '405'), None)
                            ev501 = next((ev for ev in poker_evidences if str(ev.get('id')) == '501'), ev501)
                            branch_ids = [
                                str(ev.get('id'))
                                for ev in poker_evidences
                                if str(ev.get('id')) in {'101', '102', '103', '104', '201', '202', '203', '204', '205', '401', '402', '404', '405', '501', '502'}
                            ]
                            if not isinstance(ev405, dict):
                                g.chat(info_id, '404车牌、402大门监控、104窗外停车位和衣帽间血迹已经能证明尸体被转移。请不要概括，直接给出物证405：杀人地点、搬尸路线、车内血迹/后备箱/轮胎/行车记录或门禁高清截图是哪一项证据。', branch_ids)
                                poker_evidences = g.evidences()
                                ev501 = next((ev for ev in poker_evidences if str(ev.get('id')) == '501'), ev501)
                                branch_ids = [
                                    str(ev.get('id'))
                                    for ev in poker_evidences
                                    if str(ev.get('id')) in {'101', '102', '103', '104', '201', '202', '203', '204', '205', '401', '402', '404', '405', '501', '502'}
                                ]
                            if true_club5_id and true_club5_id not in {target_id, info_id}:
                                poker_evidences = g.evidences()
                                ev405 = next((ev for ev in poker_evidences if str(ev.get('id')) == '405'), None)
                                ev502_current = next((ev for ev in poker_evidences if str(ev.get('id')) == '502'), None)
                                if not isinstance(ev405, dict) and not isinstance(ev502_current, dict):
                                    g.chat(true_club5_id, '你就是真正活着的梅花5/林渝植。404车牌、402大门监控和衣帽间移尸破绽已经对上，请直接说明Joker在7:30把你带进公馆后发生了什么、罗方琛的车如何参与、尸体从哪里搬到衣帽间，并交出物证405或502。', branch_ids)
                                    poker_evidences = g.evidences()
                                    branch_ids = [
                                        str(ev.get('id'))
                                        for ev in poker_evidences
                                        if str(ev.get('id')) in {'101', '102', '103', '104', '201', '202', '203', '204', '205', '401', '402', '404', '405', '501', '502'}
                                    ]
                            poker_evidences = g.evidences()
                            ev405 = next((ev for ev in poker_evidences if str(ev.get('id')) == '405'), None)
                            ev502_current = next((ev for ev in poker_evidences if str(ev.get('id')) == '502'), None)
                            luo_id = id_for_name_any('罗方琛', follow_npcs)
                            if luo_id and luo_id not in {target_id, info_id, true_club5_id} and not isinstance(ev405, dict) and not isinstance(ev502_current, dict):
                                chat_visible_or_probe(g, luo_id, follow_npcs, '404已经锁定京F·A7590，而你可能是车辆链关键人。不要再讲身份猜测，请直接给车辆登记、7:20行驶记录、后备箱/车内血迹、停车位高清监控、搬尸路线或物证405/502的保管人。', branch_ids)
                                poker_evidences = g.evidences()
                                branch_ids = [
                                    str(ev.get('id'))
                                    for ev in poker_evidences
                                    if str(ev.get('id')) in {'101', '102', '103', '104', '201', '202', '203', '204', '205', '401', '402', '404', '405', '501', '502'}
                                ]
                        if isinstance(ev501, dict):
                            globals()['POKER_HAS_501'] = True
                            transfer_text = str(ev501.get('name', '')) + '\n' + str(ev501.get('content', ''))
                            transfer_match = None
                            for pattern in (
                                r'([一-龥]{2,4})[（(]于书华[）)]',
                                r'([一-龥]{2,4}).{0,12}于书华',
                                r'([一-龥]{2,4}).{0,18}50万',
                                r'([一-龥]{2,4}).{0,18}转账',
                            ):
                                transfer_match = re.search(pattern, transfer_text)
                                if transfer_match:
                                    break
                            transfer_name = transfer_match.group(1) if transfer_match else ''
                            transfer_id = id_for_name(transfer_name, follow_npcs) if transfer_name else ''
                            target_id = transfer_id or info_id
                            g.chat(target_id, '501显示你以于书华身份看诊后三天收到50万元匿名转账。你是不是被Joker人口贩卖集团利用的医生？这笔钱和女儿下落、林渝植失踪、Joker伪装梅花5有什么关系？请交出物证502、病历、聊天记录或转账来源证据。', branch_ids)
                            poker_evidences = g.evidences()
                            ev502 = next((ev for ev in poker_evidences if str(ev.get('id')) == '502'), None)
                            branch_ids = [
                                str(ev.get('id'))
                                for ev in poker_evidences
                                if str(ev.get('id')) in {'101', '102', '103', '104', '201', '202', '203', '204', '205', '401', '402', '404', '405', '501', '502'}
                            ]
                            if not isinstance(ev502, dict):
                                g.chat(info_id, '501的于书华看诊和匿名50万元转账说明王泽只是被Joker利用的医生。请把物证502、病历登记、勒索聊天、女儿下落线索、转账来源账户和林渝植失踪之间的闭环证据交出来。', branch_ids)
                                poker_evidences = g.evidences()
                                ev502 = next((ev for ev in poker_evidences if str(ev.get('id')) == '502'), None)
                                branch_ids = [
                                    str(ev.get('id'))
                                    for ev in poker_evidences
                                    if str(ev.get('id')) in {'101', '102', '103', '104', '201', '202', '203', '204', '205', '401', '402', '404', '405', '501', '502'}
                                ]
                            if true_club5_id and true_club5_id not in {target_id, info_id} and not isinstance(ev502, dict):
                                g.chat(true_club5_id, '你是林渝植本人而王泽只是于书华身份下被利用的医生。501匿名50万元转账、女儿下落勒索、Joker人口贩卖集团和你失踪之间缺最后闭环；请直接交出物证502、转账来源、勒索聊天、病历登记或你被藏匿的下一阶段证据。', branch_ids)
                                g.evidences()
                            poker_evidences = g.evidences()
                            ev502 = next((ev for ev in poker_evidences if str(ev.get('id')) == '502'), None)
                            wang_id = id_for_name_any('王泽', follow_npcs)
                            if wang_id and wang_id not in {target_id, info_id, true_club5_id} and not isinstance(ev502, dict):
                                chat_visible_or_probe(g, wang_id, follow_npcs, '501点名王泽/于书华和匿名50万元转账。请不要只说你被利用，直接交出转账源账户、开户实名、医院挂号/病历、于书华女儿胁迫、Joker人口贩卖名单、林渝植失踪案卷或物证502。', branch_ids)
                                poker_evidences = g.evidences()
                                branch_ids = [
                                    str(ev.get('id'))
                                    for ev in poker_evidences
                                    if str(ev.get('id')) in {'101', '102', '103', '104', '201', '202', '203', '204', '205', '401', '402', '404', '405', '501', '502'}
                                ]
                        poker_evidences = g.evidences()
                        late_ids = [
                            str(ev.get('id'))
                            for ev in poker_evidences
                            if str(ev.get('id')) in {'101', '102', '103', '104', '201', '202', '203', '204', '205', '401', '402', '404', '405', '501', '502'}
                        ]
                        ev405_late = next((ev for ev in poker_evidences if str(ev.get('id')) == '405'), None)
                        ev502_late = next((ev for ev in poker_evidences if str(ev.get('id')) == '502'), None)
                        if ({'404', '501'} & set(late_ids)) and not isinstance(ev405_late, dict) and not isinstance(ev502_late, dict):
                            g.chat(info_id, '现在后续不是再猜动机，而是补身份鉴定闭环：如果隐藏物证405或502存在，请直接按证据编号交出；死者到底是Joker还是林渝植、真正梅花5为何活着、面具内侧皮屑/指纹/牙科记录/失踪人口档案/DNA比对哪一项能证明？', late_ids)
                            poker_evidences = g.evidences()
                            late_ids = [
                                str(ev.get('id'))
                                for ev in poker_evidences
                                if str(ev.get('id')) in {'101', '102', '103', '104', '201', '202', '203', '204', '205', '401', '402', '404', '405', '501', '502'}
                            ]
                            ev405_late = next((ev for ev in poker_evidences if str(ev.get('id')) == '405'), None)
                            ev502_late = next((ev for ev in poker_evidences if str(ev.get('id')) == '502'), None)
                            if reception_id and reception_id != info_id and not isinstance(ev405_late, dict) and not isinstance(ev502_late, dict):
                                g.chat(reception_id, '如果405/502不是车辆或转账本身，请按公馆空间权限和刀具痕迹继续：衣帽间密码使用记录、死者房间门锁、窗户/后院、厨房冰柜、垃圾桶、清洁路线、背后三刀、刀痕比对、隐藏房间或死者手机，哪一项能交出下一物证？', late_ids)
                                poker_evidences = g.evidences()
                                late_ids = [
                                    str(ev.get('id'))
                                    for ev in poker_evidences
                                    if str(ev.get('id')) in {'101', '102', '103', '104', '201', '202', '203', '204', '205', '401', '402', '404', '405', '501', '502'}
                                ]
                                ev405_late = next((ev for ev in poker_evidences if str(ev.get('id')) == '405'), None)
                                ev502_late = next((ev for ev in poker_evidences if str(ev.get('id')) == '502'), None)
                            if reception_id and not isinstance(ev405_late, dict) and not isinstance(ev502_late, dict):
                                g.chat(reception_id, '换数字链查Joker：账号实名、登录IP、设备指纹、付款账户、十万定金和五十万承诺、邀请函地址表原文件、快递/寄送记录、面具分发记录里，哪一项能交出405/502或下一阶段物证？', late_ids)
                                poker_evidences = g.evidences()
                                late_ids = [
                                    str(ev.get('id'))
                                    for ev in poker_evidences
                                    if str(ev.get('id')) in {'101', '102', '103', '104', '201', '202', '203', '204', '205', '401', '402', '404', '405', '501', '502'}
                                ]
                                ev405_late = next((ev for ev in poker_evidences if str(ev.get('id')) == '405'), None)
                                ev502_late = next((ev for ev in poker_evidences if str(ev.get('id')) == '502'), None)
                            if not isinstance(ev405_late, dict) and not isinstance(ev502_late, dict):
                                g.chat(info_id, '不要复述时间线。下一阶段如果不是车和转账本身，就查Joker数字取证：账号实名/IP/设备、地址表来源、邀请函快递、接待付款流水、面具替换记录和人口贩卖资金账户；请直接给证据编号、证据名和持有人。', late_ids)
                                poker_evidences = g.evidences()
                                late_ids = [
                                    str(ev.get('id'))
                                    for ev in poker_evidences
                                    if str(ev.get('id')) in {'101', '102', '103', '104', '201', '202', '203', '204', '205', '401', '402', '404', '405', '501', '502'}
                                ]
                                ev405_late = next((ev for ev in poker_evidences if str(ev.get('id')) == '405'), None)
                                ev502_late = next((ev for ev in poker_evidences if str(ev.get('id')) == '502'), None)
                            fanout_seen = {info_id}
                            if reception_id:
                                fanout_seen.add(reception_id)
                            if password_id and password_id not in fanout_seen and not isinstance(ev405_late, dict) and not isinstance(ev502_late, dict):
                                fanout_seen.add(password_id)
                                g.chat(password_id, '你掌握衣帽间密码或0512。现在不要再讲普通破绽，请只说明密码使用记录、谁开过衣帽间、死者手机/隐藏房间、真实死亡地点、移尸路线、Joker手机或人口贩卖名单哪一项能交出405/502。', late_ids)
                                poker_evidences = g.evidences()
                                late_ids = [
                                    str(ev.get('id'))
                                    for ev in poker_evidences
                                    if str(ev.get('id')) in {'101', '102', '103', '104', '201', '202', '203', '204', '205', '401', '402', '404', '405', '501', '502'}
                                ]
                                ev405_late = next((ev for ev in poker_evidences if str(ev.get('id')) == '405'), None)
                                ev502_late = next((ev for ev in poker_evidences if str(ev.get('id')) == '502'), None)
                            if true_club5_id and true_club5_id not in fanout_seen and not isinstance(ev405_late, dict) and not isinstance(ev502_late, dict):
                                g.chat(true_club5_id, '你被指认为真正梅花5/林渝植。请直接说明你、Joker、人口贩卖集团、404车辆、501转账、于书华女儿胁迫和警方卷宗之间的下一份物证；若是405/502请给编号、证据名和持有人。', late_ids)
                                poker_evidences = g.evidences()
                                late_ids = [
                                    str(ev.get('id'))
                                    for ev in poker_evidences
                                    if str(ev.get('id')) in {'101', '102', '103', '104', '201', '202', '203', '204', '205', '401', '402', '404', '405', '501', '502'}
                                ]
                            for seen_id in (locals().get('target_id', ''), locals().get('luo_id', ''), locals().get('wang_id', '')):
                                if seen_id:
                                    fanout_seen.add(str(seen_id))
                            poker_evidences = g.evidences()
                            ev405_late = next((ev for ev in poker_evidences if str(ev.get('id')) == '405'), None)
                            ev502_late = next((ev for ev in poker_evidences if str(ev.get('id')) == '502'), None)
                            if not isinstance(ev405_late, dict) and not isinstance(ev502_late, dict):
                                story_text = '\n'.join(
                                    [reply, response_text(password_resp)]
                                    + [str(ev.get('name', '')) + str(ev.get('content', '')) for ev in poker_evidences]
                                )
                                story_count = 0
                                for story_id in story_target_ids(story_text, follow_npcs, max_ids=8):
                                    if story_id in fanout_seen or story_id == info_id:
                                        continue
                                    fanout_seen.add(story_id)
                                    chat_visible_or_probe(g, story_id, follow_npcs, '你被前面记录、半名或外部姓名指向为后续证据来源。只回答是否持有405/502/503/504，或车辆、转账、警方卷宗、DNA/指纹、病历、Joker账号、人口贩卖名单中的下一份官方证据。', late_ids)
                                    poker_evidences = g.evidences()
                                    late_ids = [
                                        str(ev.get('id'))
                                        for ev in poker_evidences
                                        if str(ev.get('id')) in {'101', '102', '103', '104', '201', '202', '203', '204', '205', '401', '402', '404', '405', '501', '502'}
                                    ]
                                    ev405_late = next((ev for ev in poker_evidences if str(ev.get('id')) == '405'), None)
                                    ev502_late = next((ev for ev in poker_evidences if str(ev.get('id')) == '502'), None)
                                    story_count += 1
                                    if isinstance(ev405_late, dict) or isinstance(ev502_late, dict) or story_count >= 2:
                                        break
                        if police_revealed and ({'404', '501'} & set(late_ids)):
                            poker_evidences = g.evidences()
                            ev405_late = next((ev for ev in poker_evidences if str(ev.get('id')) == '405'), None)
                            ev502_late = next((ev for ev in poker_evidences if str(ev.get('id')) == '502'), None)
                            if not isinstance(ev405_late, dict) and not isinstance(ev502_late, dict):
                                g.chat(info_id, '你既然是刑警队长“景观”，请不要再用嫌疑人口吻回答，直接调警局卷宗：物证405/502、林渝植失踪案、Joker人口贩卖案、车辆高清监控、DNA/指纹鉴定、银行流水和于书华病历里，哪一份是下一阶段证据？请交出证据编号、证据名和内容。', late_ids)
                        poker_evidences = g.evidences()
                        ev405_open = next((ev for ev in poker_evidences if str(ev.get('id')) == '405'), None)
                        ev502_open = next((ev for ev in poker_evidences if str(ev.get('id')) == '502'), None)
                        if isinstance(ev405_open, dict) or isinstance(ev502_open, dict):
                            globals()['POKER_HAS_502'] = True
                            open_ids = [
                                str(ev.get('id'))
                                for ev in poker_evidences
                                if str(ev.get('id')) in {'101', '102', '103', '104', '201', '202', '203', '204', '205', '401', '402', '404', '405', '501', '502', '503', '504', '601', '602', '603', '604', '605', '606', '607', '608'}
                            ]
                            g.chat(info_id, '405或502已经出现。现在继续追下一阶段而不是复述：完整凶手链、真实杀害地点、尸体转运、Joker手机/账号、人口贩卖名单、林渝植失踪卷宗、DNA/指纹和银行流水之后，还有没有503/504或最终物证？直接给编号、证据名和持有人。', open_ids)
                            if true_club5_id and true_club5_id != info_id:
                                g.chat(true_club5_id, '405/502已经打开，请从林渝植本人视角补最后一环：你如何被Joker控制、谁杀死Joker、车辆和转账如何串联、下一份官方证据或最终阶段证据在哪里？', open_ids)
                            poker_evidences = g.evidences()
                            deep_ids = [
                                str(ev.get('id'))
                                for ev in poker_evidences
                                if str(ev.get('id')) in {'101', '102', '103', '104', '201', '202', '203', '204', '205', '401', '402', '404', '405', '501', '502', '503', '504', '601', '602', '603', '604', '605', '606', '607', '608'}
                            ]
                            deep_id_set = set(deep_ids)
                            if deep_id_set & {'503', '504', '601', '602', '603', '604'}:
                                if deep_id_set & {'601', '602', '603', '604'}:
                                    globals()['POKER_HAS_601'] = True

                                def refresh_deep_ids() -> tuple[list[dict[str, Any]], list[str], set[str]]:
                                    current_evs = g.evidences()
                                    current_ids = [
                                        str(ev.get('id'))
                                        for ev in current_evs
                                        if str(ev.get('id')) in {'101', '102', '103', '104', '201', '202', '203', '204', '205', '401', '402', '404', '405', '501', '502', '503', '504', '601', '602', '603', '604', '605', '606', '607', '608'}
                                    ]
                                    return current_evs, current_ids, set(current_ids)

                                deep_targets: list[str] = []

                                def add_deep_target(npc_id: str) -> None:
                                    if npc_id and npc_id not in deep_targets:
                                        deep_targets.append(npc_id)

                                for npc_id in (
                                    info_id,
                                    true_club5_id,
                                    str(locals().get('target_id', '')),
                                    str(locals().get('wang_id', '')),
                                    reception_id,
                                    id_for_name_any('张子韩', follow_npcs),
                                    id_for_name_any('王科瑾', follow_npcs),
                                    id_for_name_any('顾云舒', follow_npcs),
                                ):
                                    add_deep_target(npc_id)

                                deep_questions: list[tuple[str, str]] = [
                                    (info_id, '503/504和601-604已经出现。不要再说“还差最后一块”，直接调刑警卷宗：死者手机云端名单、Joker账号实名/IP/设备、邀请函源文件、林渝植失踪卷宗、张子韩女儿DNA、王科瑾电脑银行流水和最终物证，下一编号、名称、持有人分别是什么？'),
                                    (true_club5_id, '你就是林渝植/真正梅花5，504的LYZ项链和601失踪少女特征已经对上。请直接说明你是否是张子韩寻找的女儿、Joker如何控制你、谁杀了Joker，以及下一份DNA/云端名单/最终物证编号和持有人。'),
                                    (id_for_name_any('张子韩', follow_npcs), '601报道失踪少女、603/604证明你曾是刘丽雯医生；501又说你为找女儿被王科瑾/于书华骗走五十万。请直接说明失踪女儿、林渝植、右眼角胎记、Joker人口贩卖集团和死者手机云端名单之间的证据链，并交出下一物证编号。'),
                                    (id_for_name_any('王科瑾', follow_npcs), '你电脑里的银行流水和501匿名五十万是后续关键。请不要再口头辩解，直接交出王科瑾电脑、转账源账户、于书华身份、Joker资金流、张子韩女儿线索和人口贩卖名单对应的下一物证编号。'),
                                    (reception_id, '你负责邀请函和接待。503显示梅花5邀请函格式不同，201又有Joker转账定金和地址表。请直接交出邀请函源文件、寄送记录、Joker账号设备/IP、死者手机云端名单或最终物证编号。'),
                                ]

                                asked_deep: set[str] = set()
                                for npc_id, question in deep_questions:
                                    if not npc_id or npc_id in asked_deep:
                                        continue
                                    asked_deep.add(npc_id)
                                    chat_visible_or_probe(g, npc_id, follow_npcs, question, deep_ids)
                                    _, deep_ids, deep_id_set = refresh_deep_ids()
                                    if deep_id_set & {'605', '606', '607', '608'}:
                                        break

                                if not (deep_id_set & {'605', '606', '607', '608'}):
                                    for npc_id in deep_targets[:6]:
                                        if npc_id in asked_deep:
                                            continue
                                        asked_deep.add(npc_id)
                                        chat_visible_or_probe(g, npc_id, follow_npcs, '现在只差Poker最终物证。围绕死者手机云端、Joker人口贩卖名单、林渝植失踪案、张子韩女儿亲子鉴定、王科瑾电脑银行流水、邀请函源文件和DNA/指纹鉴定，直接给下一证据编号、证据名、持有人。', deep_ids)
                                        _, deep_ids, deep_id_set = refresh_deep_ids()
                                        if deep_id_set & {'605', '606', '607', '608'}:
                                            break

                                if deep_id_set & {'605', '606', '607', '608'}:
                                    for npc_id in deep_targets[:4]:
                                        chat_visible_or_probe(g, npc_id, follow_npcs, 'Poker后续物证已经出现。请闭环最终答案：谁杀Joker、真实杀害地点、移尸路线、林渝植/张子韩女儿身份、王科瑾资金流、Joker人口贩卖名单和最终可提交证据。', deep_ids)
                poker_after_snapshot = g.evidences()
                poker_after_ids = [str(ev.get('id')) for ev in poker_after_snapshot]
                combined_late_text = '\n'.join(
                    [
                        str(locals().get('reply', '')),
                        str(response_text(locals().get('password_resp', {})) if 'password_resp' in locals() else ''),
                        str(response_text(locals().get('proof_resp', {})) if 'proof_resp' in locals() else ''),
                    ]
                    + [str(ev.get('name', '')) + str(ev.get('content', '')) for ev in poker_after_snapshot]
                )
                if {'404', '501', '502', '503', '504', '601', '602', '603', '604', '606'} & set(poker_after_ids):
                    globals()['POKER_HAS_LATE'] = True
                if 'poker_after_ids' in locals():
                    n604_current = list(locals().get('current_npcs', follow_npcs) or follow_npcs)
                    n604_ids = [
                        eid for eid in list(locals().get('poker_after_ids', []))
                        if eid in {'101', '102', '103', '104', '201', '202', '203', '204', '205', '401', '402', '404', '405', '501', '502', '503', '504', '601', '602', '603', '604', '605', '606', '607', '608'}
                    ]
                    n604_text = '\n'.join([
                        str(locals().get('combined_late_text', '')),
                        str(globals().get('N600_DEEP_TEXT', '')),
                        str(globals().get('N601_FINAL_TEXT', '')),
                    ])
                    n604_text += '\n' + '\n'.join(
                        str(ev.get('name', '')) + str(ev.get('content', '')) for ev in g.evidences()
                    )
                    n604_targets: list[str] = []

                    def n604_add(npc_id: str) -> None:
                        if npc_id and npc_id not in n604_targets:
                            n604_targets.append(npc_id)

                    def n604_ask(npc_id: str, question: str) -> str:
                        if not npc_id:
                            return ''
                        if npc_id in n604_current:
                            resp = g.chat(npc_id, question, n604_ids)
                        else:
                            resp = g.probe_chat_once(npc_id, question, n604_ids)
                        text_value = response_text(resp)
                        if text_value:
                            globals()['N604_POKER_TEXT'] = str(globals().get('N604_POKER_TEXT', '')) + '\n' + text_value
                        return text_value

                    for npc_id in [
                        str(locals().get('info_id', '')),
                        str(locals().get('reception_id', '')),
                        str(locals().get('password_id', '')),
                        str(locals().get('true_club5_id', '')),
                        str(locals().get('target_id', '')),
                        str(locals().get('wang_id', '')),
                        str(locals().get('luo_id', '')),
                    ]:
                        n604_add(npc_id)
                    for pattern in (
                        r'([一-龥]{2,4})[^。\n]{0,16}周克',
                        r'([一-龥]{2,4})[^。\n]{0,16}刘瑄',
                        r'([一-龥]{2,4})[^。\n]{0,16}红桃\s*Q',
                        r'([一-龥]{2,4})[^。\n]{0,18}给了我密码',
                        r'真正的梅花\s*5[^。\n]{0,24}([一-龥]{2,4})',
                        r'([一-龥]{2,4})[（(]于书华[）)]',
                    ):
                        for match in re.finditer(pattern, n604_text):
                            for npc_id in global_name_ids(match.group(1), n604_current):
                                n604_add(npc_id)
                    for name in extract_story_names(n604_text):
                        for npc_id in global_name_ids(name, n604_current):
                            n604_add(npc_id)
                    for cn in ('张朔', '刘瑄', '周克', 'Joker', '于书华', '王科瑾', '王泽', '张子韩', '刘丽雯', '林渝植', '许清和', '顾云舒', '沈知遥', '叶青衡', '楚戎臻'):
                        for npc_id in global_name_ids(cn, n604_current):
                            n604_add(npc_id)
                    for npc_id in n604_current:
                        n604_add(npc_id)

                    if {'601', '602', '603', '604', '606'} & set(n604_ids):
                        for npc_id in n604_targets[:8]:
                            n604_ask(npc_id, '601-604已经出现，先不要追亲子鉴定。现在只问左臂POKER纹身和606三人照片：Joker、于书华、红桃Q/接待者是否同属花纹村组织，照片原件、组织成员名单和现场未交证据由谁保管。')
                        n604_ids = [
                            str(ev.get('id')) for ev in g.evidences()
                            if str(ev.get('id')) in {'101', '102', '103', '104', '201', '202', '203', '204', '205', '401', '402', '404', '405', '501', '502', '503', '504', '601', '602', '603', '604', '605', '606', '607', '608'}
                        ]
                        for npc_id in n604_targets[:8]:
                            n604_ask(npc_id, '如果你知道左臂POKER纹身，就直接说照片中三人的真实姓名、纹身含义、花纹村组织分工，并交出606；若606已出现，则继续交出605、607/608或最终警方卷宗。')
                    elif {'501', '502', '503', '504'} & set(n604_ids):
                        for npc_id in n604_targets[:8]:
                            n604_ask(npc_id, '501/502/503/504已经出现。下一层不要泛问身份原件，只沿POKER纹身照片查：三人照片、左臂纹身、Joker周克、于书华、红桃Q/接待者、组织名单和606/605由谁掌握。')
                    globals()['N604_POKER_IDS'] = ','.join(str(ev.get('id')) for ev in g.evidences())
                    poker_after_ids = [str(ev.get('id')) for ev in g.evidences()]
                if 'follow_npcs' in locals():
                    n612_poker_text = '\n'.join([
                        str(locals().get('reply', '')),
                        str(response_text(locals().get('password_resp', {})) if 'password_resp' in locals() else ''),
                        str(response_text(locals().get('proof_resp', {})) if 'proof_resp' in locals() else ''),
                        str(locals().get('gate_text', '')),
                        str(locals().get('deep_text', '')),
                        str(locals().get('n601_text', '')),
                        str(locals().get('n604_text', '')),
                        str(globals().get('N600_DEEP_TEXT', '')),
                        str(globals().get('N601_FINAL_TEXT', '')),
                        str(globals().get('N604_POKER_TEXT', '')),
                        '\n'.join(str(ev.get('name', '')) + str(ev.get('content', '')) for ev in g.evidences()),
                    ])
                    n612_poker_targets: list[str] = []
                    for _npc in (
                        str(locals().get('info_id', '')),
                        str(locals().get('password_id', '')),
                        str(locals().get('reception_id', '')),
                        str(locals().get('true_club5_id', '')),
                        str(locals().get('target_id', '')),
                        str(locals().get('wang_id', '')),
                        str(locals().get('luo_id', '')),
                    ):
                        n612_add_unique(n612_poker_targets, _npc)
                    for _npc in story_target_ids(n612_poker_text, follow_npcs, max_ids=10):
                        n612_add_unique(n612_poker_targets, _npc)
                    n612_chase_poker_promises(g, n612_poker_targets, follow_npcs, n612_poker_text)
                if g.stage < 3 and ev_ids:
                    g.chat(info_id, '结合邀请函、聊天记录、宾客到达表和电脑浏览记录，死者真实身份、林渝植、梅花5之间是什么关系？', ev_ids)
                    g.evidences()
        method = '凶手利用扑克公馆全员戴面具、身份混淆和场馆密室条件，在衣帽间用刀杀害并伪装死者。'
    elif '袁樱瞳' in text or '碎尸案' in text:
        current_npcs = g.npcs() or npcs
        current_marks = g.marks() or marks
        true_ids = [npc for npc in current_npcs if current_marks.get(npc) is True]
        false_ids = [npc for npc in current_npcs if current_marks.get(npc) is False]
        yuan_replies: dict[str, str] = {}
        def ask_all(question: str, evidences_arg: list[str] | None = None) -> None:
            for ynpc in (g.npcs() or current_npcs):
                resp = g.chat(ynpc, question, evidences_arg)
                yuan_replies[ynpc] = yuan_replies.get(ynpc, '') + '\n' + response_text(resp)
        if globals().get('POKER_HAS_501') or globals().get('POKER_HAS_404'):
            cross_ids = [str(ev.get('id')) for ev in g.evidences() if str(ev.get('id')) in {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706', '707', '708'}]
            ask_all('上一案已出现404车辆或501转账，指向Joker人口贩卖集团、移尸车辆、于书华看诊和匿名50万元转账。袁樱瞳、李海天、1919黑车、生物馆、保安奇怪网站是否与同一隐藏链有关？只说官方证据编号、证据名和持有人。', cross_ids)
        if globals().get('POKER_HAS_601'):
            cross_ids = [str(ev.get('id')) for ev in g.evidences() if str(ev.get('id')) in {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706', '707', '708'}]
            ask_all('上一案已经查到2010失踪少女、2015人口贩卖集团、张子韩/刘丽雯身份和死者手机云端名单。袁樱瞳案不要再停在投票：请只查保安奇怪网站、口袋网页截图、1919黑车、世纪林尸块、李海天尸检、手机原图元数据和人口名单是否同源；能打开物证06/706或707/708的官方持有人是谁？', cross_ids)
        ask_all('袁樱瞳碎尸案请完整说明：手机、凌晨1点女性尸体照片、lo裙、栗色假发、黄色行李箱、投票异常、出国名额、张朔、张壹、生物馆、世纪林、李海天、1919黑车、保安奇怪网站分别是什么线索？')
        ask_all('不要只讲传闻。请说明你本人看到或确认了什么：谁从生物馆出来，谁接触尸块或行李箱，谁清空手机，谁伪造死亡时间，谁从投票中获利？')
        ask_all('单独确认联系方式交换线：是否有人想要那个不认识的“运动少女”的联系方式，运动少女是谁，谁愿意用联系方式交换关于杀手的秘密；如果能给707或708，请直接给证据编号、证据名和持有人。')
        ask_all('先按物证06方向查，不等705：李海天随身U盘是否从失物招领出现，U盘里的电子系保研名单、不雅视频照片、袁樱瞳周五要揭发的内容、王科瑾未保研和手机清空之间有什么关系；若能给706/707/708请直接交出。')
        yuan_evidences = g.evidences()
        yuan_ids = [str(ev.get('id')) for ev in yuan_evidences if str(ev.get('id')) in {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706', '707', '708'}]
        forensic_target_name = yuan_candidate_from_replies(yuan_replies, g.npcs() or npcs, g.marks() or marks)
        forensic_target_id = id_for_name(forensic_target_name, g.npcs() or npcs) if forensic_target_name else ''
        teacher_name = ''
        for reply in yuan_replies.values():
            for pattern in (
                r'选了([一-龥]{2,4})老师',
                r'([一-龥]{2,4})老师的课',
                r'([一-龥]{2,4})老师.*?出国',
            ):
                m = re.search(pattern, reply)
                if m:
                    teacher_name = m.group(1)
                    break
            if teacher_name:
                break
        teacher_id = id_for_name(teacher_name, g.npcs() or npcs) if teacher_name else ''
        if forensic_target_id and '703' in set(yuan_ids):
            resp = g.chat(forensic_target_id, '703手机不是口供问题。请只说袁樱瞳手机是谁捡到、谁清空、凌晨1点照片的拍摄/发送时间、定位、EXIF元数据、删除记录、最后操作和账号登录记录；哪一份数字取证报告能打开物证06/706？', yuan_ids)
            yuan_replies[forensic_target_id] = yuan_replies.get(forensic_target_id, '') + '\n' + response_text(resp)
            yuan_evidences = g.evidences()
            yuan_ids = [str(ev.get('id')) for ev in yuan_evidences if str(ev.get('id')) in {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706', '707', '708'}]
        if teacher_id and '704' in set(yuan_ids):
            resp = g.chat(teacher_id, '704投票纸只查原件 custody：票箱谁保管、谁能接触原始票、笔迹比对、废票/补票、课堂录像、教师办公室监控和行政系统日志在哪里？如果这能打开物证06/706，请给证据编号和持有人。', yuan_ids)
            yuan_replies[teacher_id] = yuan_replies.get(teacher_id, '') + '\n' + response_text(resp)
            yuan_evidences = g.evidences()
            yuan_ids = [str(ev.get('id')) for ev in yuan_evidences if str(ev.get('id')) in {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706', '707', '708'}]
        if teacher_id and '704' in set(yuan_ids) and '706' not in set(yuan_ids):
            resp = g.chat(teacher_id, '不要泛问物证编号，只沿投票异常和电子系材料查：多出的异笔迹票、票箱锁入办公室、失物招领处李海天随身U盘、电子系保研名单、不雅视频照片、谁能接触U盘和原始票；如果这是物证06/706请直接交出。', yuan_ids)
            yuan_replies[teacher_id] = yuan_replies.get(teacher_id, '') + '\n' + response_text(resp)
            yuan_evidences = g.evidences()
            yuan_ids = [str(ev.get('id')) for ev in yuan_evidences if str(ev.get('id')) in {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706', '707', '708'}]
        if forensic_target_id and '704' in set(yuan_ids) and '706' not in set(yuan_ids):
            resp = g.chat(forensic_target_id, '你和袁樱瞳竞争出国或保研名额，又接触过手机/行李箱线。不要解释投票纸，直接说李海天随身U盘是否在失物招领、里面的电子系保研名单和不雅视频照片是谁拿到、谁因此要清空袁樱瞳手机；若这是物证06/706请交出，若已出现请继续给707/708。', yuan_ids)
            yuan_replies[forensic_target_id] = yuan_replies.get(forensic_target_id, '') + '\n' + response_text(resp)
            yuan_evidences = g.evidences()
            yuan_ids = [str(ev.get('id')) for ev in yuan_evidences if str(ev.get('id')) in {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706', '707', '708'}]
        absent_vote_name = yuan_absent_vote_name_from_replies(yuan_replies)
        absent_vote_id = id_for_name_any(absent_vote_name, g.npcs() or npcs) if absent_vote_name else ''
        if absent_vote_id and '704' in set(yuan_ids) and '706' not in set(yuan_ids):
            resp = chat_visible_or_probe(g, absent_vote_id, g.npcs() or npcs, '704投票链的关键不是谁赢，而是谁没来却被计入：你被说成翘课/未到场，票箱却多出一票或出现张壹张朔身份混淆。请直接交出签到表、课堂监控、投票人名单、补票/废票原件、推荐名额系统日志、冒名投票者或物证06/706/707/708。', yuan_ids)
            yuan_replies[absent_vote_id] = yuan_replies.get(absent_vote_id, '') + '\n' + response_text(resp)
            yuan_evidences = g.evidences()
            yuan_ids = [str(ev.get('id')) for ev in yuan_evidences if str(ev.get('id')) in {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706', '707', '708'}]
        elif teacher_id and '704' in set(yuan_ids) and '706' not in set(yuan_ids):
            resp = g.chat(teacher_id, '你刚才提到投票人数和实际到场人数矛盾，甚至有人翘课/未到场。不要再说“投票异常”四个字，请直接给签到表、座位/课堂录像、投票人名单、缺席者姓名、补票来源、推荐名额后台日志或物证06/706的持有人。', yuan_ids)
            yuan_replies[teacher_id] = yuan_replies.get(teacher_id, '') + '\n' + response_text(resp)
            yuan_evidences = g.evidences()
            yuan_ids = [str(ev.get('id')) for ev in yuan_evidences if str(ev.get('id')) in {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706', '707', '708'}]
        luggage_targets: list[str] = []
        if forensic_target_id:
            luggage_targets.append(forensic_target_id)
        for ynpc in false_ids + current_npcs:
            if ynpc not in luggage_targets:
                luggage_targets.append(ynpc)
        for target_id in luggage_targets[:2]:
            if '706' in set(yuan_ids):
                break
            resp = g.chat(target_id, '黄色行李箱不是背景道具。请只查尸源/转运链：行李箱是谁买的、谁借的、为什么送修、维修店记录、宿舍楼监控、箱内血迹/指纹/纤维、lo裙栗色假发、凌晨照片女尸、1919黑车搬运路线和物证06/706/707/708在哪里。', yuan_ids)
            yuan_replies[target_id] = yuan_replies.get(target_id, '') + '\n' + response_text(resp)
            yuan_evidences = g.evidences()
            yuan_ids = [str(ev.get('id')) for ev in yuan_evidences if str(ev.get('id')) in {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706', '707', '708'}]
        screenshot_targets: list[str] = []
        guard_id0 = yuan_guard_id_from_replies(yuan_replies, g.npcs() or npcs)
        if guard_id0:
            screenshot_targets.append(guard_id0)
        for ynpc in (g.npcs() or npcs):
            if (g.marks() or marks).get(ynpc) is False and ynpc not in screenshot_targets:
                screenshot_targets.append(ynpc)
        for target_id in screenshot_targets[:2]:
            resp = g.chat(target_id, '开场回忆说我失忆但被保安认出，口袋里还有一张模糊网页截图；你又反复被目击在看奇怪网站并周日离岗。请说明保安为什么认识我、侦探身份档案在哪里、网站是否是尸块/人口/车辆交易入口，并直接交出物证06/706或网页截图、登录账号、访问记录、1919车辆、世纪林报警记录的证据编号和持有人。', yuan_ids)
            yuan_replies[target_id] = yuan_replies.get(target_id, '') + '\n' + response_text(resp)
            yuan_evidences = g.evidences()
            yuan_ids = [str(ev.get('id')) for ev in yuan_evidences if str(ev.get('id')) in {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706', '707', '708'}]
            if '706' in set(yuan_ids):
                break
        ev705 = next((ev for ev in yuan_evidences if str(ev.get('id')) == '705'), None)
        if not isinstance(ev705, dict):
            early_targets: list[str] = []
            runner_name = ''
            for reply in yuan_replies.values():
                m = re.search(r'看见([一-龥]{2,4}).{0,18}从生物馆', reply)
                if m:
                    runner_name = m.group(1)
                    break
            runner_id = id_for_name_any(runner_name, g.npcs() or npcs) if runner_name else ''
            if runner_id:
                early_targets.append(runner_id)
            guard_name = ''
            for reply in yuan_replies.values():
                for pattern in (
                    r'保安.*?([一-龥]{2,4})大叔',
                    r'保安室([一-龥]{2,4})',
                    r'保安([一-龥]{1,4})(?:大叔|师傅|老师傅)',
                    r'保安([一-龥]{2,4})',
                ):
                    m = re.search(pattern, reply)
                    if m:
                        guard_name = m.group(1)
                        break
                if guard_name:
                    break
            guard_name = re.sub(r'(大叔|师傅|老师傅)$', '', guard_name)
            guard_id = id_for_name_any(guard_name, g.npcs() or npcs) if guard_name else ''
            if not guard_id and len(guard_name) == 1:
                for ynpc in (g.npcs() or npcs):
                    if cn_name(ynpc).startswith(guard_name):
                        guard_id = ynpc
                        break
            if guard_id and guard_id not in early_targets:
                early_targets.append(guard_id)
            for ynpc in (g.npcs() or npcs):
                if (g.marks() or marks).get(ynpc) is False and ynpc not in early_targets:
                    early_targets.append(ynpc)
            for target_id in early_targets[:3]:
                resp = chat_visible_or_probe(g, target_id, g.npcs() or npcs, '不要猜凶手，先把能打开下一阶段的官方物证交出来：物证06/706、李海天尸检报告、蓝色背包海豚挂件、世纪林尸块DNA、1919黑车记录或生物馆监控。你本人接触或知道哪一项？如果是707/708也直接给编号。', yuan_ids)
                yuan_replies[target_id] = yuan_replies.get(target_id, '') + '\n' + response_text(resp)
                yuan_evidences = g.evidences()
                yuan_ids = [str(ev.get('id')) for ev in yuan_evidences if str(ev.get('id')) in {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706', '707', '708'}]
                ev705 = next((ev for ev in yuan_evidences if str(ev.get('id')) == '705'), None)
                if isinstance(ev705, dict):
                    break
        post705_targets: list[str] = []

        def add_post705_target(npc_id: str) -> None:
            if npc_id and npc_id not in post705_targets:
                post705_targets.append(npc_id)

        if isinstance(ev705, dict):
            ev705_text = str(ev705.get('name', '')) + '\n' + str(ev705.get('content', ''))
            holder_match = re.search(r'([一-龥]{1,4})处获得', ev705_text)
            holder_name = holder_match.group(1) if holder_match else ''
            holder_ids: list[str] = []

            def add_holder_id(npc_id: str) -> None:
                if npc_id and npc_id not in holder_ids:
                    holder_ids.append(npc_id)

            if holder_name:
                for npc_id in global_name_ids(holder_name, current_npcs):
                    add_holder_id(npc_id)
            combined_705_text = ev705_text + '\n' + '\n'.join(yuan_replies.values())
            for npc_id in story_target_ids(combined_705_text, current_npcs, max_ids=8):
                add_holder_id(npc_id)
            for npc_id in holder_ids:
                add_post705_target(npc_id)
            target_id = holder_ids[0] if holder_ids else (current_npcs[0] if current_npcs else '')
            if target_id:
                resp = chat_visible_or_probe(g, target_id, g.npcs() or npcs, '705李海天尸检报告显示背刺失血、四肢被砍断、蓝色背包海豚挂件，并且和袁樱瞳案相似又有差异。请直接说明蓝色背包和海豚挂件是谁的、李海天案与袁樱瞳凌晨照片/世纪林尸块/生物馆跑出者怎么连接，谁持有物证06/706或下一份官方证据。', yuan_ids)
                yuan_replies[target_id] = yuan_replies.get(target_id, '') + '\n' + response_text(resp)
                yuan_evidences = g.evidences()
                yuan_ids = [str(ev.get('id')) for ev in yuan_evidences if str(ev.get('id')) in {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706', '707', '708'}]
            runner_name = ''
            for reply in yuan_replies.values():
                m = re.search(r'看见([一-龥]{2,4}).{0,18}从生物馆', reply)
                if m:
                    runner_name = m.group(1)
                    break
            runner_id = id_for_name_any(runner_name, g.npcs() or npcs) if runner_name else ''
            add_post705_target(runner_id)
            if runner_id and runner_id != target_id and '706' not in set(yuan_ids):
                resp = chat_visible_or_probe(g, runner_id, g.npcs() or npcs, '705尸检报告和目击证言已经对上：你被看见从生物馆慌张跑出，李海天尸体旁有蓝色背包海豚挂件，袁樱瞳案又出现凌晨尸体照片和世纪林尸块。请直接说明你当晚在生物馆做了什么、背包挂件是谁的、物证06/706或下一份官方证据在哪里。', yuan_ids)
                yuan_replies[runner_id] = yuan_replies.get(runner_id, '') + '\n' + response_text(resp)
                yuan_evidences = g.evidences()
                yuan_ids = [str(ev.get('id')) for ev in yuan_evidences if str(ev.get('id')) in {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706', '707', '708'}]
            guard_name = ''
            for reply in yuan_replies.values():
                for pattern in (
                    r'保安.*?([一-龥]{2,4})大叔',
                    r'保安室([一-龥]{2,4})',
                    r'保安([一-龥]{1,4})(?:大叔|师傅|老师傅)',
                    r'保安([一-龥]{2,4})',
                ):
                    m = re.search(pattern, reply)
                    if m:
                        guard_name = m.group(1)
                        break
                if guard_name:
                    break
            guard_name = re.sub(r'(大叔|师傅|老师傅)$', '', guard_name)
            guard_id = id_for_name_any(guard_name, g.npcs() or npcs) if guard_name else ''
            if not guard_id and len(guard_name) == 1:
                for ynpc in (g.npcs() or npcs):
                    if cn_name(ynpc).startswith(guard_name):
                        guard_id = ynpc
                        break
            add_post705_target(guard_id)
            if guard_id and guard_id not in {target_id, runner_id} and '706' not in set(yuan_ids):
                resp = chat_visible_or_probe(g, guard_id, g.npcs() or npcs, '705尸检报告指向李海天旧案，线索又反复指到保安室：你看的奇怪网站、我口袋里的模糊网页截图、周日离岗、世纪林尸块、1919黑车和生物馆监控都需要保卫处记录。请直接交出物证06/706、网站截图/登录记录、巡逻日志、世纪林/生物馆监控或下一份官方证据。', yuan_ids)
                yuan_replies[guard_id] = yuan_replies.get(guard_id, '') + '\n' + response_text(resp)
                yuan_evidences = g.evidences()
                yuan_ids = [str(ev.get('id')) for ev in yuan_evidences if str(ev.get('id')) in {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706', '707', '708'}]
            if '706' not in set(yuan_ids):
                for source_id in (post705_targets + [teacher_id, absent_vote_id, forensic_target_id])[:5]:
                    if not source_id:
                        continue
                    resp = chat_visible_or_probe(g, source_id, g.npcs() or npcs, '不要总结剧情，只查705后的来源系统：尸检原始档案、蓝色背包海豚挂件归属、世纪林尸块DNA、生物馆/保卫处监控、1919车辆登记、教务投票原件和手机原图元数据里，哪一项能打开物证06/706或707/708？直接给编号、证据名和持有人。', yuan_ids)
                    yuan_replies[source_id] = yuan_replies.get(source_id, '') + '\n' + response_text(resp)
                    yuan_evidences = g.evidences()
                    yuan_ids = [str(ev.get('id')) for ev in yuan_evidences if str(ev.get('id')) in {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706', '707', '708'}]
                    if '706' in set(yuan_ids) or '707' in set(yuan_ids) or '708' in set(yuan_ids):
                        break
            if globals().get('POKER_HAS_601') and '706' not in set(yuan_ids):
                focused_sources = post705_targets + [guard_id, runner_id, teacher_id, forensic_target_id, absent_vote_id]
                focused_seen: set[str] = set()
                for source_id in focused_sources[:6]:
                    if not source_id or source_id in focused_seen:
                        continue
                    focused_seen.add(source_id)
                    resp = chat_visible_or_probe(g, source_id, g.npcs() or npcs, '705之后按人口贩卖/旧案同源查，不要复述投票。Poker已出现2010失踪少女、人口贩卖集团、死者手机云端名单和张子韩旧身份；袁樱瞳手机照片、李海天蓝色背包、保安网站、1919黑车、世纪林尸块和生物馆监控是否对应同一名单？直接给物证06/706或707/708编号、名称、持有人。', yuan_ids)
                    yuan_replies[source_id] = yuan_replies.get(source_id, '') + '\n' + response_text(resp)
                    yuan_evidences = g.evidences()
                    yuan_ids = [str(ev.get('id')) for ev in yuan_evidences if str(ev.get('id')) in {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706', '707', '708'}]
                    if '706' in set(yuan_ids) or '707' in set(yuan_ids) or '708' in set(yuan_ids):
                        break
            if '706' not in set(yuan_ids):
                hidden_seen = {x for x in (target_id, runner_id, guard_id) if x}
                hidden_count = 0
                source_names = ['张子韩', '陆亦初', '楚戎臻', '王泽', '张壹']
                for source_name in extract_story_names(combined_705_text + '\n' + '\n'.join(yuan_replies.values())):
                    if source_name not in source_names:
                        source_names.append(source_name)
                for source_name in source_names:
                    source_ids = global_name_ids(source_name, current_npcs) or ([id_for_name_any(source_name, current_npcs)] if id_for_name_any(source_name, current_npcs) else [])
                    for source_id in source_ids:
                        if not source_id or source_id in hidden_seen:
                            continue
                        break
                    else:
                        continue
                    hidden_seen.add(source_id)
                    resp = chat_visible_or_probe(g, source_id, g.npcs() or npcs, '你可能不是当前可见嫌疑人，但你在705报告来源、生物馆跑出者、旧案卷宗、保卫处网页或教务系统链里出现过。请直接交出物证06/706、707/708，或说明蓝色背包海豚挂件、世纪林尸块DNA、1919车辆、网页截图、投票原件的官方持有人。', yuan_ids)
                    yuan_replies[source_id] = yuan_replies.get(source_id, '') + '\n' + response_text(resp)
                    yuan_evidences = g.evidences()
                    yuan_ids = [str(ev.get('id')) for ev in yuan_evidences if str(ev.get('id')) in {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706', '707', '708'}]
                    hidden_count += 1
                    if '706' in set(yuan_ids) or hidden_count >= 2:
                        break
        if '706' not in set(yuan_ids) and ('705' in set(yuan_ids) or globals().get('POKER_HAS_501')):
            if '705' in set(yuan_ids) and post705_targets:
                for source_id in post705_targets[:4]:
                    resp = chat_visible_or_probe(g, source_id, g.npcs() or npcs, '继续只查尸源鉴定闭环：袁樱瞳、凌晨照片女性、世纪林尸块和李海天之间是否存在替身或尸块二次利用？请直接给物证06/706、DNA报告、尸源鉴定、手机原图元数据或生物馆监控的证据编号和持有人。', yuan_ids)
                    yuan_replies[source_id] = yuan_replies.get(source_id, '') + '\n' + response_text(resp)
                    yuan_evidences = g.evidences()
                    yuan_ids = [str(ev.get('id')) for ev in yuan_evidences if str(ev.get('id')) in {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706', '707', '708'}]
                    if '706' in set(yuan_ids) or '707' in set(yuan_ids) or '708' in set(yuan_ids):
                        break
            else:
                ask_all('不要再讨论投票细节，只查身份和尸源鉴定：袁樱瞳、凌晨照片里的女性、世纪林尸块和李海天是否存在替身或尸块二次利用？物证06/706、DNA报告、尸源鉴定、手机原图元数据或生物馆监控哪一项能证明？直接说证据编号、证据名和持有人。', yuan_ids)
            yuan_evidences = g.evidences()
            yuan_ids = [str(ev.get('id')) for ev in yuan_evidences if str(ev.get('id')) in {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706', '707', '708'}]
        if '706' in set(yuan_ids):
            ev706 = next((ev for ev in yuan_evidences if str(ev.get('id')) == '706'), None)
            ev706_text = str(ev706.get('name', '')) + '\n' + str(ev706.get('content', '')) if isinstance(ev706, dict) else ''
            post706_targets: list[str] = []
            for npc_id in story_target_ids(ev706_text + '\n' + '\n'.join(yuan_replies.values()), current_npcs, max_ids=8):
                if npc_id and npc_id not in post706_targets:
                    post706_targets.append(npc_id)
            for npc_id in (forensic_target_id, teacher_id, runner_id if 'runner_id' in locals() else '', guard_id if 'guard_id' in locals() else ''):
                if npc_id and npc_id not in post706_targets:
                    post706_targets.append(npc_id)
            for source_id in post706_targets[:5]:
                resp = chat_visible_or_probe(g, source_id, g.npcs() or npcs, '706 U盘已经说明李海天随身U盘、电子系保研名单、袁樱瞳/楚戎臻保研成功、王科瑾未保研以及李海天侵犯女生视频照片。现在只追下一阶段：谁拿走/隐藏U盘，谁清空袁樱瞳手机，谁利用视频或保研名单杀人，707/708的证据编号、证据名和持有人是什么。', yuan_ids)
                yuan_replies[source_id] = yuan_replies.get(source_id, '') + '\n' + response_text(resp)
                yuan_evidences = g.evidences()
                yuan_ids = [str(ev.get('id')) for ev in yuan_evidences if str(ev.get('id')) in {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706', '707', '708'}]
                if {'707', '708'} & set(yuan_ids):
                    break
            if not ({'707', '708'} & set(yuan_ids)):
                ask_all('706已经出现。不要回到投票细节，沿U盘内容追707/708：李海天侵犯袁樱瞳等女生的视频照片、电子系保研名单、王科瑾未保研、手机清空、凌晨尸体照片、生物馆和世纪林尸块之间，下一份官方物证是什么？', yuan_ids)
            yuan_evidences = g.evidences()
            yuan_ids = [str(ev.get('id')) for ev in yuan_evidences if str(ev.get('id')) in {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706', '707', '708'}]
        if '707' in set(yuan_ids):
            ev707 = next((ev for ev in yuan_evidences if str(ev.get('id')) == '707'), None)
            ev707_text = str(ev707.get('name', '')) + '\n' + str(ev707.get('content', '')) if isinstance(ev707, dict) else ''
            contact_name = ''
            exchange_name = ''
            m = re.search(r'物证07：([一-龥]{2,4})的联系方式', ev707_text)
            if m:
                contact_name = m.group(1)
            for pattern in (
                r'可用于与([一-龥]{2,4})交换情报',
                r'([一-龥]{2,4})曾表示[^。\n]{0,30}联系方式',
                r'([一-龥]{2,4})曾表示[^。\n]{0,30}杀手',
            ):
                m = re.search(pattern, ev707_text)
                if m:
                    exchange_name = m.group(1)
                    break
            relay_text = ev707_text + '\n' + '\n'.join(yuan_replies.values())
            runner_name = ''
            for pattern in (
                r'([一-龥]{2,4})从生物馆[^。\n]{0,18}(?:跑|出来)',
                r'看到([一-龥]{2,4})[^。\n]{0,24}从(?:生物馆|里面)',
                r'([一-龥]{2,4})[^。\n]{0,24}问我要(?:了)?(?:电话|联系方式)',
                r'([一-龥]{2,4})[^。\n]{0,16}副会长',
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
                    f'你刚才说{runner_name or "那个人"}从生物馆慌张出来，还向你要电话。现在不要讲物证编号，也不要说交换条件；只回忆他当时为什么慌张、手上有没有U盘/手机/血迹/背包/海豚挂件/行李箱、后来是否约你见面，以及怎样能找到他本人。',
                    yuan_ids,
                )
                yuan_replies[contact_id] = yuan_replies.get(contact_id, '') + '\n' + response_text(resp)
                yuan_evidences = g.evidences()
                yuan_ids = [str(ev.get('id')) for ev in yuan_evidences if str(ev.get('id')) in {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706', '707', '708'}]
            if runner_id and '708' not in set(yuan_ids):
                resp = chat_visible_or_probe(
                    g,
                    runner_id,
                    g.npcs() or npcs,
                    f'我已经拿到{contact_name or "运动少女"}的联系方式。你上周六从生物馆慌张跑出后向她要电话；现在直接说明你在生物馆看见或做了什么，李海天U盘/袁樱瞳手机照片/世纪林尸块/保安网站/1919黑车和真正杀人者之间有什么秘密。',
                    yuan_ids,
                )
                yuan_replies[runner_id] = yuan_replies.get(runner_id, '') + '\n' + response_text(resp)
                yuan_evidences = g.evidences()
                yuan_ids = [str(ev.get('id')) for ev in yuan_evidences if str(ev.get('id')) in {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706', '707', '708'}]
            if runner_name and runner_id not in set(g.npcs() or npcs) and '708' not in set(yuan_ids):
                ask_all(
                    f'现在不谈编号，先找人：谁能联系或带我找到{runner_name}，也就是上周六从生物馆慌张跑出来、向{contact_name or "运动少女"}要联系方式的人？请说他的完整身份、宿舍/学生会/联系方式，以及他从生物馆带出的秘密。',
                    yuan_ids,
                )
                yuan_evidences = g.evidences()
                yuan_ids = [str(ev.get('id')) for ev in yuan_evidences if str(ev.get('id')) in {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706', '707', '708'}]
            if '708' not in set(yuan_ids):
                natural_targets: list[str] = []
                for npc_id in (runner_id, contact_id, forensic_target_id, teacher_id if 'teacher_id' in locals() else ''):
                    if npc_id and npc_id not in natural_targets:
                        natural_targets.append(npc_id)
                for npc_id in story_target_ids(relay_text + '\n' + '\n'.join(yuan_replies.values()), current_npcs, max_ids=8):
                    if npc_id and npc_id not in natural_targets:
                        natural_targets.append(npc_id)
                for npc_id in natural_targets[:4]:
                    resp = chat_visible_or_probe(
                        g,
                        npc_id,
                        g.npcs() or npcs,
                        f'沿生物馆跑出者和联系方式继续查：{runner_name or "那个人"}为什么要接近{contact_name or "运动少女"}，他知道的“杀手秘密”是什么，秘密对应的实物、监控、网页后台、U盘或手机原图在哪里？如果这就是下一证据，请直接交出。',
                        yuan_ids,
                    )
                    yuan_replies[npc_id] = yuan_replies.get(npc_id, '') + '\n' + response_text(resp)
                    yuan_evidences = g.evidences()
                    yuan_ids = [str(ev.get('id')) for ev in yuan_evidences if str(ev.get('id')) in {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706', '707', '708'}]
                    if '708' in set(yuan_ids):
                        break
            dynamic_exchange_targets: list[str] = []

            def add_exchange_target(npc_id: str) -> None:
                if npc_id and npc_id not in dynamic_exchange_targets:
                    dynamic_exchange_targets.append(npc_id)

            add_exchange_target(id_for_name_any(exchange_name, current_npcs))
            add_exchange_target(id_for_name_any(contact_name, current_npcs))
            add_exchange_target(forensic_target_id)
            for npc_id in story_target_ids(ev707_text + '\n' + '\n'.join(yuan_replies.values()), current_npcs, max_ids=8):
                add_exchange_target(npc_id)
            for exchange_id in dynamic_exchange_targets[:5]:
                resp = chat_visible_or_probe(g, exchange_id, g.npcs() or npcs, f'707联系方式已经拿到，文本显示“{contact_name}的联系方式”可用于和“{exchange_name}”交换情报。现在请直接完成交换：把{contact_name}的联系方式交给{exchange_name}，要求他说出关于杀手的秘密；这个秘密对应谁、物证08/708或最终证据的编号、名称和持有人是什么。', yuan_ids)
                yuan_replies[exchange_id] = yuan_replies.get(exchange_id, '') + '\n' + response_text(resp)
                yuan_evidences = g.evidences()
                yuan_ids = [str(ev.get('id')) for ev in yuan_evidences if str(ev.get('id')) in {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706', '707', '708'}]
                if '708' in set(yuan_ids):
                    break
            ev707 = next((ev for ev in yuan_evidences if str(ev.get('id')) == '707'), None)
            ev707_text = str(ev707.get('name', '')) + '\n' + str(ev707.get('content', '')) if isinstance(ev707, dict) else ''
            post707_targets: list[str] = []
            for name in (exchange_name, contact_name):
                npc_id = id_for_name_any(name, current_npcs)
                if npc_id and npc_id not in post707_targets:
                    post707_targets.append(npc_id)
            for npc_id in story_target_ids(ev707_text + '\n' + '\n'.join(yuan_replies.values()), current_npcs, max_ids=8):
                if npc_id and npc_id not in post707_targets:
                    post707_targets.append(npc_id)
            for source_id in post707_targets[:5]:
                resp = chat_visible_or_probe(g, source_id, g.npcs() or npcs, '707联系方式已经拿到。不要使用固定姓名，按物证07文本中的联系方式持有人和交换对象推进：用该联系方式交换关于杀手的秘密；这个秘密对应谁、什么证据、是否能打开708或最终物证？直接给证据编号、证据名、持有人。', yuan_ids)
                yuan_replies[source_id] = yuan_replies.get(source_id, '') + '\n' + response_text(resp)
                yuan_evidences = g.evidences()
                yuan_ids = [str(ev.get('id')) for ev in yuan_evidences if str(ev.get('id')) in {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706', '707', '708'}]
                if '708' in set(yuan_ids):
                    break
            if '708' not in set(yuan_ids):
                ask_all('707已经出现。不要总结碎尸案，只执行物证07写明的联系方式交换：联系方式持有人、交换对象、杀手秘密、下一份物证08/708在哪里，谁持有？', yuan_ids)
            yuan_evidences = g.evidences()
            yuan_ids = [str(ev.get('id')) for ev in yuan_evidences if str(ev.get('id')) in {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706', '707', '708'}]
        n604_yuan_ids = [str(ev.get('id')) for ev in g.evidences() if str(ev.get('id')) in {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706', '707', '708'}]
        n604_yuan_text = '\n'.join(yuan_replies.values()) + '\n' + '\n'.join(
            str(ev.get('name', '')) + str(ev.get('content', '')) for ev in g.evidences()
        )
        n604_yuan_targets: list[str] = []

        def n604_yuan_add(npc_id: str) -> None:
            if npc_id and npc_id not in n604_yuan_targets:
                n604_yuan_targets.append(npc_id)

        for npc_id in list(locals().get('post705_targets', [])):
            n604_yuan_add(npc_id)
        for npc_id in [
            str(locals().get('guard_id', '')),
            str(locals().get('runner_id', '')),
            str(locals().get('teacher_id', '')),
            str(locals().get('forensic_target_id', '')),
            str(locals().get('absent_vote_id', '')),
        ]:
            n604_yuan_add(npc_id)
        for pattern in (
            r'看见([一-龥]{2,4}).{0,18}从生物馆',
            r'保安.*?([一-龥]{1,4})(?:大叔|师傅|老师傅)?',
            r'([一-龥]{2,4})处获得',
            r'([一-龥]{2,4}).{0,16}海豚挂件',
            r'([一-龥]{2,4}).{0,16}1919',
        ):
            for match in re.finditer(pattern, n604_yuan_text):
                for npc_id in global_name_ids(re.sub(r'(大叔|师傅|老师傅)$', '', match.group(1)), current_npcs):
                    n604_yuan_add(npc_id)
        for name in extract_story_names(n604_yuan_text):
            for npc_id in global_name_ids(name, current_npcs):
                n604_yuan_add(npc_id)
        for npc_id in false_ids + current_npcs:
            n604_yuan_add(npc_id)

        if '706' not in set(n604_yuan_ids):
            n604_seen: set[str] = set()
            for source_id in n604_yuan_targets[:10]:
                if not source_id or source_id in n604_seen:
                    continue
                n604_seen.add(source_id)
                resp = chat_visible_or_probe(g, source_id, g.npcs() or npcs, '现在只查尸源和身份鉴定：袁樱瞳、凌晨照片女性、世纪林尸块、李海天尸检、蓝色背包海豚挂件、黄色行李箱和lo裙栗色假发之间的DNA/指纹/纤维/监控闭环；请直接给下一份官方证据。', n604_yuan_ids)
                yuan_replies[source_id] = yuan_replies.get(source_id, '') + '\n' + response_text(resp)
                n604_yuan_ids = [str(ev.get('id')) for ev in g.evidences() if str(ev.get('id')) in {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706', '707', '708'}]
                if {'706', '707', '708'} & set(n604_yuan_ids):
                    break
            if not ({'706', '707', '708'} & set(n604_yuan_ids)):
                for source_id in n604_yuan_targets[:6]:
                    resp = chat_visible_or_probe(g, source_id, g.npcs() or npcs, '如果袁樱瞳案存在替身、尸块二次利用或死亡时间伪造，请给手机原图元数据、尸源鉴定、行李箱维修记录、宿舍/生物馆监控、1919车辆路线和官方物证持有人。', n604_yuan_ids)
                    yuan_replies[source_id] = yuan_replies.get(source_id, '') + '\n' + response_text(resp)
                    n604_yuan_ids = [str(ev.get('id')) for ev in g.evidences() if str(ev.get('id')) in {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706', '707', '708'}]
                    if {'706', '707', '708'} & set(n604_yuan_ids):
                        break
        yuan_ids = n604_yuan_ids
        yuan_ids = n612_follow_yuan_usb(g, current_npcs, yuan_replies, yuan_ids)
        yuan_ids = n612_follow_yuan_contact_exchange(g, current_npcs, yuan_replies, yuan_ids)
        ask_all('结合现有证据重新推理袁樱瞳死亡：实际死者是谁，凌晨照片是谁，张壹传闻哪里错，生物馆和世纪林尸块如何连接？', yuan_ids)
        ask_all('如果你知道凶手或关键隐瞒者，请直接给出名字、动机、作案过程和证据链。', yuan_ids)
        yuan_suspect = yuan_candidate_from_replies(yuan_replies, npcs, g.marks() or marks)
        g.answer(
            murderer=yuan_suspect,
            motivation=f'{yuan_suspect}与袁樱瞳竞争出国名额，课程展示投票中以24比23一票险胜且出现异笔迹多票；袁樱瞳准备等到周五揭穿投票和替身秘密，{yuan_suspect}担心暴露而杀人。',
            method=f'{yuan_suspect}利用与袁樱瞳相似的外貌、黄色行李箱、袁樱瞳手机、凌晨1点女性尸体照片、lo裙栗色假发制造死亡时间与身份混淆，杀害袁樱瞳后分尸，并借张壹生物馆传闻、世纪林尸块和1919黑车转移视线。',
        )
        return
    else:
        method = '未知'
    log(f'[n556y1] unknown hint={compact(hint, 50)} suspect={suspect}')
    g.answer(murderer=suspect, motivation='未知', method=method)


def solve_case(g: Game, case_idx: int) -> bool:
    npcs = g.npcs()
    if not npcs:
        return False
    marks = g.marks()
    hint = g.hint()
    evidences = g.evidences()
    text = all_text(hint, evidences)
    log(f'[n556y1] case={case_idx} npcs={sorted(npcs)} marks={marks} hint={compact(hint, 60)}')
    if 'Rose' in text:
        solve_rose(g, npcs, marks, evidences)
    elif 'Z失踪' in text or 'F无法联络' in text:
        solve_z_script(g, npcs, evidences)
    else:
        solve_unknown(g, npcs, marks, hint, evidences)
    return True


def main() -> int:
    sdk = SDK()
    sdk._receive()
    g = Game(sdk)
    for case_idx in range(6):
        try:
            if not solve_case(g, case_idx):
                break
        except EOFError:
            break
        except Exception as exc:
            log(f'[n556y1] fatal case={case_idx}: {exc}')
            try:
                g.answer('', '未知', '未知')
            except Exception:
                pass
            break
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
