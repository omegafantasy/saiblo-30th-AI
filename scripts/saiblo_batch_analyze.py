#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from autolab.replay_analysis import analyze_single_replay


def normalize_code_id(value: str) -> str:
    return str(value or "").replace("-", "").lower().strip()


def mean_or_none(values: list[float]) -> float | None:
    if not values:
        return None
    return round(float(statistics.mean(values)), 3)


def find_replay_for_match(run_dir: Path, match_id: int) -> Path | None:
    for path in run_dir.glob(f"{match_id}.*"):
        if path.name.startswith("match_"):
            continue
        return path
    return None


def analyze_group(run_dir: Path, our_code_id: str) -> dict[str, Any]:
    our_code_id = normalize_code_id(our_code_id)
    result: dict[str, Any] = {
        "run_dir": str(run_dir),
        "total_matches": 0,
        "finished_matches": 0,
        "downloaded_replays": 0,
        "pending_match_ids": [],
        "wins": 0,
        "losses": 0,
        "draws": 0,
        "seat_stats": {
            "0": {"matches": 0, "wins": 0, "losses": 0, "draws": 0},
            "1": {"matches": 0, "wins": 0, "losses": 0, "draws": 0},
        },
        "avg_rounds": None,
        "avg_final_base_hp_ours": None,
        "avg_final_base_hp_theirs": None,
        "avg_final_coins_ours": None,
        "avg_final_coins_theirs": None,
        "avg_max_coin_gap": None,
        "avg_max_base_hp_gap": None,
        "our_action_counts": {},
        "opp_action_counts": {},
        "final_anthp_levels": {},
        "sample_losses": [],
    }
    rounds: list[float] = []
    base_hp_ours: list[float] = []
    base_hp_theirs: list[float] = []
    coins_ours: list[float] = []
    coins_theirs: list[float] = []
    max_coin_gaps: list[float] = []
    max_base_hp_gaps: list[float] = []
    our_actions: Counter[str] = Counter()
    opp_actions: Counter[str] = Counter()
    final_anthp: Counter[int] = Counter()

    for detail_path in sorted(run_dir.glob("match_*.json")):
        result["total_matches"] += 1
        detail = json.loads(detail_path.read_text(encoding="utf-8"))
        match_id = int(detail.get("id", 0) or 0)
        state = str(detail.get("state", "")).strip()
        info = detail.get("info", [])
        our_seat = None
        our_rank = None
        if isinstance(info, list):
            for idx, row in enumerate(info):
                if not isinstance(row, dict):
                    continue
                code = row.get("code", {})
                if not isinstance(code, dict):
                    continue
                if normalize_code_id(str(code.get("id", ""))) == our_code_id:
                    our_seat = idx
                    our_rank = row.get("rank")
                    break
        if our_seat is not None:
            result["seat_stats"][str(our_seat)]["matches"] += 1
        if state in ("准备中", "评测中", ""):
            result["pending_match_ids"].append(match_id)
            continue
        result["finished_matches"] += 1
        replay_path = find_replay_for_match(run_dir, match_id)
        if replay_path is None:
            result["pending_match_ids"].append(match_id)
            continue
        result["downloaded_replays"] += 1
        replay = analyze_single_replay(replay_path)
        winner = replay.get("winner")
        if our_seat is not None and isinstance(winner, int):
            if winner == our_seat:
                result["wins"] += 1
                result["seat_stats"][str(our_seat)]["wins"] += 1
            elif winner in (0, 1):
                result["losses"] += 1
                result["seat_stats"][str(our_seat)]["losses"] += 1
                if len(result["sample_losses"]) < 5:
                    result["sample_losses"].append({"match_id": match_id, "replay": str(replay_path)})
            else:
                result["draws"] += 1
                result["seat_stats"][str(our_seat)]["draws"] += 1
        rounds.append(float(replay.get("rounds", 0) or 0))
        final_state = replay.get("final_state", {}) if isinstance(replay, dict) else {}
        metrics = replay.get("metrics", {}) if isinstance(replay, dict) else {}
        if our_seat is not None and isinstance(final_state, dict):
            base_hp = final_state.get("base_hp", [0, 0])
            coins = final_state.get("coins", [0, 0])
            anthp_levels = final_state.get("anthp_levels", [0, 0])
            try:
                base_hp_ours.append(float(base_hp[our_seat]))
                base_hp_theirs.append(float(base_hp[1 - our_seat]))
                coins_ours.append(float(coins[our_seat]))
                coins_theirs.append(float(coins[1 - our_seat]))
                final_anthp[int(anthp_levels[our_seat])] += 1
            except Exception:
                pass
        try:
            max_coin_gaps.append(float(metrics.get("max_coin_gap", 0) or 0))
            max_base_hp_gaps.append(float(metrics.get("max_base_hp_gap", 0) or 0))
        except Exception:
            pass
        pac = replay.get("player_action_counts", {})
        if isinstance(pac, dict) and our_seat is not None:
            for key, counter in ((str(our_seat), our_actions), (str(1 - our_seat), opp_actions)):
                obj = pac.get(key, {})
                if isinstance(obj, dict):
                    for action, count in obj.items():
                        try:
                            counter[str(action)] += int(count)
                        except Exception:
                            pass

    result["avg_rounds"] = mean_or_none(rounds)
    result["avg_final_base_hp_ours"] = mean_or_none(base_hp_ours)
    result["avg_final_base_hp_theirs"] = mean_or_none(base_hp_theirs)
    result["avg_final_coins_ours"] = mean_or_none(coins_ours)
    result["avg_final_coins_theirs"] = mean_or_none(coins_theirs)
    result["avg_max_coin_gap"] = mean_or_none(max_coin_gaps)
    result["avg_max_base_hp_gap"] = mean_or_none(max_base_hp_gaps)
    result["our_action_counts"] = dict(sorted(our_actions.items()))
    result["opp_action_counts"] = dict(sorted(opp_actions.items()))
    result["final_anthp_levels"] = dict(sorted(final_anthp.items()))
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Aggregate downloaded Saiblo room-match batches")
    parser.add_argument("--save-root", required=True)
    parser.add_argument("--our-code-id", required=True)
    parser.add_argument("--output", default="")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    save_root = Path(args.save_root).resolve()
    groups: dict[str, Any] = {}
    for run_dir in sorted(p for p in save_root.iterdir() if p.is_dir()):
        groups[run_dir.name] = analyze_group(run_dir, args.our_code_id)
    out = {"save_root": str(save_root), "groups": groups}
    if args.output:
        output_path = Path(args.output).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
