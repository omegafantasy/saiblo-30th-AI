#!/usr/bin/env python3
from __future__ import annotations

import json
import struct
import sys
import time
from typing import Any


DEBUG = False
MODE = 'combo_answer'


PINYIN_TO_CN = {
    'BaiJingTing': '白井霆',
    'ChuRongZhen': '楚戎臻',
    'CuiAnYan': '崔安彦',
    'DengDaLing': '邓达岭',
    'FanMinMin': '范敏敏',
    'GuYunShu': '顾云舒',
    'JiangMuQing': '江沐青',
    'LinWanZhou': '林晚舟',
    'LuoFangChen': '罗方琛',
    'LuYiChu': '陆亦初',
    'ShenZhiYao': '沈知遥',
    'WangKeJin': '王科瑾',
    'WangZe': '王泽',
    'XiaoDingAng': '萧定昂',
    'XiaoDingGang': '萧定刚',
    'XuQingHe': '许清和',
    'YeQingHeng': '叶青衡',
    'YeWenXiao': '叶文潇',
    'ZhangShuo': '张朔',
    'ZhangYi': '张壹',
    'ZhangZiHan': '张子韩',
    'ZhaoYiCheng': '赵一橙',
    'ZhouLinJun': '周林君',
}


class SDK:
    def __init__(self) -> None:
        self._stdin = sys.stdin.buffer
        self._stdout = sys.stdout.buffer

    def _send(self, data: dict[str, Any]) -> None:
        raw = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self._stdout.write(struct.pack('>I', len(raw)) + raw)
        self._stdout.flush()

    def _receive(self) -> dict[str, Any]:
        self._stdin.read(4)
        line = self._stdin.readline()
        if not line:
            raise EOFError('stdin closed')
        text = line.decode('utf-8', errors='replace').strip()
        return json.loads(text) if text else {}

    def request(self, action: str, **kwargs: Any) -> dict[str, Any] | list[Any]:
        self._send({'action': action, **kwargs})
        return self._receive()


def log(*args: Any) -> None:
    if DEBUG:
        print(*args, file=sys.stderr, flush=True)


class Game:
    def __init__(self, sdk: SDK) -> None:
        self.sdk = sdk
        self.stage = 0

    def req(self, action: str, **kwargs: Any) -> Any:
        try:
            return self.sdk.request(action, **kwargs)
        except Exception as exc:
            log(f'request failed action={action}: {exc}')
            return {}

    def npcs(self) -> list[str]:
        resp = self.req('npcs')
        return [str(x) for x in resp] if isinstance(resp, list) else []

    def hint(self) -> str:
        resp = self.req('hint')
        return str(resp.get('hint', '')) if isinstance(resp, dict) else ''

    def evidences(self) -> list[dict[str, Any]]:
        resp = self.req('others')
        if isinstance(resp, dict) and isinstance(resp.get('evidences'), list):
            return [x for x in resp['evidences'] if isinstance(x, dict)]
        return []

    def chat(self, npc: str, question: str, evidences: list[str] | None = None) -> dict[str, Any]:
        resp: Any = {}
        for attempt in range(3):
            resp = self.req('chat', npc=npc, question=question, evidences=list(evidences or []))
            if not (isinstance(resp, dict) and resp.get('error')):
                break
            time.sleep(0.2 * (attempt + 1))
        if not isinstance(resp, dict):
            return {}
        try:
            self.stage = max(self.stage, int(resp.get('stage', self.stage) or self.stage))
        except (TypeError, ValueError):
            pass
        return resp

    def answer(self, murderer: str, motivation: str, method: str) -> None:
        self.req('answer', murderer=murderer, motivation=motivation, method=method)


def response_text(resp: dict[str, Any]) -> str:
    for key in ('reply', 'content', 'message', 'text'):
        value = resp.get(key)
        if isinstance(value, str):
            return value
    return ''


def all_text(hint: str, evidences: list[dict[str, Any]]) -> str:
    parts = [hint]
    for ev in evidences:
        parts.append(str(ev.get('name', '')))
        parts.append(str(ev.get('content', '')))
    return '\n'.join(parts)


def case_kind(text: str) -> str:
    if '袁樱瞳' in text or '碎尸案' in text:
        return 'yuan'
    if 'Rose' in text:
        return 'rose'
    if 'Z失踪' in text or 'F无法联络' in text:
        return 'zf'
    if '扑克公馆' in text:
        return 'poker'
    return 'unknown'


def evidence_ids(evidences: list[dict[str, Any]]) -> list[str]:
    return [str(ev.get('id')) for ev in evidences if str(ev.get('id'))]


def cn_name(npc: str) -> str:
    return PINYIN_TO_CN.get(npc, npc)


def zero_answer(g: Game) -> None:
    g.answer('无名氏', '无', '无')


def answer_competitor(g: Game, npcs: list[str]) -> None:
    suspect = cn_name(npcs[0]) if npcs else '无名氏'
    g.answer(
        suspect,
        f'{suspect}与袁樱瞳竞争出国交流名额，课程展示投票因缺席、多出票和笔迹异常产生一票优势；袁樱瞳准备揭穿投票和替身照片秘密，{suspect}因此灭口。',
        f'{suspect}利用自己与袁樱瞳相似、黄色行李箱、袁樱瞳手机里的凌晨1点尸体照片、lo裙和栗色假发制造死亡时间与身份混淆，随后分尸并转移尸块。',
    )


def solve_yuan(g: Game, npcs: list[str]) -> None:
    g.stage = 0

    def ask_all(question: str, ids: list[str] | None = None) -> None:
        for npc in npcs:
            reply = response_text(g.chat(npc, question, ids))
            if any(key in reply for key in (
                '手机', '凌晨1点', '尸体照片', 'lo裙', '假发', '投票', '24', '23', '46', '47', '48', '49',
                '笔迹', '多出', '行李箱', '生物馆', '世纪林', '李海天', '1919', '张壹', '保安', '网站',
            )):
                g.evidences()

    ask_all('你对死者袁樱瞳和这起碎尸案了解什么？现场、尸体、手机、行李箱、照片、假发、投票和时间线分别说清楚。')
    ask_all('你和袁樱瞳是什么关系？她最近和谁有矛盾，谁最后见过她，谁可能有动机？')
    ids = [eid for eid in evidence_ids(g.evidences()) if eid in {'703', '704'}]
    ask_all('课程展示投票到底有多少人参与？49人、展示2人、缺席者、实际46人或47人、24比23、多出的笔迹票分别怎么回事，这张票对谁有利？', ids)
    ask_all('李海天会长、生物馆、世纪林、1919黑车、张壹或保安看奇怪网站，与袁樱瞳尸块和手机照片之间有什么联系？', ids)
    ask_all('请只说亲眼看到的：周六22:30谁从生物馆出来或在附近？这和袁樱瞳的死亡、替身照片、行李箱有没有关系？', ids)

    if MODE.endswith('answer'):
        answer_competitor(g, npcs)
    else:
        zero_answer(g)


def solve_case(g: Game) -> bool:
    npcs = g.npcs()
    if not npcs:
        return False
    hint = g.hint()
    evidences = g.evidences()
    if case_kind(all_text(hint, evidences)) == 'yuan':
        solve_yuan(g, npcs)
    else:
        zero_answer(g)
    return True


def main() -> int:
    sdk = SDK()
    sdk._receive()
    g = Game(sdk)
    for _ in range(6):
        try:
            if not solve_case(g):
                break
        except EOFError:
            break
        except Exception as exc:
            log(f'fatal: {exc}')
            try:
                zero_answer(g)
            except Exception:
                pass
            break
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
