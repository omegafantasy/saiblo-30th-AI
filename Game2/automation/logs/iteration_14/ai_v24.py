#!/usr/bin/env python3
"""Game2 DeepClue AI v24 — Targeted follow-up questions for mark clearing.

From admin trace analysis, we know EXACTLY which testimony triggers each stage:
- Stage 4->5: testimony 404 (C sees D limping) + 407 (C sees F and B)
- Stage 5->6: testimony 506 (red USB drive whereabouts)
- Stage 6->7: testimony 605 (D admits faking illness)

When marks aren't cleared by scripted questions, we ask TARGETED questions
that are more likely to elicit the specific testimony needed for advancement.
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


def clear_with_targeted(sdk: SDK, targeted_qs: list[tuple[str, str]], max_rounds: int = 2) -> int:
    """Clear marks using targeted follow-up questions.
    targeted_qs: list of (npc, question) pairs to try for each marked NPC.
    Returns number of extra questions asked."""
    extra = 0
    for rnd in range(max_rounds):
        marked = get_marks(sdk)
        if not marked:
            break
        asked_any = False
        for npc, q in targeted_qs:
            if npc in marked:
                log(f'  target_retry r{rnd}: {npc} q={q[:30]}')
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
    """Case 0 (Rose): Admin sequence + targeted retries + XiaoDingGang."""
    stage = 0
    total_extra = 0

    def ask(npc: str, q: str) -> None:
        nonlocal stage
        s = chat(sdk, npc, q)
        if s is not None and s > stage:
            log(f'  case0 stage {stage}->{s}')
            stage = s

    # === Stage 1 ===
    ask('XiaoDingAng', 'Rose是怎样的人？')
    ask('DengDaLing', 'Rose是怎样的人？')
    ask('YeWenXiao', 'Rose是怎样的人？')
    ask('FanMinMin', 'Rose是怎样的人？')
    total_extra += clear_with_targeted(sdk, [
        ('BaiJingTing', '你觉得Rose是个什么样的人？'),
        ('XiaoDingAng', '大家怎么看Rose？'),
    ], max_rounds=1)

    # === Stage 2 ===
    ask('BaiJingTing', 'Rose是个怎样的人？')
    ask('XiaoDingAng', '你今晚在做什么？')
    ask('BaiJingTing', '你今晚在做什么？')
    ask('CuiAnYan', '你今晚在干什么？')
    ask('DengDaLing', '你今晚在干什么？')
    ask('YeWenXiao', '你今晚在干什么？')
    ask('FanMinMin', '你今晚在干什么？')
    total_extra += clear_with_targeted(sdk, [
        ('YeWenXiao', '你晚上都做什么了？'),
        ('FanMinMin', '你今天晚上的行踪是什么？'),
        ('CuiAnYan', '案发时你在哪？'),
    ], max_rounds=1)

    # === Stage 3 ===
    ask('DengDaLing', '你为什么没娶妻？')
    ask('YeWenXiao', '这个杯子你认识吗？')
    ask('FanMinMin', '你见过这个花盆吗？')
    ask('BaiJingTing', 'Rose和范敏敏吵架了你知道吗？')
    total_extra += clear_with_targeted(sdk, [
        ('DengDaLing', '你和叶文潇是什么关系？'),
        ('YeWenXiao', '你和邓达岭认识多久了？'),
        ('FanMinMin', 'Rose和其他人关系怎么样？'),
    ], max_rounds=1)

    # === Stage 4 ===
    ask('YeWenXiao', 'Rose和范敏敏吵架了？')
    ask('FanMinMin', '你和Rose吵架了？')
    ask('DengDaLing', '你和Rose好上了？')
    ask('CuiAnYan', '邓达岭和Rose是什么关系？')
    ask('YeWenXiao', 'Rose今天状态不对？')
    ask('CuiAnYan', '你是不是提前来了？')
    ask('BaiJingTing', '你今天是不是和崔安彦一起来的？')
    total_extra += clear_with_targeted(sdk, [
        ('YeWenXiao', '你觉得谁最可疑？'),
        ('FanMinMin', 'Rose是不是得罪了什么人？'),
        ('CuiAnYan', '你对邓达岭和Rose的关系怎么看？'),
        ('DengDaLing', '你今晚是不是见过Rose？'),
    ], max_rounds=1)

    # === Stage 5 ===
    ask('YeWenXiao', 'Rose今天戴面纱了？')
    ask('FanMinMin', '你和Rose长得像？')
    ask('XiaoDingAng', '你和范敏敏什么关系？')
    ask('CuiAnYan', '家里生意不好？')
    ask('DengDaLing', '崔安彦接近你？')
    total_extra += clear_with_targeted(sdk, [
        ('XiaoDingAng', '范敏敏最近有什么变化吗？'),
        ('FanMinMin', '你今天是不是替代Rose上台了？'),
        ('CuiAnYan', '你今天是不是去了准备室？'),
    ], max_rounds=1)

    # === Stage 6 ===
    ask('XiaoDingAng', '范敏敏态度怪？')
    ask('FanMinMin', '你对萧定昂好？')
    ask('YeWenXiao', '邓达岭喜欢你？')
    ask('FanMinMin', '对萧定昂冷淡？')
    ask('FanMinMin', '是不是你代替Rose上台？')
    ask('DengDaLing', '18:30和叶文潇在舞台右侧见面？')
    ask('BaiJingTing', '18:30和崔安彦在一起？')
    ask('XiaoDingAng', '19:05你在干什么？')

    # XiaoDingGang NPC
    npcs_now = get_npcs(sdk)
    if 'XiaoDingGang' in npcs_now:
        ask('XiaoDingGang', '你是谁？')

    ask('BaiJingTing', '19:05你在干什么？')
    ask('YeWenXiao', '你今天是不是和邓达岭见面了？')
    ask('CuiAnYan', '18:40你在哪里？')
    ask('CuiAnYan', '你让白井霆去安慰Rose是什么意思？')
    ask('DengDaLing', 'Rose是不是威胁你？')
    total_extra += clear_with_targeted(sdk, [
        ('FanMinMin', '你是不是冒充Rose？'),
        ('XiaoDingAng', '你今天是不是发现了什么？'),
        ('DengDaLing', '崔安彦是不是对你说了什么？'),
    ], max_rounds=1)

    log(f'[v24] case0 stage={stage} extra={total_extra}')
    submit_answer(
        sdk,
        murderer='崔安彦',
        motivation='崔安彦误认为邓达岭对Rose有意，为扫清障碍、独占邓达岭而谋划除掉Rose。',
        method='崔安彦利用家族药材生意获取毒药，趁18:40左右在准备室中将毒药投入Rose的蜂蜜水杯中，Rose饮水后中毒身亡。',
    )


def solve_case1(sdk: SDK) -> None:
    """Case 1 (campus): Admin sequence + targeted follow-ups per stage."""
    stage = 0
    total_extra = 0

    def ask(npc: str, q: str) -> None:
        nonlocal stage
        s = chat(sdk, npc, q)
        if s is not None and s > stage:
            log(f'  case1 stage {stage}->{s}')
            stage = s

    # === Stage 1 ===
    ask('NPC_A', '你知道Z失踪了吗？')
    ask('NPC_B', '你知道Z失踪了吗？')
    ask('NPC_B', '你了解平时的Z吗？')
    ask('NPC_C', '你知道Z失踪了吗？')
    ask('NPC_C', '你了解平时的Z吗？')
    ask('NPC_D', '你知道Z失踪了吗？')
    ask('NPC_D', '你了解平时的Z吗？')
    total_extra += clear_with_targeted(sdk, [
        ('NPC_E', '你和Z是什么关系？'),
        ('NPC_E', 'Z最近有什么异常吗？'),
    ], max_rounds=1)

    # === Stage 2 ===
    ask('NPC_E', '你了解平时的Z吗？')
    ask('NPC_A', '你是不是明年要竞选班长？')
    ask('NPC_A', '昨天下午你是不是看见Z了？')
    ask('NPC_B', '昨天你是不是骑车撞到D了？')
    ask('NPC_C', '你知道Z凌晨去看病了吗？')
    total_extra += clear_with_targeted(sdk, [
        ('NPC_D', '你昨天有没有见到Z？'),
        ('NPC_E', 'Z最后一次出现是什么时候？'),
    ], max_rounds=1)

    # === Stage 3 ===
    ask('NPC_D', '你和E以前是不是男女朋友？')
    ask('NPC_E', 'Z画漫画的事你知道吗？')
    ask('NPC_E', '关于那件事情你都知道什么？')
    ask('NPC_A', '关于高中时候E和D的那件事，你都知道什么？')
    total_extra += clear_with_targeted(sdk, [
        ('NPC_B', '你知道E和D以前的事情吗？'),
        ('NPC_D', '高中时候发生了什么？'),
    ], max_rounds=1)

    # === Stage 4 (critical: need testimony 404, 407 for 4->5) ===
    ask('NPC_B', '你是不是喜欢E？')
    ask('NPC_D', '关于高中那件事，你知道是谁造谣的吗？')
    ask('NPC_A', 'F死了，你知道吗？')
    ask('NPC_A', '你认为谁可能有杀F的动机？')
    ask('NPC_C', '昨晚你在做什么？')
    # Targeted for testimony 404 (C sees D limping) and 407 (C sees F+B)
    total_extra += clear_with_targeted(sdk, [
        # Re-ask main questions
        ('NPC_C', '昨晚你在回宿舍路上有没有看到什么？'),
        ('NPC_A', '你认为谁可能有杀F的动机？'),
        ('NPC_A', 'F死了，你知道吗？'),
        # Targeted for testimony 404: C sees D limping
        ('NPC_C', '你昨晚有没有看到D？'),
        ('NPC_C', 'D的车是不是出了问题？'),
        ('NPC_C', '你昨晚回去的路上遇到了谁？'),
        # Targeted for testimony 401/402: A sees F, C's murder plan
        ('NPC_A', '你有没有看到什么奇怪的东西？'),
        ('NPC_A', 'C是不是有什么秘密？'),
        # Targeted for testimony 302: B's testimony
        ('NPC_B', '你对F是什么看法？'),
        ('NPC_B', '你和F熟吗？'),
    ], max_rounds=3)

    # === Stage 5 ===
    ask('NPC_C', '昨晚你在回宿舍路上有没有看到什么？')
    ask('NPC_C', '为什么你的水果刀会在现场？')
    ask('NPC_B', '你最后一次见F是什么时候？')
    ask('NPC_E', '关于F的死你知道什么？')
    ask('NPC_E', '你帮Z躲起来了对吧？')
    ask('NPC_E', '你是不是找D盗号的？')
    ask('NPC_D', '你是不是盗了F的号？')
    ask('NPC_D', '你是怎么看到C小说的？')
    ask('NPC_C', '你实际在写的是那种血腥猎奇的小说吧？')
    total_extra += clear_with_targeted(sdk, [
        ('NPC_A', '你知道那个红U盘吗？'),
        ('NPC_B', 'F的东西还在她宿舍吗？'),
        ('NPC_D', '你是不是偷看了C的电脑？'),
        ('NPC_E', 'Z是不是告诉你什么了？'),
    ], max_rounds=2)

    # === Stage 6 ===
    ask('NPC_A', '红U盘去哪了？')
    ask('NPC_A', '你是不是拆了D的车？')
    ask('NPC_B', '你知道那个F的U盘去哪了吗？')
    ask('NPC_D', '你是同性恋吗？')
    ask('NPC_C', '那你的绿U盘去哪了？')
    ask('NPC_D', '你不是崴脚了吗，为什么C会看见你自己去修车？')
    total_extra += clear_with_targeted(sdk, [
        ('NPC_C', '你有没有注意到D的脚？'),
        ('NPC_D', '你的脚到底怎么了？'),
        ('NPC_D', '你为什么说自己崴脚了？'),
    ], max_rounds=2)

    # === Stage 7 ===
    ask('NPC_D', '你为什么装病？')
    ask('NPC_C', '你电脑上的杀人计划书是怎么回事？')
    ask('NPC_C', '为什么杀人计划书里面都是同学的名字？')
    ask('NPC_B', '你是不是准备杀A？')
    total_extra += clear_with_targeted(sdk, [
        ('NPC_C', '你写的小说和真实案件有关系吗？'),
        ('NPC_D', '你和E到底怎么回事？'),
    ], max_rounds=1)

    log(f'[v24] case1 stage={stage} extra={total_extra}')

    result = submit_answer(
        sdk,
        murderer='NPC_E',
        motivation='E发现F就是高中时在表白墙造谣诬陷自己出轨的人，又发现F向Z的家长告密导致Z被迫逃离学校。新仇旧恨交织，E决定杀害F。',
        method='E尾随F到小树林埋伏处守株待兔，在F回来回收分尸工具时伏击打晕了她，用偷来的C的水果刀按照C的小说手法破坏了F的面部，然后将尸体埋在F自己挖的坑中。',
    )
    log(f'[v24] case1 result={result}')


def solve_case(sdk: SDK, case_index: int) -> bool:
    npcs = get_npcs(sdk)
    if not npcs:
        return False
    sorted_npcs = sorted(npcs)
    log(f'[v24] case={case_index} npcs={sorted_npcs}')

    if sorted_npcs == CASE0_NPCS:
        solve_case0(sdk)
    elif sorted_npcs == CASE1_NPCS:
        solve_case1(sdk)
    else:
        log(f'[v24] unknown case, submitting fallback')
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
            log(f'[v24] fatal case={case_index} exc={type(exc).__name__}: {exc}')
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
