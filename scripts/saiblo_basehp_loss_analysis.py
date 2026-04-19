#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
SDK_DIR = ROOT_DIR / "Game1" / "Ant-Game" / "SDK"
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(SDK_DIR) not in sys.path:
    sys.path.insert(0, str(SDK_DIR))

from utils.constants import AntStatus, OFFSET, PLAYER_BASES  # type: ignore

ANCHORS = {
    0: {(4, 9): "front_anchor", (5, 7): "rear_left", (5, 11): "rear_right", (6, 9): "mid_anchor"},
    1: {(14, 9): "front_anchor", (13, 7): "rear_left", (13, 11): "rear_right", (12, 9): "mid_anchor"},
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Analyze why our base HP was lost in downloaded Saiblo replays")
    parser.add_argument("--save-root", required=True)
    parser.add_argument("--our-code-id", required=True)
    parser.add_argument("--output", default="")
    return parser


def normalize_code_id(value: str) -> str:
    return str(value or "").replace("-", "").lower().strip()


def seat_of(detail: dict[str, Any], our_code_id: str) -> int | None:
    for idx, row in enumerate(detail.get("info", [])):
        if not isinstance(row, dict):
            continue
        code = row.get("code", {})
        if not isinstance(code, dict):
            continue
        if normalize_code_id(str(code.get("id", ""))) == our_code_id:
            return idx
    return None


def neighbors(player: int, pos: tuple[int, int]) -> set[tuple[int, int]]:
    x, y = pos
    return {(x + dx, y + dy) for dx, dy in OFFSET[player]}


def classify_zone(base: tuple[int, int], prev_pos: tuple[int, int] | None) -> str:
    if prev_pos is None:
        return "unknown"
    bx, by = base
    x, y = prev_pos
    if base == (2, 9):
        if x < bx:
            return "behind"
        if x > bx and abs(y - by) <= 1:
            return "front"
        if x > bx:
            return "front_side"
        return "side"
    if x > bx:
        return "behind"
    if x < bx and abs(y - by) <= 1:
        return "front"
    if x < bx:
        return "front_side"
    return "side"


def load_first_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def summarize_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    by_kind = Counter(e["kind"] for e in events)
    by_level = Counter(e["level"] for e in events)
    by_zone = Counter(e["zone"] for e in events)
    by_anchor = Counter(tuple(e["alive_anchors"]) for e in events)
    recent_tp = sum(1 for e in events if e["teleport_recent"])
    out: dict[str, Any] = {
        "count": len(events),
        "by_kind": dict(by_kind),
        "by_level": dict(by_level),
        "by_zone": dict(by_zone),
        "teleport_recent_count": recent_tp,
        "teleport_recent_rate": round(recent_tp / len(events), 3) if events else None,
        "teleport_within": dict(Counter(e["teleport_within"] for e in events if e["teleport_within"] is not None)),
        "alive_anchor_sets": [[list(k), v] for k, v in by_anchor.most_common(8)],
        "sample_events": events[:16],
    }
    return out


def main() -> int:
    args = build_parser().parse_args()
    save_root = Path(args.save_root).resolve()
    our_code_id = normalize_code_id(args.our_code_id)
    result: dict[str, Any] = {
        "save_root": str(save_root),
        "our_code_id": our_code_id,
        "groups": {},
    }
    all_events: list[dict[str, Any]] = []

    for group_dir in sorted(p for p in save_root.iterdir() if p.is_dir()):
        events: list[dict[str, Any]] = []
        for detail_path in sorted(group_dir.glob("match_*.json")):
            detail = load_first_json(detail_path)
            if not isinstance(detail, dict) or detail.get("state") != "评测成功":
                continue
            match_id = int(detail.get("id", 0) or 0)
            replay_path = group_dir / f"{match_id}.json"
            if not replay_path.is_file():
                continue
            replay = load_first_json(replay_path)
            if not isinstance(replay, list):
                continue
            our_seat = seat_of(detail, our_code_id)
            if our_seat is None:
                continue
            opp_seat = 1 - our_seat
            base = PLAYER_BASES[our_seat]
            history: dict[int, list[dict[str, Any]]] = {}

            for round_index, frame in enumerate(replay, start=1):
                if not isinstance(frame, dict):
                    continue
                round_state = frame.get("round_state", {})
                if not isinstance(round_state, dict):
                    continue
                if round_index > 1:
                    prev_state = replay[round_index - 2]["round_state"]
                    camp_drop = int(prev_state["camps"][our_seat]) - int(round_state["camps"][our_seat])
                    if camp_drop > 0:
                        success_ants = [
                            ant
                            for ant in round_state.get("ants", [])
                            if isinstance(ant, dict)
                            and int(ant.get("player", -1)) == opp_seat
                            and int(ant.get("status", -1)) == int(AntStatus.SUCCESS)
                            and (int(ant["pos"]["x"]), int(ant["pos"]["y"])) == base
                        ]
                        if len(success_ants) < camp_drop:
                            extras = [
                                ant
                                for ant in round_state.get("ants", [])
                                if isinstance(ant, dict)
                                and int(ant.get("player", -1)) == opp_seat
                                and int(ant.get("status", -1)) == int(AntStatus.SUCCESS)
                            ]
                            seen = {int(ant["id"]) for ant in success_ants}
                            success_ants.extend([ant for ant in extras if int(ant["id"]) not in seen])

                        prev_tower_pos = {
                            (int(t["pos"]["x"]), int(t["pos"]["y"])): t
                            for t in prev_state.get("towers", [])
                            if isinstance(t, dict) and int(t.get("player", -1)) == our_seat
                        }

                        for ant in success_ants[:camp_drop]:
                            ant_id = int(ant["id"])
                            hist = history.get(ant_id, [])
                            prev_ant = hist[-1] if len(hist) >= 1 else None
                            prev_pos = None
                            if prev_ant is not None:
                                prev_pos = (int(prev_ant["pos"]["x"]), int(prev_ant["pos"]["y"]))

                            tp_recent = False
                            tp_within: int | None = None
                            for k in range(1, min(len(hist), 6)):
                                newer = hist[-k]
                                older = hist[-k - 1]
                                newer_pos = (int(newer["pos"]["x"]), int(newer["pos"]["y"]))
                                older_pos = (int(older["pos"]["x"]), int(older["pos"]["y"]))
                                if newer_pos not in neighbors(opp_seat, older_pos):
                                    tp_recent = True
                                    tp_within = k if tp_within is None else min(tp_within, k)

                            alive_anchors = tuple(
                                sorted(name for pos, name in ANCHORS[our_seat].items() if pos in prev_tower_pos)
                            )
                            event = {
                                "group": group_dir.name,
                                "match_id": match_id,
                                "round": round_index,
                                "our_seat": our_seat,
                                "kind": int(ant.get("kind", -1)),
                                "level": int(ant.get("level", -1)),
                                "behavior": int(ant.get("behavior", -1)),
                                "hp": int(ant.get("hp", 0)),
                                "age": int(ant.get("age", 0)),
                                "zone": classify_zone(base, prev_pos),
                                "teleport_recent": tp_recent,
                                "teleport_within": tp_within,
                                "alive_anchors": list(alive_anchors),
                            }
                            events.append(event)
                            all_events.append(event)

                current_ants = round_state.get("ants", [])
                for ant in current_ants:
                    if not isinstance(ant, dict):
                        continue
                    ant_id = int(ant.get("id", -1))
                    if ant_id < 0:
                        continue
                    history.setdefault(ant_id, []).append(ant)
                    if len(history[ant_id]) > 8:
                        history[ant_id] = history[ant_id][-8:]

        result["groups"][group_dir.name] = summarize_events(events)

    result["combined"] = summarize_events(all_events)
    if args.output:
        out_path = Path(args.output).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
