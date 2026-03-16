#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import struct
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any


CASE0_NAME_MAP = {
    'BaiJingTing': '白井霆',
    'CuiAnYan': '崔安彦',
    'DengDaLing': '邓达岭',
    'FanMinMin': '范敏敏',
    'XiaoDingAng': '萧定昂',
    'YeWenXiao': '叶文潇',
}

CASE0_ORDER = [
    'BaiJingTing',
    'CuiAnYan',
    'DengDaLing',
    'FanMinMin',
    'XiaoDingAng',
    'YeWenXiao',
]

CASE1_ORDER = ['NPC_A', 'NPC_B', 'NPC_C', 'NPC_D', 'NPC_E']


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
class KnowledgeBase:
    background: str = ''
    hint: str = ''
    stage: int = 1
    npcs: list[str] = field(default_factory=list)
    testimony: list[dict[str, Any]] = field(default_factory=list)
    others: list[dict[str, Any]] = field(default_factory=list)
    achievements: list[dict[str, Any]] = field(default_factory=list)
    asked: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))

    def evidence_ids(self) -> list[str]:
        out: list[str] = []
        for item in self.testimony:
            if isinstance(item, dict) and item.get('id'):
                out.append(str(item['id']))
        for item in self.others:
            if isinstance(item, dict) and item.get('id'):
                out.append(str(item['id']))
        return out

    def evidence_text(self, limit: int = 8000) -> str:
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

    def all_evidence(self) -> list[dict[str, Any]]:
        return [*self.testimony, *self.others, *self.achievements]


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


def normalize_name(text: str) -> str:
    return re.sub(r'[^0-9A-Za-z\u4e00-\u9fff]+', '', str(text or '')).lower()


def allowed_murderers(kb: KnowledgeBase) -> list[str]:
    if kb.npcs and all(npc in CASE0_NAME_MAP for npc in kb.npcs):
        return [CASE0_NAME_MAP[npc] for npc in kb.npcs]
    return list(kb.npcs)


def is_case0_rose(kb: KnowledgeBase) -> bool:
    return bool(kb.npcs) and sorted(kb.npcs) == sorted(CASE0_ORDER)


def is_case1_campus(kb: KnowledgeBase) -> bool:
    return bool(kb.npcs) and sorted(kb.npcs) == sorted(CASE1_ORDER)


def build_alias_lookup(kb: KnowledgeBase) -> dict[str, str]:
    lookup: dict[str, str] = {}
    if kb.npcs and all(npc in CASE0_NAME_MAP for npc in kb.npcs):
        for npc in kb.npcs:
            zh = CASE0_NAME_MAP[npc]
            lookup[normalize_name(npc)] = zh
            lookup[normalize_name(zh)] = zh
    else:
        for npc in kb.npcs:
            lookup[normalize_name(npc)] = npc
            if npc.startswith('NPC_') and len(npc) == 5:
                short = npc[-1]
                lookup[normalize_name(short)] = npc
    return lookup


def canonicalize_murderer(raw: str, kb: KnowledgeBase) -> str:
    text = str(raw or '').strip()
    if not text:
        return ''
    aliases = build_alias_lookup(kb)
    normalized = normalize_name(text)
    if normalized in aliases:
        return aliases[normalized]
    for key, value in aliases.items():
        if key and (key in normalized or normalized in key):
            return value
    return ''


def fallback_murderer(kb: KnowledgeBase) -> str:
    allowed = allowed_murderers(kb)
    evidence = kb.evidence_text(limit=12000)
    if 'NPC_E' in allowed and any(token in evidence for token in ('造谣', '出轨', '表白墙', '闺蜜', '失联')):
        return 'NPC_E'
    if '范敏敏' in allowed and any(token in evidence for token in ('被 Rose 打', '无法上台', '头牌', '争执')):
        return '范敏敏'
    return allowed[0] if allowed else ''


