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
class KnowledgeBase:
    background: str = ''
    hint: str = ''
    stage: int = 1
    npcs: list[str] = field(default_factory=list)
    testimony: list[dict[str, Any]] = field(default_factory=list)
    others: list[dict[str, Any]] = field(default_factory=list)
    achievements: list[dict[str, Any]] = field(default_factory=list)
    asked: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))
    steps: int = 0
    step_budget: int = 24

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
        out: list[dict[str, str]] = []
        for source in (self.testimony, self.others):
            for item in source:
                if isinstance(item, dict):
                    out.append({
                        'id': str(item.get('id', '')),
                        'name': str(item.get('name', '')),
                        'content': str(item.get('content', '')),
                    })
        return out

    def evidence_text(self, limit: int = 7000) -> str:
        parts: list[str] = []
        for item in self.testimony:
            if isinstance(item, dict):
                parts.append(f"[T {item.get('id')}] {item.get('name','')} {item.get('content','')}")
        for item in self.others:
            if isinstance(item, dict):
                parts.append(f"[E {item.get('id')}] {item.get('name','')} {item.get('content','')}")
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


def refresh(sdk: SDK, kb: KnowledgeBase) -> None:
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
        kb.others = [x for x in resp['evidences'] if isinstance(x, dict)]
    resp = sdk.request('achievements')
    if isinstance(resp, dict) and isinstance(resp.get('achievements'), list):
        kb.achievements = [x for x in resp['achievements'] if isinstance(x, dict)]


def marks(sdk: SDK) -> dict[str, bool]:
    resp = sdk.request('marks')
    return resp if isinstance(resp, dict) else {}


def evidence_pick(kb: KnowledgeBase, budget: int = 3) -> list[str]:
    ids = kb.evidence_ids()
    if not ids:
        return []
    return ids[-budget:]


def generic_question_bank() -> list[str]:
    return [
        '请按时间顺序完整说明案发当天你从开始到结束的行动、位置、见过的人和异常情况。',
        '你与死者以及其他在场人物的关系、利益冲突、债务、感情或秘密是什么？',
        '请解释目前所有与你有关的矛盾、证据和别人对你的怀疑。',
        '如果要你指出最可疑的人、动机和作案机会，你会怎么分析？',
    ]


def ask_once(sdk: SDK, kb: KnowledgeBase, npc: str, question: str, evidences: list[str]) -> bool:
    if kb.steps >= kb.step_budget:
        return False
    key = question + '|' + '/'.join(evidences)
    if key in kb.asked[npc]:
        return False
    kb.asked[npc].add(key)
    kb.steps += 1
    resp = sdk.request('chat', npc=npc, question=question, evidences=evidences)
    if isinstance(resp, dict) and 'stage' in resp:
        try:
            kb.stage = int(resp.get('stage', kb.stage) or kb.stage)
        except Exception:
            pass
    return True


def generic_sweep(sdk: SDK, kb: KnowledgeBase) -> None:
    current_marks = marks(sdk)
    targets = [npc for npc in kb.npcs if current_marks.get(npc)] or list(kb.npcs)
    templates = generic_question_bank()
    for npc in targets:
        for question in templates[:2]:
            if not ask_once(sdk, kb, npc, question, evidence_pick(kb, 2)):
                return
        refresh(sdk, kb)


