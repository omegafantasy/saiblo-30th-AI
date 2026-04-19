#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


K_BASE_HP = 50
K_MAP_SIZE = 19
K_EDGE = 10
K_TOWER_BUILD_BASE_COST = 15
K_LEVEL2_TOWER_UPGRADE_COST = 60
K_LEVEL3_TOWER_UPGRADE_COST = 200
K_TOWER_DOWNGRADE_REFUND_RATIO = 0.9
BASES = [(2, K_EDGE - 1), (K_MAP_SIZE - 3, K_EDGE - 1)]

TOWER_MAX_HP = {
    0: 10,
    1: 15,
    2: 15,
    3: 15,
    4: 15,
    11: 15,
    12: 15,
    13: 15,
    21: 15,
    22: 15,
    23: 15,
    31: 15,
    32: 15,
    33: 15,
    41: 15,
    42: 15,
    43: 15,
}

OP_NAMES = {
    11: "build",
    12: "upgrade",
    13: "downgrade",
    21: "lightning",
    22: "emp",
    23: "deflector",
    24: "evasion",
    31: "upgrade_generation",
    32: "upgrade_ant",
}


def percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    pos = q * (len(ordered) - 1)
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return float(ordered[lo])
    weight = pos - lo
    return float(ordered[lo]) * (1.0 - weight) + float(ordered[hi]) * weight


def stats(values: list[int | float]) -> dict[str, float]:
    xs = [float(v) for v in values]
    if not xs:
        return {"count": 0.0, "avg": 0.0, "p50": 0.0, "p95": 0.0, "max": 0.0}
    return {
        "count": float(len(xs)),
        "avg": sum(xs) / len(xs),
        "p50": percentile(xs, 0.5),
        "p95": percentile(xs, 0.95),
        "max": max(xs),
    }


