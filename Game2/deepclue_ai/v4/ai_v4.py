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
    evidence_asked: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))

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

    def evidence_text(self, limit: int = 8500) -> str:
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


def ask_once(sdk: SDK, kb: KB, npc: str, question: str, evidences: list[str]) -> dict[str, Any]:
    key = question + '|' + '/'.join(evidences)
    if key in kb.asked[npc]:
        return {}
    kb.asked[npc].add(key)
    resp = sdk.request('chat', npc=npc, question=question, evidences=evidences)
    if isinstance(resp, dict):
        merge_chat_result(kb, resp)
        return resp
    return {}


def opening_questions(kb: KB) -> list[str]:
    return [
        '你眼中的受害者或失踪者是怎样的人？你和他或她是什么关系？',
        '请按时间顺序说明案发前后你的行动、位置、见过的人和异常情况。',
        '你是否注意到任何异常人物、异常物品或异常冲突？',
        '如果要指出一个最可疑的人，你会怀疑谁？为什么？',
    ]


def followup_questions(kb: KB) -> list[str]:
    items = [
        '你和受害者或失踪者之间有没有矛盾、秘密、利益冲突或感情问题？',
        '请解释目前与你有关、最容易被怀疑的一点。',
        '你是否隐瞒了某段时间线、某件物品或某个人？请直接说明。',
        '关于当前最关键的线索，你还能补充什么？',
    ]
    if kb.hint:
        items.insert(0, f'关于当前提示“{kb.hint[:60]}”，你知道什么？')
    return items


def choose_evidence_prompts(kb: KB, npc: str, limit: int = 2) -> list[tuple[str, list[str]]]:
    out: list[tuple[str, list[str]]] = []
    for item in reversed(kb.evidence_items()):
        eid = item.get('id', '')
        name = item.get('name', '').strip()
        if not eid or not name or eid in kb.evidence_asked[npc]:
            continue
        kb.evidence_asked[npc].add(eid)
        out.append((f'你见过“{name[:32]}”吗？这和案件有什么关系？', [eid]))
        if len(out) >= limit:
            break
    return out


def explore_case(sdk: SDK, kb: KB) -> None:
    refresh_all(sdk, kb)
    question_count = 0
    stage_at_last_full_sync = kb.stage

    for npc in kb.npcs:
        for question in opening_questions(kb)[:2]:
            ask_once(sdk, kb, npc, question, [])
            question_count += 1
        sync_marks_hint(sdk, kb)

    stagnation = 0
    while question_count < 64 and stagnation < 2:
        targets = [npc for npc in kb.npcs if kb.marks.get(npc)] or list(kb.npcs)
        progress_before = (kb.stage, len(kb.testimony), len(kb.others), len(kb.achievements))
        for npc in targets:
            for question, evidences in choose_evidence_prompts(kb, npc, 1):
                ask_once(sdk, kb, npc, question, evidences)
                question_count += 1
                if question_count % 3 == 0:
                    sync_marks_hint(sdk, kb)
                if kb.stage != stage_at_last_full_sync:
                    refresh_all(sdk, kb)
                    stage_at_last_full_sync = kb.stage
                if question_count >= 64:
                    break
            if question_count >= 64:
                break
            for question in followup_questions(kb)[:3]:
                ask_once(sdk, kb, npc, question, [])
                question_count += 1
                if question_count % 3 == 0:
                    sync_marks_hint(sdk, kb)
                if kb.stage != stage_at_last_full_sync:
                    refresh_all(sdk, kb)
                    stage_at_last_full_sync = kb.stage
                if question_count >= 64:
                    break
            if question_count >= 64:
                break
        refresh_all(sdk, kb)
        progress_after = (kb.stage, len(kb.testimony), len(kb.others), len(kb.achievements))
        if progress_after == progress_before and not any(bool(v) for v in kb.marks.values()):
            stagnation += 1
        else:
            stagnation = 0


def final_answer(sdk: SDK, kb: KB) -> dict[str, str]:
    prompt = {
        'background': kb.background,
        'hint': kb.hint,
        'npcs': kb.npcs,
        'evidence': kb.evidence_text(limit=8000),
        'requirements': [
            '输出严格 JSON 对象，格式: {"murderer":...,"motivation":...,"method":...}',
            '优先保证 murderer 正确',
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
    log(f'[game2-v4] case={case_index} stage={kb.stage} npcs={len(kb.npcs)}')
    explore_case(sdk, kb)
    refresh_all(sdk, kb)
    answer = final_answer(sdk, kb)
    log(f"[game2-v4] answer case={case_index} murderer={answer['murderer']!r}")
    resp = sdk.request('answer', **answer)
    log(f'[game2-v4] answer_result case={case_index} resp={resp}')
    return True


def main() -> int:
    sdk = SDK()
    welcome = sdk._receive()
    log(f'[game2-v4] welcome={welcome}')
    case_index = 0
    while True:
        try:
            ok = solve_case(sdk, case_index)
        except EOFError:
            break
        except Exception as exc:
            log(f'[game2-v4] fatal case={case_index} exc={type(exc).__name__}: {exc}')
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
