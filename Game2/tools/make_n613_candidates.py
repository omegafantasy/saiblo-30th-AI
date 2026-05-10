#!/usr/bin/env python3
from __future__ import annotations

import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "Game2" / "deepclue_ai"

BASE_N607 = OUT / "n607a" / "ai.py"
BASE_N612 = OUT / "n612b" / "ai.py"
BASE_N601 = OUT / "n601f" / "ai.py"


OLD_POKER_QS = [
    "503/504和601-604已经出现。不要再说“还差最后一块”，直接调刑警卷宗：死者手机云端名单、Joker账号实名/IP/设备、邀请函源文件、林渝植失踪卷宗、张子韩女儿DNA、王科瑾电脑银行流水和最终物证，下一编号、名称、持有人分别是什么？",
    "你就是林渝植/真正梅花5，504的LYZ项链和601失踪少女特征已经对上。请直接说明你是否是张子韩寻找的女儿、Joker如何控制你、谁杀了Joker，以及下一份DNA/云端名单/最终物证编号和持有人。",
    "601报道失踪少女、603/604证明你曾是刘丽雯医生；501又说你为找女儿被王科瑾/于书华骗走五十万。请直接说明失踪女儿、林渝植、右眼角胎记、Joker人口贩卖集团和死者手机云端名单之间的证据链，并交出下一物证编号。",
    "你电脑里的银行流水和501匿名五十万是后续关键。请不要再口头辩解，直接交出王科瑾电脑、转账源账户、于书华身份、Joker资金流、张子韩女儿线索和人口贩卖名单对应的下一物证编号。",
    "你负责邀请函和接待。503显示梅花5邀请函格式不同，201又有Joker转账定金和地址表。请直接交出邀请函源文件、寄送记录、Joker账号设备/IP、死者手机云端名单或最终物证编号。",
]

NEW_POKER_QS = [
    "503/504和601-604已经出现，先不要追散乱DNA。请直接调刑警卷宗里的606三人照片：Joker周克、于书华、红桃Q/接待联络者是否同属花纹村POKER组织；照片原件、左臂纹身、组织名册、现场未交605/607/608由谁保管。",
    "你就是林渝植/真正梅花5，504的LYZ项链和601失踪少女特征已经对上。现在只追Joker如何控制你、谁把Joker约进衣帽间、左臂POKER纹身三人照片、组织名册和605/607/608最终警方证据。",
    "601报道失踪少女、603/604证明刘丽雯旧身份。请把女儿线索转到花纹村组织证据：Joker周克、于书华、红桃Q/刘瑄、左臂POKER纹身、606三人照片原件、谁杀Joker、605/607/608下一卷宗。",
    "501匿名五十万和于书华身份已经指向你。请直接说明于书华、Joker周克、红桃Q/刘瑄、左臂POKER纹身、花纹村组织名册、三人照片原件、现场未交605和最终警方卷宗之间的关系。",
    "你负责邀请函和接待，又最可能接近红桃Q/刘瑄联络链。请不要复述接待工作，只查Joker周克、于书华、红桃Q、左臂POKER纹身、606三人照片、邀请源文件、组织名册和现场未交证据。",
]


POST707_BLOCK = r'''
        if '707' in set(yuan_ids) and '708' not in set(yuan_ids):
            ev707 = next((ev for ev in g.evidences() if str(ev.get('id')) == '707'), None)
            ev707_text = str(ev707.get('name', '')) + '\n' + str(ev707.get('content', '')) if isinstance(ev707, dict) else ''
            contact_name = ''
            exchange_name = ''
            m = re.search(r'物证07：([一-龥]{1,4})的联系方式', ev707_text)
            if m:
                contact_name = m.group(1)
            for pattern in (
                r'可用于与([一-龥]{1,4})交换情报',
                r'与([一-龥]{1,4})交换情报',
                r'([一-龥]{1,4})曾表示[^。\n]{0,40}联系方式',
            ):
                m = re.search(pattern, ev707_text)
                if m:
                    exchange_name = m.group(1)
                    break
            post707_text = ev707_text + '\n' + '\n'.join(yuan_replies.values())
            runner_name = exchange_name
            for pattern in (
                r'看见([一-龥]{2,4})从生物馆',
                r'看见([一-龥]{2,4})[^。\n]{0,18}从生物馆',
                r'([一-龥]{2,4})[^。\n]{0,18}从生物馆[^。\n]{0,16}跑出来',
                r'([一-龥]{2,4})是学生会副会长',
            ):
                m = re.search(pattern, post707_text)
                if m:
                    runner_name = m.group(1)
                    break
            post707_targets: list[str] = []

            def add_post707_target(npc_id: str) -> None:
                if npc_id and npc_id not in post707_targets:
                    post707_targets.append(npc_id)

            for name in (exchange_name, runner_name, contact_name):
                if name:
                    for npc_id in global_name_ids(name, current_npcs):
                        add_post707_target(npc_id)
            for npc_id in story_target_ids(post707_text, current_npcs, max_ids=10):
                add_post707_target(npc_id)
            for npc_id in current_npcs:
                add_post707_target(npc_id)

            contact_label = contact_name or '那个经常运动的同学'
            runner_label = runner_name or exchange_name or '生物馆跑出者'
            direct_q = (
                f'{contact_label}已经愿意留下联系方式，我现在把这条线索转达给你。不要再讨论“交换”两个字，也不要谈编号；'
                f'你上周六从生物馆慌张跑出来后想联系{contact_label}，说明你知道关键事实。请直接说：你在生物馆看到或处理了什么，'
                '李海天U盘、袁樱瞳手机原图、凌晨尸体照片、世纪林尸块、保安奇怪网站、1919黑车和真正杀人者之间是什么关系；'
                '如果有实物、监控、后台记录或官方文件，请直接交出。'
            )
            locate_q = (
                f'现在只找{runner_label}本人或他留下的材料：学生会办公室、电子系大楼、男生宿舍、电话记录、QQ/微信消息、'
                '生物馆门禁和监控里哪一项能证明他当晚为什么慌张。不要复述传闻，直接说可调取的实物或记录。'
            )
            asked_post707: set[str] = set()
            for source_id in post707_targets[:8]:
                if not source_id or source_id in asked_post707:
                    continue
                asked_post707.add(source_id)
                question = direct_q if (runner_name and cn_name(source_id) == runner_name) or (exchange_name and cn_name(source_id) == exchange_name) else locate_q
                resp = chat_visible_or_probe(g, source_id, g.npcs() or npcs, question, yuan_ids)
                yuan_replies[source_id] = yuan_replies.get(source_id, '') + '\n' + response_text(resp)
                yuan_ids = [str(ev.get('id')) for ev in g.evidences() if str(ev.get('id')) in {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706', '707', '708'}]
                if '708' in set(yuan_ids):
                    break
            if '708' not in set(yuan_ids):
                ask_all(
                    f'707联系方式已经出现。不要说暗号或编号，只执行现实动作：找到{runner_label}，把{contact_label}的联系方式转达给他，'
                    '让他说清生物馆当晚发生了什么，以及哪份U盘、手机原图、监控、网页后台、车辆记录或官方文件能证明杀手。',
                    yuan_ids,
                )
                yuan_ids = [str(ev.get('id')) for ev in g.evidences() if str(ev.get('id')) in {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706', '707', '708'}]
'''


