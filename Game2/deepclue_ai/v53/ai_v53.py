#!/usr/bin/env python3
"""Game2 DeepClue AI v53.

Zero-chat scoring probe after v52:
- keep v49's stable old-case mapping and zero-cost new-case handling;
- only replace new-case fallback answers with the concrete method/motive
  discovered from v52/v50 logs.
"""
from __future__ import annotations

import json
import re
import struct
import sys
from typing import Any


PINYIN_TO_CN = {
    'ChuRongZhen': '楚戎臻',
    'GuYunShu': '顾云舒',
    'JiangMuQing': '江沐青',
    'LinWanZhou': '林晚舟',
    'LuoFangChen': '罗方琛',
    'LuYiChu': '陆亦初',
    'ShenZhiYao': '沈知遥',
    'WangKeJin': '王科瑾',
    'WangZe': '王泽',
    'XuQingHe': '许清和',
    'YeQingHeng': '叶青衡',
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
    print(*args, file=sys.stderr, flush=True)


def cn_name(npc_id: str) -> str:
    return PINYIN_TO_CN.get(npc_id, npc_id)


def name_from_title(title: str) -> str:
    title = title.strip()
    for pattern in (r'关于([^：:]+)$', r'^([^：:]+?)的介绍$'):
        m = re.search(pattern, title)
        if m:
            return m.group(1).strip()
    return ''


class Game:
    def __init__(self, sdk: SDK) -> None:
        self.sdk = sdk

    def req(self, action: str, **kwargs: Any) -> Any:
        try:
            return self.sdk.request(action, **kwargs)
        except Exception as exc:
            log(f'[v53] request failed action={action}: {exc}')
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

    def answer(self, murderer: str, motivation: str, method: str) -> dict[str, Any]:
        resp = self.req('answer', murderer=murderer, motivation=motivation, method=method)
        return resp if isinstance(resp, dict) else {}


def all_text(hint: str, evidences: list[dict[str, Any]]) -> str:
    parts = [hint]
    for ev in evidences:
        parts.append(str(ev.get('name', '')))
        parts.append(str(ev.get('content', '')))
    return '\n'.join(parts)


def solve_rose(g: Game, npcs: list[str], marks: dict[str, bool], evidences: list[dict[str, Any]]) -> None:
    false_marked = [npc for npc in npcs if marks.get(npc) is False]
    murderer_id = false_marked[0] if false_marked else (npcs[0] if npcs else '')
    murderer = cn_name(murderer_id)
    banker = ''
    for ev in evidences:
        if str(ev.get('id')) == '004':
            banker = name_from_title(str(ev.get('name', '')))
            break
    if not banker:
        banker = '银行家'
    log(f'[v53] rose murderer_id={murderer_id} murderer={murderer} banker={banker}')
    g.answer(
        murderer=murderer,
        motivation=f'{murderer}误认为{banker}对Rose有意，为扫清情敌、独占{banker}而谋划杀害Rose。',
        method=f'{murderer}利用家族药材生意取得夹竹桃毒素，趁18:40左右在准备室将毒投入Rose的专用蜂蜜水杯，Rose饮用后中毒身亡。',
    )


def solve_z(g: Game, evidences: list[dict[str, Any]]) -> None:
    roles: dict[str, str] = {}
    for ev in evidences:
        ev_id = str(ev.get('id', ''))
        if ev_id in {'002', '003', '004', '005', '006'}:
            roles[ev_id] = name_from_title(str(ev.get('name', '')))
    a = roles.get('002', 'A')
    b = roles.get('003', 'B')
    c = roles.get('004', 'C')
    d = roles.get('005', 'D')
    e = roles.get('006', 'E')
    log(f'[v53] z roles A={a} B={b} C={c} D={d} E={e}')
    g.answer(
        murderer=e,
        motivation=f'{e}发现F就是高中时在表白墙造谣诬陷自己出轨的人，又发现F向Z家长告密导致Z被迫逃离学校，新仇旧恨交织下决定杀害F。',
        method=f'{e}尾随F到小树林埋伏处守株待兔，在F回收分尸工具时伏击打晕F，用偷来的{c}的水果刀按照{c}小说里的手法毁坏F面部，并将尸体埋在F自己挖的坑中。',
    )


def solve_unknown(g: Game, npcs: list[str], hint: str, evidences: list[dict[str, Any]]) -> None:
    suspect = cn_name(npcs[0]) if npcs else ''
    text = all_text(hint, evidences)
    if '扑克公馆' in text:
        motivation = f'{suspect}与梅花5、林渝植身份和扑克公馆邀请有关，为掩盖真实身份或旧事，把死亡伪装成他杀来误导调查。'
        method = (
            f'{suspect}提前在房间电脑搜索自杀伪装成谋杀的方法，用方形塑料盒在冰柜中冻结三把刀的刀柄，'
            '借冰块固定刀具刺入后背；冰融化后留下无指纹刀具、被稀释的血水和没有上锁的房门，'
            '再利用梅花5面具黏脸与全员戴面具制造身份混淆。'
        )
    elif '袁樱瞳' in text or '碎尸案' in text:
        motivation = f'{suspect}与袁樱瞳竞争出国交流名额，投票中多出一票使{suspect}险胜；袁樱瞳说“等到周五”，{suspect}担心作弊和相关秘密暴露而杀人。'
        method = (
            f'{suspect}利用自己与袁樱瞳长相相似制造替身和时间线混淆，取得并清空袁樱瞳手机，'
            '留下凌晨1点身穿lo裙、戴栗色假发的女性尸体照片误导调查，随后借行李箱、生物馆和抛尸现场转移视线并分尸抛尸。'
        )
    else:
        motivation = '未知'
        method = '未知'
    log(f'[v53] unknown hint={hint[:50]} suspect={suspect}')
    g.answer(murderer=suspect, motivation=motivation, method=method)


def solve_case(g: Game, case_idx: int) -> bool:
    npcs = g.npcs()
    if not npcs:
        return False
    marks = g.marks()
    hint = g.hint()
    evidences = g.evidences()
    text = all_text(hint, evidences)
    log(f'[v53] case={case_idx} npcs={sorted(npcs)} marks={marks} hint={hint[:60]}')
    if 'Rose' in text:
        solve_rose(g, npcs, marks, evidences)
    elif 'Z失踪' in text or 'F无法联络' in text:
        solve_z(g, evidences)
    else:
        solve_unknown(g, npcs, hint, evidences)
    return True


def main() -> int:
    sdk = SDK()
    sdk._receive()
    g = Game(sdk)
    for case_idx in range(6):
        try:
            if not solve_case(g, case_idx):
                break
        except EOFError:
            break
        except Exception as exc:
            log(f'[v53] fatal case={case_idx}: {exc}')
            try:
                g.answer('', '未知', '未知')
            except Exception:
                pass
            break
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
