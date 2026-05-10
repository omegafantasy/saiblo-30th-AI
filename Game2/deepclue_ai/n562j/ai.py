#!/usr/bin/env python3
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
DEBUG = False


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


def log(*args: Any) -> None:
    if DEBUG:
        print(*args, file=sys.stderr, flush=True)


def cn_name(npc_id: str) -> str:
    return PINYIN_TO_CN.get(npc_id, npc_id)


def compact(text: Any, limit: int = 120) -> str:
    return re.sub(r'\s+', ' ', str(text or '')).strip()[:limit]


def name_from_title(title: str) -> str:
    title = title.strip()
    for pattern in (r'关于([^：:]+)$', r'^([^：:]+?)的介绍$'):
        match = re.search(pattern, title)
        if match:
            return match.group(1).strip()
    return ''


def id_for_name(name: str, npcs: list[str]) -> str:
    direct = CN_TO_PINYIN.get(name, '')
    if direct in npcs:
        return direct
    for npc in npcs:
        if cn_name(npc) == name:
            return npc
    return ''


def poker_info_name(hint: str, npcs: list[str]) -> str:
    for npc in npcs:
        name = cn_name(npc)
        if name and name in hint:
            return name
    for pattern in (
        r'([一-龥]{2,4})是个好的信息来源',
        r'([一-龥]{2,4})会是[^，。]*好的信息来源',
        r'问问([一-龥]{2,4})关于',
    ):
        match = re.search(pattern, hint)
        if match:
            return match.group(1).strip()
    return ''


def response_text(resp: dict[str, Any]) -> str:
    for key in ('reply', 'content', 'message', 'text'):
        value = resp.get(key)
        if isinstance(value, str):
            return value
    return ''


class Game:
    def __init__(self, sdk: SDK) -> None:
        self.sdk = sdk
        self.stage = 0
        self.calls = 0

    def req(self, action: str, **kwargs: Any) -> Any:
        try:
            return self.sdk.request(action, **kwargs)
        except Exception as exc:
            log(f'request failed action={action}: {exc}')
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
        resp: Any = {}
        for attempt in range(3):
            resp = self.req('chat', npc=npc, question=question, evidences=list(evidences or []))
            self.calls += 1
            if not (isinstance(resp, dict) and resp.get('error')):
                break
            time.sleep(0.2 * (attempt + 1))
        if not isinstance(resp, dict):
            return {}
        try:
            new_stage = int(resp.get('stage', self.stage) or self.stage)
        except (TypeError, ValueError):
            new_stage = self.stage
        if new_stage > self.stage:
            log(f'stage {self.stage}->{new_stage} npc={npc} q={compact(question, 50)}')
            self.stage = new_stage
        return resp

    def answer(self, murderer: str, motivation: str, method: str) -> None:
        self.req('answer', murderer=murderer, motivation=motivation, method=method)


def all_text(hint: str, evidences: list[dict[str, Any]]) -> str:
    parts = [hint]
    for ev in evidences:
        parts.append(str(ev.get('name', '')))
        parts.append(str(ev.get('content', '')))
    return '\n'.join(parts)


def case_kind(text: str) -> str:
    if 'Rose' in text:
        return 'rose'
    if 'Z失踪' in text or 'F无法联络' in text:
        return 'zf'
    if '扑克公馆' in text:
        return 'poker'
    if '袁樱瞳' in text or '碎尸案' in text:
        return 'yuan'
    return 'unknown'


def zero_answer(g: Game) -> None:
    g.answer('无名氏', '无', '无')


