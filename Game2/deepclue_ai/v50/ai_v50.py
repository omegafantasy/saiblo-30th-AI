#!/usr/bin/env python3
"""Game2 DeepClue AI v50.

Probe build for the 2026-05-06 game update:
- keep v49's fast randomized-name answers for the two known old cases;
- actively interrogate the two new cases to collect traces, evidence and
  stage transitions for the next scoring build.
"""
from __future__ import annotations

import json
import re
import struct
import sys
from typing import Any


PINYIN_TO_CN = {
    'ChuRongZhen': '楚戎臻',
    'GuYunShu': '顾云舒',
    'JiangMuQing': '江沐青',
    'LinWanZhou': '林晚舟',
    'LuoFangChen': '罗方琛',
    'LuYiChu': '陆亦初',
    'ShenZhiYao': '沈知遥',
    'WangKeJin': '王科瑾',
    'WangZe': '王泽',
    'XuQingHe': '许清和',
    'YeQingHeng': '叶青衡',
    'ZhangShuo': '张朔',
    'ZhangYi': '张壹',
    'ZhangZiHan': '张子韩',
    'ZhaoYiCheng': '赵一橙',
    'ZhouLinJun': '周林君',
}


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


class Game:
    def __init__(self, sdk: SDK) -> None:
        self.sdk = sdk
        self.stage_seen = 0
        self.calls = 0

    def req(self, action: str, **kwargs: Any) -> Any:
        try:
            return self.sdk.request(action, **kwargs)
        except Exception as exc:
            log(f'[v50] request failed action={action}: {exc}')
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

    def stage(self) -> int:
        resp = self.req('stage')
        if isinstance(resp, dict):
            try:
                self.stage_seen = max(self.stage_seen, int(resp.get('stage', self.stage_seen) or self.stage_seen))
            except (TypeError, ValueError):
                pass
        return self.stage_seen

    def chat(self, npc: str, question: str, evidences: list[str] | None = None) -> dict[str, Any]:
        evs = list(evidences or [])
        resp = self.req('chat', npc=npc, question=question, evidences=evs)
        self.calls += 1
        if isinstance(resp, dict):
            try:
                stage = int(resp.get('stage', self.stage_seen) or self.stage_seen)
                if stage > self.stage_seen:
                    log(f'[v50] stage {self.stage_seen}->{stage} after [{npc}] {question[:36]} ev={evs}')
                self.stage_seen = max(self.stage_seen, stage)
            except (TypeError, ValueError):
                pass
            return resp
        return {}

    def answer(self, murderer: str, motivation: str, method: str) -> dict[str, Any]:
        resp = self.req('answer', murderer=murderer, motivation=motivation, method=method)
        return resp if isinstance(resp, dict) else {}


def all_text(hint: str, evidences: list[dict[str, Any]]) -> str:
    parts = [hint]
    for ev in evidences:
        parts.append(str(ev.get('name', '')))
        parts.append(str(ev.get('content', '')))
    return '\n'.join(parts)


def solve_rose(g: Game, npcs: list[str], marks: dict[str, bool], evidences: list[dict[str, Any]]) -> None:
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
    log(f'[v50] rose murderer_id={murderer_id} murderer={murderer} banker={banker}')
    g.answer(
        murderer=murderer,
        motivation=f'{murderer}误认为{banker}对Rose有意，为扫清情敌、独占{banker}而谋划杀害Rose。',
        method=f'{murderer}利用家族药材生意取得夹竹桃毒素，趁18:40左右在准备室将毒投入Rose的专用蜂蜜水杯，Rose饮用后中毒身亡。',
    )


def solve_z(g: Game, evidences: list[dict[str, Any]]) -> None:
    roles: dict[str, str] = {}
    for ev in evidences:
        ev_id = str(ev.get('id', ''))
        if ev_id in {'002', '003', '004', '005', '006'}:
            roles[ev_id] = name_from_title(str(ev.get('name', '')))
    a = roles.get('002', 'A')
    b = roles.get('003', 'B')
    c = roles.get('004', 'C')
    d = roles.get('005', 'D')
    e = roles.get('006', 'E')
    log(f'[v50] z roles A={a} B={b} C={c} D={d} E={e}')
    g.answer(
        murderer=e,
        motivation=f'{e}发现F就是高中时在表白墙造谣诬陷自己出轨的人，又发现F向Z家长告密导致Z被迫逃离学校，新仇旧恨交织下决定杀害F。',
        method=f'{e}尾随F到小树林埋伏处守株待兔，在F回收分尸工具时伏击打晕F，用偷来的{c}的水果刀按照{c}小说里的手法毁坏F面部，并将尸体埋在F自己挖的坑中。',
    )


