#!/usr/bin/env python3
from __future__ import annotations

import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'Game2' / 'deepclue_ai'
BASE = OUT / 'n606a' / 'ai.py'


TEACHER_704_BLOCK = """        if teacher_id and '704' in set(yuan_ids):
            resp = g.chat(teacher_id, '704投票纸只查原件 custody：票箱谁保管、谁能接触原始票、笔迹比对、废票/补票、课堂录像、教师办公室监控和行政系统日志在哪里？如果这能打开物证06/706，请给证据编号和持有人。', yuan_ids)
            yuan_replies[teacher_id] = yuan_replies.get(teacher_id, '') + '\\n' + response_text(resp)
            yuan_evidences = g.evidences()
            yuan_ids = [str(ev.get('id')) for ev in yuan_evidences if str(ev.get('id')) in {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706', '707', '708'}]
"""

YUAN_USB_AFTER_TEACHER = TEACHER_704_BLOCK + """        if teacher_id and '704' in set(yuan_ids) and '706' not in set(yuan_ids):
            resp = g.chat(teacher_id, '不要泛问物证编号，只沿投票异常和电子系材料查：多出的异笔迹票、票箱锁入办公室、失物招领处李海天随身U盘、电子系保研名单、不雅视频照片、谁能接触U盘和原始票；如果这是物证06/706请直接交出。', yuan_ids)
            yuan_replies[teacher_id] = yuan_replies.get(teacher_id, '') + '\\n' + response_text(resp)
            yuan_evidences = g.evidences()
            yuan_ids = [str(ev.get('id')) for ev in yuan_evidences if str(ev.get('id')) in {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706', '707', '708'}]
"""

FORENSIC_ADMIN_QUESTION = "不要只解释投票纸。出国名额的行政链在哪里：推荐表、学院系统日志、名单变更、导师签字、办公室邮件/监控、谁能改结果、袁樱瞳周五要揭发哪份记录？如果是物证06/706请直接给编号和持有人。"
FORENSIC_USB_QUESTION = "你和袁樱瞳竞争出国或保研名额，又接触过手机/行李箱线。不要解释投票纸，直接说李海天随身U盘是否在失物招领、里面的电子系保研名单和不雅视频照片是谁拿到、谁因此要清空袁樱瞳手机；若这是物证06/706请交出，若已出现请继续给707/708。"

POST_706_ANCHOR = """        if '706' in set(yuan_ids):
            ask_all('706已经出现。继续按后续阶段追707/708：尸源DNA、手机原图元数据、保卫处网页后台、1919车辆登记、生物馆/世纪林监控、教务投票原件和李海天旧案卷宗里，下一份官方物证编号、证据名、持有人分别是什么？', yuan_ids)
            yuan_evidences = g.evidences()
            yuan_ids = [str(ev.get('id')) for ev in yuan_evidences if str(ev.get('id')) in {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706', '707', '708'}]
"""

POST_706_TARGETED = """        if '706' in set(yuan_ids):
            ev706 = next((ev for ev in yuan_evidences if str(ev.get('id')) == '706'), None)
            ev706_text = str(ev706.get('name', '')) + '\\n' + str(ev706.get('content', '')) if isinstance(ev706, dict) else ''
            post706_targets: list[str] = []
            for npc_id in story_target_ids(ev706_text + '\\n' + '\\n'.join(yuan_replies.values()), current_npcs, max_ids=8):
                if npc_id and npc_id not in post706_targets:
                    post706_targets.append(npc_id)
            for npc_id in (forensic_target_id, teacher_id, runner_id if 'runner_id' in locals() else '', guard_id if 'guard_id' in locals() else ''):
                if npc_id and npc_id not in post706_targets:
                    post706_targets.append(npc_id)
            for source_id in post706_targets[:5]:
                resp = chat_visible_or_probe(g, source_id, g.npcs() or npcs, '706 U盘已经说明李海天随身U盘、电子系保研名单、袁樱瞳/楚戎臻保研成功、王科瑾未保研以及李海天侵犯女生视频照片。现在只追下一阶段：谁拿走/隐藏U盘，谁清空袁樱瞳手机，谁利用视频或保研名单杀人，707/708的证据编号、证据名和持有人是什么。', yuan_ids)
                yuan_replies[source_id] = yuan_replies.get(source_id, '') + '\\n' + response_text(resp)
                yuan_evidences = g.evidences()
                yuan_ids = [str(ev.get('id')) for ev in yuan_evidences if str(ev.get('id')) in {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706', '707', '708'}]
                if {'707', '708'} & set(yuan_ids):
                    break
            if not ({'707', '708'} & set(yuan_ids)):
                ask_all('706已经出现。不要回到投票细节，沿U盘内容追707/708：李海天侵犯袁樱瞳等女生的视频照片、电子系保研名单、王科瑾未保研、手机清空、凌晨尸体照片、生物馆和世纪林尸块之间，下一份官方物证是什么？', yuan_ids)
            yuan_evidences = g.evidences()
            yuan_ids = [str(ev.get('id')) for ev in yuan_evidences if str(ev.get('id')) in {'001', '002', '003', '004', '701', '702', '703', '704', '705', '706', '707', '708'}]
"""

