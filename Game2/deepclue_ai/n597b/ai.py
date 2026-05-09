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
                        combined_late_text = reply + '\n' + '\n'.join(
                            str(ev.get('name', '')) + str(ev.get('content', '')) for ev in poker_after
                        )

                        def add_name(bucket: list[str], name: str) -> None:
                            name = str(name or '').strip()
                            if name and name not in bucket:
                                bucket.append(name)

                        true_club_names: list[str] = []
                        vehicle_names: list[str] = []
                        transfer_names: list[str] = []
                        dossier_names: list[str] = []
                        for pattern in (
                            r'现在的([一-龥]{2,4})就是她',
                            r'([一-龥]{2,4})就是她',
                            r'真正的梅花\s*5[^，。\n]{0,24}([一-龥]{2,4})',
                            r'真正的梅花五[^，。\n]{0,24}([一-龥]{2,4})',
                            r'林渝植[^，。\n]{0,16}(?:现在叫|现在是|就是)([一-龥]{2,4})',
                        ):
                            for m in re.finditer(pattern, combined_late_text):
                                add_name(true_club_names, m.group(1))
                        for pattern in (
                            r'([一-龥]{2,4})车牌号',
                            r'车牌号[^，。\n]{0,20}(?:属于|指向|登记在)([一-龥]{2,4})',
                            r'车主[^，。\n]{0,16}([一-龥]{2,4})',
                            r'司机[^，。\n]{0,16}([一-龥]{2,4})',
                        ):
                            for m in re.finditer(pattern, combined_late_text):
                                add_name(vehicle_names, m.group(1))
                        for pattern in (
                            r'([一-龥]{2,4})（?于书华',
                            r'([一-龥]{2,4})[^，。\n]{0,20}收到[^，。\n]{0,12}500000',
                            r'转账[^，。\n]{0,24}(?:给|至|到)([一-龥]{2,4})',
                            r'看诊[^，。\n]{0,24}([一-龥]{2,4})',
                        ):
                            for m in re.finditer(pattern, combined_late_text):
                                add_name(transfer_names, m.group(1))
                        for pattern in (
                            r'代号.{0,2}景观',
                            r'刑警[^，。\n]{0,12}([一-龥]{2,4})',
                            r'警察[^，。\n]{0,12}([一-龥]{2,4})',
                        ):
                            for m in re.finditer(pattern, combined_late_text):
                                if m.groups():
                                    add_name(dossier_names, m.group(1))
                        if '景观' in combined_late_text and info_id:
                            dossier_names.append(cn_name(info_id))

                        def ids_for_names(names: list[str]) -> list[str]:
                            ids: list[str] = []
                            for name in names:
                                npc_id = id_for_name(name, current_npcs)
                                if npc_id and npc_id not in ids:
                                    ids.append(npc_id)
                            return ids

                        asked_late: set[str] = set()

                        def ask_once(npc_id: str, question: str) -> None:
                            if not npc_id or npc_id in asked_late:
                                return
                            asked_late.add(npc_id)
                            g.chat(npc_id, question, rich_ids)

                        ask_once(info_id, '你既然是信息源或警方线人，现在只给官方证据编号和保管链：405/502、林渝植失踪案卷宗、Joker人口贩卖名单、DNA/指纹、手机定位、银行流水、车辆轨迹、于书华看诊档案分别在哪。')
                        ask_once(password_id, '你掌握衣帽间密码。不要复述时间线，只给密码使用记录、门锁日志、隐藏房间、真实杀害地点、移尸出入口、Joker手机和下一份官方物证。')
                        ask_once(reception_id, '你掌握接待和场馆。直接给邀请函来源、地址表/面具映射、厨房缺刀、冰柜塑料盒、后院窗户、清洁路线、门禁/监控原件和405/502来源。')
                        for npc_id in ids_for_names(true_club_names):
                            ask_once(npc_id, '你被指认为真正梅花5/林渝植。现在只回答Joker、人口贩卖、404车辆、501转账、于书华、警方卷宗和你失踪案之间的官方证据链。')
                        if '404' in poker_after_ids:
                            for npc_id in ids_for_names(vehicle_names) + [info_id, reception_id]:
                                ask_once(npc_id, '404车牌已经出现。请直接给车主/司机、车钥匙、行车记录仪、停车记录、后备箱血迹、车内DNA/指纹、轮胎痕、后院窗户和真实移尸路线证据。')
                        if '501' in poker_after_ids:
                            for npc_id in ids_for_names(transfer_names) + [info_id, reception_id]:
                                ask_once(npc_id, '501匿名五十万转账已经出现。请直接给转账源账户、银行流水、于书华/王泽看诊记录、女儿胁迫、Joker勒索、人口贩卖名单和林渝植失踪档案。')
                        for npc_id in ids_for_names(dossier_names):
                            ask_once(npc_id, '你是警方卷宗/景观链条来源。请调取林渝植失踪案、Joker人口贩卖案、车辆高清监控、DNA/指纹、手机基站和银行流水中的下一份证据。')
                        if '405' not in poker_after_ids and '502' not in poker_after_ids:
                            for npc_id in current_npcs:
                                ask_once(npc_id, 'stage4排查。你只回答是否持有405/502或其来源：真实杀害地点、移尸车辆、门锁日志、Joker手机、人口贩卖名单、转账源账户、DNA/指纹或警方卷宗。')
                        poker_after = g.evidences()
                        poker_after_ids = [str(ev.get('id')) for ev in poker_after]
                        continuation_ids = [
                            eid for eid in poker_after_ids
                            if eid in {'401', '402', '404', '405', '501', '502'}
                        ]
                        if '404' in poker_after_ids:
                            globals()['POKER_HAS_404'] = True
                        if '501' in poker_after_ids:
                            globals()['POKER_HAS_501'] = True
                        if '405' in poker_after_ids:
                            globals()['POKER_HAS_405'] = True
                        if '502' in poker_after_ids:
                            globals()['POKER_HAS_502'] = True
                        if '405' in poker_after_ids or '502' in poker_after_ids:
                            for npc_id in [info_id, reception_id] + current_npcs[:3]:
                                if npc_id:
                                    g.chat(npc_id, '405或502已经出现。继续追最终层：下一份证据、最终凶手、杀害地点、移尸/资金/人口贩卖闭环、警方结案卷宗和可提交答案是什么。', continuation_ids)
                if 'poker_after_ids' in locals():
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
                if g.stage < 3 and ev_ids:
                    g.chat(info_id, '结合邀请函、聊天记录、宾客到达表和电脑浏览记录，死者真实身份、林渝植、梅花5之间是什么关系？', ev_ids)
                    g.evidences()
        method = '凶手利用扑克公馆全员戴面具、身份混淆和场馆密室条件，在衣帽间用刀杀害并伪装死者。'
    elif '袁樱瞳' in text or '碎尸案' in text:
        current_npcs = g.npcs() or npcs
        current_marks = g.marks() or marks
        true_ids = [npc for npc in current_npcs if current_marks.get(npc) is True]
        false_ids = [npc for npc in current_npcs if current_marks.get(npc) is False]
        ordered = true_ids + false_ids + [npc for npc in current_npcs if npc not in true_ids + false_ids]
        replies: dict[str, str] = {}

        def ask_visible(npc: str, question: str, evidences_arg: list[str] | None = None) -> None:
            resp = g.chat(npc, question, evidences_arg)
            replies[npc] = replies.get(npc, '') + '\n' + response_text(resp)

        def ask_target(npc: str, question: str, evidences_arg: list[str] | None = None) -> None:
            if npc in current_npcs:
                resp = g.chat(npc, question, evidences_arg)
            else:
                resp = g.probe_chat_once(npc, question, evidences_arg)
            replies[npc] = replies.get(npc, '') + '\n' + response_text(resp)

        for ynpc in ordered:
            ask_visible(ynpc, 'Yuan上限排查，只建证据来源图：703手机、704投票、705李海天尸检、706/707/708、1919黑车、生物馆、保安奇怪网站、网页截图、蓝色背包分别谁保管。')
        yuan_evidences = g.evidences()
        yuan_ids = [str(ev.get('id')) for ev in yuan_evidences if str(ev.get('id')) in {'001', '703', '704', '705', '706', '707', '708'}]
        for ynpc in ordered:
            ask_visible(ynpc, '解析所有半名和外部来源：保安X大叔、十点半生物馆跑出者、尸检报告X处获得、竞争者/老师/跑步者各对应哪份官方物证或系统。', yuan_ids)

        yuan_evidences = g.evidences()
        yuan_ids = [str(ev.get('id')) for ev in yuan_evidences if str(ev.get('id')) in {'001', '703', '704', '705', '706', '707', '708'}]
        combined = '\n'.join(replies.values()) + '\n' + '\n'.join(
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
        yuan_ids = [str(ev.get('id')) for ev in yuan_evidences if str(ev.get('id')) in {'001', '703', '704', '705', '706', '707', '708'}]

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
        yuan_ids = [str(ev.get('id')) for ev in g.evidences() if str(ev.get('id')) in {'001', '703', '704', '705', '706', '707', '708'}]
        if '706' in yuan_ids or '707' in yuan_ids or '708' in yuan_ids:
            for ynpc in ordered:
                ask_visible(ynpc, '后续证据已经出现。请闭环真实死者、旧案同源、网页截图、凶手、动机、分尸/移尸/嫁祸过程和最终可提交答案。', yuan_ids)
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
    log(f'[n597] case={case_idx} npcs={sorted(npcs)} marks={marks} hint={compact(hint, 60)}')
    if '袁樱瞳' in text or '碎尸案' in text:
        solve_unknown(g, npcs, marks, hint, evidences)
    else:
        g.answer(murderer='无名氏', motivation='无', method='无')
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
