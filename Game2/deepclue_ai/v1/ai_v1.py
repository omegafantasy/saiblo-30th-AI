#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import struct
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any


class SDK:
    def __init__(self) -> None:
        self._stdin = sys.stdin.buffer
        self._stdout = sys.stdout.buffer

    def _send(self, data: dict[str, Any]) -> None:
        msg = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self._stdout.write(struct.pack(">I", len(msg)) + msg)
        self._stdout.flush()

    def _receive(self) -> dict[str, Any]:
        header = self._stdin.read(4)
        line = self._stdin.readline()
        if not line:
            raise EOFError("stdin closed")
        msg = line.decode("utf-8", errors="replace").strip()
        return json.loads(msg) if msg else {}

    def request(self, action: str, **kwargs: Any) -> dict[str, Any] | list[Any]:
        payload = {"action": action, **kwargs}
        self._send(payload)
        return self._receive()

    def call_llm(self, **kwargs: Any) -> dict[str, Any]:
        resp = self.request("call", **kwargs)
        return resp if isinstance(resp, dict) else {"error": f"invalid llm response: {type(resp).__name__}"}


def log(*args: Any) -> None:
    print(*args, file=sys.stderr, flush=True)


@dataclass
class KnowledgeBase:
    background: str = ""
    hint: str = ""
    stage: int = 1
    npcs: list[str] = field(default_factory=list)
    testimony: list[dict[str, Any]] = field(default_factory=list)
    others: list[dict[str, Any]] = field(default_factory=list)
    achievements: list[dict[str, Any]] = field(default_factory=list)
    asked: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))
    stage_rounds: dict[int, int] = field(default_factory=lambda: defaultdict(int))

    def evidence_ids(self) -> list[str]:
        ids = []
        for item in self.testimony:
            if isinstance(item, dict) and item.get("id"):
                ids.append(str(item["id"]))
        for item in self.others:
            if isinstance(item, dict) and item.get("id"):
                ids.append(str(item["id"]))
        return ids

    def evidence_text(self, limit: int = 12000) -> str:
        chunks: list[str] = []
        for entry in self.testimony:
            if not isinstance(entry, dict):
                continue
            chunks.append(f"[T {entry.get('id')}] {entry.get('name','')} {entry.get('content','')}")
        for entry in self.others:
            if not isinstance(entry, dict):
                continue
            chunks.append(f"[E {entry.get('id')}] {entry.get('name','')} {entry.get('content','')}")
        for entry in self.achievements:
            if not isinstance(entry, dict):
                continue
            chunks.append(f"[A {entry.get('id')}] {entry.get('name','')} {entry.get('description','')}")
        text = "\n".join(chunks)
        return text[:limit]


def normalize_json_object(text: str) -> dict[str, Any] | None:
    text = text.strip()
    if not text:
        return None
    match = re.search(r"\{.*\}", text, re.S)
    if match:
        text = match.group(0)
    try:
        obj = json.loads(text)
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None


def refresh_global_state(sdk: SDK, kb: KnowledgeBase) -> None:
    background = sdk.request("background")
    if isinstance(background, dict):
        kb.background = str(background.get("background", ""))
    stage = sdk.request("stage")
    if isinstance(stage, dict):
        kb.stage = int(stage.get("stage", kb.stage) or kb.stage)
    hint = sdk.request("hint")
    if isinstance(hint, dict):
        kb.hint = str(hint.get("hint", ""))
    npcs = sdk.request("npcs")
    if isinstance(npcs, list):
        kb.npcs = [str(x) for x in npcs]
    testimony = sdk.request("testimony")
    if isinstance(testimony, list):
        kb.testimony = [x for x in testimony if isinstance(x, dict)]
    others = sdk.request("others")
    if isinstance(others, dict):
        items = others.get("evidences", [])
        if isinstance(items, list):
            kb.others = [x for x in items if isinstance(x, dict)]
    achievements = sdk.request("achievements")
    if isinstance(achievements, dict):
        items = achievements.get("achievements", [])
        if isinstance(items, list):
            kb.achievements = [x for x in items if isinstance(x, dict)]