AFTER_INITIAL_YUAN = """        ask_all('不要只讲传闻。请说明你本人看到或确认了什么：谁从生物馆出来，谁接触尸块或行李箱，谁清空手机，谁伪造死亡时间，谁从投票中获利？')
"""

USB_FIRST_YUAN = AFTER_INITIAL_YUAN + """        ask_all('先按物证06方向查，不等705：李海天随身U盘是否从失物招领出现，U盘里的电子系保研名单、不雅视频照片、袁樱瞳周五要揭发的内容、王科瑾未保研和手机清空之间有什么关系；若能给706/707/708请直接交出。')
"""

OLD_POKER_QS = [
    "503/504和601-604已经出现。不要再说“还差最后一块”，直接调刑警卷宗：死者手机云端名单、Joker账号实名/IP/设备、邀请函源文件、林渝植失踪卷宗、张子韩女儿DNA、王科瑾电脑银行流水和最终物证，下一编号、名称、持有人分别是什么？",
    "你就是林渝植/真正梅花5，504的LYZ项链和601失踪少女特征已经对上。请直接说明你是否是张子韩寻找的女儿、Joker如何控制你、谁杀了Joker，以及下一份DNA/云端名单/最终物证编号和持有人。",
    "601报道失踪少女、603/604证明你曾是刘丽雯医生；501又说你为找女儿被王科瑾/于书华骗走五十万。请直接说明失踪女儿、林渝植、右眼角胎记、Joker人口贩卖集团和死者手机云端名单之间的证据链，并交出下一物证编号。",
    "你电脑里的银行流水和501匿名五十万是后续关键。请不要再口头辩解，直接交出王科瑾电脑、转账源账户、于书华身份、Joker资金流、张子韩女儿线索和人口贩卖名单对应的下一物证编号。",
    "你负责邀请函和接待。503显示梅花5邀请函格式不同，201又有Joker转账定金和地址表。请直接交出邀请函源文件、寄送记录、Joker账号设备/IP、死者手机云端名单或最终物证编号。",
]

NEW_POKER_QS = [
    "503/504和601-604已经出现后不要追散乱DNA，第一优先查606三人照片和左臂POKER纹身：Joker周克、于书华、红桃Q/接待者是否同属花纹村组织，照片原件、组织名册、现场未交605/606由谁保管。",
    "你就是林渝植/真正梅花5，504的LYZ项链和601失踪少女特征已经对上。请只回答左臂POKER纹身、606三人照片、Joker如何控制你、谁把Joker引入衣帽间，以及605/607/608的下一份官方证据。",
    "601报道失踪少女、603/604证明你曾是刘丽雯医生。现在不要泛讲亲子鉴定，直接查女儿、心形胎记、Joker人口贩卖集团、POKER纹身三人照片和现场未交605/606/607/608。",
    "501匿名五十万和于书华身份已经指向你。请直接说明于书华、Joker周克、红桃Q/刘瑄、左臂POKER纹身、组织名册和三人照片之间的关系，并交出605/606/607/608。",
    "你负责邀请函和接待，又可能对应红桃Q/刘瑄。请不要复述接待工作，只查Joker周克、于书华、红桃Q、左臂POKER纹身、606三人照片、组织名册和现场未交证据。",
]


def build(label: str, src: str) -> str:
    out = src
    if label in {'n607a', 'n607b'}:
        if TEACHER_704_BLOCK not in out:
            raise RuntimeError('teacher 704 block not found')
        out = out.replace(TEACHER_704_BLOCK, YUAN_USB_AFTER_TEACHER, 1)
        if FORENSIC_ADMIN_QUESTION not in out:
            raise RuntimeError('forensic admin question not found')
        out = out.replace(FORENSIC_ADMIN_QUESTION, FORENSIC_USB_QUESTION, 1)
        if POST_706_ANCHOR not in out:
            raise RuntimeError('post 706 anchor not found')
        out = out.replace(POST_706_ANCHOR, POST_706_TARGETED, 1)
    if label == 'n607b':
        if AFTER_INITIAL_YUAN not in out:
            raise RuntimeError('initial Yuan anchor not found')
        out = out.replace(AFTER_INITIAL_YUAN, USB_FIRST_YUAN, 1)
    if label == 'n607c':
        for old, new in zip(OLD_POKER_QS, NEW_POKER_QS, strict=True):
            if old not in out:
                raise RuntimeError(f'poker question not found: {old[:20]}')
            out = out.replace(old, new, 1)
        out = out.replace("deep_targets[:6]", "deep_targets[:8]", 1)
    return out


def write_candidate(label: str, text: str) -> None:
    target = OUT / label
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    (target / 'ai.py').write_text(text, encoding='utf-8')


def main() -> int:
    src = BASE.read_text(encoding='utf-8')
    for label in ('n607a', 'n607b', 'n607c'):
        write_candidate(label, build(label, src))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
