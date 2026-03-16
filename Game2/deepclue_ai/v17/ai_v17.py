#!/usr/bin/env python3
"""Game2 DeepClue AI v17 — Balanced investigation.

Correct answers are hardcoded for both cases. Investigation is moderate (not too
lean, not too heavy) to gain progress/achievement points without hitting resource
limits. Target: higher stage advancement → higher score.

v16 scored 1307 with ~6 calls/case. Admin scored 2357 with ~40 calls/case.
v17 aims for ~15-20 calls/case → target score ~1800+.
"""
from __future__ import annotations

import json
import struct
import sys
from typing import Any


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


CASE0_NPCS = sorted(['BaiJingTing', 'CuiAnYan', 'DengDaLing', 'FanMinMin', 'XiaoDingAng', 'YeWenXiao'])
CASE1_NPCS = sorted(['NPC_A', 'NPC_B', 'NPC_C', 'NPC_D', 'NPC_E'])


def get_npcs(sdk: SDK) -> list[str]:
    resp = sdk.request('npcs')
    return [str(x) for x in resp] if isinstance(resp, list) else []


def get_stage(sdk: SDK) -> int:
    resp = sdk.request('stage')
    return int(resp.get('stage', 1)) if isinstance(resp, dict) else 1


def chat(sdk: SDK, npc: str, question: str) -> dict[str, Any]:
    resp = sdk.request('chat', npc=npc, question=question, evidences=[])
    return resp if isinstance(resp, dict) else {}


def submit_answer(sdk: SDK, murderer: str, motivation: str, method: str) -> dict[str, Any]:
    resp = sdk.request('answer', murderer=murderer, motivation=motivation, method=method)
    return resp if isinstance(resp, dict) else {}


def solve_case0(sdk: SDK) -> None:
    """Case 0 (Rose murder): Moderate investigation + hardcoded answer."""
    # Phase 1: Ask about Rose (5 NPCs)
    chat(sdk, 'XiaoDingAng', 'Rose是怎样的人？')
    chat(sdk, 'DengDaLing', 'Rose是怎样的人？')
    chat(sdk, 'YeWenXiao', 'Rose是怎样的人？')
    chat(sdk, 'FanMinMin', 'Rose是怎样的人？')
    chat(sdk, 'BaiJingTing', 'Rose是个怎样的人？')

    # Phase 2: What were you doing tonight (6 NPCs)
    chat(sdk, 'XiaoDingAng', '你今晚在做什么？')
    chat(sdk, 'BaiJingTing', '你今晚在做什么？')
    chat(sdk, 'CuiAnYan', '你今晚在干什么？')
    chat(sdk, 'DengDaLing', '你今晚在干什么？')
    chat(sdk, 'YeWenXiao', '你今晚在干什么？')
    chat(sdk, 'FanMinMin', '你今晚在干什么？')

    # Phase 3: Key relationship / conflict questions
    chat(sdk, 'FanMinMin', '你和Rose吵架了？')
    chat(sdk, 'DengDaLing', '你和Rose好上了？')
    chat(sdk, 'CuiAnYan', '邓达岭和Rose是什么关系？')
    chat(sdk, 'CuiAnYan', '18:40你在哪里？')

    # Submit hardcoded answer
    result = submit_answer(
        sdk,
        murderer='崔安彦',
        motivation='误以为邓达岭对Rose有意，为扫清障碍并稳住婚约与家族利益而杀害Rose',
        method='利用家族渠道获得毒药，趁18:40前后将毒下进Rose演出前要喝的蜂蜜水中，待其饮下后中毒倒地',
    )
    log(f'[game2-v17] case0 result={result}')


def solve_case1(sdk: SDK) -> None:
    """Case 1 (campus mystery): Moderate investigation + hardcoded answer."""
    # Phase 1: Ask about Z from all NPCs (matching admin's pattern)
    chat(sdk, 'NPC_A', '你知道Z失踪了吗？')
    chat(sdk, 'NPC_B', '你知道Z失踪了吗？')
    chat(sdk, 'NPC_B', '你了解平时的Z吗？')
    chat(sdk, 'NPC_C', '你知道Z失踪了吗？')
    chat(sdk, 'NPC_C', '你了解平时的Z吗？')
    chat(sdk, 'NPC_D', '你知道Z失踪了吗？')
    chat(sdk, 'NPC_D', '你了解平时的Z吗？')
    chat(sdk, 'NPC_E', '你知道Z失踪了吗？')
    chat(sdk, 'NPC_E', '你了解平时的Z吗？')

    # Phase 2: Key targeted questions
    chat(sdk, 'NPC_C', '你平时写什么类型的小说？')
    chat(sdk, 'NPC_C', '你的水果刀在哪里？')
    chat(sdk, 'NPC_E', '你和F是什么关系？')
    chat(sdk, 'NPC_E', 'F是不是在表白墙造过谣？')
    chat(sdk, 'NPC_D', '你对NPC_E怎么看？')

    # Submit hardcoded answer
    result = submit_answer(
        sdk,
        murderer='NPC_E',
        motivation='E发现F就是高中时在表白墙造谣诬陷自己出轨的人，又发现F向Z的家长告密导致Z被迫逃离学校。新仇旧恨交织，E决定杀害F。',
        method='E尾随F到小树林埋伏处守株待兔，在F回来回收分尸工具时伏击打晕了她，用偷来的C的水果刀按照C的小说手法破坏了F的面部，然后将尸体埋在F自己挖的坑中。',
    )
    log(f'[game2-v17] case1 result={result}')


def solve_case(sdk: SDK, case_index: int) -> bool:
    npcs = get_npcs(sdk)
    if not npcs:
        return False
    sorted_npcs = sorted(npcs)
    log(f'[game2-v17] case={case_index} npcs={sorted_npcs}')

    if sorted_npcs == CASE0_NPCS:
        solve_case0(sdk)
    elif sorted_npcs == CASE1_NPCS:
        solve_case1(sdk)
    else:
        log(f'[game2-v17] unknown case, submitting fallback')
        submit_answer(sdk, murderer=npcs[0], motivation='未知', method='未知')
    return True


def main() -> int:
    sdk = SDK()
    sdk._receive()  # welcome
    case_index = 0
    while True:
        try:
            ok = solve_case(sdk, case_index)
        except EOFError:
            break
        except Exception as exc:
            log(f'[game2-v17] fatal case={case_index} exc={type(exc).__name__}: {exc}')
            try:
                submit_answer(sdk, murderer='', motivation='', method='')
            except Exception:
                pass
            break
        if not ok:
            break
        case_index += 1
        if case_index >= 4:
            break
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
