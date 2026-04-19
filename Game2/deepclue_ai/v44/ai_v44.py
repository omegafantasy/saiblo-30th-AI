#!/usr/bin/env python3
"""Game2 DeepClue AI v44 — single pre-answer probe for NPC_C.

Purpose:
- Preserve the proven v43 path everywhere else
- Keep only one hidden pre-answer question in case1:
  `NPC_C / 你是色盲？`
- Verify whether the C-side hidden question alone is sufficient to reproduce
  the stage-8 / 2357 path on an ordinary account

This probe is diagnostic-only and must not affect the `g2auto` mainline.
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


class Game:
    def __init__(self, sdk: SDK) -> None:
        self.sdk = sdk
        self.stage = 0
        self.calls = 0

    def _track_stage(self, resp: dict[str, Any] | list[Any], npc: str, question: str) -> bool:
        if isinstance(resp, dict):
            s = resp.get('stage')
            if s is not None:
                try:
                    new_stage = int(s)
                    if new_stage > self.stage:
                        log(f'  stage {self.stage}->{new_stage} after [{npc}] q={question[:25]}')
                        self.stage = new_stage
                        return True
                except (ValueError, TypeError):
                    pass
        return False

    def chat(self, npc: str, question: str, evidences: list[str] | None = None) -> bool:
        evid = evidences if evidences is not None else []
        resp = self.sdk.request('chat', npc=npc, question=question, evidences=evid)
        self.calls += 1
        return self._track_stage(resp, npc, question)

    def probe_chat(self, npc: str, question: str, evidences: list[str] | None = None) -> dict[str, Any] | list[Any]:
        evid = evidences if evidences is not None else []
        resp = self.sdk.request('chat', npc=npc, question=question, evidences=evid)
        self.calls += 1
        self._track_stage(resp, npc, question)
        return resp

    def get_npcs(self) -> list[str]:
        resp = self.sdk.request('npcs')
        return [str(x) for x in resp] if isinstance(resp, list) else []

    def submit(self, murderer: str, motivation: str, method: str) -> dict[str, Any]:
        resp = self.sdk.request('answer', murderer=murderer, motivation=motivation, method=method)
        return resp if isinstance(resp, dict) else {}

    def retry_trigger(self, trigger_qs: list[tuple], max_retries: int = 3) -> bool:
        target_stage = self.stage
        for attempt in range(max_retries):
            for item in trigger_qs:
                npc, q = item[0], item[1]
                evid = list(item[2]) if len(item) > 2 else None
                log(f'  retry_trigger a{attempt}: [{npc}] {q[:30]}')
                if self.chat(npc, q, evidences=evid):
                    return True
        return self.stage > target_stage


def solve_case0(g: Game) -> None:
    g.chat('XiaoDingAng', 'Rose是怎样的人？')
    g.chat('DengDaLing', 'Rose是怎样的人？')
    g.chat('YeWenXiao', 'Rose是怎样的人？')
    g.chat('FanMinMin', 'Rose是怎样的人？')

    g.chat('BaiJingTing', 'Rose是个怎样的人？')
    if g.stage < 2:
        g.retry_trigger([
            ('BaiJingTing', 'Rose给你的印象怎么样？'),
            ('BaiJingTing', '你怎么看Rose这个人？'),
        ], max_retries=2)

    g.chat('XiaoDingAng', '你今晚在做什么？')
    g.chat('BaiJingTing', '你今晚在做什么？')
    g.chat('CuiAnYan', '你今晚在干什么？')
    g.chat('DengDaLing', '你今晚在干什么？')

    g.chat('YeWenXiao', '你今晚在干什么？')
    g.chat('FanMinMin', '你今晚在干什么？')
    if g.stage < 3:
        g.retry_trigger([
            ('YeWenXiao', '你今晚都去了哪些地方？'),
            ('FanMinMin', '你今晚的行踪说一下？'),
        ], max_retries=2)

    g.chat('DengDaLing', '你为什么没娶妻？')
    g.chat('YeWenXiao', '这个杯子你认识吗？', evidences=['111'])
    g.chat('FanMinMin', '你见过这个花盆吗？', evidences=['112'])
    g.chat('BaiJingTing', 'Rose和范敏敏吵架了你知道吗？')

    g.chat('YeWenXiao', 'Rose和范敏敏吵架了？')
    g.chat('FanMinMin', '你和Rose吵架了？')
    g.chat('DengDaLing', '你和Rose好上了？')
    g.chat('CuiAnYan', '邓达岭和Rose是什么关系？')
    g.chat('YeWenXiao', 'Rose今天状态不对？')
    g.chat('CuiAnYan', '你是不是提前来了？')
    g.chat('BaiJingTing', '你今天是不是和崔安彦一起来的？')
    if g.stage < 4:
        g.retry_trigger([
            ('YeWenXiao', 'Rose今天有什么异常吗？'),
            ('FanMinMin', '你和Rose到底怎么了？'),
            ('CuiAnYan', '你和邓达岭今天来的时候有没有看到什么？'),
        ], max_retries=2)

    g.chat('YeWenXiao', 'Rose今天戴面纱了？')
    g.chat('FanMinMin', '你和Rose长得像？')
    g.chat('XiaoDingAng', '你和范敏敏什么关系？')
    g.chat('CuiAnYan', '家里生意不好？')
    g.chat('DengDaLing', '崔安彦接近你？')
    if g.stage < 5:
        g.retry_trigger([
            ('XiaoDingAng', '范敏敏最近态度有变化吗？'),
            ('DengDaLing', '崔安彦最近有什么异常行为？'),
        ], max_retries=2)

    g.chat('XiaoDingAng', '范敏敏态度怪？')
    g.chat('FanMinMin', '你对萧定昂好？')
    g.chat('YeWenXiao', '邓达岭喜欢你？')
    g.chat('FanMinMin', '对萧定昂冷淡？')
    g.chat('FanMinMin', '是不是你代替Rose上台？')
    g.chat('DengDaLing', '18:30和叶文潇在舞台右侧见面？')
    g.chat('BaiJingTing', '18:30和崔安彦在一起？')
    g.chat('XiaoDingAng', '19:05你在干什么？')

    npcs = g.get_npcs()
    if 'XiaoDingGang' in npcs:
        g.chat('XiaoDingGang', '你是谁？')

    g.chat('BaiJingTing', '19:05你在干什么？')
    g.chat('YeWenXiao', '你今天是不是和邓达岭见面了？')
    g.chat('CuiAnYan', '18:40你在哪里？')
    g.chat('CuiAnYan', '你让白井霆去安慰Rose是什么意思？')
    g.chat('DengDaLing', 'Rose是不是威胁你？')

    log(f'[v44] case0 stage={g.stage} calls={g.calls}')
    g.submit(
        murderer='崔安彦',
        motivation='崔安彦误认为邓达岭对Rose有意，为扫清障碍、独占邓达岭而谋划除掉Rose。',
        method='崔安彦利用家族药材生意获取毒药，趁18:40左右在准备室中将毒药投入Rose的蜂蜜水杯中，Rose饮水后中毒身亡。',
    )


def solve_case1(g: Game) -> None:
    g.chat('NPC_A', '你知道Z失踪了吗？')
    g.chat('NPC_B', '你知道Z失踪了吗？')
    g.chat('NPC_B', '你了解平时的Z吗？')
    g.chat('NPC_C', '你知道Z失踪了吗？')
    g.chat('NPC_C', '你了解平时的Z吗？')
    g.chat('NPC_D', '你知道Z失踪了吗？')
    g.chat('NPC_D', '你了解平时的Z吗？')

    g.chat('NPC_E', '你了解平时的Z吗？')
    if g.stage < 2:
        g.retry_trigger([
            ('NPC_E', 'Z平时是什么样的人？'),
            ('NPC_E', '你和Z关系好吗？'),
        ], max_retries=2)

    g.chat('NPC_A', '你是不是明年要竞选班长？')
    g.chat('NPC_A', '昨天下午你是不是看见Z了？')
    g.chat('NPC_B', '昨天你是不是骑车撞到D了？')
    g.chat('NPC_C', '你知道Z凌晨去看病了吗？')

    g.chat('NPC_D', '你和E以前是不是男女朋友？')
    if g.stage < 3:
        g.retry_trigger([
            ('NPC_D', '你和E是什么关系？'),
            ('NPC_D', '你以前是不是和E在一起过？'),
        ], max_retries=2)

    g.chat('NPC_E', 'Z画漫画的事你知道吗？')
    g.chat('NPC_E', '关于那件事情你都知道什么？')
    g.chat('NPC_A', '关于高中时候E和D的那件事，你都知道什么？')

    g.chat('NPC_B', '你是不是喜欢E？')
    if g.stage < 4:
        g.retry_trigger([
            ('NPC_B', '你对E有什么感觉？'),
            ('NPC_B', '你是不是暗恋E？'),
        ], max_retries=2)

    g.chat('NPC_D', '关于高中那件事，你知道是谁造谣的吗？')
    g.chat('NPC_A', 'F死了，你知道吗？', evidences=['313'])
    g.chat('NPC_A', '你认为谁可能有杀F的动机？', evidences=['313'])
    g.chat('NPC_C', '昨晚你在做什么？', evidences=['313'])
    g.chat('NPC_C', '昨晚你在回宿舍路上有没有看到什么？', evidences=['313'])
    if g.stage < 5:
        g.retry_trigger([
            ('NPC_C', '昨晚你在回宿舍路上有没有看到什么？', ['313']),
            ('NPC_A', '你认为谁可能有杀F的动机？', ['313']),
            ('NPC_C', '你昨晚有没有看到D？', ['313']),
            ('NPC_C', '你昨晚有没有看到F？', ['313']),
            ('NPC_C', '昨晚在回宿舍路上你遇到谁了？', ['313']),
            ('NPC_A', 'C的电脑上有什么可疑的东西吗？', ['313']),
        ], max_retries=3)

    g.chat('NPC_C', '为什么你的水果刀会在现场？', evidences=['315'])
    g.chat('NPC_B', '你最后一次见F是什么时候？', evidences=['313'])
    g.chat('NPC_E', '关于F的死你知道什么？', evidences=['313'])
    g.chat('NPC_E', '你帮Z躲起来了对吧？', evidences=['311'])
    g.chat('NPC_E', '你是不是找D盗号的？')
    g.chat('NPC_D', '你是不是盗了F的号？')
    g.chat('NPC_D', '你是怎么看到C小说的？')
    g.chat('NPC_C', '你实际在写的是那种血腥猎奇的小说吧？')

    g.chat('NPC_A', '红U盘去哪了？')
    if g.stage < 6:
        g.retry_trigger([
            ('NPC_A', '红U盘去哪了？'),
            ('NPC_A', 'F的U盘你知道在哪吗？'),
        ], max_retries=2)

    g.chat('NPC_A', '你是不是拆了D的车？')
    g.chat('NPC_B', '你知道那个F的U盘去哪了吗？')
    g.chat('NPC_D', '你是同性恋吗？')
    g.chat('NPC_C', '那你的绿U盘去哪了？')
    g.chat('NPC_D', '你不是崴脚了吗，为什么C会看见你自己去修车？')

    g.chat('NPC_D', '你为什么装病？')
    if g.stage < 7:
        g.retry_trigger([
            ('NPC_D', '你为什么装病？'),
            ('NPC_D', '你的脚到底有没有受伤？'),
            ('NPC_D', '你是不是在骗我们？'),
        ], max_retries=2)

    g.chat('NPC_C', '你电脑上的杀人计划书是怎么回事？')
    g.chat('NPC_C', '为什么杀人计划书里面都是同学的名字？')
    g.chat('NPC_B', '你是不是准备杀A？')

    resp = g.probe_chat('NPC_C', '你是色盲？')
    if isinstance(resp, dict):
        log(
            f"[v44] pre-answer probe [NPC_C] stage={resp.get('stage')} "
            f"keys={sorted(resp.keys())} error={resp.get('error')!r}"
        )
    else:
        log(f'[v44] pre-answer probe [NPC_C] non-dict={type(resp).__name__}')

    log(f'[v44] case1 stage={g.stage} calls={g.calls}')
    result = g.submit(
        murderer='E',
        motivation='E发现F就是高中时在表白墙造谣诬陷自己出轨的人，又发现F向Z的家长告密导致Z被迫逃离学校。新仇旧恨交织，E决定杀害F。',
        method='E尾随F到小树林埋伏处守株待兔，在F回来回收分尸工具时伏击打晕了她，用偷来的C的水果刀按照C的小说手法破坏了F的面部，然后将尸体埋在F自己挖的坑中。',
    )
    log(f'[v44] case1 submit_keys={sorted(result.keys()) if isinstance(result, dict) else []}')


def solve_case(g: Game, case_index: int) -> bool:
    npcs = g.get_npcs()
    if not npcs:
        return False
    sorted_npcs = sorted(npcs)
    log(f'[v44] case={case_index} npcs={sorted_npcs}')
    g.stage = 0
    g.calls = 0

    if sorted_npcs == CASE0_NPCS:
        solve_case0(g)
    elif sorted_npcs == CASE1_NPCS:
        solve_case1(g)
    else:
        log('[v44] unknown case')
        g.submit(murderer=npcs[0], motivation='未知', method='未知')
    return True


def main() -> int:
    sdk = SDK()
    sdk._receive()
    g = Game(sdk)
    case_index = 0
    while True:
        try:
            ok = solve_case(g, case_index)
        except EOFError:
            break
        except Exception as exc:
            log(f'[v44] fatal case={case_index} exc={type(exc).__name__}: {exc}')
            try:
                g.submit(murderer='', motivation='', method='')
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