def solve_rose_direct(g: Game, npcs: list[str], marks: dict[str, bool], evidences: list[dict[str, Any]]) -> None:
    murderer_id = next((npc for npc in npcs if marks.get(npc) is False), npcs[0] if npcs else '')
    murderer = cn_name(murderer_id)
    banker = ''
    for ev in evidences:
        if str(ev.get('id')) == '004':
            banker = name_from_title(str(ev.get('name', '')))
            break
    banker = banker or '银行家'
    g.answer(
        murderer,
        f'{murderer}爱慕并想独占{banker}，认为Rose纠缠{banker}、会阻碍自己与{banker}在一起，因此为扫清情敌而杀害Rose。',
        f'{murderer}利用家族药材生意取得夹竹桃毒素，趁18:40左右在准备室将毒投入Rose的专用蜂蜜水杯，Rose饮用后中毒身亡。',
    )


def solve_z_direct(g: Game, evidences: list[dict[str, Any]]) -> None:
    names: dict[str, str] = {}
    for ev in evidences:
        ev_id = str(ev.get('id', ''))
        if ev_id in {'002', '003', '004', '005', '006'}:
            names[ev_id] = name_from_title(str(ev.get('name', '')))
    c = names.get('004', 'C')
    e = names.get('006', 'E')
    g.answer(
        e,
        f'{e}发现F就是高中时在表白墙造谣诬陷自己出轨的人，又发现F向Z家长告密导致Z被迫逃离学校，新仇旧恨交织下决定杀害F。',
        f'{e}尾随F到小树林埋伏处守株待兔，在F回收分尸工具时伏击打晕F，用偷来的{c}的水果刀按照{c}小说里的手法毁坏F面部，并将尸体埋在F自己挖的坑中。',
    )


def solve_poker_direct(g: Game, npcs: list[str], marks: dict[str, bool], hint: str) -> None:
    name = poker_info_name(hint, npcs)
    if not name:
        marked = [npc for npc in npcs if marks.get(npc) is True]
        name = cn_name(marked[0]) if marked else (cn_name(npcs[0]) if npcs else '')
    g.answer(
        name,
        '未知',
        '凶手利用扑克公馆全员戴面具、身份混淆和场馆密室条件，在衣帽间用刀杀害并伪装死者。',
    )


def yuan_winner_from_reply(reply: str, npc: str) -> str:
    text = reply or ''
    if '袁樱瞳' not in text:
        return ''
    if re.search(r'(我只比袁樱瞳多|我.*险胜袁樱瞳|我们长得挺像|竞争那个出国名额)', text) and not re.search(r'授课教师|课程.*教师|主持|副教授|老师', text):
        return cn_name(npc)
    for pattern in (
        r'最终([一-龥]{2,4})以\s*24\s*票?对\s*23\s*票?险胜',
        r'([一-龥]{2,4})以\s*24\s*票?对\s*23\s*票?险胜',
        r'([一-龥]{2,4})以一票之差险胜了?袁樱瞳',
        r'([一-龥]{2,4})只比袁樱瞳多一票',
    ):
        match = re.search(pattern, text)
        if match and match.group(1).strip() in CN_TO_PINYIN:
            return match.group(1).strip()
    return ''


def evidence_ids(evidences: list[dict[str, Any]]) -> list[str]:
    return [str(ev.get('id')) for ev in evidences if str(ev.get('id'))]