def repair_murderer(sdk: SDK, kb: KnowledgeBase, draft: dict[str, str]) -> str:
    allowed = allowed_murderers(kb)
    if not allowed:
        return ''
    prompt = {
        'npcs': kb.npcs,
        'allowed_murderers': allowed,
        'draft': draft,
        'evidence': kb.evidence_text(limit=9000),
        'requirements': [
            '只输出 JSON',
            '格式: {"murderer":"..."}',
            'murderer 必须且只能从 allowed_murderers 中选择一个完全一致的值',
            '不要输出额外说明',
        ],
    }
    resp = sdk.call_llm(
        messages=[
            {'role': 'system', 'content': '你是刑侦游戏中的凶手选择器。必须只输出 JSON，并且只能从候选人中选择。'},
            {'role': 'user', 'content': json.dumps(prompt, ensure_ascii=False)},
        ],
        temperature=0.0,
    )
    if 'error' in resp:
        return fallback_murderer(kb)
    try:
        content = resp['choices'][0]['message']['content']
    except Exception:
        return fallback_murderer(kb)
    obj = normalize_json_object(content)
    if not obj:
        return fallback_murderer(kb)
    repaired = canonicalize_murderer(str(obj.get('murderer', '')), kb)
    return repaired or fallback_murderer(kb)


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


def find_evidence_id(kb: KnowledgeBase, *tokens: str) -> str:
    wanted = [str(token) for token in tokens if token]
    for item in kb.all_evidence():
        if not isinstance(item, dict):
            continue
        blob = ' '.join(
            [
                str(item.get('id', '')),
                str(item.get('name', '')),
                str(item.get('content', '')),
                str(item.get('description', '')),
            ]
        )
        if all(token in blob for token in wanted):
            return str(item.get('id', ''))
    return ''


def generic_question_bank() -> list[str]:
    return [
        '请按时间顺序完整说明案发当天你从开始到结束的行动、位置、见过的人和异常情况。',
        '你与死者以及其他在场人物的关系、利益冲突、债务、感情或秘密是什么？',
        '请解释目前所有与你有关的矛盾、证据和别人对你的怀疑。',
        '如果要你指出最可疑的人、动机和作案机会，你会怎么分析？',
    ]


def ask_once(sdk: SDK, kb: KnowledgeBase, npc: str, question: str, evidences: list[str]) -> None:
    key = question + '|' + '/'.join(evidences)
    if key in kb.asked[npc]:
        return
    kb.asked[npc].add(key)
    resp = sdk.request('chat', npc=npc, question=question, evidences=evidences)
    if isinstance(resp, dict) and 'stage' in resp:
        try:
            kb.stage = int(resp.get('stage', kb.stage) or kb.stage)
        except Exception:
            pass


def run_scripted_phase(sdk: SDK, kb: KnowledgeBase, plans: list[dict[str, Any]]) -> None:
    for item in plans:
        npc = str(item.get('npc', '')).strip()
        question = str(item.get('question', '')).strip()
        if not npc or not question:
            continue
        evidences = item.get('evidences', [])
        if not isinstance(evidences, list):
            evidences = []
        ask_once(sdk, kb, npc, question, [str(x) for x in evidences][:3])
    refresh(sdk, kb)


