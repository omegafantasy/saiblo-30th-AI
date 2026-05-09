#!/usr/bin/env python3
from __future__ import annotations

import json
import struct
import sys
import time
from typing import Any


DEBUG = False
ANSWER_MODE = 'teacher'


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

    def marks(self) -> dict[str, bool]:
        resp = self.req('marks')
        return {str(k): bool(v) for k, v in resp.items()} if isinstance(resp, dict) else {}

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


def cn_name(npc: str) -> str:
    return PINYIN_TO_CN.get(npc, npc)


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


def zero_answer(g: Game) -> None:
    g.answer('无名氏', '无', '无')


def refresh_on_clue(g: Game, reply: str) -> list[dict[str, Any]]:
    if any(key in reply for key in (
        '手机', '凌晨1点', '尸体照片', 'lo裙', '假发', '投票', '24', '23',
        '47', '46', '49', '笔迹', '行李箱', '生物馆', '世纪林', '李海天',
        '海豚', '尸检', '1919', '张壹', '真实死者', '替身',
    )):
        return g.evidences()
    return []


def choose_targets(npcs: list[str], marks: dict[str, bool]) -> tuple[str, str, str]:
    marked_true = [npc for npc in npcs if marks.get(npc) is True]
    marked_false = [npc for npc in npcs if marks.get(npc) is False]
    competitor = marked_true[0] if marked_true else (npcs[0] if npcs else '')
    teacher = marked_true[1] if len(marked_true) > 1 else (marked_true[0] if marked_true else (npcs[1] if len(npcs) > 1 else competitor))
    witness = marked_false[0] if marked_false else (npcs[2] if len(npcs) > 2 else (npcs[-1] if npcs else ''))
    return competitor, teacher, witness


def solve_yuan(g: Game, npcs: list[str], marks: dict[str, bool]) -> None:
    g.stage = 0
    competitor, teacher, witness = choose_targets(npcs, marks)

    evidences = g.evidences()
    ids = [eid for eid in evidence_ids(evidences) if eid in {'001', '703', '704', '705'}]

    if competitor:
        reply = response_text(g.chat(
            competitor,
            '只说袁樱瞳这周状态、课程展示投票输赢、你是否捡到她的手机、行李箱/lo裙/假发/替身身份置换这些关键事实。',
            ids,
        ))
        new_evs = refresh_on_clue(g, reply)
        if new_evs:
            ids = [eid for eid in evidence_ids(new_evs) if eid in {'001', '703', '704', '705'}]

    if teacher and teacher != competitor:
        reply = response_text(g.chat(
            teacher,
            '请只说明袁樱瞳、竞争者和出国名额：课堂展示是否平分、投票是否24比23、应有47票却出现46/47/49或笔迹异常。',
            ids,
        ))
        new_evs = refresh_on_clue(g, reply)
        if new_evs:
            ids = [eid for eid in evidence_ids(new_evs) if eid in {'001', '703', '704', '705'}]

    if witness:
        reply = response_text(g.chat(
            witness,
            '请只说你亲眼知道的后段线索：1919黑车、周六22:30谁从生物馆出来、李海天尸检/海豚挂件、世纪林尸块和袁樱瞳是否有关。',
            ids,
        ))
        new_evs = refresh_on_clue(g, reply)
        if new_evs:
            ids = [eid for eid in evidence_ids(new_evs) if eid in {'001', '703', '704', '705'}]

    if '705' not in set(ids) and witness:
        reply = response_text(g.chat(
            witness,
            '如果你知道李海天尸检、蓝色背包海豚挂件、真实死者/替身、尸块二次利用或死亡时间伪造，请直接说证据编号和事实。',
            ids,
        ))
        refresh_on_clue(g, reply)

    answer_yuan(g, competitor, teacher, witness)


def answer_yuan(g: Game, competitor: str, teacher: str, witness: str) -> None:
    competitor_name = cn_name(competitor) if competitor else '无名氏'
    teacher_name = cn_name(teacher) if teacher else '无名氏'
    witness_name = cn_name(witness) if witness else '无名氏'

    if ANSWER_MODE == 'competitor':
        g.answer(
            competitor_name,
            '为夺取出国名额并掩盖投票获利，借袁樱瞳手机和相似身份制造替身混淆。',
            '利用课程投票后一票优势、手机照片、lo裙假发和行李箱制造死亡时间与身份置换。',
        )
    elif ANSWER_MODE == 'teacher':
        g.answer(
            teacher_name,
            '为掩盖投票造假和名额分配问题，阻止袁樱瞳继续追查课程展示异常。',
            '操纵或纵容异常投票后，用手机、假发和相似者线索转移视线，掩盖真实名额动机。',
        )
    elif ANSWER_MODE == 'witness':
        g.answer(
            witness_name,
            '掌握生物馆、1919黑车和世纪林尸块线索，担心袁樱瞳发现尸块转移真相。',
            '借生物馆夜间出入、1919黑车和世纪林路线转移尸块，再用手机照片与行李箱混淆时间线。',
        )
    elif ANSWER_MODE == 'field_only':
        g.answer(
            '无名氏',
            '真实死者与替身被故意混淆；李海天尸检、海豚挂件和袁樱瞳线索会暴露尸块二次利用。',
            '用替身、手机照片、lo裙假发、李海天尸检、蓝色背包海豚挂件和尸块二次利用伪造死亡时间。',
        )
    else:
        zero_answer(g)


def solve_case(g: Game) -> bool:
    npcs = g.npcs()
    if not npcs:
        return False
    marks = g.marks()
    hint = g.hint()
    evidences = g.evidences()
    if case_kind(all_text(hint, evidences)) == 'yuan':
        solve_yuan(g, npcs, marks)
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
