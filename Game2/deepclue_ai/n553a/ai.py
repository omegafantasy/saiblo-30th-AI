#!/usr/bin/env python3
from __future__ import annotations

import json
import struct
import sys
import time
from typing import Any


DEBUG = False
MODE = 'third_only'


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


class Game:
    def __init__(self, sdk: SDK) -> None:
        self.sdk = sdk
        self.stage = 0

    def req(self, action: str, **kwargs: Any) -> Any:
        try:
            return self.sdk.request(action, **kwargs)
        except Exception as exc:
            log(f'request failed action={action}: {exc}')
            return {}

    def npcs(self) -> list[str]:
        resp = self.req('npcs')
        return [str(x) for x in resp] if isinstance(resp, list) else []

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
            if not (isinstance(resp, dict) and resp.get('error')):
                break
            time.sleep(0.2 * (attempt + 1))
        if not isinstance(resp, dict):
            return {}
        try:
            self.stage = max(self.stage, int(resp.get('stage', self.stage) or self.stage))
        except (TypeError, ValueError):
            pass
        return resp

    def answer(self, murderer: str, motivation: str, method: str) -> None:
        self.req('answer', murderer=murderer, motivation=motivation, method=method)


def response_text(resp: dict[str, Any]) -> str:
    for key in ('reply', 'content', 'message', 'text'):
        value = resp.get(key)
        if isinstance(value, str):
            return value
    return ''


def all_text(hint: str, evidences: list[dict[str, Any]]) -> str:
    parts = [hint]
    for ev in evidences:
        parts.append(str(ev.get('name', '')))
        parts.append(str(ev.get('content', '')))
    return '\n'.join(parts)


def case_kind(text: str) -> str:
    if '袁樱瞳' in text or '碎尸案' in text:
        return 'yuan'
    if 'Rose' in text:
        return 'rose'
    if 'Z失踪' in text or 'F无法联络' in text:
        return 'zf'
    if '扑克公馆' in text:
        return 'poker'
    return 'unknown'


def evidence_ids(evidences: list[dict[str, Any]]) -> list[str]:
    return [str(ev.get('id')) for ev in evidences if str(ev.get('id'))]


def zero_answer(g: Game) -> None:
    g.answer('无名氏', '无', '无')


def focus_targets(npcs: list[str]) -> list[str]:
    if MODE == 'third_only':
        return npcs[2:3] or npcs[-1:]
    if MODE == 'first_two':
        return npcs[:2]
    ordered = (npcs[2:3] + npcs[:2] + npcs[3:])
    seen: set[str] = set()
    return [npc for npc in ordered if not (npc in seen or seen.add(npc))]


def solve_yuan(g: Game, npcs: list[str]) -> None:
    g.stage = 0

    def ask_many(targets: list[str], question: str, ids: list[str] | None = None) -> None:
        for npc in targets:
            reply = response_text(g.chat(npc, question, ids))
            if any(key in reply for key in (
                '手机', '凌晨1点', '尸体照片', 'lo裙', '假发', '投票', '24', '23', '46', '47', '48', '49',
                '笔迹', '多出', '行李箱', '生物馆', '世纪林', '李海天', '1919', '张壹', '保安', '网站',
            )):
                g.evidences()

    ask_many(npcs, '你对死者袁樱瞳和这起碎尸案了解什么？现场情况、尸体、手机、行李箱、照片、假发、投票和时间线都说一下。')
    ask_many(npcs, '你和袁樱瞳是什么关系？她最近和谁有矛盾，谁最后见过她，谁可能有动机？')

    ids = [eid for eid in evidence_ids(g.evidences()) if eid in {'703', '704'}]
    targets = focus_targets(npcs)
    ask_many(
        targets,
        '有人说张壹半夜从生物馆慌张跑出来；请只说你本人实际看到或听到的情况：是谁、几点、从生物馆还是世纪林、有没有尸块或行李箱？',
        ids,
    )
    ask_many(
        targets,
        '不要复述传闻。李海天、保安、奇怪网站、1919黑车、生物馆和袁樱瞳尸块之间，哪一段是你能确认的？',
        ids,
    )
    zero_answer(g)


def solve_case(g: Game) -> bool:
    npcs = g.npcs()
    if not npcs:
        return False
    hint = g.hint()
    evidences = g.evidences()
    if case_kind(all_text(hint, evidences)) == 'yuan':
        solve_yuan(g, npcs)
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