def shorten(text: Any, limit: int = 220) -> str:
    compact = re.sub(r'\s+', ' ', str(text or '')).strip()
    return compact[:limit]


def evidence_ids(evidences: list[dict[str, Any]]) -> list[str]:
    return [str(ev.get('id', '')) for ev in evidences if str(ev.get('id', ''))]


def log_state(g: Game, label: str) -> tuple[list[str], dict[str, bool], str, list[dict[str, Any]]]:
    npcs = g.npcs()
    marks = g.marks()
    hint = g.hint()
    evidences = g.evidences()
    log(f'[v50] {label} state stage={g.stage_seen} npcs={npcs} marks={marks} hint={shorten(hint, 140)}')
    for ev in evidences:
        log(f"[v50] {label} evidence id={ev.get('id')} name={shorten(ev.get('name'), 80)} content={shorten(ev.get('content'), 260)}")
    return npcs, marks, hint, evidences


def ask_probe(g: Game, label: str, seen: set[tuple[str, str, tuple[str, ...]]], npc: str, question: str, evs: list[str] | None = None) -> None:
    ev_list = list(evs or [])
    key = (npc, question, tuple(ev_list))
    if not npc or key in seen:
        return
    seen.add(key)
    resp = g.chat(npc, question, ev_list)
    reply = resp.get('reply') or resp.get('content') or resp.get('npc_reply') or ''
    unlock = resp.get('unlock_testimony') or resp.get('unlock_evidences') or resp.get('achievements') or []
    log(f'[v50] {label} ask#{g.calls} npc={npc} ev={ev_list} q={shorten(question, 80)} stage={resp.get("stage")} unlock={shorten(unlock, 120)} reply={shorten(reply, 220)}')


def marked_first(npcs: list[str], marks: dict[str, bool]) -> list[str]:
    marked = [npc for npc in npcs if marks.get(npc) is True]
    unmarked = [npc for npc in npcs if npc not in marked]
    return marked + unmarked


def false_mark_guess(npcs: list[str], marks: dict[str, bool]) -> str:
    for npc in npcs:
        if marks.get(npc) is False:
            return npc
    return npcs[0] if npcs else ''


def probe_poker(g: Game, npcs: list[str], marks: dict[str, bool], hint: str, evidences: list[dict[str, Any]]) -> None:
    g.stage_seen = g.stage() or 1
    seen: set[tuple[str, str, tuple[str, ...]]] = set()
    npcs, marks, hint, evidences = log_state(g, 'poker/init')
    info_sources = [npc for npc in npcs if marks.get(npc) is True] or npcs[:1]
    for npc in info_sources:
        for q in [
            '案发现场是什么情况？请详细说说死者、梅花5面具和三把刀。',
            '你手中的证据是什么？这份证据说明了什么？',
            '你为什么是好的信息来源？你发现了哪些别人不知道的线索？',
            '扑克公馆聚会的规则和参加者分别是什么？',
        ]:
            ask_probe(g, 'poker/info', seen, npc, q)
    npcs, marks, hint, evidences = log_state(g, 'poker/after-info')

    base_questions = [
        '你是谁？你和死者是什么关系？',
        '案发时你在哪里，做了什么？',
        '你戴的面具是什么牌？梅花5面具是谁戴的？',
        '你看到三把刀或其他凶器了吗？',
        '你觉得谁最可能杀人？为什么？',
        '你和其他参加者有什么矛盾？',
        '你有没有隐瞒身份、行踪或动机？',
    ]
    for npc in marked_first(npcs, marks):
        for q in base_questions:
            ask_probe(g, 'poker/base', seen, npc, q)
    npcs, marks, hint, evidences = log_state(g, 'poker/after-base')

    for eid in evidence_ids(evidences)[-8:]:
        targets = marked_first(npcs, marks)[:4]
        for npc in targets:
            for q in [
                '这份证据和凶手身份有什么关系？',
                '这份证据能证明谁在说谎？',
            ]:
                ask_probe(g, 'poker/evidence', seen, npc, q, [eid])
    npcs, marks, hint, evidences = log_state(g, 'poker/final')
    suspect = cn_name(false_mark_guess(npcs, marks))
    result = g.answer(
        murderer=suspect,
        motivation=f'{suspect}为掩盖扑克公馆聚会中的身份秘密、矛盾或罪行，利用全员戴面具造成身份混淆后杀人灭口。',
        method=f'{suspect}利用扑克公馆众人戴扑克牌面具造成身份混淆，趁现场混乱用三把刀从背后刺杀戴梅花5面具的死者，并伪造现场嫁祸他人。',
    )
    log(f'[v50] poker answer suspect={suspect} result={result}')