def tower_build_cost_for_count(tower_count: int) -> int:
    tower_count = max(tower_count, 0)
    cost = K_TOWER_BUILD_BASE_COST
    for _ in range(tower_count // 2):
        cost *= 3
    if tower_count % 2 == 1:
        cost *= 2
    return cost


def upgrade_tower_cost(target_type: int) -> int:
    return K_LEVEL2_TOWER_UPGRADE_COST if target_type < 10 else K_LEVEL3_TOWER_UPGRADE_COST


def tower_max_hp(tower_type: int) -> int:
    return TOWER_MAX_HP.get(tower_type, 15)


def downgrade_target_type(tower_type: int) -> int:
    return 0 if tower_type == 0 else tower_type // 10


def basic_hp_after_full_downgrade(tower_type: int, hp: int) -> int:
    if tower_type == 0:
        return hp
    current_type = tower_type
    current_hp = hp
    while current_type != 0:
        previous_max_hp = tower_max_hp(current_type)
        current_type = downgrade_target_type(current_type)
        downgraded_max_hp = tower_max_hp(current_type)
        current_hp = max(1, (downgraded_max_hp * current_hp + previous_max_hp - 1) // previous_max_hp)
    return current_hp


def tower_full_salvage_value(towers: dict[int, dict[str, int]]) -> float:
    total = 0.0
    basic_ratios: list[float] = []
    for tower in towers.values():
        tower_type = int(tower["type"])
        hp = int(tower["hp"])
        current_type = tower_type
        current_hp = hp
        while current_type != 0:
            total += (
                upgrade_tower_cost(current_type)
                * K_TOWER_DOWNGRADE_REFUND_RATIO
                * max(current_hp, 0)
                / max(1, tower_max_hp(current_type))
            )
            previous_max_hp = tower_max_hp(current_type)
            current_type = downgrade_target_type(current_type)
            downgraded_max_hp = tower_max_hp(current_type)
            current_hp = max(1, (downgraded_max_hp * current_hp + previous_max_hp - 1) // previous_max_hp)
        basic_ratios.append(max(current_hp, 0) / max(1, tower_max_hp(0)))
    basic_ratios.sort(reverse=True)
    tower_count = len(basic_ratios)
    for ratio in basic_ratios:
        total += tower_build_cost_for_count(tower_count - 1) * K_TOWER_DOWNGRADE_REFUND_RATIO * ratio
        tower_count -= 1
    return total


def hex_distance(x0: int, y0: int, x1: int, y1: int) -> int:
    dy = abs(y0 - y1)
    if dy % 2:
        if x0 > x1:
            dx = max(0, abs(x0 - x1) - dy // 2 - (y0 % 2))
        else:
            dx = max(0, abs(x0 - x1) - dy // 2 - (1 - (y0 % 2)))
    else:
        dx = max(0, abs(x0 - x1) - dy // 2)
    return dx + dy


def half_plane_delta(player: int, x: int, y: int) -> int:
    own_x, own_y = BASES[player]
    enemy_x, enemy_y = BASES[1 - player]
    return hex_distance(x, y, own_x, own_y) - hex_distance(x, y, enemy_x, enemy_y)


def ant_in_own_half(player: int, ant: dict[str, Any]) -> bool:
    pos = ant["pos"]
    return half_plane_delta(player, int(pos["x"]), int(pos["y"])) <= 0


def op_category(op_list: list[dict[str, Any]]) -> str:
    if not op_list:
        return "hold"
    op_type = int(op_list[0]["type"])
    return OP_NAMES.get(op_type, str(op_type))


def load_json_lines(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line.startswith("{") or not line.endswith("}"):
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            out.append(value)
    return out


def estimate_round_cashflow(
    player: int,
    op_list: list[dict[str, Any]],
    towers: dict[int, dict[str, int]],
) -> tuple[float, float]:
    spend = 0.0
    refund = 0.0
    current_count = len(towers)
    for op in op_list:
        op_type = int(op["type"])
        if op_type == 11:
            spend += tower_build_cost_for_count(current_count)
        elif op_type == 12:
            spend += upgrade_tower_cost(int(op["args"]))
        elif op_type == 13:
            tower_id = int(op["id"])
            tower = towers.get(tower_id)
            if tower is None:
                continue
            tower_type = int(tower["type"])
            hp = int(tower["hp"])
            if tower_type == 0:
                refund += (
                    tower_build_cost_for_count(current_count - 1)
                    * K_TOWER_DOWNGRADE_REFUND_RATIO
                    * hp
                    / max(1, tower_max_hp(0))
                )
            else:
                refund += (
                    upgrade_tower_cost(tower_type)
                    * K_TOWER_DOWNGRADE_REFUND_RATIO
                    * hp
                    / max(1, tower_max_hp(tower_type))
                )
        elif op_type == 21:
            spend += 90.0
        elif op_type == 22:
            spend += 135.0
        elif op_type in (23, 24):
            spend += 60.0
    return spend, refund


def analyze_match(match_dir: Path) -> dict[str, Any]:
    replay = json.loads((match_dir / "replay.json").read_text(encoding="utf-8"))
    logs = [load_json_lines(match_dir / "ai0.stderr.log"), load_json_lines(match_dir / "ai1.stderr.log")]
    decisions_by_player = [
        {int(entry["round"]): entry for entry in logs[player] if entry.get("kind") == "decision"}
        for player in (0, 1)
    ]

    towers: list[dict[int, dict[str, int]]] = [dict(), dict()]
    prev_hp = [K_BASE_HP, K_BASE_HP]

    metrics: list[dict[str, Any]] = []
    for player in (0, 1):
        metrics.append(
            {
                "coins": [],
                "asset_value": [],
                "base_damage_events": 0,
                "base_damage_rounds": 0,
                "damage_with_combat_ring2": 0,
                "damage_with_combat_ring1": 0,
                "gross_spend": 0.0,
                "refund_income": 0.0,
                "ops": Counter(),
                "combat_action_ring2": Counter(),
                "combat_action_ring1": Counter(),
                "lookahead_hp_loss4_by_action": defaultdict(list),
                "lookahead_tower_destroy4_by_action": defaultdict(list),
                "tower_destroyed": 0,
                "tower_destroyed_with_combat_ring2": 0,
                "enemy_ids": set(),
                "enemy_worker_ids": set(),
                "enemy_combat_ids": set(),
                "enemy_combat_ring4_ids": set(),
                "enemy_combat_ring2_ids": set(),
                "enemy_combat_ring1_ids": set(),
                "enemy_combat_half_rounds": 0,
                "enemy_combat_ring4_rounds": 0,
                "enemy_combat_ring2_rounds": 0,
                "enemy_combat_ring1_rounds": 0,
                "decision_elapsed_us": [],
                "plans_unique": [],
                "best_name": Counter(),
            }
        )

    camps_by_round = [[int(rec["round_state"]["camps"][p]) for rec in replay] for p in (0, 1)]
    tower_destroy_events_by_round = [[0 for _ in replay] for _ in (0, 1)]

    for round_index, record in enumerate(replay):
        round_state = record["round_state"]
        ants = round_state.get("ants", [])
        coins = round_state.get("coins", [0, 0])
        camps = round_state.get("camps", [0, 0])

        for player in (0, 1):
            decision = decisions_by_player[player].get(round_index)
            if decision is not None:
                elapsed = decision.get("elapsed_us")
                if isinstance(elapsed, (int, float)):
                    metrics[player]["decision_elapsed_us"].append(int(elapsed))
                plans_unique = decision.get("plans_unique")
                if isinstance(plans_unique, (int, float)):
                    metrics[player]["plans_unique"].append(int(plans_unique))
                metrics[player]["best_name"][str(decision.get("best_name", ""))] += 1

            spend, refund = estimate_round_cashflow(player, record.get(f"op{player}", []), towers[player])
            metrics[player]["gross_spend"] += spend
            metrics[player]["refund_income"] += refund

            action = op_category(record.get(f"op{player}", []))
            metrics[player]["ops"][action] += 1

            own_base_x, own_base_y = BASES[player]
            enemy_ants = [ant for ant in ants if int(ant["player"]) == 1 - player]
            enemy_combat = [ant for ant in enemy_ants if int(ant.get("kind", 0)) == 1]
            metrics[player]["coins"].append(int(coins[player]))

            has_ring4 = False
            has_ring2 = False
            has_ring1 = False
            has_half = False
            for ant in enemy_ants:
                ant_id = int(ant["id"])
                metrics[player]["enemy_ids"].add(ant_id)
                if int(ant.get("kind", 0)) == 1:
                    metrics[player]["enemy_combat_ids"].add(ant_id)
                else:
                    metrics[player]["enemy_worker_ids"].add(ant_id)

            for ant in enemy_combat:
                ant_id = int(ant["id"])
                pos = ant["pos"]
                dist = hex_distance(int(pos["x"]), int(pos["y"]), own_base_x, own_base_y)
                if ant_in_own_half(player, ant):
                    has_half = True
                if dist <= 4:
                    has_ring4 = True
                    metrics[player]["enemy_combat_ring4_ids"].add(ant_id)
                if dist <= 2:
                    has_ring2 = True
                    metrics[player]["enemy_combat_ring2_ids"].add(ant_id)
                if dist <= 1:
                    has_ring1 = True
                    metrics[player]["enemy_combat_ring1_ids"].add(ant_id)

            if has_half:
                metrics[player]["enemy_combat_half_rounds"] += 1
            if has_ring4:
                metrics[player]["enemy_combat_ring4_rounds"] += 1
            if has_ring2:
                metrics[player]["enemy_combat_ring2_rounds"] += 1
                metrics[player]["combat_action_ring2"][action] += 1
            if has_ring1:
                metrics[player]["enemy_combat_ring1_rounds"] += 1
                metrics[player]["combat_action_ring1"][action] += 1

            current_hp = int(camps[player])
            damage = max(0, prev_hp[player] - current_hp)
            if damage > 0:
                metrics[player]["base_damage_events"] += damage
                metrics[player]["base_damage_rounds"] += 1
                if has_ring2:
                    metrics[player]["damage_with_combat_ring2"] += damage
                if has_ring1:
                    metrics[player]["damage_with_combat_ring1"] += damage
            prev_hp[player] = current_hp

        for tower_record in round_state.get("towers", []):
            player = int(tower_record["player"])
            tower_id = int(tower_record["id"])
            tower_type = int(tower_record["type"])
            if tower_type == -1:
                if tower_id in towers[player]:
                    del towers[player][tower_id]
                tower_destroy_events_by_round[player][round_index] += 1
                metrics[player]["tower_destroyed"] += 1
                enemy_player = 1 - player
                enemy_ants = [ant for ant in ants if int(ant["player"]) == enemy_player and int(ant.get("kind", 0)) == 1]
                base_x, base_y = BASES[player]
                if any(
                    hex_distance(int(ant["pos"]["x"]), int(ant["pos"]["y"]), base_x, base_y) <= 2
                    for ant in enemy_ants
                ):
                    metrics[player]["tower_destroyed_with_combat_ring2"] += 1
                continue
            towers[player][tower_id] = {
                "type": tower_type,
                "hp": int(tower_record.get("hp", tower_max_hp(tower_type))),
                "x": int(tower_record["pos"]["x"]),
                "y": int(tower_record["pos"]["y"]),
            }

        for player in (0, 1):
            metrics[player]["asset_value"].append(tower_full_salvage_value(towers[player]))

    for round_index, record in enumerate(replay):
        for player in (0, 1):
            action = op_category(record.get(f"op{player}", []))
            end_index = min(len(replay) - 1, round_index + 4)
            hp_loss4 = camps_by_round[player][round_index] - camps_by_round[player][end_index]
            tower_destroy4 = sum(tower_destroy_events_by_round[player][round_index + 1 : end_index + 1])
            metrics[player]["lookahead_hp_loss4_by_action"][action].append(hp_loss4)
            metrics[player]["lookahead_tower_destroy4_by_action"][action].append(tower_destroy4)

    out_players: list[dict[str, Any]] = []
    for player in (0, 1):
        data = metrics[player]
        rounds = len(replay)
        final_hp = camps_by_round[player][-1]
        hp_lost = K_BASE_HP - final_hp
        coins = data["coins"]
        asset_values = data["asset_value"]
        lookahead_hp = {
            key: stats(values)
            for key, values in data["lookahead_hp_loss4_by_action"].items()
        }
        lookahead_tower = {
            key: stats(values)
            for key, values in data["lookahead_tower_destroy4_by_action"].items()
        }
        out_players.append(
            {
                "final_hp": final_hp,
                "hp_lost": hp_lost,
                "base_damage_events": data["base_damage_events"],
                "base_damage_rounds": data["base_damage_rounds"],
                "damage_with_combat_ring2": data["damage_with_combat_ring2"],
                "damage_with_combat_ring1": data["damage_with_combat_ring1"],
                "coins": stats(coins),
                "coin_low_rounds_le_15": sum(1 for coin in coins if coin <= 15),
                "coin_high_rounds_ge_90": sum(1 for coin in coins if coin >= 90),
                "asset_value": stats(asset_values),
                "gross_spend": data["gross_spend"],
                "refund_income": data["refund_income"],
                "net_op_cashflow": data["refund_income"] - data["gross_spend"],
                "ops": dict(data["ops"]),
                "hold_rate": data["ops"].get("hold", 0) / rounds if rounds else 0.0,
                "enemy_ids_seen": len(data["enemy_ids"]),
                "enemy_worker_ids_seen": len(data["enemy_worker_ids"]),
                "enemy_combat_ids_seen": len(data["enemy_combat_ids"]),
                "enemy_combat_half_rounds": data["enemy_combat_half_rounds"],
                "enemy_combat_ring4_rounds": data["enemy_combat_ring4_rounds"],
                "enemy_combat_ring2_rounds": data["enemy_combat_ring2_rounds"],
                "enemy_combat_ring1_rounds": data["enemy_combat_ring1_rounds"],
                "enemy_combat_ring4_ids": len(data["enemy_combat_ring4_ids"]),
                "enemy_combat_ring2_ids": len(data["enemy_combat_ring2_ids"]),
                "enemy_combat_ring1_ids": len(data["enemy_combat_ring1_ids"]),
                "combat_blocked_before_ring1": (
                    len(data["enemy_combat_ids"]) - len(data["enemy_combat_ring1_ids"])
                ),
                "combat_action_ring2": dict(data["combat_action_ring2"]),
                "combat_action_ring1": dict(data["combat_action_ring1"]),
                "tower_destroyed": data["tower_destroyed"],
                "tower_destroyed_with_combat_ring2": data["tower_destroyed_with_combat_ring2"],
                "decision_elapsed_us": stats(data["decision_elapsed_us"]),
                "plans_unique": stats(data["plans_unique"]),
                "best_name_top": data["best_name"].most_common(8),
                "lookahead_hp_loss4_by_action": lookahead_hp,
                "lookahead_tower_destroy4_by_action": lookahead_tower,
            }
        )

    return {
        "seed": int(match_dir.name.split("_")[-1]),
        "rounds": len(replay),
        "winner": int(replay[-1]["round_state"]["winner"]),
        "players": out_players,
    }


def aggregate(matches: list[dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {"match_count": len(matches), "winner_counts": Counter(), "players": []}
    for match in matches:
        result["winner_counts"][str(match["winner"])] += 1

    for player in (0, 1):
        collect: dict[str, list[float]] = defaultdict(list)
        ops = Counter()
        combat_ring2_actions = Counter()
        best_names = Counter()
        lookahead_hp: dict[str, list[float]] = defaultdict(list)
        lookahead_tower: dict[str, list[float]] = defaultdict(list)

        for match in matches:
            data = match["players"][player]
            collect["final_hp"].append(data["final_hp"])
            collect["hp_lost"].append(data["hp_lost"])
            collect["base_damage_events"].append(data["base_damage_events"])
            collect["damage_with_combat_ring2"].append(data["damage_with_combat_ring2"])
            collect["gross_spend"].append(data["gross_spend"])
            collect["refund_income"].append(data["refund_income"])
            collect["net_op_cashflow"].append(data["net_op_cashflow"])
            collect["coin_low_rounds_le_15"].append(data["coin_low_rounds_le_15"])
            collect["coin_high_rounds_ge_90"].append(data["coin_high_rounds_ge_90"])
            collect["enemy_ids_seen"].append(data["enemy_ids_seen"])
            collect["enemy_combat_ids_seen"].append(data["enemy_combat_ids_seen"])
            collect["enemy_combat_ring2_rounds"].append(data["enemy_combat_ring2_rounds"])
            collect["enemy_combat_ring1_ids"].append(data["enemy_combat_ring1_ids"])
            collect["combat_blocked_before_ring1"].append(data["combat_blocked_before_ring1"])
            collect["tower_destroyed"].append(data["tower_destroyed"])
            collect["tower_destroyed_with_combat_ring2"].append(data["tower_destroyed_with_combat_ring2"])
            collect["hold_rate"].append(data["hold_rate"])
            collect["coin_avg"].append(data["coins"]["avg"])
            collect["coin_min"].append(data["coins"]["max"] if False else data["coins"]["avg"])
            collect["asset_avg"].append(data["asset_value"]["avg"])
            collect["decision_elapsed_avg_us"].append(data["decision_elapsed_us"]["avg"])
            collect["decision_elapsed_p95_us"].append(data["decision_elapsed_us"]["p95"])
            collect["plans_unique_avg"].append(data["plans_unique"]["avg"])
            collect["plans_unique_p95"].append(data["plans_unique"]["p95"])
            ops.update(data["ops"])
            combat_ring2_actions.update(data["combat_action_ring2"])
            best_names.update(dict(data["best_name_top"]))
            for key, bucket in data["lookahead_hp_loss4_by_action"].items():
                lookahead_hp[key].append(bucket["avg"])
            for key, bucket in data["lookahead_tower_destroy4_by_action"].items():
                lookahead_tower[key].append(bucket["avg"])

        result["players"].append(
            {
                "final_hp": stats(collect["final_hp"]),
                "hp_lost": stats(collect["hp_lost"]),
                "base_damage_events": stats(collect["base_damage_events"]),
                "damage_with_combat_ring2": stats(collect["damage_with_combat_ring2"]),
                "gross_spend": stats(collect["gross_spend"]),
                "refund_income": stats(collect["refund_income"]),
                "net_op_cashflow": stats(collect["net_op_cashflow"]),
                "coin_low_rounds_le_15": stats(collect["coin_low_rounds_le_15"]),
                "coin_high_rounds_ge_90": stats(collect["coin_high_rounds_ge_90"]),
                "enemy_ids_seen": stats(collect["enemy_ids_seen"]),
                "enemy_combat_ids_seen": stats(collect["enemy_combat_ids_seen"]),
                "enemy_combat_ring2_rounds": stats(collect["enemy_combat_ring2_rounds"]),
                "enemy_combat_ring1_ids": stats(collect["enemy_combat_ring1_ids"]),
                "combat_blocked_before_ring1": stats(collect["combat_blocked_before_ring1"]),
                "tower_destroyed": stats(collect["tower_destroyed"]),
                "tower_destroyed_with_combat_ring2": stats(collect["tower_destroyed_with_combat_ring2"]),
                "hold_rate": stats(collect["hold_rate"]),
                "coin_avg": stats(collect["coin_avg"]),
                "asset_avg": stats(collect["asset_avg"]),
                "decision_elapsed_avg_us": stats(collect["decision_elapsed_avg_us"]),
                "decision_elapsed_p95_us": stats(collect["decision_elapsed_p95_us"]),
                "plans_unique_avg": stats(collect["plans_unique_avg"]),
                "plans_unique_p95": stats(collect["plans_unique_p95"]),
                "ops_total": dict(ops),
                "combat_action_ring2_total": dict(combat_ring2_actions),
                "best_name_top": best_names.most_common(8),
                "lookahead_hp_loss4_by_action": {
                    key: stats(values) for key, values in lookahead_hp.items()
                },
                "lookahead_tower_destroy4_by_action": {
                    key: stats(values) for key, values in lookahead_tower.items()
                },
            }
        )

    result["winner_counts"] = dict(result["winner_counts"])
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze replay/debug output from cpp self-play batch runs.")
    parser.add_argument("batch_dir", type=Path)
    parser.add_argument("--output-json", type=Path, default=None)
    args = parser.parse_args()

    batch_dir = args.batch_dir.resolve()
    matches_dir = batch_dir / "matches"
    matches = [analyze_match(match_dir) for match_dir in sorted(matches_dir.glob("seed_*"))]
    report = {"aggregate": aggregate(matches), "matches": matches}

    if args.output_json is not None:
        args.output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(report["aggregate"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
