#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import struct
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
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
        header = self._stdin.read(4)
        line = self._stdin.readline()
        if not line:
            raise EOFError('stdin closed')
        msg = line.decode('utf-8', errors='replace').strip()
        return json.loads(msg) if msg else {}

    def request(self, action: str, **kwargs: Any) -> dict[str, Any] | list[Any]:
        self._send({'action': action, **kwargs})
        return self._receive()

    def call_llm(self, **kwargs: Any) -> dict[str, Any]:
        resp = self.request('call', **kwargs)
        return resp if isinstance(resp, dict) else {'error': f'invalid llm response: {type(resp).__name__}'}


def log(*args: Any) -> None:
    print(*args, file=sys.stderr, flush=True)


@dataclass
class KB:
    background: str = ''
    hint: str = ''
    stage: int = 1
    npcs: list[str] = field(default_factory=list)
    testimony: list[dict[str, Any]] = field(default_factory=list)
    others: list[dict[str, Any]] = field(default_factory=list)
    achievements: list[dict[str, Any]] = field(default_factory=list)
    asked: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))
    evidence_asked: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))

    def evidence_ids(self) -> list[str]:
        out: list[str] = []
        for item in self.testimony:
            if isinstance(item, dict) and item.get('id'):
                out.append(str(item['id']))
        for item in self.others:
            if isinstance(item, dict) and item.get('id'):
                out.append(str(item['id']))
        return out

    def evidence_items(self) -> list[dict[str, str]]:
        items: list[dict[str, str]] = []
        for source in (self.testimony, self.others):
            for item in source:
                if not isinstance(item, dict):
                    continue
                items.append({
                    'id': str(item.get('id', '')),
                    'name': str(item.get('name', '')),
                    'content': str(item.get('content', '')),
                })
        return items

    def evidence_text(self, limit: int = 9000) -> str:
        parts: list[str] = []
        for item in self.evidence_items():
            parts.append(f"[{item['id']}] {item['name']} {item['content']}")
        for item in self.achievements:
            if isinstance(item, dict):
                parts.append(f"[A {item.get('id')}] {item.get('name','')} {item.get('description','')}")
        return '\n'.join(parts)[:limit]


def normalize_json_object(text: str) -> dict[str, Any] | None:
    text = text.strip()
    if not text:
        return None
    m = re.search(r'\{.*\}', text, re.S)
    if m:
        text = m.group(0)
    try:
        obj = json.loads(text)
    except Exception:
        return None
    return obj if isinstance(obj, dict) else None


def refresh(sdk: SDK, kb: KB) -> None:
    resp = sdk.request('background')
    if isinstance(resp, dict):
        kb.background = str(resp.get('background', ''))
    resp = sdk.request('stage')
    if isinstance(resp, dict):
        kb.stage = int(resp.get('stage', kb.stage) or kb.stage)
    resp = sdk.request('hint')
    if isinstance(resp, dict):
        kb.hint = str(resp.get('hint', ''))
    resp = sdk.request('npcs')
    if isinstance(resp, list):
        kb.npcs = [str(x) for x in resp]
    resp = sdk.request('testimony')
    if isinstance(resp, list):
        kb.testimony = [x for x in resp if isinstance(x, dict)]
    resp = sdk.request('others')
    if isinstance(resp, dict) and isinstance(resp.get('evidences'), list):
        kb.others = [x for x in resp.get('evidences', []) if isinstance(x, dict)]
    resp = sdk.request('achievements')
    if isinstance(resp, dict) and isinstance(resp.get('achievements'), list):
        kb.achievements = [x for x in resp.get('achievements', []) if isinstance(x, dict)]


def get_marks(sdk: SDK) -> dict[str, bool]:
    resp = sdk.request('marks')
    return resp if isinstance(resp, dict) else {}


def ask_once(sdk: SDK, kb: KB, npc: str, question: str, evidences: list[str]) -> tuple[int, int, int]:
    key = question + '|' + '/'.join(evidences)
    if key in kb.asked[npc]:
        return len(kb.testimony), len(kb.others), len(kb.achievements)
    kb.asked[npc].add(key)
    before = (len(kb.testimony), len(kb.others), len(kb.achievements))
    resp = sdk.request('chat', npc=npc, question=question, evidences=evidences)
    if isinstance(resp, dict) and 'stage' in resp:
        try:
            kb.stage = int(resp.get('stage', kb.stage) or kb.stage)
        except Exception:
            pass
    refresh(sdk, kb)
    after = (len(kb.testimony), len(kb.others), len(kb.achievements))
    return after[0] - before[0], after[1] - before[1], after[2] - before[2]


def opening_questions(kb: KB) -> list[str]:
    return [
        '请先介绍你对受害者或失踪者的印象、关系和最近互动。',
        '请按时间顺序完整说明案发前后你在哪里、见过谁、做过什么。',
        '你是否注意到任何异常人物、异常物品或异常冲突？',
        '如果你觉得有人最可疑，请直接指出是谁、为什么。',
    ]


