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
    replies: list[dict[str, str]] = field(default_factory=list)

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


def merge_chat_result(kb: KB, npc: str, question: str, resp: dict[str, Any]) -> None:
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
    reply = str(resp.get('reply', '')) if isinstance(resp, dict) else ''
    kb.replies.append({'npc': npc, 'question': question, 'reply': reply})


def ask_once(sdk: SDK, kb: KB, npc: str, question: str, evidences: list[str]) -> bool:
    key = question + '|' + '/'.join(evidences)
    if key in kb.asked[npc]:
        return False
    kb.asked[npc].add(key)
    resp = sdk.request('chat', npc=npc, question=question, evidences=evidences)
    if isinstance(resp, dict):
        merge_chat_result(kb, npc, question, resp)
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
        return f'你见过“{name[:24]}”吗？这说明了什么？', [eid]
    return None


def explore_case(sdk: SDK, kb: KB) -> None:
    refresh_all(sdk, kb)
    total = 0
    last_stage = kb.stage
    opening = [
        '你眼中的受害者或失踪者是怎样的人？你和他或她是什么关系？',
        '请按时间顺序说明案发前后你的行动、位置、见过的人和异常情况。',
    ]
    for q in opening:
        for npc in choose_targets(kb):
            if ask_once(sdk, kb, npc, q, []):
                total += 1
        sync_marks_hint(sdk, kb)
        if kb.stage != last_stage:
            refresh_all(sdk, kb)
            last_stage = kb.stage

    followups = [
        '你和受害者或失踪者之间有没有矛盾、秘密、利益冲突或感情问题？',
        '如果要指出一个最可疑的人，你会怀疑谁？为什么？',
        '请解释目前与你有关、最容易被怀疑的一点。',
    ]
    for idx in range(3):
        targets = choose_targets(kb)
        for npc in targets:
            picked = choose_evidence_question(kb, npc)
            if picked and total < 28:
                if ask_once(sdk, kb, npc, picked[0], picked[1]):
                    total += 1
            if total >= 28:
                break
            q = followups[idx]
            if idx == 0 and kb.hint:
                q = f'关于当前提示“{kb.hint[:50]}”，你能补充什么？'
            if ask_once(sdk, kb, npc, q, []):
                total += 1
            if total >= 28:
                break
        sync_marks_hint(sdk, kb)
        if kb.stage != last_stage:
            refresh_all(sdk, kb)
            last_stage = kb.stage
        if total >= 28:
            break

    for npc in choose_targets(kb)[:3]:
        if ask_once(sdk, kb, npc, '如果让你直接判断，谁最可能是真凶？动机和手法分别是什么？', []):
            total += 1
    refresh_all(sdk, kb)


def split_sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r'[。！？!?\n]+', text) if s.strip()]


def pick_murderer(kb: KB) -> str:
    scores = {npc: 0 for npc in kb.npcs}
    corpora = []
    corpora.extend(item.get('content', '') for item in kb.testimony if isinstance(item, dict))
    corpora.extend(item.get('content', '') for item in kb.others if isinstance(item, dict))
    corpora.extend(item.get('reply', '') for item in kb.replies[-16:])
    for text in corpora:
        for npc in kb.npcs:
            if npc in text:
                scores[npc] += 1
        if '真凶' in text or '凶手' in text or '嫌疑' in text:
            for npc in kb.npcs:
                if npc in text:
                    scores[npc] += 3
    best = max(scores.items(), key=lambda kv: kv[1])[0] if scores else ''
    return best or (kb.npcs[0] if kb.npcs else '')


def pick_sentence(kb: KB, murderer: str, keywords: list[str], fallback: str) -> str:
    candidates: list[tuple[int, str]] = []
    texts = []
    texts.extend(item.get('reply', '') for item in kb.replies[-20:])
    texts.extend(item.get('content', '') for item in kb.testimony if isinstance(item, dict))
    texts.extend(item.get('content', '') for item in kb.others if isinstance(item, dict))
    for text in texts:
        for sent in split_sentences(text):
            score = 0
            if murderer and murderer in sent:
                score += 3
            for kw in keywords:
                if kw in sent:
                    score += 2
            if score > 0:
                candidates.append((score, sent))
    if not candidates:
        return fallback[:120]
    candidates.sort(key=lambda x: (-x[0], len(x[1])))
    return candidates[0][1][:180]


def final_answer(kb: KB) -> dict[str, str]:
    murderer = pick_murderer(kb)
    motivation = pick_sentence(
        kb,
        murderer,
        ['因为', '为了', '嫉妒', '报复', '竞争', '威胁', '秘密', '关系', '喜欢', '恨'],
        kb.hint or kb.background,
    )
    method = pick_sentence(
        kb,
        murderer,
        ['毒', '刀', '药', '水', '酒', '埋', '勒', '打', '伏击', '尸体', '面部', '凶器'],
        kb.hint or kb.background,
    )
    return {
        'murderer': murderer,
        'motivation': motivation,
        'method': method,
    }


def solve_case(sdk: SDK, case_index: int) -> bool:
    kb = KB()
    refresh_all(sdk, kb)
    if not kb.background and not kb.npcs:
        return False
    log(f'[game2-v6] case={case_index} stage={kb.stage} npcs={len(kb.npcs)}')
    explore_case(sdk, kb)
    answer = final_answer(kb)
    log(f"[game2-v6] answer case={case_index} murderer={answer['murderer']!r}")
    resp = sdk.request('answer', **answer)
    log(f'[game2-v6] answer_result case={case_index} resp={resp}')
    return True


def main() -> int:
    sdk = SDK()
    welcome = sdk._receive()
    log(f'[game2-v6] welcome={welcome}')
    case_index = 0
    while True:
        try:
            ok = solve_case(sdk, case_index)
        except EOFError:
            break
        except Exception as exc:
            log(f'[game2-v6] fatal case={case_index} exc={type(exc).__name__}: {exc}')
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
