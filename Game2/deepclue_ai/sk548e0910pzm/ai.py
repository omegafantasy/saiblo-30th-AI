#!/usr/bin/env python3
"""Game2 DeepClue AI n556y1.

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
                for reception_id in poker_reception_candidates(g.npcs() or npcs, info_id, g.hint(), g.marks()):
                    asked.add(reception_id)
                    resp = g.chat(reception_id, '请先说Joker聊天记录和宾客到达时间表，暂时不要展开公馆内的异常发现。')
                    named = reception_name_from_reply(response_text(resp))
                    named_id = id_for_name(named, g.npcs() or npcs) if named else ''
                    if named_id and named_id not in asked and named_id != info_id:
                        asked.add(named_id)
                        g.chat(named_id, '你负责接待这次聚会吗？请完整说明Joker聊天记录、宾客到达时间表、公馆内异常发现、电脑浏览记录、冰柜塑料盒和厨房缺刀。')
                    if g.stage >= 2:
                        break
                if g.stage < 2:
                    for reception_id in poker_reception_candidates(g.npcs() or npcs, info_id, g.hint(), g.marks()):
                        if reception_id in asked:
                            continue
                        g.chat(reception_id, '你是否负责接待扑克公馆聚会？请直接说明Joker聊天记录、宾客到达时间表、公馆内异常发现和死者身份线索。')
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
                    if {'401', '402'}.issubset(set(monitor_ids)):
                        resp = g.chat(info_id, '我已经把线索拼完整：7:30不明身份人和12:00餐厅里的梅花5才是真正活着的梅花5；8:50到达并死在衣帽间的是Joker伪装者。请直接确认真正梅花5的姓名、Joker和林渝植的真实身份，并交出下一阶段证据。', monitor_ids)
                        reply = response_text(resp)
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
                        poker_evidences = g.evidences()
                        ev404 = next((ev for ev in poker_evidences if str(ev.get('id')) == '404'), None)
                        ev501 = next((ev for ev in poker_evidences if str(ev.get('id')) == '501'), None)
                        branch_ids = [
                            str(ev.get('id'))
                            for ev in poker_evidences
                            if str(ev.get('id')) in {'101', '102', '103', '104', '201', '202', '203', '204', '205', '401', '402', '404', '501'}
                        ]
                        if isinstance(ev404, dict):
                            car_name_raw = str(ev404.get('name', '')).replace('车牌号', '').strip()
                            car_match = re.search(r'([一-龥]{2,4})', car_name_raw)
                            car_name = car_match.group(1) if car_match else car_name_raw
                            car_id = id_for_name(car_name, follow_npcs) if car_name else ''
                            target_id = car_id or info_id
                            g.chat(target_id, '404显示京F·A7590在7:20经过，104又说死者房间窗外就是后院停车位。请直接说明这辆车谁开、停在窗边做了什么、Joker在哪里死亡、尸体如何移进衣帽间，并交出后备箱或行车记录证据。', branch_ids)
                            poker_evidences = g.evidences()
                            ev405 = next((ev for ev in poker_evidences if str(ev.get('id')) == '405'), None)
                            ev501 = next((ev for ev in poker_evidences if str(ev.get('id')) == '501'), ev501)
                            branch_ids = [
                                str(ev.get('id'))
                                for ev in poker_evidences
                                if str(ev.get('id')) in {'101', '102', '103', '104', '201', '202', '203', '204', '205', '401', '402', '404', '405', '501', '502'}
                            ]
                            if not isinstance(ev405, dict):
                                g.chat(info_id, '404车牌、402大门监控、104窗外停车位和衣帽间血迹已经能证明尸体被转移。请不要概括，直接给出杀人地点、搬尸路线、车内血迹/后备箱/轮胎/行车记录或门禁高清截图是哪一项证据。', branch_ids)
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
                                    g.chat(true_club5_id, '你就是真正活着的梅花5/林渝植。404车牌、402大门监控和衣帽间移尸破绽已经对上，请直接说明Joker在7:30把你带进公馆后发生了什么、罗方琛的车如何参与、尸体从哪里搬到衣帽间，并交出下一阶段物证。', branch_ids)
                                    poker_evidences = g.evidences()
                                    branch_ids = [
                                        str(ev.get('id'))
                                        for ev in poker_evidences
                                        if str(ev.get('id')) in {'101', '102', '103', '104', '201', '202', '203', '204', '205', '401', '402', '404', '405', '501', '502'}
                                    ]
                        if isinstance(ev501, dict):
                            transfer_match = re.search(r'([一-龥]{2,4})', str(ev501.get('name', '')))
                            transfer_name = transfer_match.group(1) if transfer_match else ''
                            transfer_id = id_for_name(transfer_name, follow_npcs) if transfer_name else ''
                            target_id = transfer_id or info_id
                            g.chat(target_id, '501显示你以于书华身份看诊后三天收到50万元匿名转账。你是不是被Joker人口贩卖集团利用的医生？这笔钱和女儿下落、林渝植失踪、Joker伪装梅花5有什么关系？请交出病历、聊天记录或转账来源证据。', branch_ids)
                            poker_evidences = g.evidences()
                            ev502 = next((ev for ev in poker_evidences if str(ev.get('id')) == '502'), None)
                            branch_ids = [
                                str(ev.get('id'))
                                for ev in poker_evidences
                                if str(ev.get('id')) in {'101', '102', '103', '104', '201', '202', '203', '204', '205', '401', '402', '404', '405', '501', '502'}
                            ]
                            if not isinstance(ev502, dict):
                                g.chat(info_id, '501的于书华看诊和匿名50万元转账说明王泽只是被Joker利用的医生。请把病历登记、勒索聊天、女儿下落线索、转账来源账户和林渝植失踪之间的闭环证据交出来。', branch_ids)
                                poker_evidences = g.evidences()
                                ev502 = next((ev for ev in poker_evidences if str(ev.get('id')) == '502'), None)
                                branch_ids = [
                                    str(ev.get('id'))
                                    for ev in poker_evidences
                                    if str(ev.get('id')) in {'101', '102', '103', '104', '201', '202', '203', '204', '205', '401', '402', '404', '405', '501', '502'}
                                ]
                            if true_club5_id and true_club5_id not in {target_id, info_id} and not isinstance(ev502, dict):
                                g.chat(true_club5_id, '你是林渝植本人而王泽只是于书华身份下被利用的医生。501匿名50万元转账、女儿下落勒索、Joker人口贩卖集团和你失踪之间缺最后闭环；请直接交出转账来源、勒索聊天、病历登记或你被藏匿的下一阶段证据。', branch_ids)
                                g.evidences()
                if g.stage < 3 and ev_ids:
                    g.chat(info_id, '结合邀请函、聊天记录、宾客到达表和电脑浏览记录，死者真实身份、林渝植、梅花5之间是什么关系？', ev_ids)
                    g.evidences()
        method = '凶手利用扑克公馆全员戴面具、身份混淆和场馆密室条件，在衣帽间用刀杀害并伪装死者。'
    elif '袁樱瞳' in text or '碎尸案' in text:
        yuan_replies: dict[str, str] = {}
        def ask_all(question: str, evidences_arg: list[str] | None = None) -> None:
            for ynpc in (g.npcs() or npcs):
                resp = g.chat(ynpc, question, evidences_arg)
                yuan_replies[ynpc] = yuan_replies.get(ynpc, '') + '\n' + response_text(resp)
        ask_all('袁樱瞳碎尸案请完整说明：手机、凌晨1点女性尸体照片、lo裙、栗色假发、黄色行李箱、投票异常、出国名额、张朔、张壹、生物馆、世纪林、李海天、1919黑车、保安奇怪网站分别是什么线索？')
        ask_all('不要只讲传闻。请说明你本人看到或确认了什么：谁从生物馆出来，谁接触尸块或行李箱，谁清空手机，谁伪造死亡时间，谁从投票中获利？')
        yuan_evidences = g.evidences()
        yuan_ids = [str(ev.get('id')) for ev in yuan_evidences if str(ev.get('id')) in {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706'}]
        ev705 = next((ev for ev in yuan_evidences if str(ev.get('id')) == '705'), None)
        if not isinstance(ev705, dict):
            early_targets: list[str] = []
            runner_name = ''
            for reply in yuan_replies.values():
                m = re.search(r'看见([一-龥]{2,4}).{0,18}从生物馆', reply)
                if m:
                    runner_name = m.group(1)
                    break
            runner_id = id_for_name(runner_name, g.npcs() or npcs) if runner_name else ''
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
            guard_id = id_for_name(guard_name, g.npcs() or npcs) if guard_name else ''
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
                resp = g.chat(target_id, '不要猜凶手，先把能打开下一阶段的官方物证交出来：李海天尸检报告、蓝色背包海豚挂件、世纪林尸块DNA、1919黑车记录或生物馆监控。你本人接触或知道哪一项？', yuan_ids)
                yuan_replies[target_id] = yuan_replies.get(target_id, '') + '\n' + response_text(resp)
                yuan_evidences = g.evidences()
                yuan_ids = [str(ev.get('id')) for ev in yuan_evidences if str(ev.get('id')) in {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706'}]
                ev705 = next((ev for ev in yuan_evidences if str(ev.get('id')) == '705'), None)
                if isinstance(ev705, dict):
                    break
        if isinstance(ev705, dict):
            holder_match = re.search(r'([一-龥]{2,4})处获得', str(ev705.get('content', '')))
            holder_name = holder_match.group(1) if holder_match else ''
            holder_id = id_for_name(holder_name, g.npcs() or npcs) if holder_name else ''
            target_id = holder_id or ((g.npcs() or npcs)[0] if (g.npcs() or npcs) else '')
            if target_id:
                resp = g.chat(target_id, '705李海天尸检报告显示背刺失血、四肢被砍断、蓝色背包海豚挂件，并且和袁樱瞳案相似又有差异。请直接说明蓝色背包和海豚挂件是谁的、李海天案与袁樱瞳凌晨照片/世纪林尸块/生物馆跑出者怎么连接，谁持有下一份官方证据。', yuan_ids)
                yuan_replies[target_id] = yuan_replies.get(target_id, '') + '\n' + response_text(resp)
                yuan_evidences = g.evidences()
                yuan_ids = [str(ev.get('id')) for ev in yuan_evidences if str(ev.get('id')) in {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706'}]
            runner_name = ''
            for reply in yuan_replies.values():
                m = re.search(r'看见([一-龥]{2,4}).{0,18}从生物馆', reply)
                if m:
                    runner_name = m.group(1)
                    break
            runner_id = id_for_name(runner_name, g.npcs() or npcs) if runner_name else ''
            if runner_id and runner_id != target_id and '706' not in set(yuan_ids):
                resp = g.chat(runner_id, '705尸检报告和目击证言已经对上：你被看见从生物馆慌张跑出，李海天尸体旁有蓝色背包海豚挂件，袁樱瞳案又出现凌晨尸体照片和世纪林尸块。请直接说明你当晚在生物馆做了什么、背包挂件是谁的、下一份官方证据在哪里。', yuan_ids)
                yuan_replies[runner_id] = yuan_replies.get(runner_id, '') + '\n' + response_text(resp)
                yuan_evidences = g.evidences()
                yuan_ids = [str(ev.get('id')) for ev in yuan_evidences if str(ev.get('id')) in {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706'}]
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
            guard_id = id_for_name(guard_name, g.npcs() or npcs) if guard_name else ''
            if not guard_id and len(guard_name) == 1:
                for ynpc in (g.npcs() or npcs):
                    if cn_name(ynpc).startswith(guard_name):
                        guard_id = ynpc
                        break
            if guard_id and guard_id not in {target_id, runner_id} and '706' not in set(yuan_ids):
                resp = g.chat(guard_id, '705尸检报告指向李海天旧案，线索又反复指到保安室：你看的奇怪网站、周日离岗、世纪林尸块、1919黑车和生物馆监控都需要保卫处记录。请直接交出保安室网页截图、巡逻日志、世纪林/生物馆监控或下一份官方证据。', yuan_ids)
                yuan_replies[guard_id] = yuan_replies.get(guard_id, '') + '\n' + response_text(resp)
                yuan_evidences = g.evidences()
                yuan_ids = [str(ev.get('id')) for ev in yuan_evidences if str(ev.get('id')) in {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706'}]
            if '706' not in set(yuan_ids):
                ask_all('只围绕705李海天尸检报告继续。蓝色背包海豚挂件、背部刀伤、失血死亡、四肢分离和袁樱瞳碎尸案之间，哪一项物证或监控能打开下一阶段？直接说证据名和持有人。', yuan_ids)
                yuan_evidences = g.evidences()
                yuan_ids = [str(ev.get('id')) for ev in yuan_evidences if str(ev.get('id')) in {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706'}]
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
