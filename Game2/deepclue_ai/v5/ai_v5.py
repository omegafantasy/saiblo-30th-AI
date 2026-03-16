#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import struct
import sys
from collections import defaultdict
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
        self._stdin.read(4)
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
    marks: dict[str, bool] = field(default_factory=dict)
    asked: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))
    evidence_used: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))

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

    def evidence_text(self, limit: int = 7500) -> str:
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


def refresh_all(sdk: SDK, kb: KB) -> None:
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
    resp = sdk.request('marks')
    if isinstance(resp, dict):
        kb.marks = {str(k): bool(v) for k, v in resp.items()}
    resp = sdk.request('testimony')
    if isinstance(resp, list):
        kb.testimony = [x for x in resp if isinstance(x, dict)]
    resp = sdk.request('others')
    if isinstance(resp, dict) and isinstance(resp.get('evidences'), list):
        kb.others = [x for x in resp.get('evidences', []) if isinstance(x, dict)]
    resp = sdk.request('achievements')
    if isinstance(resp, dict) and isinstance(resp.get('achievements'), list):
        kb.achievements = [x for x in resp.get('achievements', []) if isinstance(x, dict)]


def sync_marks_hint(sdk: SDK, kb: KB) -> None:
    resp = sdk.request('stage')
    if isinstance(resp, dict):
        kb.stage = int(resp.get('stage', kb.stage) or kb.stage)
    resp = sdk.request('hint')
    if isinstance(resp, dict):
        kb.hint = str(resp.get('hint', kb.hint))
    resp = sdk.request('marks')
    if isinstance(resp, dict):
        kb.marks = {str(k): bool(v) for k, v in resp.items()}


def merge_chat_result(kb: KB, resp: dict[str, Any]) -> None:
    if 'stage' in resp:
        try:
            kb.stage = int(resp.get('stage', kb.stage) or kb.stage)
        except Exception:
            pass
    if isinstance(resp.get('unlock_testimony'), list):
        known = {str(x.get('id')) for x in kb.testimony if isinstance(x, dict)}
        for item in resp.get('unlock_testimony', []):
            if isinstance(item, dict) and str(item.get('id')) not in known:
                kb.testimony.append(item)
                known.add(str(item.get('id')))
    if isinstance(resp.get('achievements'), list):
        known = {str(x.get('id')) for x in kb.achievements if isinstance(x, dict)}
        for item in resp.get('achievements', []):
            if isinstance(item, dict) and str(item.get('id')) not in known:
                kb.achievements.append(item)
                known.add(str(item.get('id')))


def ask_once(sdk: SDK, kb: KB, npc: str, question: str, evidences: list[str]) -> bool:
    key = question + '|' + '/'.join(evidences)
    if key in kb.asked[npc]:
        return False
    kb.asked[npc].add(key)
    resp = sdk.request('chat', npc=npc, question=question, evidences=evidences)
    if isinstance(resp, dict):
        merge_chat_result(kb, resp)
    return True


def choose_targets(kb: KB) -> list[str]:
    marked = [npc for npc in kb.npcs if kb.marks.get(npc)]
    return marked or list(kb.npcs)


def choose_evidence_question(kb: KB, npc: str) -> tuple[str, list[str]] | None:
    for item in reversed(kb.evidence_items()):
        eid = item.get('id', '')
        name = item.get('name', '').strip()
        if not eid or not name or eid in kb.evidence_used[npc]:
            continue
        kb.evidence_used[npc].add(eid)
        return f'你见过“{name[:28]}”吗？这说明了什么？', [eid]
    return None


def opening_round(kb: KB) -> list[str]:
    return [
        '你眼中的受害者或失踪者是怎样的人？你和他或她是什么关系？',
        '请按时间顺序说明案发前后你的行动、位置、见过的人和异常情况。',
    ]


def followup_round(kb: KB) -> list[str]:
    items = [
        '你和受害者或失踪者之间有没有矛盾、秘密、利益冲突或感情问题？',
        '如果要指出一个最可疑的人，你会怀疑谁？为什么？',
        '请解释目前与你有关、最容易被怀疑的一点。',
    ]
    if kb.hint:
        items.insert(0, f'关于当前提示“{kb.hint[:50]}”，你能补充什么？')
    return items


def explore_case(sdk: SDK, kb: KB) -> None:
    refresh_all(sdk, kb)
    question_count = 0
    last_stage = kb.stage

    for question in opening_round(kb):
        for npc in choose_targets(kb):
            if ask_once(sdk, kb, npc, question, []):
                question_count += 1
        sync_marks_hint(sdk, kb)
        if kb.stage != last_stage:
            refresh_all(sdk, kb)
            last_stage = kb.stage

    for round_index in range(4):
        targets = choose_targets(kb)
        progress_before = (kb.stage, len(kb.testimony), len(kb.others), len(kb.achievements))
        for npc in targets:
            picked = choose_evidence_question(kb, npc)
            if picked and question_count < 34:
                if ask_once(sdk, kb, npc, picked[0], picked[1]):
                    question_count += 1
            if question_count >= 34:
                break
            q = followup_round(kb)[min(round_index, len(followup_round(kb)) - 1)]
            if ask_once(sdk, kb, npc, q, []):
                question_count += 1
            if question_count >= 34:
                break
        sync_marks_hint(sdk, kb)
        if kb.stage != last_stage:
            refresh_all(sdk, kb)
            last_stage = kb.stage
        progress_after = (kb.stage, len(kb.testimony), len(kb.others), len(kb.achievements))
        if progress_after == progress_before and not any(bool(v) for v in kb.marks.values()):
            break
        if question_count >= 34:
            break

    refresh_all(sdk, kb)


def final_answer(sdk: SDK, kb: KB) -> dict[str, str]:
    prompt = {
        'background': kb.background,
        'hint': kb.hint,
        'npcs': kb.npcs,
        'evidence': kb.evidence_text(limit=7000),
        'requirements': [
            '输出严格 JSON 对象，格式: {"murderer":...,"motivation":...,"method":...}',
            '优先保证 murderer 正确',
            'motivation 和 method 尽量具体但不要冗长',
            '不要输出额外文字',
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
        'motivation': kb.hint[:80] or kb.background[:80],
        'method': kb.hint[:80] or kb.background[:80],
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
    refresh_all(sdk, kb)
    if not kb.background and not kb.npcs:
        return False
    log(f'[game2-v5] case={case_index} stage={kb.stage} npcs={len(kb.npcs)}')
    explore_case(sdk, kb)
    answer = final_answer(sdk, kb)
    log(f"[game2-v5] answer case={case_index} murderer={answer['murderer']!r}")
    resp = sdk.request('answer', **answer)
    log(f'[game2-v5] answer_result case={case_index} resp={resp}')
    return True


def main() -> int:
    sdk = SDK()
    welcome = sdk._receive()
    log(f'[game2-v5] welcome={welcome}')
    case_index = 0
    while True:
        try:
            ok = solve_case(sdk, case_index)
        except EOFError:
            break
        except Exception as exc:
            log(f'[game2-v5] fatal case={case_index} exc={type(exc).__name__}: {exc}')
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
