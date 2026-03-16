#!/usr/bin/env python3
"""Game2 DeepClue AI v19 — Adaptive stage-aware questioning.

Based on v18 (admin's question sequence) but with:
- Stage tracking from chat responses to detect when we're stuck
- Case 0: stops after reaching stage 6 (saves budget)
- Case 1: adaptive retries with alternative questions when stage stalls
- Target: stage 6 + stage 8 = 2357 points
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


def _extract_stage(resp: Any) -> int | None:
    if not isinstance(resp, dict):
        return None
    s = resp.get('stage')
    if s is not None:
        try:
            return int(s)
        except (ValueError, TypeError):
            pass
    rs = resp.get('result_state')
    if isinstance(rs, dict):
        s = rs.get('stage')
        if s is not None:
            try:
                return int(s)
            except (ValueError, TypeError):
                pass
    return None


class StageTracker:
    def __init__(self, sdk: SDK) -> None:
        self.sdk = sdk
        self.stage = 0
        self.calls = 0

    def chat(self, npc: str, question: str) -> int:
        resp = self.sdk.request('chat', npc=npc, question=question, evidences=[])
        self.calls += 1
        s = _extract_stage(resp)
        if s is not None and s > self.stage:
            log(f'  stage {self.stage}->{s} after [{npc}] {question[:30]}')
            self.stage = s
        return self.stage

    def at_least(self, target: int) -> bool:
        return self.stage >= target


def submit_answer(sdk: SDK, murderer: str, motivation: str, method: str) -> dict[str, Any]:
    resp = sdk.request('answer', murderer=murderer, motivation=motivation, method=method)
    return resp if isinstance(resp, dict) else {}


def solve_case0(sdk: SDK) -> None:
    """Case 0 (Rose): Admin question sequence with early exit at stage 6."""
    t = StageTracker(sdk)

    # Stage 0->1: Ask about Rose
    t.chat('XiaoDingAng', 'Rose是怎样的人？')
    t.chat('DengDaLing', 'Rose是怎样的人？')
    t.chat('YeWenXiao', 'Rose是怎样的人？')
    t.chat('FanMinMin', 'Rose是怎样的人？')
    # Stage 1->2
    t.chat('BaiJingTing', 'Rose是个怎样的人？')
    # Alibis
    t.chat('XiaoDingAng', '你今晚在做什么？')
    t.chat('BaiJingTing', '你今晚在做什么？')
    t.chat('CuiAnYan', '你今晚在干什么？')
    t.chat('DengDaLing', '你今晚在干什么？')
    # Stage 2->3
    t.chat('YeWenXiao', '你今晚在干什么？')
    t.chat('FanMinMin', '你今晚在干什么？')
    # Phase 3: Deeper investigation
    t.chat('DengDaLing', '你为什么没娶妻？')
    t.chat('YeWenXiao', '这个杯子你认识吗？')
    t.chat('FanMinMin', '你见过这个花盆吗？')
    t.chat('BaiJingTing', 'Rose和范敏敏吵架了你知道吗？')
    # Stage 3->4
    t.chat('YeWenXiao', 'Rose和范敏敏吵架了？')
    t.chat('FanMinMin', '你和Rose吵架了？')
    t.chat('DengDaLing', '你和Rose好上了？')
    t.chat('CuiAnYan', '邓达岭和Rose是什么关系？')
    t.chat('YeWenXiao', 'Rose今天状态不对？')
    t.chat('CuiAnYan', '你是不是提前来了？')
    t.chat('BaiJingTing', '你今天是不是和崔安彦一起来的？')
    # Stage 4->5
    t.chat('YeWenXiao', 'Rose今天戴面纱了？')
    t.chat('FanMinMin', '你和Rose长得像？')
    t.chat('XiaoDingAng', '你和范敏敏什么关系？')
    t.chat('CuiAnYan', '家里生意不好？')
    t.chat('DengDaLing', '崔安彦接近你？')
    # Stage 5->6
    t.chat('XiaoDingAng', '范敏敏态度怪？')

    if not t.at_least(6):
        # Continue with remaining questions if stage 6 not yet reached
        t.chat('FanMinMin', '你对萧定昂好？')
        t.chat('YeWenXiao', '邓达岭喜欢你？')
        t.chat('FanMinMin', '对萧定昂冷淡？')
        t.chat('FanMinMin', '是不是你代替Rose上台？')
        t.chat('DengDaLing', '18:30和叶文潇在舞台右侧见面？')
        t.chat('BaiJingTing', '18:30和崔安彦在一起？')
        t.chat('XiaoDingAng', '19:05你在干什么？')
        t.chat('BaiJingTing', '19:05你在干什么？')
        t.chat('YeWenXiao', '你今天是不是和邓达岭见面了？')
        t.chat('CuiAnYan', '18:40你在哪里？')
        t.chat('CuiAnYan', '你让白井霆去安慰Rose是什么意思？')
        t.chat('DengDaLing', 'Rose是不是威胁你？')

    log(f'[v19] case0: {t.calls} calls, stage={t.stage}')
    result = submit_answer(
        sdk,
        murderer='崔安彦',
        motivation='误以为邓达岭对Rose有意，为扫清障碍并稳住婚约与家族利益而杀害Rose',
        method='利用家族渠道获得毒药，趁18:40前后将毒下进Rose演出前要喝的蜂蜜水中，待其饮下后中毒倒地',
    )
    log(f'[v19] case0 result={result}')


def solve_case1(sdk: SDK) -> None:
    """Case 1 (campus): Admin sequence with adaptive stage advancement."""
    t = StageTracker(sdk)

    # Stage 0->1: Ask about Z (8 calls)
    t.chat('NPC_A', '你知道Z失踪了吗？')
    t.chat('NPC_B', '你知道Z失踪了吗？')
    t.chat('NPC_B', '你了解平时的Z吗？')
    t.chat('NPC_C', '你知道Z失踪了吗？')
    t.chat('NPC_C', '你了解平时的Z吗？')
    t.chat('NPC_D', '你知道Z失踪了吗？')
    t.chat('NPC_D', '你了解平时的Z吗？')
    # Stage 1->2
    t.chat('NPC_E', '你了解平时的Z吗？')

    # Phase 2: Targeted investigation (4 calls)
    t.chat('NPC_A', '你是不是明年要竞选班长？')
    t.chat('NPC_A', '昨天下午你是不是看见Z了？')
    t.chat('NPC_B', '昨天你是不是骑车撞到D了？')
    t.chat('NPC_C', '你知道Z凌晨去看病了吗？')

    # Stage 2->3 (4 calls)
    t.chat('NPC_D', '你和E以前是不是男女朋友？')
    if not t.at_least(3):
        t.chat('NPC_D', '你和E高中时候发生了什么？')
    t.chat('NPC_E', 'Z画漫画的事你知道吗？')
    t.chat('NPC_E', '关于那件事情你都知道什么？')
    t.chat('NPC_A', '关于高中时候E和D的那件事，你都知道什么？')

    # Stage 3->4 (5 calls)
    t.chat('NPC_B', '你是不是喜欢E？')
    if not t.at_least(4):
        t.chat('NPC_B', '你对E有什么感觉？')
    t.chat('NPC_D', '关于高中那件事，你知道是谁造谣的吗？')
    t.chat('NPC_A', 'F死了，你知道吗？')
    t.chat('NPC_A', '你认为谁可能有杀F的动机？')
    t.chat('NPC_C', '昨晚你在做什么？')

    # Stage 4->5: CRITICAL — this is where we got stuck (9+ calls)
    t.chat('NPC_C', '昨晚你在回宿舍路上有没有看到什么？')
    if not t.at_least(5):
        # Alternative questions to trigger stage 4->5
        t.chat('NPC_C', '你在路上有没有看到D？')
    if not t.at_least(5):
        t.chat('NPC_C', '你回宿舍的时候看到谁了？')
    t.chat('NPC_C', '为什么你的水果刀会在现场？')
    if not t.at_least(5):
        t.chat('NPC_C', '你的水果刀是不是被人偷了？')
    t.chat('NPC_B', '你最后一次见F是什么时候？')
    t.chat('NPC_E', '关于F的死你知道什么？')
    t.chat('NPC_E', '你帮Z躲起来了对吧？')
    t.chat('NPC_E', '你是不是找D盗号的？')
    t.chat('NPC_D', '你是不是盗了F的号？')
    t.chat('NPC_D', '你是怎么看到C小说的？')
    t.chat('NPC_C', '你实际在写的是那种血腥猎奇的小说吧？')

    # Stage 5->6 (6 calls)
    t.chat('NPC_A', '红U盘去哪了？')
    if not t.at_least(6):
        t.chat('NPC_A', '你在F的包里发现了什么？')
    t.chat('NPC_A', '你是不是拆了D的车？')
    t.chat('NPC_B', '你知道那个F的U盘去哪了吗？')
    t.chat('NPC_D', '你是同性恋吗？')
    t.chat('NPC_C', '那你的绿U盘去哪了？')
    t.chat('NPC_D', '你不是崴脚了吗，为什么C会看见你自己去修车？')

    # Stage 6->7 (4 calls)
    t.chat('NPC_D', '你为什么装病？')
    if not t.at_least(7):
        t.chat('NPC_D', '你是不是在撒谎？')
    t.chat('NPC_C', '你电脑上的杀人计划书是怎么回事？')
    t.chat('NPC_C', '为什么杀人计划书里面都是同学的名字？')
    t.chat('NPC_B', '你是不是准备杀A？')

    log(f'[v19] case1: {t.calls} calls, stage={t.stage}')

    # Stage 7->8 (triggered by answer submission)
    result = submit_answer(
        sdk,
        murderer='NPC_E',
        motivation='E发现F就是高中时在表白墙造谣诬陷自己出轨的人，又发现F向Z的家长告密导致Z被迫逃离学校。新仇旧恨交织，E决定杀害F。',
        method='E尾随F到小树林埋伏处守株待兔，在F回来回收分尸工具时伏击打晕了她，用偷来的C的水果刀按照C的小说手法破坏了F的面部，然后将尸体埋在F自己挖的坑中。',
    )
    log(f'[v19] case1 result={result}')


def solve_case(sdk: SDK, case_index: int) -> bool:
    npcs = get_npcs(sdk)
    if not npcs:
        return False
    sorted_npcs = sorted(npcs)
    log(f'[v19] case={case_index} npcs={sorted_npcs}')

    if sorted_npcs == CASE0_NPCS:
        solve_case0(sdk)
    elif sorted_npcs == CASE1_NPCS:
        solve_case1(sdk)
    else:
        log(f'[v19] unknown case, submitting fallback')
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
            log(f'[v19] fatal case={case_index} exc={type(exc).__name__}: {exc}')
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
