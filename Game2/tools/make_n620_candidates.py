#!/usr/bin/env python3
from __future__ import annotations

import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "Game2" / "deepclue_ai"
BASE = OUT / "n618a" / "ai.py"

ANCHOR = "        method = '凶手利用扑克公馆全员戴面具、身份混淆和场馆密室条件，在衣帽间用刀杀害并伪装死者。'\n"


def retitle(src: str, label: str) -> str:
    for old in ("n618a", "n617a", "n556y1"):
        src = src.replace(f'"""Game2 DeepClue AI {old}.', f'"""Game2 DeepClue AI {label}.', 1)
    return src


def poker_answer_block(mode: str) -> str:
    return f"""        n620_ids = [str(ev.get('id')) for ev in g.evidences()]
        if '606' in set(n620_ids):
            n620_text = (
                str(globals().get('N601_FINAL_TEXT', ''))
                + '\\n'
                + str(locals().get('combined_late_text', ''))
                + '\\n'
                + '\\n'.join(str(ev.get('name', '')) + str(ev.get('content', '')) for ev in g.evidences())
            )
            n620_answer_mode = '{mode}'
            n620_murderer = ''
            if n620_answer_mode == 'explicit':
                for pattern in (
                    r'摘要成立。凶手是([一-龥]{{2,4}})',
                    r'凶手就是([一-龥]{{2,4}})',
                    r'真正动手杀死他的，是([一-龥]{{2,4}})',
                    r'亲手杀死他的，是([一-龥]{{2,4}})',
                    r'人是我杀的',
                ):
                    m = re.search(pattern, n620_text)
                    if m:
                        if pattern == r'人是我杀的':
                            n620_murderer = suspect
                        else:
                            n620_murderer = m.group(1)
                        break
            elif n620_answer_mode == 'club5':
                for pattern in (
                    r'真正的梅花\\s*5\\s*是([一-龥]{{2,4}})',
                    r'真正的梅花五[^，。\\n]{{0,24}}([一-龥]{{2,4}})',
                    r'林渝植[^，。\\n]{{0,20}}(?:就是|现在是|也就是)([一-龥]{{2,4}})',
                    r'([一-龥]{{2,4}})[，。]?她就是林渝植',
                ):
                    m = re.search(pattern, n620_text)
                    if m:
                        n620_murderer = m.group(1)
                        break
            elif n620_answer_mode == 'redq':
                for pattern in (
                    r'红桃\\s*Q[^，。\\n]{{0,12}}(?:也就是|是)([一-龥]{{2,4}})',
                    r'([一-龥]{{2,4}})[^，。\\n]{{0,12}}红桃\\s*Q',
                    r'约\\s*Joker[^，。\\n]{{0,20}}的是([一-龥]{{2,4}})',
                    r'诱导\\s*Joker[^，。\\n]{{0,20}}的是([一-龥]{{2,4}})',
                ):
                    m = re.search(pattern, n620_text)
                    if m:
                        n620_murderer = m.group(1)
                        break
            if not n620_murderer:
                n620_murderer = suspect
            n620_motivation = (
                f'{{n620_murderer}}与Joker周克及POKER人口贩卖组织存在仇怨或利益切割；'
                '606三人照片证明组织关系，501转账、503特殊邀请函、504的LYZ随身物和601-604旧案证明死者并非真正梅花5，而是被引入公馆清算的Joker。'
            )
            n620_method = (
                f'{{n620_murderer}}利用扑克公馆全员戴面具造成身份混淆，借红桃Q/联络人或手机云端约见记录把Joker周克引到衣帽间，'
                '在衣帽间持刀杀害或配合杀害后伪装成梅花5死亡现场，并用时间线、面具和移尸痕迹转移视线。'
            )
            g.answer(murderer=n620_murderer, motivation=n620_motivation, method=n620_method)
            return
"""


def build(label: str, mode: str) -> str:
    out = retitle(BASE.read_text(encoding="utf-8"), label)
    if ANCHOR not in out:
        raise RuntimeError(f"{label}: poker answer anchor not found")
    return out.replace(ANCHOR, poker_answer_block(mode) + ANCHOR, 1)


def write_candidate(label: str, text: str) -> None:
    target = OUT / label
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    (target / "ai.py").write_text(text, encoding="utf-8")


def main() -> int:
    write_candidate("n620a", build("n620a", "explicit"))
    write_candidate("n620b", build("n620b", "club5"))
    write_candidate("n620c", build("n620c", "redq"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