def retitle(src: str, label: str) -> str:
    src = src.replace('"""Game2 DeepClue AI n556y1.', f'"""Game2 DeepClue AI {label}.', 1)
    for old in ('n601f', 'n607a', 'n611a', 'n612b'):
        src = src.replace(f'"""Game2 DeepClue AI {old}.', f'"""Game2 DeepClue AI {label}.', 1)
    return src


def apply_poker_606(src: str) -> str:
    out = src
    for old, new in zip(OLD_POKER_QS, NEW_POKER_QS, strict=True):
        if old not in out:
            raise RuntimeError(f"missing Poker anchor: {old[:32]}")
        out = out.replace(old, new, 1)
    out = out.replace("deep_targets[:6]", "deep_targets[:8]", 1)
    return out


def add_post707(src: str) -> str:
    if "if '707' in set(yuan_ids) and '708' not in set(yuan_ids):" in src:
        return src
    marker = "        n604_yuan_ids = [str(ev.get('id')) for ev in g.evidences() if str(ev.get('id')) in {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706', '707', '708'}]\n"
    if marker not in src:
        raise RuntimeError("Yuan insertion marker not found")
    return src.replace(marker, POST707_BLOCK + marker, 1)


def tighten_n612_post707(src: str) -> str:
    out = add_post707(src)
    old = "ask_all('单独确认联系方式交换线：是否有人想要那个不认识的“运动少女”的联系方式，运动少女是谁，谁愿意用联系方式交换关于杀手的秘密；如果能给707或708，请直接给证据编号、证据名和持有人。')"
    new = "ask_all('单独确认夜跑联系方式线：谁在生物馆附近慌张跑出后向那个经常运动的同学要微信或电话；那人完整姓名、学生会/电子系身份、常去地点、当晚异常和可调取记录是什么。')"
    if old in out:
        out = out.replace(old, new, 1)
    return out


def strengthen_n601_post606(src: str) -> str:
    out = src
    old = "若606三人照片已出现，请解释照片来源、三人的真实姓名和POKER纹身组织含义，并直接交出缺失的605或下一份卷宗。"
    new = (
        "若606三人照片已出现，不要再解释纹身含义；现在只追后续证据：照片原件的保管链、Joker周克手机云端/账号、红桃Q刘瑄联络记录、"
        "于书华组织名册、谁把Joker引入衣帽间、谁杀了Joker、现场已经掌握但未交出的605以及607/608最终警方卷宗。"
    )
    if old not in out:
        raise RuntimeError("n601 post-606 anchor not found")
    out = out.replace(old, new, 1)
    old2 = "601-604或606若已出现，停止复述案情，只按官方材料追缺口：605、刘丽雯女儿失踪/报案/亲子鉴定、林渝植档案、心形胎记医疗记录、Joker人口贩卖名册、花纹村余党、张子韩密码来源和警方结案证据。"
    new2 = (
        "601-604或606若已出现，停止复述案情，先按POKER组织最终材料追缺口：606三人照片、605现场未交原件、"
        "Joker周克/于书华/红桃Q刘瑄组织名册、密码来源、衣帽间约见记录、死者手机云端和警方结案证据。"
    )
    if old2 in out:
        out = out.replace(old2, new2, 1)
    return out


def write_candidate(label: str, text: str) -> None:
    target = OUT / label
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    (target / "ai.py").write_text(text, encoding="utf-8")


def main() -> int:
    n607 = retitle(BASE_N607.read_text(encoding="utf-8"), "n613a")
    write_candidate("n613a", add_post707(apply_poker_606(n607)))

    n612 = retitle(BASE_N612.read_text(encoding="utf-8"), "n613b")
    write_candidate("n613b", tighten_n612_post707(n612))

    n601 = retitle(BASE_N601.read_text(encoding="utf-8"), "n613c")
    write_candidate("n613c", strengthen_n601_post606(n601))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