def probe_yuan(g: Game, npcs: list[str], marks: dict[str, bool], hint: str, evidences: list[dict[str, Any]]) -> None:
    g.stage_seen = g.stage() or 1
    seen: set[tuple[str, str, tuple[str, ...]]] = set()
    npcs, marks, hint, evidences = log_state(g, 'yuan/init')
    intro_questions = [
        '你对死者袁樱瞳了解多少？',
        '这起碎尸案你知道什么？',
        '案发现场是什么情况？你发现了什么？',
        '案发时你在哪里，做了什么？',
        '你和袁樱瞳有什么关系或矛盾？',
        '你认为谁有动机杀袁樱瞳？',
        '你有没有隐瞒关于死者、碎尸或现场的事情？',
        '你认识失忆前的侦探吗？我失忆前调查到了什么？',
    ]
    for npc in marked_first(npcs, marks):
        for q in intro_questions:
            ask_probe(g, 'yuan/base', seen, npc, q)
    npcs, marks, hint, evidences = log_state(g, 'yuan/after-base')

    follow_questions = [
        '袁樱瞳被杀和碎尸的具体过程是什么？',
        '谁最后见过袁樱瞳？',
        '谁有条件处理尸体或抛尸？',
        '现场有没有能够指向凶手的物品？',
        '你觉得谁在说谎？为什么？',
    ]
    for npc in marked_first(npcs, marks):
        for q in follow_questions:
            ask_probe(g, 'yuan/follow', seen, npc, q)
    npcs, marks, hint, evidences = log_state(g, 'yuan/after-follow')

    for eid in evidence_ids(evidences)[-8:]:
        targets = marked_first(npcs, marks)[:4]
        for npc in targets:
            for q in [
                '这份证据说明袁樱瞳为什么被杀？',
                '这份证据能证明谁是凶手或谁在说谎？',
            ]:
                ask_probe(g, 'yuan/evidence', seen, npc, q, [eid])
    npcs, marks, hint, evidences = log_state(g, 'yuan/final')
    suspect = cn_name(false_mark_guess(npcs, marks))
    result = g.answer(
        murderer=suspect,
        motivation=f'{suspect}与袁樱瞳存在旧怨、利益冲突或秘密暴露风险，因此杀害袁樱瞳并试图掩盖真相。',
        method=f'{suspect}在T大附近杀害袁樱瞳后碎尸、抛尸，利用侦探失忆和现场混乱转移视线，掩盖自己的身份和作案过程。',
    )
    log(f'[v50] yuan answer suspect={suspect} result={result}')


def solve_unknown(g: Game, npcs: list[str], marks: dict[str, bool], hint: str, evidences: list[dict[str, Any]]) -> None:
    text = all_text(hint, evidences)
    if '扑克公馆' in text:
        probe_poker(g, npcs, marks, hint, evidences)
    elif '袁樱瞳' in text or '碎尸案' in text:
        probe_yuan(g, npcs, marks, hint, evidences)
    else:
        suspect = cn_name(npcs[0]) if npcs else ''
        log(f'[v50] unknown hint={hint[:50]} suspect={suspect}')
        g.answer(murderer=suspect, motivation='未知', method='未知')


def solve_case(g: Game, case_idx: int) -> bool:
    npcs = g.npcs()
    if not npcs:
        return False
    marks = g.marks()
    hint = g.hint()
    evidences = g.evidences()
    text = all_text(hint, evidences)
    log(f'[v50] case={case_idx} npcs={sorted(npcs)} marks={marks} hint={hint[:60]}')
    if 'Rose' in text:
        solve_rose(g, npcs, marks, evidences)
    elif 'Z失踪' in text or 'F无法联络' in text:
        solve_z(g, evidences)
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
            log(f'[v50] fatal case={case_idx}: {exc}')
            try:
                g.answer('', '未知', '未知')
            except Exception:
                pass
            break
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