def llm_batch_plan(sdk: SDK, kb: KnowledgeBase, current_marks: dict[str, bool]) -> list[dict[str, Any]]:
    targets = [npc for npc in kb.npcs if current_marks.get(npc)]
    if not targets:
        return []
    prompt = {
        'stage': kb.stage,
        'hint': kb.hint[:900],
        'targets': targets[:4],
        'known_evidence': kb.evidence_text(limit=4500),
        'already_asked': {npc: sorted(kb.asked[npc])[-4:] for npc in targets[:4]},
        'requirements': [
            '输出严格 JSON 对象',
            '格式: {"plans":[{"npc":"...","question":"...","evidences":["..."]}]}',
            '最多输出 4 个计划',
            '每个 npc 最多 1 个问题',
            '问题必须具体，优先问时间线缺口、关系、动机、证据矛盾',
            '如有证据名，可直接引用证据名或证据所指向的关系',
            '不要输出额外文字',
        ],
    }
    resp = sdk.call_llm(
        messages=[
            {'role': 'system', 'content': '你是侦探游戏中的调查规划器。必须只输出 JSON。'},
            {'role': 'user', 'content': json.dumps(prompt, ensure_ascii=False)},
        ],
        temperature=0.1,
    )
    if 'error' in resp:
        return []
    try:
        content = resp['choices'][0]['message']['content']
    except Exception:
        return []
    obj = normalize_json_object(content)
    if not obj or not isinstance(obj.get('plans'), list):
        return []
    known_ids = set(kb.evidence_ids())
    out: list[dict[str, Any]] = []
    for item in obj['plans'][:4]:
        if not isinstance(item, dict):
            continue
        npc = str(item.get('npc', '')).strip()
        question = str(item.get('question', '')).strip()
        evidences = item.get('evidences', [])
        if npc not in targets or not question:
            continue
        if not isinstance(evidences, list):
            evidences = []
        clean = [str(x) for x in evidences if str(x) in known_ids][:2]
        out.append({'npc': npc, 'question': question[:160], 'evidences': clean})
    return out


def evidence_probe(sdk: SDK, kb: KnowledgeBase) -> None:
    current_marks = marks(sdk)
    targets = [npc for npc in kb.npcs if current_marks.get(npc)] or list(kb.npcs)
    latest = [item for item in reversed(kb.evidence_items()) if item.get('name')][:3]
    for item, npc in zip(latest, targets):
        question = f"{item['name'][:40]} 这件证物与你、死者或当前嫌疑人之间有什么关系？"
        if not ask_once(sdk, kb, npc, question, [item['id']] if item.get('id') else []):
            return
    refresh(sdk, kb)


def targeted_sweep(sdk: SDK, kb: KnowledgeBase) -> None:
    current_marks = marks(sdk)
    plans = llm_batch_plan(sdk, kb, current_marks)
    if not plans:
        for npc, has_more in current_marks.items():
            if has_more:
                if not ask_once(sdk, kb, npc, '请你只回答目前最关键、最能改变凶手判断的一条信息。', evidence_pick(kb, 2)):
                    break
        refresh(sdk, kb)
        return
    for item in plans:
        if not ask_once(sdk, kb, item['npc'], item['question'], item['evidences']):
            break
    refresh(sdk, kb)


def final_answer(sdk: SDK, kb: KnowledgeBase) -> dict[str, str]:
    prompt = {
        'background': kb.background,
        'hint': kb.hint,
        'stage': kb.stage,
        'npcs': kb.npcs,
        'evidence': kb.evidence_text(limit=7000),
        'requirements': [
            '输出严格 JSON 对象，格式: {"murderer":...,"motivation":...,"method":...}',
            '优先保证 murderer 正确',
            '如果显而易见的嫌疑人与关键证据不一致，不要选表面冲突最大的人',
            'motivation 和 method 要具体且简洁',
            '不要输出额外说明',
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
    kb = KnowledgeBase()
    refresh(sdk, kb)
    if not kb.background and not kb.npcs:
        return False
    log(f'[game2-v7] case={case_index} stage={kb.stage} npcs={len(kb.npcs)}')

    generic_sweep(sdk, kb)
    rounds = 0
    while rounds < 2 and kb.steps < kb.step_budget:
        current_marks = marks(sdk)
        if not any(bool(v) for v in current_marks.values()):
            break
        targeted_sweep(sdk, kb)
        rounds += 1
    if kb.steps < kb.step_budget - 2:
        evidence_probe(sdk, kb)
    if kb.steps < kb.step_budget - 2:
        current_marks = marks(sdk)
        if any(bool(v) for v in current_marks.values()):
            targeted_sweep(sdk, kb)

    answer = final_answer(sdk, kb)
    log(f"[game2-v7] case={case_index} steps={kb.steps} murderer={answer['murderer']!r}")
    resp = sdk.request('answer', **answer)
    log(f'[game2-v7] answer_result case={case_index} resp={resp}')
    return True


def main() -> int:
    sdk = SDK()
    welcome = sdk._receive()
    log(f'[game2-v7] welcome={welcome}')
    case_index = 0
    while True:
        try:
            ok = solve_case(sdk, case_index)
        except EOFError:
            break
        except Exception as exc:
            log(f'[game2-v7] fatal case={case_index} exc={type(exc).__name__}: {exc}')
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
