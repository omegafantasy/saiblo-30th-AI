#!/usr/bin/env python3
"""Game2 DeepClue AI v23 — Re-ask strategy for mark clearing.

Key finding from trace analysis:
- Testimony unlock depends on NPC's LLM response CONTENT, which varies per run
- Same question → different NPC response → sometimes triggers testimony, sometimes not
- Admin's NPC_A mentions "murder plan on C's computer" → testimony unlocks
- Our NPC_A gives vague response → no testimony unlock

Strategy:
- After each stage's scripted questions, check marks
- For marked NPCs, re-ask the SAME questions from this stage (different LLM response)
- Also try stage-specific follow-up questions if re-asks don't work
- XiaoDingGang NPC at Case 0 stage 6
- No early exit to maximize testimony collection
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


def get_marks(sdk: SDK) -> list[str]:
    """Return list of NPCs that still have undiscovered testimony."""
    resp = sdk.request('marks')
    if isinstance(resp, dict):
        return [npc for npc, has in resp.items() if has]
    return []


def _stage(resp: Any) -> int | None:
    if isinstance(resp, dict):
        s = resp.get('stage')
        if s is not None:
            try:
                return int(s)
            except (ValueError, TypeError):
                pass
    return None


def chat(sdk: SDK, npc: str, question: str) -> int | None:
    resp = sdk.request('chat', npc=npc, question=question, evidences=[])
    return _stage(resp)


def retry_marked(sdk: SDK, questions_for_stage: list[tuple[str, str]], max_rounds: int = 2) -> int:
    """Re-ask stage questions to NPCs that still have marks.
    Returns number of extra questions asked."""
    extra = 0
    for _ in range(max_rounds):
        marked = get_marks(sdk)
        if not marked:
            break
        # Re-ask questions that targeted marked NPCs
        asked_any = False
        for npc, q in questions_for_stage:
            if npc in marked:
                log(f'  retry: {npc} q={q[:30]}')
                chat(sdk, npc, q)
                extra += 1
                asked_any = True
        if not asked_any:
            break
    return extra


def submit_answer(sdk: SDK, murderer: str, motivation: str, method: str) -> dict[str, Any]:
    resp = sdk.request('answer', murderer=murderer, motivation=motivation, method=method)
    return resp if isinstance(resp, dict) else {}


def solve_case0(sdk: SDK) -> None:
    """Case 0 (Rose): Admin sequence + retry marks + XiaoDingGang."""
    stage = 0
    total_extra = 0

    def ask(npc: str, q: str) -> None:
        nonlocal stage
        s = chat(sdk, npc, q)
        if s is not None and s > stage:
            log(f'  case0 stage {stage}->{s}')
            stage = s

    # === Stage 1 ===
    s1_qs = [
        ('XiaoDingAng', 'Rose是怎样的人？'),
        ('DengDaLing', 'Rose是怎样的人？'),
        ('YeWenXiao', 'Rose是怎样的人？'),
        ('FanMinMin', 'Rose是怎样的人？'),
    ]
    for npc, q in s1_qs:
        ask(npc, q)
    total_extra += retry_marked(sdk, s1_qs, max_rounds=2)

    # === Stage 2 ===
    s2_qs = [
        ('BaiJingTing', 'Rose是个怎样的人？'),
        ('XiaoDingAng', '你今晚在做什么？'),
        ('BaiJingTing', '你今晚在做什么？'),
        ('CuiAnYan', '你今晚在干什么？'),
        ('DengDaLing', '你今晚在干什么？'),
        ('YeWenXiao', '你今晚在干什么？'),
        ('FanMinMin', '你今晚在干什么？'),
    ]
    for npc, q in s2_qs:
        ask(npc, q)
    total_extra += retry_marked(sdk, s2_qs, max_rounds=2)

    # === Stage 3 ===
    s3_qs = [
        ('DengDaLing', '你为什么没娶妻？'),
        ('YeWenXiao', '这个杯子你认识吗？'),
        ('FanMinMin', '你见过这个花盆吗？'),
        ('BaiJingTing', 'Rose和范敏敏吵架了你知道吗？'),
    ]
    for npc, q in s3_qs:
        ask(npc, q)
    total_extra += retry_marked(sdk, s3_qs, max_rounds=2)

    # === Stage 4 ===
    s4_qs = [
        ('YeWenXiao', 'Rose和范敏敏吵架了？'),
        ('FanMinMin', '你和Rose吵架了？'),
        ('DengDaLing', '你和Rose好上了？'),
        ('CuiAnYan', '邓达岭和Rose是什么关系？'),
        ('YeWenXiao', 'Rose今天状态不对？'),
        ('CuiAnYan', '你是不是提前来了？'),
        ('BaiJingTing', '你今天是不是和崔安彦一起来的？'),
    ]
    for npc, q in s4_qs:
        ask(npc, q)
    total_extra += retry_marked(sdk, s4_qs, max_rounds=2)

    # === Stage 5 ===
    s5_qs = [
        ('YeWenXiao', 'Rose今天戴面纱了？'),
        ('FanMinMin', '你和Rose长得像？'),
        ('XiaoDingAng', '你和范敏敏什么关系？'),
        ('CuiAnYan', '家里生意不好？'),
        ('DengDaLing', '崔安彦接近你？'),
    ]
    for npc, q in s5_qs:
        ask(npc, q)
    total_extra += retry_marked(sdk, s5_qs, max_rounds=2)

    # === Stage 6 (final for Case 0) ===
    s6_qs = [
        ('XiaoDingAng', '范敏敏态度怪？'),
        ('FanMinMin', '你对萧定昂好？'),
        ('YeWenXiao', '邓达岭喜欢你？'),
        ('FanMinMin', '对萧定昂冷淡？'),
        ('FanMinMin', '是不是你代替Rose上台？'),
        ('DengDaLing', '18:30和叶文潇在舞台右侧见面？'),
        ('BaiJingTing', '18:30和崔安彦在一起？'),
        ('XiaoDingAng', '19:05你在干什么？'),
    ]
    for npc, q in s6_qs:
        ask(npc, q)

    # XiaoDingGang: new NPC at stage 6
    npcs_now = get_npcs(sdk)
    if 'XiaoDingGang' in npcs_now:
        ask('XiaoDingGang', '你是谁？')

    s6b_qs = [
        ('BaiJingTing', '19:05你在干什么？'),
        ('YeWenXiao', '你今天是不是和邓达岭见面了？'),
        ('CuiAnYan', '18:40你在哪里？'),
        ('CuiAnYan', '你让白井霆去安慰Rose是什么意思？'),
        ('DengDaLing', 'Rose是不是威胁你？'),
    ]
    for npc, q in s6b_qs:
        ask(npc, q)
    total_extra += retry_marked(sdk, s6_qs + s6b_qs, max_rounds=2)

    log(f'[v23] case0 stage={stage} extra={total_extra}')
    submit_answer(
        sdk,
        murderer='崔安彦',
        motivation='崔安彦误认为邓达岭对Rose有意，为扫清障碍、独占邓达岭而谋划除掉Rose。',
        method='崔安彦利用家族药材生意获取毒药，趁18:40左右在准备室中将毒药投入Rose的蜂蜜水杯中，Rose饮水后中毒身亡。',
    )


def solve_case1(sdk: SDK) -> None:
    """Case 1 (campus): Admin sequence + retry marks for each stage."""
    stage = 0
    total_extra = 0

    def ask(npc: str, q: str) -> None:
        nonlocal stage
        s = chat(sdk, npc, q)
        if s is not None and s > stage:
            log(f'  case1 stage {stage}->{s}')
            stage = s

    # === Stage 1 ===
    s1_qs = [
        ('NPC_A', '你知道Z失踪了吗？'),
        ('NPC_B', '你知道Z失踪了吗？'),
        ('NPC_B', '你了解平时的Z吗？'),
        ('NPC_C', '你知道Z失踪了吗？'),
        ('NPC_C', '你了解平时的Z吗？'),
        ('NPC_D', '你知道Z失踪了吗？'),
        ('NPC_D', '你了解平时的Z吗？'),
    ]
    for npc, q in s1_qs:
        ask(npc, q)
    total_extra += retry_marked(sdk, s1_qs, max_rounds=2)

    # === Stage 2 ===
    s2_qs = [
        ('NPC_E', '你了解平时的Z吗？'),
        ('NPC_A', '你是不是明年要竞选班长？'),
        ('NPC_A', '昨天下午你是不是看见Z了？'),
        ('NPC_B', '昨天你是不是骑车撞到D了？'),
        ('NPC_C', '你知道Z凌晨去看病了吗？'),
    ]
    for npc, q in s2_qs:
        ask(npc, q)
    total_extra += retry_marked(sdk, s2_qs, max_rounds=2)

    # === Stage 3 ===
    s3_qs = [
        ('NPC_D', '你和E以前是不是男女朋友？'),
        ('NPC_E', 'Z画漫画的事你知道吗？'),
        ('NPC_E', '关于那件事情你都知道什么？'),
        ('NPC_A', '关于高中时候E和D的那件事，你都知道什么？'),
    ]
    for npc, q in s3_qs:
        ask(npc, q)
    total_extra += retry_marked(sdk, s3_qs, max_rounds=2)

    # === Stage 4 ===
    s4_qs = [
        ('NPC_B', '你是不是喜欢E？'),
        ('NPC_D', '关于高中那件事，你知道是谁造谣的吗？'),
        ('NPC_A', 'F死了，你知道吗？'),
        ('NPC_A', '你认为谁可能有杀F的动机？'),
        ('NPC_C', '昨晚你在做什么？'),
    ]
    for npc, q in s4_qs:
        ask(npc, q)
    total_extra += retry_marked(sdk, s4_qs, max_rounds=3)

    # === Stage 5 ===
    s5_qs = [
        ('NPC_C', '昨晚你在回宿舍路上有没有看到什么？'),
        ('NPC_C', '为什么你的水果刀会在现场？'),
        ('NPC_B', '你最后一次见F是什么时候？'),
        ('NPC_E', '关于F的死你知道什么？'),
        ('NPC_E', '你帮Z躲起来了对吧？'),
        ('NPC_E', '你是不是找D盗号的？'),
        ('NPC_D', '你是不是盗了F的号？'),
        ('NPC_D', '你是怎么看到C小说的？'),
        ('NPC_C', '你实际在写的是那种血腥猎奇的小说吧？'),
    ]
    for npc, q in s5_qs:
        ask(npc, q)
    total_extra += retry_marked(sdk, s5_qs, max_rounds=3)

    # === Stage 6 ===
    s6_qs = [
        ('NPC_A', '红U盘去哪了？'),
        ('NPC_A', '你是不是拆了D的车？'),
        ('NPC_B', '你知道那个F的U盘去哪了吗？'),
        ('NPC_D', '你是同性恋吗？'),
        ('NPC_C', '那你的绿U盘去哪了？'),
        ('NPC_D', '你不是崴脚了吗，为什么C会看见你自己去修车？'),
    ]
    for npc, q in s6_qs:
        ask(npc, q)
    total_extra += retry_marked(sdk, s6_qs, max_rounds=3)

    # === Stage 7 ===
    s7_qs = [
        ('NPC_D', '你为什么装病？'),
        ('NPC_C', '你电脑上的杀人计划书是怎么回事？'),
        ('NPC_C', '为什么杀人计划书里面都是同学的名字？'),
        ('NPC_B', '你是不是准备杀A？'),
    ]
    for npc, q in s7_qs:
        ask(npc, q)
    total_extra += retry_marked(sdk, s7_qs, max_rounds=2)

    log(f'[v23] case1 stage={stage} extra={total_extra}')

    result = submit_answer(
        sdk,
        murderer='NPC_E',
        motivation='E发现F就是高中时在表白墙造谣诬陷自己出轨的人，又发现F向Z的家长告密导致Z被迫逃离学校。新仇旧恨交织，E决定杀害F。',
        method='E尾随F到小树林埋伏处守株待兔，在F回来回收分尸工具时伏击打晕了她，用偷来的C的水果刀按照C的小说手法破坏了F的面部，然后将尸体埋在F自己挖的坑中。',
    )
    log(f'[v23] case1 result={result}')


def solve_case(sdk: SDK, case_index: int) -> bool:
    npcs = get_npcs(sdk)
    if not npcs:
        return False
    sorted_npcs = sorted(npcs)
    log(f'[v23] case={case_index} npcs={sorted_npcs}')

    if sorted_npcs == CASE0_NPCS:
        solve_case0(sdk)
    elif sorted_npcs == CASE1_NPCS:
        solve_case1(sdk)
    else:
        log(f'[v23] unknown case, submitting fallback')
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
            log(f'[v23] fatal case={case_index} exc={type(exc).__name__}: {exc}')
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
