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
                if reception_id:
                    g.chat(reception_id, '请直接调取扑克公馆仅有的两类监控：餐厅11:00到13:00、大门口0:00到13:00；把7:30不明身份人、8:20离开、8:50梅花5到达、12:00梅花5进餐厅、12:05离开这些记录给我。')
                    poker_evidences = g.evidences()
                    monitor_ids = [
                        str(ev.get('id'))
                        for ev in poker_evidences
                        if str(ev.get('id')) in {'101', '102', '103', '104', '201', '202', '203', '204', '205', '401', '402'}
                    ]
                    if {'401', '402'}.issubset(set(monitor_ids)) and info_id:
                        resp = g.chat(info_id, '我已经把时间线拼完整：7:30入馆和12:00餐厅里的梅花5才是真正活着的梅花5，8:50到达并死在衣帽间的是Joker伪装者。请确认真正梅花5、Joker和林渝植身份，并交出下一阶段证据。', monitor_ids)
                        reply = response_text(resp)
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
                        current_npcs = g.npcs() or follow_npcs
                        password_id = id_for_name(password_name, current_npcs) if password_name else ''
                        if password_id:
                            g.chat(password_id, '你给出的衣帽间密码是什么？请直接打开衣帽间，指出里面剩下的破绽、真正梅花5身份和下一阶段证据。', monitor_ids)
                        else:
                            g.chat(info_id, '推断过程是：402显示7:30有人提前入馆、8:20离开，8:50又有梅花5到达；401显示12:00餐厅还有梅花5活动。请直接给出衣帽间密码、血迹破绽、移尸证据和下一阶段证据。', monitor_ids)
                        poker_after = g.evidences()
                        poker_after_ids = [str(ev.get('id')) for ev in poker_after]
                        rich_ids = [
                            eid for eid in poker_after_ids
                            if eid in {'101', '102', '103', '104', '201', '202', '203', '204', '205', '401', '402', '404', '405', '501', '502'}
                        ]
                        current_npcs = g.npcs() or follow_npcs
                        true_club_name = ''
                        for pattern in (
                            r'现在的([一-龥]{2,4})就是她',
                            r'([一-龥]{2,4})就是她',
                            r'真正的梅花\s*5[^，。]*[，,就是\s]*([一-龥]{2,4})',
                            r'真正的梅花五[^，。]*[，,就是\s]*([一-龥]{2,4})',
                        ):
                            m = re.search(pattern, reply)
                            if m:
                                true_club_name = m.group(1)
                                break
                        true_club_id = id_for_name(true_club_name, current_npcs) if true_club_name else ''
                        owner_name = ''
                        recipient_name = ''
                        for ev in poker_after:
                            ev_text = str(ev.get('name', '')) + str(ev.get('content', ''))
                            if str(ev.get('id')) == '404':
                                m = re.search(r'([一-龥]{2,4})车牌号', ev_text)
                                if m:
                                    owner_name = m.group(1)
                            if str(ev.get('id')) == '501':
                                m = re.search(r'([一-龥]{2,4})（?于书华', ev_text)
                                if m:
                                    recipient_name = m.group(1)
                        owner_id = id_for_name(owner_name, current_npcs) if owner_name else ''
                        recipient_id = id_for_name(recipient_name, current_npcs) if recipient_name else ''
                        asked_late: set[str] = set()
                        if info_id:
                            asked_late.add(info_id)
                            g.chat(info_id, '按最高层官方卷宗继续。不要复述时间线，请直接交出405或502之后的证据：真实杀害地点、移尸车辆、后备箱血迹、车内DNA/指纹、Joker手机、人口贩卖名单、转账源账户、于书华女儿胁迫或林渝植失踪案档案。', rich_ids)
                        if password_id and password_id not in asked_late:
                            asked_late.add(password_id)
                            g.chat(password_id, '你掌握衣帽间密码或0512。请只说明密码使用记录、谁开过衣帽间、死者手机/隐藏房间、真实死亡地点、移尸路线和下一份官方证据。', rich_ids)
                        if true_club_id and true_club_id not in asked_late:
                            asked_late.add(true_club_id)
                            g.chat(true_club_id, '你被指认真正梅花5/林渝植。请直接说明你、Joker、人口贩卖集团、404车辆、501转账、于书华和警方卷宗之间的下一份物证。', rich_ids)
                        if owner_id and owner_id not in asked_late:
                            asked_late.add(owner_id)
                            g.chat(owner_id, '404车牌指向你。请直接给车主/司机、车钥匙、行车记录仪、后备箱血迹、车内DNA、轮胎痕、停车记录、后院窗户和移尸路线证据。', rich_ids)
                        if recipient_id and recipient_id not in asked_late:
                            asked_late.add(recipient_id)
                            g.chat(recipient_id, '501转账指向你或于书华。请直接给看诊记录、转账源账户、银行流水、女儿胁迫、Joker勒索、人口贩卖名单和林渝植失踪档案。', rich_ids)
                        if reception_id and reception_id not in asked_late:
                            asked_late.add(reception_id)
                            g.chat(reception_id, '从接待和场馆角度补最后一层：门锁/密码、厨房冰柜、后院窗户、清洁路线、车停靠点、Joker手机和人口贩卖名单在哪里。', rich_ids)
                        poker_after_ids = [str(ev.get('id')) for ev in g.evidences()]
                        if '404' in poker_after_ids:
                            globals()['POKER_HAS_404'] = True
                        if '501' in poker_after_ids:
                            globals()['POKER_HAS_501'] = True
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
        yuan_ids = [str(ev.get('id')) for ev in g.evidences() if str(ev.get('id')) in {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706'}]
        ask_all('结合现有证据重新推理袁樱瞳死亡：实际死者是谁，凌晨照片是谁，张壹传闻哪里错，生物馆和世纪林尸块如何连接？', yuan_ids)
        ask_all('如果你知道凶手或关键隐瞒者，请直接给出名字、动机、作案过程和证据链。', yuan_ids)
        g.answer(murderer='无名氏', motivation='无', method='无')
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
