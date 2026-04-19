#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from autolab.replay_analysis import ACTION_LABELS


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Dump a compact round window from a local Game1 replay")
    parser.add_argument("--replay", required=True, help="replay json path")
    parser.add_argument("--start", type=int, required=True, help="inclusive start round index")
    parser.add_argument("--end", type=int, required=True, help="inclusive end round index")
    parser.add_argument("--output", default="", help="optional json output path")
    return parser


def _load_replay(path: Path) -> List[Dict[str, Any]]:
    raw = path.read_text(encoding="utf-8", errors="ignore")
    decoder = json.JSONDecoder()
    payload, _ = decoder.raw_decode(raw.lstrip())
    if not isinstance(payload, list):
        raise RuntimeError(f"unsupported replay root type: {type(payload).__name__}")
    return payload


def _op_type(op: Any) -> int:
    if isinstance(op, dict):
        try:
            return int(op.get("type", -1))
        except Exception:
            return -1
    if isinstance(op, list) and op:
        try:
            return int(op[0])
        except Exception:
            return -1
    return -1


def _label_action(op: Any) -> str:
    return ACTION_LABELS.get(_op_type(op), f"op_{_op_type(op)}")


def _tower_counts(state: Any) -> List[int]:
    counts = [0, 0]
    if not isinstance(state, dict):
        return counts
    towers = state.get("towers", [])
    if not isinstance(towers, list):
        return counts
    for tower in towers:
        if not isinstance(tower, dict):
            continue
        try:
            player = int(tower.get("player", -1))
            tower_type = int(tower.get("type", -1))
        except Exception:
            continue
        if player in (0, 1) and tower_type >= 0:
            counts[player] += 1
    return counts


def _coins(state: Any) -> List[int]:
    values = [0, 0]
    if not isinstance(state, dict):
        return values
    raw = state.get("coins", [])
    if not isinstance(raw, list):
        return values
    for idx in (0, 1):
        if idx >= len(raw):
            continue
        try:
            values[idx] = int(raw[idx])
        except Exception:
            values[idx] = 0
    return values


def _base_hp(state: Any) -> List[int]:
    values = [0, 0]
    if not isinstance(state, dict):
        return values
    raw = state.get("camps", [])
    if not isinstance(raw, list):
        return values
    for idx in (0, 1):
        if idx >= len(raw):
            continue
        try:
            values[idx] = int(raw[idx])
        except Exception:
            values[idx] = 0
    return values


def _ant_counts(state: Any) -> List[int]:
    values = [0, 0]
    if not isinstance(state, dict):
        return values
    ants = state.get("ants", [])
    if not isinstance(ants, list):
        return values
    for ant in ants:
        if not isinstance(ant, dict):
            continue
        try:
            player = int(ant.get("player", -1))
        except Exception:
            continue
        if player in (0, 1):
            values[player] += 1
    return values


def _state_summary(state: Any) -> Dict[str, Any]:
    return {
        "base_hp": _base_hp(state),
        "coins": _coins(state),
        "tower_counts": _tower_counts(state),
        "ant_counts": _ant_counts(state),
    }


def _frame_actions(frame: Dict[str, Any], key: str) -> List[str]:
    ops = frame.get(key, [])
    if not isinstance(ops, list):
        return []
    return [_label_action(op) for op in ops]


def main() -> int:
    args = build_parser().parse_args()
    replay_path = Path(args.replay).resolve()
    payload = _load_replay(replay_path)
    start = max(0, int(args.start))
    end = min(len(payload) - 1, int(args.end))
    rows: List[Dict[str, Any]] = []
    for round_index in range(start, end + 1):
        frame = payload[round_index]
        if not isinstance(frame, dict):
            continue
        pre_state = payload[round_index - 1].get("round_state", {}) if round_index > 0 and isinstance(payload[round_index - 1], dict) else {}
        post_state = frame.get("round_state", {})
        rows.append(
            {
                "round": round_index,
                "pre": _state_summary(pre_state),
                "actions": {
                    "0": _frame_actions(frame, "op0"),
                    "1": _frame_actions(frame, "op1"),
                },
                "post": _state_summary(post_state),
            }
        )

    result = {
        "replay_file": str(replay_path),
        "start_round": start,
        "end_round": end,
        "rows": rows,
    }
    if args.output:
        output_path = Path(args.output).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