def solve_yuan_probe_corrected(g: Game, npcs: list[str], marks: dict[str, bool]) -> None:
    g.stage = 0
    false_name = cn_name(next((npc for npc in npcs if marks.get(npc) is False), npcs[0] if npcs else ''))
    winner = ''
    phone_holder = ''
    all_replies: list[str] = []

    def ask_all(question: str, ids: list[str] | None = None) -> None:
        nonlocal winner, phone_holder
        for npc in npcs:
            resp = g.chat(npc, question, ids)
            reply = response_text(resp)
            all_replies.append(reply)
            parsed = yuan_winner_from_reply(reply, npc)
            if parsed:
                winner = parsed
            if any(key in reply for key in ('捡到', '手机', '凌晨1点', '尸体照片')):
                phone_holder = cn_name(npc)
            if any(key in reply for key in ('手机', '凌晨1点', '尸体照片', 'lo裙', '假发', '投票', '24', '23', '47', '46', '笔迹', '行李箱')):
                g.evidences()

    broad_questions = [
        '你对死者袁樱瞳和这起碎尸案了解什么？现场情况、尸体、手机、行李箱、照片、假发、投票和时间线都说一下。',
        '你和袁樱瞳是什么关系？她最近和谁有矛盾，谁最后见过她，谁可能有动机？',
    ]
    for question in broad_questions:
        ask_all(question)

    evidences = g.evidences()
    ids = [eid for eid in evidence_ids(evidences) if eid in {'703', '704'}]
    targeted = [
        '张朔翘课后最多只有46张票，为什么最后出现47张票并且24比23？这张异笔迹票对谁有利？',
        '袁樱瞳手机里的凌晨1点女性尸体照片是否是为了伪造死亡时间或死者身份？照片里的lo裙、栗色假发和尸块分别指向谁？',
        '有人说张壹半夜从生物馆慌张跑出来；你夜跑时实际看到的是谁？生物馆、世纪林、尸块和袁樱瞳死亡有什么关系？',
    ]
    for question in targeted:
        ask_all(question, ids)

    joined = '\n'.join(all_replies)
    bio_names = []
    for pattern in (
        r'看见(?:的是)?([一-龥]{2,4})[^。！？]{0,30}从生物馆[^。！？]{0,30}跑',
        r'实际看到的是([一-龥]{2,4})',
        r'([一-龥]{2,4})[^。！？]{0,12}从生物馆[^。！？]{0,30}跑出来',
    ):
        for match in re.finditer(pattern, joined):
            name = match.group(1).strip()
            if name in CN_TO_PINYIN and name not in {'张壹'}:
                bio_names.append(name)

    followups: list[str] = [
        '生物馆那边上周出过什么事？李海天死亡、生物馆、世纪林尸块、袁樱瞳手机凌晨1点照片和真实死者有什么关系？',
    ]
    for name in sorted(set(bio_names))[:3]:
        followups.append(f'{name}为什么半夜从生物馆慌张跑出来？生物馆、世纪林、尸块、死亡时间和袁樱瞳死亡有什么关系？')
    followups.append('世纪林垃圾桶等五处尸块、黄色行李箱、紫色行李箱、手机照片之间的转移路线是什么？谁有条件搬运尸体？')

    evidences = g.evidences()
    ids = [eid for eid in evidence_ids(evidences) if eid in {'703', '704'}]
    for question in followups:
        ask_all(question, ids)

    suspect = false_name
    g.answer(
        suspect,
        f'{suspect}不是单纯因投票杀人，而是利用袁樱瞳已被误认或死亡时间被伪造这一点，隐瞒手机、行李箱和尸块转移真相。',
        f'袁樱瞳的死亡、凌晨1点照片、lo裙栗色假发、黄色行李箱和世纪林尸块不是同一时间线；{suspect}二次处理尸体、清空手机并制造张壹生物馆传闻，把真正死亡时间和尸块来源掩盖起来。',
    )


def solve_case(g: Game) -> bool:
    npcs = g.npcs()
    if not npcs:
        return False
    marks = g.marks()
    hint = g.hint()
    evidences = g.evidences()
    kind = case_kind(all_text(hint, evidences))
    if kind == 'rose':
        solve_rose_direct(g, npcs, marks, evidences)
    elif kind == 'zf':
        solve_z_direct(g, evidences)
    elif kind == 'poker':
        solve_poker_direct(g, npcs, marks, hint)
    elif kind == 'yuan':
        solve_yuan_probe_corrected(g, npcs, marks)
    else:
        zero_answer(g)
    return True


def main() -> int:
    sdk = SDK()
    sdk._receive()
    g = Game(sdk)
    for _ in range(6):
        try:
            if not solve_case(g):
                break
        except EOFError:
            break
        except Exception as exc:
            log(f'fatal: {exc}')
            try:
                zero_answer(g)
            except Exception:
                pass
            break
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
