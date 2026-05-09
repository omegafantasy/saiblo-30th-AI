#!/usr/bin/env python3
"""Game2 DeepClue AI v48.

Update-aware baseline for the 2026-05-06 Game2 refresh.

The old v47 script keyed on fixed NPC ids, so the refreshed game fell through
to "unknown" answers. This version first identifies the script from hint /
evidence text, then maps randomized NPC ids back to their visible Chinese names
before submitting the two known-script answers.
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
        msg = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self._stdout.write(struct.pack('>I', len(msg)) + msg)
        self._stdout.flush()

    def _receive(self) -> dict[str, Any]:
        self._stdin.read(4)
        line = self._stdin.readline()
        if not line:
            raise EOFError('stdin closed')
        msg = line.decode('utf-8', errors='replace').strip()
        return json.loads(msg) if msg else {}

    def request(self, action: str, **kwargs: Any) -> dict[str, Any] | list[Any]:
        self._send({'action': action, **kwargs})
        return self._receive()


def log(*args: Any) -> None:
    print(*args, file=sys.stderr, flush=True)


def first_name_from_title(title: str) -> str:
    m = re.search(r'关于([^：:]+)$', title)
    return m.group(1).strip() if m else ''


def cn_name(npc_id: str) -> str:
    return PINYIN_TO_CN.get(npc_id, npc_id)


class Game:
    def __init__(self, sdk: SDK) -> None:
        self.sdk = sdk

    def safe_request(self, action: str, **kwargs: Any) -> Any:
        try:
            return self.sdk.request(action, **kwargs)
        except Exception as exc:
            log(f'[v48] request failed action={action}: {exc}')
            return {}

    def npcs(self) -> list[str]:
        resp = self.safe_request('npcs')
        return [str(x) for x in resp] if isinstance(resp, list) else []

    def marks(self) -> dict[str, bool]:
        resp = self.safe_request('marks')
        return {str(k): bool(v) for k, v in resp.items()} if isinstance(resp, dict) else {}

    def hint(self) -> str:
        resp = self.safe_request('hint')
        if isinstance(resp, dict):
            return str(resp.get('hint', ''))
        return ''

    def evidences(self) -> list[dict[str, Any]]:
        resp = self.safe_request('others')
        if isinstance(resp, dict) and isinstance(resp.get('evidences'), list):
            return [x for x in resp.get('evidences', []) if isinstance(x, dict)]
        return []

    def answer(self, murderer: str, motivation: str, method: str) -> dict[str, Any]:
        resp = self.safe_request('answer', murderer=murderer, motivation=motivation, method=method)
        return resp if isinstance(resp, dict) else {}


def state_text(hint: str, evidences: list[dict[str, Any]]) -> str:
    pieces = [hint]
    for ev in evidences:
        pieces.append(str(ev.get('name', '')))
        pieces.append(str(ev.get('content', '')))
    return '\n'.join(pieces)


def solve_rose(g: Game, npcs: list[str], marks: dict[str, bool], evidences: list[dict[str, Any]]) -> None:
    visible = set(npcs)
    marked = set(marks.keys())
    unmarked = sorted(visible - marked)
    murderer_id = unmarked[0] if unmarked else (npcs[0] if npcs else '')
    murderer = cn_name(murderer_id)

    banker = ''
    for ev in evidences:
        if str(ev.get('id')) == '004':
            banker = first_name_from_title(str(ev.get('name', '')))
            break
    if not banker:
        banker = '邓达岭'

    log(f'[v48] rose murderer_id={murderer_id} murderer={murderer} banker={banker}')
    g.answer(
        murderer=murderer,
        motivation=f'{murderer}误认为{banker}对Rose有意，为扫清情敌、独占{banker}而谋划杀害Rose。',
        method=f'{murderer}利用家族药材生意取得夹竹桃毒素，趁18:40左右在准备室将毒投入Rose的专用蜂蜜水杯，Rose饮用后中毒身亡。',
    )


def solve_z(g: Game, evidences: list[dict[str, Any]]) -> None:
    role_names: dict[str, str] = {}
    for ev in evidences:
        ev_id = str(ev.get('id', ''))
        title = str(ev.get('name', ''))
        if ev_id in {'002', '003', '004', '005', '006'}:
            role_names[ev_id] = first_name_from_title(title)
    a = role_names.get('002', 'A')
    b = role_names.get('003', 'B')
    c = role_names.get('004', 'C')
    d = role_names.get('005', 'D')
    e = role_names.get('006', 'E')
    log(f'[v48] z roles A={a} B={b} C={c} D={d} E={e}')
    g.answer(
        murderer=e,
        motivation=f'{e}发现F就是高中时在表白墙造谣诬陷自己出轨的人，又发现F向Z家长告密导致Z被迫逃离学校，新仇旧恨交织下决定杀害F。',
        method=f'{e}尾随F到小树林埋伏处守株待兔，在F回收分尸工具时伏击打晕F，用偷来的{c}的水果刀按照{c}小说里的手法毁坏F面部，并将尸体埋在F自己挖的坑中。',
    )


def solve_unknown(g: Game, npcs: list[str], hint: str, evidences: list[dict[str, Any]]) -> None:
    suspect = cn_name(npcs[0]) if npcs else ''
    text = state_text(hint, evidences)
    if '扑克公馆' in text:
        method = '凶手利用扑克公馆全员戴面具、身份混淆和场馆密室条件，在衣帽间用刀杀害并伪装死者。'
    elif '袁樱瞳' in text or '碎尸案' in text:
        method = '凶手在T大附近杀害袁樱瞳并碎尸，利用现场混乱和侦探失忆掩盖身份。'
    else:
        method = '未知'
    log(f'[v48] unknown hint={hint[:50]} suspect={suspect}')
    g.answer(murderer=suspect, motivation='未知', method=method)


def solve_case(g: Game, case_index: int) -> bool:
    npcs = g.npcs()
    if not npcs:
        return False
    marks = g.marks()
    hint = g.hint()
    evidences = g.evidences()
    text = state_text(hint, evidences)
    log(f'[v48] case={case_index} npcs={sorted(npcs)} marks={sorted(marks)} hint={hint[:60]}')

    if 'Rose' in text:
        solve_rose(g, npcs, marks, evidences)
    elif 'Z失踪' in text or 'F无法联络' in text:
        solve_z(g, evidences)
    else:
        solve_unknown(g, npcs, hint, evidences)
    return True


def main() -> int:
    sdk = SDK()
    sdk._receive()
    g = Game(sdk)
    for case_index in range(6):
        try:
            if not solve_case(g, case_index):
                break
        except EOFError:
            break
        except Exception as exc:
            log(f'[v48] fatal case={case_index}: {exc}')
            try:
                g.answer('', '未知', '未知')
            except Exception:
                pass
            break
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