def choose_evidence_for_npc(kb: KnowledgeBase, npc: str, budget: int = 3) -> list[str]:
    del npc
    ids = kb.evidence_ids()
    if not ids:
        return []
    tail = ids[-budget:]
    if len(tail) < budget:
        return ids[:budget]
    return tail


def fallback_questions(kb: KnowledgeBase, npc: str) -> list[dict[str, Any]]:
    base = [
        {"question": f"请完整回忆案发前后你看到和做过的事。", "evidences": []},
        {"question": f"你与死者、其他关键人物之间是什么关系？", "evidences": choose_evidence_for_npc(kb, npc, 2)},
        {"question": f"请解释你时间线中最可疑、最容易被误解的一段。", "evidences": choose_evidence_for_npc(kb, npc, 3)},
    ]
    return base


def llm_plan_questions(sdk: SDK, kb: KnowledgeBase, npc: str, marks: dict[str, bool]) -> list[dict[str, Any]]:
    prompt = {
        "background": kb.background[:2500],
        "hint": kb.hint[:1200],
        "stage": kb.stage,
        "npc": npc,
        "npc_has_more": bool(marks.get(npc, False)),
        "known_evidence": kb.evidence_text(limit=6000),
        "already_asked": sorted(kb.asked[npc])[-8:],
        "requirements": [
            "输出严格 JSON 对象，格式: {\"questions\":[{\"question\":...,\"evidences\":[...]}, ...]}",
            "最多 3 个问题",
            "优先挖掘时间线、作案机会、关系、动机、证据矛盾",
            "evidences 里只填已经出现过的证据 ID",
        ],
    }
    resp = sdk.call_llm(
        messages=[
            {"role": "system", "content": "你是侦探推理游戏中的提问规划器。必须只输出 JSON。"},
            {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
        ],
        temperature=0.2,
    )
    if "error" in resp:
        return fallback_questions(kb, npc)
    try:
        content = resp["choices"][0]["message"]["content"]
    except Exception:
        return fallback_questions(kb, npc)
    obj = normalize_json_object(content)
    if not obj:
        return fallback_questions(kb, npc)
    items = obj.get("questions", [])
    if not isinstance(items, list):
        return fallback_questions(kb, npc)
    out: list[dict[str, Any]] = []
    known_ids = set(kb.evidence_ids())
    for item in items[:3]:
        if not isinstance(item, dict):
            continue
        question = str(item.get("question", "")).strip()
        evidences = item.get("evidences", [])
        if not question:
            continue
        if not isinstance(evidences, list):
            evidences = []
        clean_ids = [str(x) for x in evidences if str(x) in known_ids][:3]
        out.append({"question": question[:160], "evidences": clean_ids})
    return out or fallback_questions(kb, npc)


def talk_to_npc(sdk: SDK, kb: KnowledgeBase, npc: str, question: str, evidences: list[str]) -> None:
    key = f"{question}|{'/'.join(evidences)}"
    if key in kb.asked[npc]:
        return
    kb.asked[npc].add(key)
    resp = sdk.request("chat", npc=npc, question=question, evidences=evidences)
    if isinstance(resp, dict):
        if "stage" in resp:
            try:
                kb.stage = int(resp.get("stage", kb.stage) or kb.stage)
            except Exception:
                pass
        unlocks = resp.get("unlock_testimony", [])
        if isinstance(unlocks, list):
            known = {str(x.get("id")) for x in kb.testimony if isinstance(x, dict)}
            for item in unlocks:
                if isinstance(item, dict) and str(item.get("id")) not in known:
                    kb.testimony.append(item)
                    known.add(str(item.get("id")))
        achievements = resp.get("achievements", [])
        if isinstance(achievements, list):
            known = {str(x.get("id")) for x in kb.achievements if isinstance(x, dict)}
            for item in achievements:
                if isinstance(item, dict) and str(item.get("id")) not in known:
                    kb.achievements.append(item)
                    known.add(str(item.get("id")))


def analyze_solution(sdk: SDK, kb: KnowledgeBase) -> dict[str, str]:
    prompt = {
        "background": kb.background,
        "hint": kb.hint,
        "stage": kb.stage,
        "npcs": kb.npcs,
        "evidence": kb.evidence_text(limit=10000),
        "requirements": [
            "输出严格 JSON 对象，格式: {\"murderer\":...,\"motivation\":...,\"method\":...,\"confidence\":0-1,\"why\":...}",
            "优先保证 murderer 正确，其次 motivation 和 method",
            "回答应简洁，不要输出额外解释段落",
        ],
    }
    resp = sdk.call_llm(
        messages=[
            {"role": "system", "content": "你是刑侦推理助手。必须只输出 JSON。"},
            {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
        ],
        temperature=0.1,
    )
    default = {"murderer": "", "motivation": kb.hint[:60], "method": kb.hint[:60]}
    if "error" in resp:
        return default
    try:
        content = resp["choices"][0]["message"]["content"]
    except Exception:
        return default
    obj = normalize_json_object(content)
    if not obj:
        return default
    out = {
        "murderer": str(obj.get("murderer", "")).strip(),
        "motivation": str(obj.get("motivation", "")).strip(),
        "method": str(obj.get("method", "")).strip(),
    }
    if not out["murderer"]:
        out["murderer"] = kb.npcs[0] if kb.npcs else ""
    if not out["motivation"]:
        out["motivation"] = kb.hint[:80] or kb.background[:80]
    if not out["method"]:
        out["method"] = kb.hint[:80] or kb.background[:80]
    return out


def solve_case(sdk: SDK, case_index: int) -> bool:
    kb = KnowledgeBase()
    refresh_global_state(sdk, kb)
    if not kb.background and not kb.npcs:
        return False
    log(f"[game2] case={case_index} stage={kb.stage} npcs={len(kb.npcs)} testimonies={len(kb.testimony)} others={len(kb.others)}")

    max_rounds = 7
    for _ in range(max_rounds):
        refresh_global_state(sdk, kb)
        marks_resp = sdk.request("marks")
        marks = marks_resp if isinstance(marks_resp, dict) else {}
        pending = [npc for npc in kb.npcs if bool(marks.get(npc, False))]
        if not pending:
            pending = list(kb.npcs)
        for npc in pending:
            plans = llm_plan_questions(sdk, kb, npc, marks)
            for plan in plans[:2]:
                question = str(plan.get("question", "")).strip()
                evidences = [str(x) for x in plan.get("evidences", [])][:3]
                if question:
                    talk_to_npc(sdk, kb, npc, question, evidences)
        kb.stage_rounds[kb.stage] += 1
        refresh_global_state(sdk, kb)
        marks_resp = sdk.request("marks")
        marks = marks_resp if isinstance(marks_resp, dict) else {}
        if not any(bool(v) for v in marks.values()) and kb.stage_rounds[kb.stage] >= 2:
            break

    answer = analyze_solution(sdk, kb)
    log(f"[game2] answer case={case_index} murderer={answer['murderer']!r}")
    resp = sdk.request("answer", **answer)
    log(f"[game2] answer_result case={case_index} resp={resp}")
    return True


def main() -> int:
    sdk = SDK()
    welcome = sdk._receive()
    log(f"[game2] welcome={welcome}")
    case_index = 0
    while True:
        try:
            ok = solve_case(sdk, case_index)
        except EOFError:
            break
        except Exception as exc:
            log(f"[game2] fatal case={case_index} exc={type(exc).__name__}: {exc}")
            try:
                sdk.request("answer", murderer="", motivation="", method="")
            except Exception:
                pass
            break
        if not ok:
            break
        case_index += 1
        if case_index >= 4:
            break
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