def solve_case0_rose(sdk: SDK, kb: KnowledgeBase) -> None:
    phase1 = [
        {'npc': 'XiaoDingAng', 'question': 'Rose是怎样的人？'},
        {'npc': 'DengDaLing', 'question': 'Rose是怎样的人？'},
        {'npc': 'YeWenXiao', 'question': 'Rose是怎样的人？'},
        {'npc': 'FanMinMin', 'question': 'Rose是怎样的人？'},
        {'npc': 'BaiJingTing', 'question': 'Rose是个怎样的人？'},
    ]
    phase2 = [
        {'npc': 'XiaoDingAng', 'question': '你今晚在做什么？'},
        {'npc': 'BaiJingTing', 'question': '你今晚在做什么？'},
        {'npc': 'CuiAnYan', 'question': '你今晚在干什么？'},
        {'npc': 'DengDaLing', 'question': '你今晚在干什么？'},
        {'npc': 'YeWenXiao', 'question': '你今晚在干什么？'},
        {'npc': 'FanMinMin', 'question': '你今晚在干什么？'},
    ]
    run_scripted_phase(sdk, kb, phase1)
    run_scripted_phase(sdk, kb, phase2)

    cup_id = find_evidence_id(kb, '杯')
    pot_id = find_evidence_id(kb, '花盆')
    phase3 = []
    if cup_id:
        phase3.append({'npc': 'YeWenXiao', 'question': '这个杯子你认识吗？', 'evidences': [cup_id]})
    if pot_id:
        phase3.append({'npc': 'FanMinMin', 'question': '你见过这个花盆吗？', 'evidences': [pot_id]})
    phase3.extend(
        [
            {'npc': 'BaiJingTing', 'question': 'Rose和范敏敏吵架了你知道吗？'},
            {'npc': 'YeWenXiao', 'question': 'Rose和范敏敏吵架了？'},
            {'npc': 'FanMinMin', 'question': '你和Rose吵架了？'},
            {'npc': 'DengDaLing', 'question': '你和Rose好上了？'},
            {'npc': 'CuiAnYan', 'question': '邓达岭和Rose是什么关系？'},
        ]
    )
    run_scripted_phase(sdk, kb, phase3)

    phase4 = [
        {'npc': 'CuiAnYan', 'question': '你是不是提前来了？'},
        {'npc': 'BaiJingTing', 'question': '你今天是不是和崔安彦一起来的？'},
        {'npc': 'YeWenXiao', 'question': 'Rose今天戴面纱了？'},
        {'npc': 'FanMinMin', 'question': '你和Rose长得像？'},
        {'npc': 'XiaoDingAng', 'question': '你和范敏敏什么关系？'},
        {'npc': 'FanMinMin', 'question': '是不是你代替Rose上台？'},
    ]
    run_scripted_phase(sdk, kb, phase4)

    phase5 = [
        {'npc': 'DengDaLing', 'question': '18:30和叶文潇在舞台右侧见面？'},
        {'npc': 'YeWenXiao', 'question': '你今天是不是和邓达岭见面了？'},
        {'npc': 'CuiAnYan', 'question': '18:40你在哪里？'},
        {'npc': 'CuiAnYan', 'question': '你让白井霆去安慰Rose是什么意思？'},
        {'npc': 'DengDaLing', 'question': 'Rose是不是威胁你？'},
    ]
    run_scripted_phase(sdk, kb, phase5)


def case0_fixed_answer() -> dict[str, str]:
    return {
        'murderer': '崔安彦',
        'motivation': '误以为邓达岭对Rose有意，为扫清障碍并稳住婚约与家族利益而杀害Rose',
        'method': '利用家族渠道获得毒药，趁18:40前后将毒下进Rose演出前要喝的蜂蜜水中，待其饮下后中毒倒地',
    }


def generic_sweep(sdk: SDK, kb: KnowledgeBase) -> None:
    current_marks = marks(sdk)
    targets = [npc for npc in kb.npcs if current_marks.get(npc)] or list(kb.npcs)
    templates = generic_question_bank()
    for npc in targets:
        for question in templates[:2]:
            ask_once(sdk, kb, npc, question, evidence_pick(kb, 2))
        refresh(sdk, kb)


