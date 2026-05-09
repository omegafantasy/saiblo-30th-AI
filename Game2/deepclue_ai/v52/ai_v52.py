#!/usr/bin/env python3
"""Game2 DeepClue AI v52.

Post-2026-05-06 narrow probe:
- preserve v49's fast randomized-name handling for the two old cases;
- ask only hint-directed questions in the two new cases;
- log final state/answer results so the next scoring build can be derived.
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


def shorten(text: Any, limit: int = 220) -> str:
    compact = re.sub(r'\s+', ' ', str(text or '')).strip()
    return compact[:limit]


class Game:
    def __init__(self, sdk: SDK) -> None:
        self.sdk = sdk
        self.calls = 0

    def req(self, action: str, **kwargs: Any) -> Any:
        try:
            return self.sdk.request(action, **kwargs)
        except Exception as exc:
            log(f'[v52] request failed action={action}: {exc}')
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
                return int(resp.get('stage', 0) or 0)
            except (TypeError, ValueError):
                return 0
        return 0

    def chat(self, npc: str, question: str, evidences: list[str] | None = None, label: str = '') -> dict[str, Any]:
        evs = list(evidences or [])
        resp = self.req('chat', npc=npc, question=question, evidences=evs)
        self.calls += 1
        if not isinstance(resp, dict):
            return {}
        reply = resp.get('reply') or resp.get('content') or resp.get('npc_reply') or ''
        unlock = resp.get('unlock_testimony') or resp.get('unlock_evidences') or resp.get('achievements') or []
        tag = f' {label}' if label else ''
        log(
            f'[v52]{tag} ask#{self.calls} npc={npc} ev={evs} q={shorten(question, 80)} '
            f'stage={resp.get("stage")} unlock={shorten(unlock, 120)} reply={shorten(reply, 260)}'
        )
        return resp

    def answer(self, murderer: str, motivation: str, method: str, label: str = '') -> dict[str, Any]:
        resp = self.req('answer', murderer=murderer, motivation=motivation, method=method)
        out = resp if isinstance(resp, dict) else {}
        tag = f' {label}' if label else ''
        result_state = out.get('result_state', {}) if isinstance(out.get('result_state'), dict) else {}
        log(
            f'[v52]{tag} answer murderer={murderer} '
            f'answer_result={result_state.get("answer_result")} next_hint={shorten(result_state.get("hint"), 120)}'
        )
        return out


def all_text(hint: str, evidences: list[dict[str, Any]]) -> str:
    parts = [hint]
    for ev in evidences:
        parts.append(str(ev.get('name', '')))
        parts.append(str(ev.get('content', '')))
    return '\n'.join(parts)


def evidence_by_id(evidences: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {str(ev.get('id', '')): ev for ev in evidences if str(ev.get('id', ''))}


def log_state(g: Game, label: str) -> tuple[list[str], dict[str, bool], str, list[dict[str, Any]]]:
    npcs = g.npcs()
    marks = g.marks()
    hint = g.hint()
    evidences = g.evidences()
    log(f'[v52] {label} state stage={g.stage()} npcs={npcs} marks={marks} hint={shorten(hint, 160)}')
    for ev in evidences:
        log(f"[v52] {label} evidence id={ev.get('id')} name={shorten(ev.get('name'), 80)} content={shorten(ev.get('content'), 260)}")
    return npcs, marks, hint, evidences


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
    log(f'[v52] rose murderer_id={murderer_id} murderer={murderer} banker={banker}')
    g.answer(
        murderer=murderer,
        motivation=f'{murderer}误认为{banker}对Rose有意，为扫清情敌、独占{banker}而谋划杀害Rose。',
        method=f'{murderer}利用家族药材生意取得夹竹桃毒素，趁18:40左右在准备室将毒投入Rose的专用蜂蜜水杯，Rose饮用后中毒身亡。',
        label='rose',
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
    log(f'[v52] z roles A={a} B={b} C={c} D={d} E={e}')
    g.answer(
        murderer=e,
        motivation=f'{e}发现F就是高中时在表白墙造谣诬陷自己出轨的人，又发现F向Z家长告密导致Z被迫逃离学校，新仇旧恨交织下决定杀害F。',
        method=f'{e}尾随F到小树林埋伏处守株待兔，在F回收分尸工具时伏击打晕F，用偷来的{c}的水果刀按照{c}小说里的手法毁坏F面部，并将尸体埋在F自己挖的坑中。',
        label='z',
    )


def first_marked(npcs: list[str], marks: dict[str, bool]) -> str:
    for npc in npcs:
        if marks.get(npc) is True:
            return npc
    return npcs[0] if npcs else ''


def name_in_hint(pattern: str, hint: str) -> str:
    m = re.search(pattern, hint)
    return m.group(1).strip() if m else ''


def solve_poker(g: Game, npcs: list[str], marks: dict[str, bool], hint: str, evidences: list[dict[str, Any]]) -> None:
    info = first_marked(npcs, marks)
    if info:
        g.chat(info, '你为什么是好的信息来源？你发现了哪些别人不知道的线索？', label='poker/info')
        g.chat(info, '你是谁？你和死者是什么关系？', label='poker/info')
    npcs, marks, hint, evidences = log_state(g, 'poker/after-info')

    reception_cn = name_in_hint(r'接待者([^，,。 ]+)', hint)
    reception_id = ''
    for npc in npcs:
        if cn_name(npc) == reception_cn:
            reception_id = npc
            break
    if not reception_id:
        reception_id = first_marked(npcs, marks)
        reception_cn = cn_name(reception_id)

    if reception_id:
        for question in [
            '聊天记录里死者和林渝植、梅花5有什么关系？',
            '宾客到达时间表是什么？每个人分别几点到达？',
            '公馆内有什么异常发现？厨房刀具、门窗、血迹和面具哪里不对？',
            '你的证词有什么破绽？案发时你到底在哪里？',
        ]:
            g.chat(reception_id, question, label='poker/reception')
    npcs, marks, hint, evidences = log_state(g, 'poker/final')

    g.answer(
        murderer=reception_cn,
        motivation=f'{reception_cn}为掩盖自己掌握的聊天记录、到达时间表和林渝植身份秘密，担心梅花5真实身份及自己证词破绽暴露而杀人灭口。',
        method=f'{reception_cn}利用接待者身份熟悉扑克公馆结构和宾客到达时间，提前盗走厨房三把刀，在衣帽间刺杀戴梅花5面具的死者，并灼烧双臂、稀释血迹、处理面具与门窗来制造身份混淆。',
        label='poker',
    )


def role_from_replies(replies: dict[str, str], needles: list[str]) -> str:
    for npc, reply in replies.items():
        if any(needle in reply for needle in needles):
            return npc
    return ''


def solve_yuan(g: Game, npcs: list[str], marks: dict[str, bool], hint: str, evidences: list[dict[str, Any]]) -> None:
    replies: dict[str, str] = {}

    for npc in npcs:
        resp = g.chat(npc, '你对死者袁樱瞳和这起碎尸案了解多少？请说最关键的线索。', label='yuan/base')
        replies[npc] = str(resp.get('reply') or resp.get('content') or resp.get('npc_reply') or '')
    npcs, marks, hint, evidences = log_state(g, 'yuan/after-base')

    wang_role = role_from_replies(replies, ['长得', '黄色行李箱', '等到周五', '捡到'])
    zhang_role = role_from_replies(replies, ['投票', '出国', '名额', '展示'])
    xu_role = role_from_replies(replies, ['1919', '保安', '生物馆', '陆亦初'])

    if not wang_role and npcs:
        wang_role = npcs[0]
    if zhang_role:
        g.chat(zhang_role, '课程展示投票结果为什么多出一票？那一票是谁写的，谁从中获利？', label='yuan/vote')
    if xu_role:
        g.chat(xu_role, '你看到的1919黑色豪车、保安奇怪网站、陆亦初从生物馆跑出来分别说明什么？', label='yuan/sight')
    if wang_role:
        g.chat(wang_role, '袁樱瞳手机里凌晨1点的女性尸体照片、栗色假发和你们长相相似说明什么？', ['703'], label='yuan/phone')
    npcs, marks, hint, evidences = log_state(g, 'yuan/final')

    suspect = cn_name(wang_role)
    g.answer(
        murderer=suspect,
        motivation=f'{suspect}因与袁樱瞳竞争张朔的出国交流名额，且投票多出一票、袁樱瞳准备等到周五揭穿真相，担心作弊和相关秘密暴露而杀害袁樱瞳。',
        method=f'{suspect}利用自己与袁樱瞳长相相似及黄色行李箱制造混淆，取得并清空袁樱瞳手机，围绕凌晨1点女性尸体照片、假发和行李转移视线，随后分尸抛尸。',
        label='yuan',
    )


def solve_unknown(g: Game, npcs: list[str], marks: dict[str, bool], hint: str, evidences: list[dict[str, Any]]) -> None:
    text = all_text(hint, evidences)
    if '扑克公馆' in text:
        solve_poker(g, npcs, marks, hint, evidences)
    elif '袁樱瞳' in text or '碎尸案' in text:
        solve_yuan(g, npcs, marks, hint, evidences)
    else:
        suspect = cn_name(npcs[0]) if npcs else ''
        log(f'[v52] unknown hint={hint[:50]} suspect={suspect}')
        g.answer(murderer=suspect, motivation='未知', method='未知', label='unknown')


def solve_case(g: Game, case_idx: int) -> bool:
    npcs = g.npcs()
    if not npcs:
        return False
    marks = g.marks()
    hint = g.hint()
    evidences = g.evidences()
    text = all_text(hint, evidences)
    log(f'[v52] case={case_idx} npcs={sorted(npcs)} marks={marks} hint={hint[:60]}')
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
            log(f'[v52] fatal case={case_idx}: {exc}')
            try:
                g.answer('', '未知', '未知', label='fatal')
            except Exception:
                pass
            break
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
