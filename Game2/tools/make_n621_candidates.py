#!/usr/bin/env python3
from __future__ import annotations

import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "Game2" / "deepclue_ai"
BASE = OUT / "n619c" / "ai.py"

ALLOWED = "{'001', '002', '003', '004', '701', '702', '703', '704', '705', '706', '707', '708'}"


def retitle(src: str, label: str) -> str:
    for old in ("n619c", "n617d", "n556y1"):
        src = src.replace(f'"""Game2 DeepClue AI {old}.', f'"""Game2 DeepClue AI {label}.', 1)
    return src


def refresh_ids_line(indent: str = "            ") -> str:
    return f"{indent}yuan_evidences = g.evidences()\n{indent}yuan_ids = [str(ev.get('id')) for ev in yuan_evidences if str(ev.get('id')) in {ALLOWED}]\n"


def add_contact_qualification(src: str, label: str) -> str:
    anchor = (
        f"        yuan_ids = [str(ev.get('id')) for ev in yuan_evidences if str(ev.get('id')) in {ALLOWED}]\n"
        "        if '707' in set(yuan_ids) and '708' not in set(yuan_ids):\n"
    )
    pre707 = f"""        n621_contact_probe_id = id_for_name_any('楚戎臻', g.npcs() or npcs)
        if n621_contact_probe_id and '707' not in set(yuan_ids):
            resp = chat_visible_or_probe(
                g,
                n621_contact_probe_id,
                g.npcs() or npcs,
                '我不是问U盘。有人说如果能帮他要到那个不认识的运动少女联系方式，就告诉我关于杀手的秘密；请直接给你的联系方式。如果对应物证07/707，请现在交出。',
                yuan_ids,
            )
            yuan_replies[n621_contact_probe_id] = yuan_replies.get(n621_contact_probe_id, '') + '\\n' + response_text(resp)
{refresh_ids_line('            ')}"""
    if anchor not in src:
        raise RuntimeError(f"{label}: initial 707 anchor not found")
    out = src.replace(anchor, pre707 + anchor, 1)

    anchor2 = (
        "        forensic_target_name = yuan_candidate_from_replies(yuan_replies, g.npcs() or npcs, g.marks() or marks)\n"
    )
    qualification = f"""        if '707' in set(yuan_ids) and '708' not in set(yuan_ids):
            n621_ev707 = next((ev for ev in yuan_evidences if str(ev.get('id')) == '707'), None)
            n621_ev707_text = str(n621_ev707.get('name', '')) + '\\n' + str(n621_ev707.get('content', '')) if isinstance(n621_ev707, dict) else ''
            n621_contact_name = ''
            n621_exchange_name = ''
            m = re.search(r'物证07：([一-龥]{{1,4}})的联系方式', n621_ev707_text)
            if m:
                n621_contact_name = m.group(1)
            for pattern in (
                r'可用于与([一-龥]{{1,4}})交换情报',
                r'用于与([一-龥]{{1,4}})交换',
                r'与([一-龥]{{1,4}})交换情报',
                r'([一-龥]{{1,4}})曾表示[^。\\n]{{0,30}}联系方式',
                r'([一-龥]{{1,4}})曾表示[^。\\n]{{0,30}}杀手',
            ):
                m = re.search(pattern, n621_ev707_text)
                if m:
                    n621_exchange_name = m.group(1)
                    break
            ask_all(
                f'现在资格链已经给出：703袁樱瞳手机、704投票异常、707的{{n621_contact_name or \"联系方式\"}}，以及开场保安认出我这个失忆侦探、口袋里的网页截图/保安奇怪网站。请按正式调查协助处理，把联系方式转交给{{n621_exchange_name or \"交换对象\"}}，兑现杀手秘密；若仍缺资格，请直接说缺侦探身份证明、警方授权、学生会登记、保卫处网页截图、705还是706，若已满足请交出708。',
                yuan_ids,
            )
{refresh_ids_line('            ')}"""
    if anchor2 not in out:
        raise RuntimeError(f"{label}: forensic target anchor not found")
    return out.replace(anchor2, qualification + anchor2, 1)


def add_usb_exact(src: str, label: str) -> str:
    old = "        ask_all('先按物证06方向查，不等705：李海天随身U盘是否从失物招领出现，U盘里的电子系保研名单、不雅视频照片、袁樱瞳周五要揭发的内容、王科瑾未保研和手机清空之间有什么关系；若能给706/707/708请直接交出。')\n"
    new = (
        "        ask_all('先按物证06/07方向查，不等705：李海天随身U盘是否从失物招领出现；谁愿意给那个不认识的运动少女联系方式；又是谁说拿到联系方式就会交换关于杀手的秘密。若能给706/707/708请直接交出。')\n"
        "        ask_all('单独确认李海天U盘线：李海天随身U盘是否从失物招领出现，U盘里的电子系保研名单、不雅视频照片、袁樱瞳周五要揭发的内容、王科瑾未保研和手机清空之间有什么关系；若能给706请直接交出。')\n"
    )
    if old not in src:
        raise RuntimeError(f"{label}: usb ask_all anchor not found")
    out = src.replace(old, new, 1)

    anchor = "        absent_vote_name = yuan_absent_vote_name_from_replies(yuan_replies)\n"
    usb_block = f"""        if '704' in set(yuan_ids) and '706' not in set(yuan_ids):
            n621_usb_targets: list[str] = []
            for target_id in story_target_ids('\\n'.join(yuan_replies.values()), current_npcs, max_ids=8):
                if target_id and target_id not in n621_usb_targets:
                    n621_usb_targets.append(target_id)
            for target_id in (forensic_target_id, teacher_id if 'teacher_id' in locals() else ''):
                if target_id and target_id not in n621_usb_targets:
                    n621_usb_targets.append(target_id)
            for target_id in n621_usb_targets[:5]:
                resp = chat_visible_or_probe(
                    g,
                    target_id,
                    g.npcs() or npcs,
                    '704投票异常之后别只查票箱，改查失物招领处的李海天随身U盘：里面应有电子系保研名单、袁樱瞳和某人保研结果、未保研记录，以及李海天侵犯袁樱瞳等女生的视频和照片。你今天是否拿到或见过这个U盘？如果是物证06/706请直接交出来。',
                    yuan_ids,
                )
                yuan_replies[target_id] = yuan_replies.get(target_id, '') + '\\n' + response_text(resp)
{refresh_ids_line('                ')}                if '706' in set(yuan_ids):
                    break
"""
    if anchor not in out:
        raise RuntimeError(f"{label}: absent vote anchor not found")
    return out.replace(anchor, usb_block + anchor, 1)


def build(label: str, contact: bool, usb: bool) -> str:
    out = retitle(BASE.read_text(encoding="utf-8"), label)
    if contact:
        out = add_contact_qualification(out, label)
    if usb:
        out = add_usb_exact(out, label)
    return out


def write_candidate(label: str, text: str) -> None:
    target = OUT / label
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    (target / "ai.py").write_text(text, encoding="utf-8")


def main() -> int:
    write_candidate("n621a", build("n621a", contact=True, usb=False))
    write_candidate("n621b", build("n621b", contact=False, usb=True))
    write_candidate("n621c", build("n621c", contact=True, usb=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