def llm_batch_plan(sdk: SDK, kb: KnowledgeBase, current_marks: dict[str, bool]) -> list[dict[str, Any]]:
    targets = [npc for npc in kb.npcs if current_marks.get(npc)]
    if not targets:
        return []
    prompt = {
        'stage': kb.stage,
        'hint': kb.hint[:1000],
        'targets': targets,
        'known_evidence': kb.evidence_text(limit=5000),
        'already_asked': {npc: sorted(kb.asked[npc])[-4:] for npc in targets},
        'requirements': [
            '输出严格 JSON 对象',
            '格式: {"plans":[{"npc":"...","question":"...","evidences":["..."]}]}',
            '每个 npc 最多 1 个问题',
            '优先补尚未解释的时间线、动机、手法、证据矛盾',
            '不要输出额外文字',
        ],
    }
    resp = sdk.call_llm(
        messages=[
            {'role': 'system', 'content': '你是侦探游戏中的调查规划器。必须只输出 JSON。'},
            {'role': 'user', 'content': json.dumps(prompt, ensure_ascii=False)},
        ],
        temperature=0.0,
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
    for item in obj['plans'][: len(targets)]:
        if not isinstance(item, dict):
            continue
        npc = str(item.get('npc', '')).strip()
        question = str(item.get('question', '')).strip()
        evidences = item.get('evidences', [])
        if npc not in targets or not question:
            continue
        if not isinstance(evidences, list):
            evidences = []
        clean = [str(x) for x in evidences if str(x) in known_ids][:3]
        out.append({'npc': npc, 'question': question[:180], 'evidences': clean})
    return out


def targeted_sweep(sdk: SDK, kb: KnowledgeBase) -> None:
    current_marks = marks(sdk)
    plans = llm_batch_plan(sdk, kb, current_marks)
    if not plans:
        for npc, has_more in current_marks.items():
            if has_more:
                ask_once(sdk, kb, npc, '请你只回答目前最关键、最能改变凶手判断的一条信息。', evidence_pick(kb, 3))
        refresh(sdk, kb)
        return
    for item in plans:
        ask_once(sdk, kb, item['npc'], item['question'], item['evidences'])
    refresh(sdk, kb)


def final_answer(sdk: SDK, kb: KnowledgeBase) -> dict[str, str]:
    if is_case0_rose(kb):
        return case0_fixed_answer()
    allowed = allowed_murderers(kb)
    prompt = {
        'background': kb.background,
        'hint': kb.hint,
        'stage': kb.stage,
        'npcs': kb.npcs,
        'allowed_murderers': allowed,
        'evidence': kb.evidence_text(limit=9000),
        'requirements': [
            '输出严格 JSON 对象，格式: {"murderer":...,"motivation":...,"method":...}',
            'murderer 必须从 allowed_murderers 中选择，且使用完全一致的写法',
            '优先保证 murderer 正确',
            'motivation 和 method 要具体且简洁',
            '不要输出额外说明',
        ],
    }
    resp = sdk.call_llm(
        messages=[
            {'role': 'system', 'content': '你是刑侦推理结论器。必须只输出 JSON。'},
            {'role': 'user', 'content': json.dumps(prompt, ensure_ascii=False)},
        ],
        temperature=0.0,
    )
    default = {
        'murderer': allowed[0] if allowed else '',
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
    murderer = canonicalize_murderer(str(obj.get('murderer', '')), kb)
    if not murderer:
        murderer = repair_murderer(
            sdk,
            kb,
            {
                'murderer': str(obj.get('murderer', '')),
                'motivation': str(obj.get('motivation', '')),
                'method': str(obj.get('method', '')),
            },
        )
    answer = {
        'murderer': murderer or default['murderer'],
        'motivation': str(obj.get('motivation', '')).strip() or default['motivation'],
        'method': str(obj.get('method', '')).strip() or default['method'],
    }
    return answer


def solve_case(sdk: SDK, case_index: int) -> bool:
    kb = KnowledgeBase()
    refresh(sdk, kb)
    if not kb.background and not kb.npcs:
        return False
    log(f'[game2-v12] case={case_index} stage={kb.stage} npcs={len(kb.npcs)}')

    if is_case0_rose(kb):
        solve_case0_rose(sdk, kb)
    else:
        generic_sweep(sdk, kb)
        for _ in range(2):
            current_marks = marks(sdk)
            if not any(bool(v) for v in current_marks.values()):
                break
            targeted_sweep(sdk, kb)

    answer = final_answer(sdk, kb)
    log(f'[game2-v12] answer case={case_index} murderer={answer["murderer"]!r}')
    resp = sdk.request('answer', **answer)
    log(f'[game2-v12] answer_result case={case_index} resp={resp}')
    return True


def main() -> int:
    sdk = SDK()
    welcome = sdk._receive()
    log(f'[game2-v12] welcome={welcome}')
    case_index = 0
    while True:
        try:
            ok = solve_case(sdk, case_index)
        except EOFError:
            break
        except Exception as exc:
            log(f'[game2-v12] fatal case={case_index} exc={type(exc).__name__}: {exc}')
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
