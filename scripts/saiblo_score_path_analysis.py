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

from utils.constants import AntStatus, PLAYER_BASES  # type: ignore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Analyze actual scorer-ant paths in downloaded Saiblo replays")
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


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def normalize_pos(our_seat: int, pos: tuple[int, int]) -> tuple[int, int]:
    if our_seat == 0:
        return pos
    return (18 - pos[0], pos[1])


def compress_consecutive(path: list[tuple[int, int]]) -> list[tuple[int, int]]:
    out: list[tuple[int, int]] = []
    for pos in path:
        if not out or out[-1] != pos:
            out.append(pos)
    return out


def path_tail(path: list[tuple[int, int]], size: int) -> tuple[tuple[int, int], ...]:
    if len(path) <= size:
        return tuple(path)
    return tuple(path[-size:])


def summarize_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    entry_cells = Counter(tuple(event["entry_cell"]) for event in events if event["entry_cell"] is not None)
    last3 = Counter(tuple(tuple(cell) for cell in event["tail3"]) for event in events)
    last4 = Counter(tuple(tuple(cell) for cell in event["tail4"]) for event in events)
    last6 = Counter(tuple(tuple(cell) for cell in event["tail6"]) for event in events)
    by_kind = Counter(event["kind"] for event in events)
    by_zone = Counter(event["zone"] for event in events)
    return {
        "count": len(events),
        "by_kind": dict(by_kind),
        "by_zone": dict(by_zone),
        "entry_cells": [[list(k), v] for k, v in entry_cells.most_common(16)],
        "tail3_paths": [[list(map(list, k)), v] for k, v in last3.most_common(16)],
        "tail4_paths": [[list(map(list, k)), v] for k, v in last4.most_common(16)],
        "tail6_paths": [[list(map(list, k)), v] for k, v in last6.most_common(16)],
        "sample_events": events[:20],
    }


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
            detail = load_json(detail_path)
            if not isinstance(detail, dict) or detail.get("state") != "评测成功":
                continue
            match_id = int(detail.get("id", 0) or 0)
            replay_path = group_dir / f"{match_id}.json"
            if not replay_path.is_file():
                continue
            replay = load_json(replay_path)
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

                        for ant in success_ants[:camp_drop]:
                            ant_id = int(ant["id"])
                            hist = history.get(ant_id, [])
                            raw_path = [
                                normalize_pos(our_seat, (int(old["pos"]["x"]), int(old["pos"]["y"])))
                                for old in hist[-8:]
                            ]
                            raw_path.append(normalize_pos(our_seat, base))
                            compressed = compress_consecutive(raw_path)
                            entry_cell = compressed[-2] if len(compressed) >= 2 else None
                            event = {
                                "group": group_dir.name,
                                "match_id": match_id,
                                "round": round_index,
                                "our_seat": our_seat,
                                "kind": int(ant.get("kind", -1)),
                                "level": int(ant.get("level", -1)),
                                "hp": int(ant.get("hp", 0)),
                                "age": int(ant.get("age", 0)),
                                "zone": classify_zone((2, 9), entry_cell),
                                "entry_cell": list(entry_cell) if entry_cell is not None else None,
                                "tail3": [list(cell) for cell in path_tail(compressed, 3)],
                                "tail4": [list(cell) for cell in path_tail(compressed, 4)],
                                "tail6": [list(cell) for cell in path_tail(compressed, 6)],
                            }
                            events.append(event)
                            all_events.append(event)

                for ant in round_state.get("ants", []):
                    if not isinstance(ant, dict):
                        continue
                    ant_id = int(ant.get("id", -1))
                    if ant_id < 0:
                        continue
                    history.setdefault(ant_id, []).append(ant)
                    if len(history[ant_id]) > 10:
                        history[ant_id] = history[ant_id][-10:]

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
