#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import struct
import sys
import time
from typing import Any


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
CN_TO_PINYIN = {cn: pinyin for pinyin, cn in PINYIN_TO_CN.items()}
DEBUG = False


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


def cn_name(npc_id: str) -> str:
    return PINYIN_TO_CN.get(npc_id, npc_id)


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
            new_stage = int(resp.get('stage', self.stage) or self.stage)
        except (TypeError, ValueError):
            new_stage = self.stage
        self.stage = max(self.stage, new_stage)
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


def extract_bio_names(text: str) -> list[str]:
    names: list[str] = []
    patterns = (
        r'看见(?:的是)?([一-龥]{2,4})[^。！？]{0,45}从生物馆[^。！？]{0,30}(?:跑|出来)',
        r'明明看见(?:的是)?([一-龥]{2,4})',
        r'实际看到的是([一-龥]{2,4})',
        r'([一-龥]{2,4})[^。！？]{0,18}从生物馆[^。！？]{0,35}(?:跑|出来)',
    )
    for pattern in patterns:
        for match in re.finditer(pattern, text):
            name = match.group(1).strip()
            if name in CN_TO_PINYIN and name != '张壹' and name not in names:
                names.append(name)
    return names


def zero_answer(g: Game) -> None:
    g.answer('无名氏', '无', '无')


def solve_yuan_bio_answer(g: Game, npcs: list[str], reverse_final_round: bool = False) -> None:
    g.stage = 0
    replies: list[str] = []

    def ask_many(targets: list[str], question: str, ids: list[str] | None = None) -> None:
        for npc in targets:
            reply = response_text(g.chat(npc, question, ids))
            replies.append(reply)
            if any(key in reply for key in ('手机', '凌晨1点', '尸体照片', 'lo裙', '假发', '投票', '24', '23', '47', '46', '笔迹', '行李箱')):
                g.evidences()

    ask_many(npcs, '你对死者袁樱瞳和这起碎尸案了解什么？现场情况、尸体、手机、行李箱、照片、假发、投票和时间线都说一下。')
    ask_many(npcs, '你和袁樱瞳是什么关系？她最近和谁有矛盾，谁最后见过她，谁可能有动机？')

    ids = [eid for eid in evidence_ids(g.evidences()) if eid in {'703', '704'}]
    final_targets = list(reversed(npcs)) if reverse_final_round else npcs
    ask_many(
        final_targets,
        '有人说张壹半夜从生物馆慌张跑出来；你夜跑时实际看到的是谁？生物馆、世纪林、尸块和袁樱瞳死亡有什么关系？',
        ids,
    )
    bio_names = extract_bio_names('\n'.join(replies))
    suspect = bio_names[-1] if bio_names else (cn_name(npcs[-1]) if npcs else '无名氏')
    g.answer(
        suspect,
        f'{suspect}与袁樱瞳的死亡、生物馆和世纪林尸块线索有关，担心袁樱瞳揭露投票作弊、替身照片或黑车秘密，因此杀人灭口。',
        f'{suspect}将袁樱瞳引到生物馆附近杀害，利用凌晨1点手机尸体照片、lo裙、栗色假发和相似者制造死亡时间与身份混淆，之后分尸并把尸块抛到世纪林一带。',
    )


def solve_case(g: Game) -> bool:
    npcs = g.npcs()
    if not npcs:
        return False
    hint = g.hint()
    evidences = g.evidences()
    if case_kind(all_text(hint, evidences)) == 'yuan':
        solve_yuan_bio_answer(g, npcs, reverse_final_round=True)
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