def generic_followups(kb: KB) -> list[str]:
    items = [
        '你和受害者或失踪者之间是否有矛盾、秘密、利益冲突或感情纠葛？',
        '你是否隐瞒了某段时间线、某件物品或某个人？请直接说明。',
        '请解释目前与你有关、最容易被怀疑的一点。',
        '关于当前提示，你知道什么关键事实？',
    ]
    if kb.hint:
        items.insert(0, f'关于当前提示“{kb.hint[:80]}”，你知道什么？')
    return items


def choose_evidence_prompts(kb: KB, npc: str, limit: int = 3) -> list[tuple[str, list[str]]]:
    out: list[tuple[str, list[str]]] = []
    for item in reversed(kb.evidence_items()):
        eid = item.get('id', '')
        name = item.get('name', '').strip()
        if not eid or not name or eid in kb.evidence_asked[npc]:
            continue
        kb.evidence_asked[npc].add(eid)
        out.append((f'你见过“{name[:40]}”吗？它和案件有什么关系？', [eid]))
        if len(out) >= limit:
            break
    return out


def explore_case(sdk: SDK, kb: KB) -> None:
    round_limit = 72
    question_count = 0

    for npc in kb.npcs:
        for question in opening_questions(kb)[:2]:
            ask_once(sdk, kb, npc, question, [])
            question_count += 1
            if question_count >= round_limit:
                return

    stagnation = 0
    while question_count < round_limit and stagnation < 2:
        marks = get_marks(sdk)
        targets = [npc for npc in kb.npcs if marks.get(npc)] or list(kb.npcs)
        before = (kb.stage, len(kb.testimony), len(kb.others), len(kb.achievements))
        progress = 0
        for npc in targets:
            for question, evidences in choose_evidence_prompts(kb, npc, 2):
                d1, d2, d3 = ask_once(sdk, kb, npc, question, evidences)
                progress += max(0, d1) + max(0, d2) + max(0, d3)
                question_count += 1
                if question_count >= round_limit:
                    break
            if question_count >= round_limit:
                break
            for question in generic_followups(kb):
                d1, d2, d3 = ask_once(sdk, kb, npc, question, [])
                progress += max(0, d1) + max(0, d2) + max(0, d3)
                question_count += 1
                if question_count >= round_limit:
                    break
            if question_count >= round_limit:
                break
        after = (kb.stage, len(kb.testimony), len(kb.others), len(kb.achievements))
        if progress > 0 or after != before or any(bool(v) for v in marks.values()):
            stagnation = 0 if after != before or progress > 0 else stagnation + 1
        else:
            stagnation += 1


def final_answer(sdk: SDK, kb: KB) -> dict[str, str]:
    prompt = {
        'background': kb.background,
        'hint': kb.hint,
        'npcs': kb.npcs,
        'evidence': kb.evidence_text(limit=8500),
        'requirements': [
            '输出严格 JSON 对象，格式: {"murderer":...,"motivation":...,"method":...}',
            '先保证 murderer 正确，再保证 motivation 和 method 具体',
            '不要输出任何额外文字',
        ],
    }
    resp = sdk.call_llm(
        messages=[
            {'role': 'system', 'content': '你是刑侦推理结论器。必须只输出 JSON。'},
            {'role': 'user', 'content': json.dumps(prompt, ensure_ascii=False)},
        ],
        temperature=0.05,
    )
    default = {
        'murderer': kb.npcs[0] if kb.npcs else '',
        'motivation': kb.hint[:100] or kb.background[:100],
        'method': kb.hint[:100] or kb.background[:100],
    }
    if 'error' in resp:
        return default
    try:
        content = resp['choices'][0]['message']['content']
    except Exception:
        return default
    obj = normalize_json_object(content)
    if not obj:
        return default
    return {
        'murderer': str(obj.get('murderer', '')).strip() or default['murderer'],
        'motivation': str(obj.get('motivation', '')).strip() or default['motivation'],
        'method': str(obj.get('method', '')).strip() or default['method'],
    }


def solve_case(sdk: SDK, case_index: int) -> bool:
    kb = KB()
    refresh(sdk, kb)
    if not kb.background and not kb.npcs:
        return False
    log(f'[game2-v3] case={case_index} stage={kb.stage} npcs={len(kb.npcs)}')
    explore_case(sdk, kb)
    refresh(sdk, kb)
    answer = final_answer(sdk, kb)
    log(f"[game2-v3] answer case={case_index} murderer={answer['murderer']!r}")
    resp = sdk.request('answer', **answer)
    log(f'[game2-v3] answer_result case={case_index} resp={resp}')
    return True


def main() -> int:
    sdk = SDK()
    welcome = sdk._receive()
    log(f'[game2-v3] welcome={welcome}')
    case_index = 0
    while True:
        try:
            ok = solve_case(sdk, case_index)
        except EOFError:
            break
        except Exception as exc:
            log(f'[game2-v3] fatal case={case_index} exc={type(exc).__name__}: {exc}')
            try:
                sdk.request('answer', murderer='', motivation='', method='')
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
