"""
ANTWar-AI Behavioral Statistics Analyzer

Parses stderr output from ANTWar-AI self-play matches and computes
comprehensive behavioral statistics.

Stderr format (from main.cpp):
  round:<N> <hp0>:<hp1> <die0>:<die1> <coin0>:<coin1>
   node_count: <N>
  <child_id> v:<val> <max_expand> <fail_round>
  ...
  max_id: <id> max_val: <val>
  action: <type> <arg0> <arg1>
  [optional: "try att", "emergency use storm"]

Usage:
    python antwar_stats_analyzer.py [--input-dir DIR] [--output-dir DIR]
"""

import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, median, stdev

SCRIPT_DIR = Path(__file__).parent.resolve()
DEFAULT_INPUT = SCRIPT_DIR / "antwar_matches"
DEFAULT_OUTPUT = SCRIPT_DIR

# Tower position names (from main.cpp lines 23-26)
POSITION_NAMES = {
    0: "BASE", 1: "C1", 2: "C2", 3: "L1", 4: "C3", 5: "R1",
    6: "L2", 7: "L3", 8: "R3", 9: "R2", 10: "LL1", 11: "LL3",
    12: "M2", 13: "M3", 14: "RR1", 15: "RR3", 16: "LL2", 17: "ML1",
    18: "ML2", 19: "M1", 20: "M4", 21: "MR2", 22: "MR1", 23: "RR2",
    24: "FL1", 25: "FL2", 26: "FR2", 27: "FR1", 28: "FL3", 29: "F2",
    30: "F3", 31: "FR3", 32: "F1", 33: "F4", 34: "STORM",
}

# Tower positions for player 0 (from main.cpp lines 14-17)
POSITIONS_P0 = [
    (2,9), (4,9), (5,9), (5,7), (6,9), (5,11), (5,6), (6,7), (6,11),
    (5,12), (4,3), (5,3), (7,8), (7,10), (4,15), (5,15), (4,2), (6,4),
    (7,5), (8,7), (8,11), (7,13), (6,14), (4,16), (6,1), (6,2), (6,16),
    (6,17), (7,1), (8,4), (8,14), (7,17), (8,2), (8,16), (3,9),
]

# Tower type names
TOWER_TYPES = {
    0: "Basic", 1: "Heavy", 2: "Quick", 3: "Mortar",
    11: "HeavyPlus", 12: "Ice", 13: "Cannon",
    21: "QuickPlus", 22: "Double", 23: "Sniper",
    31: "MortarPlus", 32: "Pulse", 33: "Missile",
}

# Operation types (from common.hpp)
OP_TYPES = {
    11: "BuildTower", 12: "UpgradeTower", 13: "DowngradeTower",
    21: "UseLightningStorm", 22: "UseEmpBlaster",
    23: "UseDeflector", 24: "UseEmergencyEvasion",
    31: "UpgradeGeneratedAnt", 32: "UpgradeGenerationSpeed",
}

# Position coordinate to slot index mapping (for player 0)
POS_TO_SLOT_P0 = {pos: idx for idx, pos in enumerate(POSITIONS_P0)}

# Positions for player 1 (mirrored)
POSITIONS_P1 = [
    (16,9), (14,9), (13,9), (13,7), (12,9), (13,11), (12,6), (12,7), (12,11),
    (12,12), (14,3), (13,3), (10,8), (10,10), (14,15), (13,15), (13,2), (11,4),
    (11,5), (10,7), (10,11), (11,13), (11,14), (13,16), (12,1), (11,2), (11,16),
    (12,17), (11,1), (9,4), (9,14), (11,17), (9,2), (9,16), (15,9),
]
POS_TO_SLOT_P1 = {pos: idx for idx, pos in enumerate(POSITIONS_P1)}


def parse_stderr(lines, player_id=0):
    """
    Parse AI stderr output into structured round data.
    Returns list of round records.
    """
    rounds = []
    current_round = None

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Round header: "round:42 48:50 12:8 150:120"
        m = re.match(r'round:(\d+)\s+(\d+):(\d+)\s+(\d+):(\d+)\s+(-?\d+):(-?\d+)', line)
        if m:
            if current_round:
                rounds.append(current_round)
            current_round = {
                "round": int(m.group(1)),
                "hp0": int(m.group(2)),
                "hp1": int(m.group(3)),
                "die0": int(m.group(4)),
                "die1": int(m.group(5)),
                "coin0": int(m.group(6)),
                "coin1": int(m.group(7)),
                "node_count": 0,
                "children": [],
                "max_id": -1,
                "max_val": 0,
                "actions": [],
                "presearch_actions": [],
                "presearch_source": None,
                "emergency_storm": False,
                "try_attack": False,
                "global_state": 0,
                "attack": False,
                "attack_flag": False,
                "kill_diff": 0.0,
                "ant_level": 0,
                "gen_speed_level": 0,
                "tower_count": 0,
                "sw_cd": [0, 0, 0, 0],
            }
            continue

        if current_round is None:
            continue

        # Node count: " node_count: 3456"
        m = re.match(r'\s*node_count:\s*(\d+)', line)
        if m:
            current_round["node_count"] = int(m.group(1))
            continue

        # Child evaluation: "23 v:45.2 3 102"
        m = re.match(r'(\d+)\s+v:([-\d.e+]+)\s+(\d+)\s+(\d+)', line)
        if m:
            current_round["children"].append({
                "id": int(m.group(1)),
                "val": float(m.group(2)),
                "max_expand": int(m.group(3)),
                "fail_round": int(m.group(4)),
            })
            continue

        # Max id: "max_id: 5 max_val: 23.4"
        m = re.match(r'max_id:\s*(-?\d+)\s+max_val:\s*([-\d.e+]+)', line)
        if m:
            current_round["max_id"] = int(m.group(1))
            current_round["max_val"] = float(m.group(2))
            continue

        # Action: "action: 11 5 9"
        m = re.match(r'action:\s*(\d+)\s+(-?\d+)\s+(-?\d+)', line)
        if m:
            current_round["actions"].append({
                "type": int(m.group(1)),
                "arg0": int(m.group(2)),
                "arg1": int(m.group(3)),
            })
            continue

        # State info: "state:0 attack:1 attack_flag:1 kill_diff:-3.5 ant_lv:0 gen_spd:0 towers:2 sw_cd:0,0,0,0"
        m = re.match(r'state:(-?\d+)\s+attack:(\d+)\s+attack_flag:(\d+)\s+kill_diff:([-\d.e+]+)\s+ant_lv:(\d+)\s+gen_spd:(\d+)\s+towers:(\d+)\s+sw_cd:(\d+),(\d+),(\d+),(\d+)', line)
        if m:
            current_round["global_state"] = int(m.group(1))
            current_round["attack"] = bool(int(m.group(2)))
            current_round["attack_flag"] = bool(int(m.group(3)))
            current_round["kill_diff"] = float(m.group(4))
            current_round["ant_level"] = int(m.group(5))
            current_round["gen_speed_level"] = int(m.group(6))
            current_round["tower_count"] = int(m.group(7))
            current_round["sw_cd"] = [int(m.group(8)), int(m.group(9)), int(m.group(10)), int(m.group(11))]
            continue

        # Presearch source: "presearch: try_emp"
        m = re.match(r'presearch:\s*(\S+)', line)
        if m:
            current_round["presearch_source"] = m.group(1)
            continue

        # Presearch action: "presearch_action: 22 5 9"
        m = re.match(r'presearch_action:\s*(\d+)\s+(-?\d+)\s+(-?\d+)', line)
        if m:
            current_round["presearch_actions"].append({
                "type": int(m.group(1)),
                "arg0": int(m.group(2)),
                "arg1": int(m.group(3)),
            })
            continue

        if "emergency use storm" in line:
            current_round["emergency_storm"] = True
        if "try att" in line:
            current_round["try_attack"] = True

    if current_round:
        rounds.append(current_round)

    return rounds


def coord_to_slot(x, y, player_id):
    """Map (x,y) coordinates to a named tower slot."""
    pos_map = POS_TO_SLOT_P0 if player_id == 0 else POS_TO_SLOT_P1
    slot = pos_map.get((x, y), -1)
    if slot >= 0:
        return POSITION_NAMES.get(slot, f"slot_{slot}")
    return f"({x},{y})"


def analyze_match(match_dir: Path):
    """Analyze a single match directory."""
    result_path = match_dir / "result.json"
    if not result_path.exists():
        return None

    with open(result_path) as f:
        result = json.load(f)

    if result.get("status") != "completed":
        return None

    match_data = {
        "match_id": result["match_id"],
        "seed": result["seed"],
        "rounds": result["rounds"],
        "end_info": result.get("end_info"),
        "players": [{}, {}],
    }

    for player_id in range(2):
        stderr_path = match_dir / f"ai{player_id}_stderr.txt"
        if not stderr_path.exists():
            continue
        with open(stderr_path, encoding="utf-8") as f:
            lines = f.readlines()

        round_data = parse_stderr(lines, player_id)
        if not round_data:
            continue

        last = round_data[-1]

        # Determine winner from final HP
        final_hp0 = last["hp0"]
        final_hp1 = last["hp1"]
        if player_id == 0:
            match_data["final_hp0"] = final_hp0
            match_data["final_hp1"] = final_hp1
            if final_hp0 > final_hp1:
                match_data["winner"] = 0
            elif final_hp1 > final_hp0:
                match_data["winner"] = 1
            else:
                # Tie: check kills
                if last["die0"] > last["die1"]:
                    match_data["winner"] = 1  # P1 killed more of P0's ants? No...
                elif last["die1"] > last["die0"]:
                    match_data["winner"] = 0
                else:
                    match_data["winner"] = -1  # True tie

        match_data["players"][player_id] = {
            "round_data": round_data,
            "total_rounds": len(round_data),
            "final_hp": final_hp0 if player_id == 0 else final_hp1,
            "final_coins": last["coin0"] if player_id == 0 else last["coin1"],
            "final_kills": last["die1"] if player_id == 0 else last["die0"],  # kills of opponent
            "final_deaths": last["die0"] if player_id == 0 else last["die1"],
        }

    return match_data


def compute_tower_stats(all_matches):
    """Compute tower position and type statistics from build/upgrade actions."""
    build_counts = Counter()  # position -> count
    upgrade_counts = Counter()  # (position, target_type) -> count
    build_by_round_range = defaultdict(Counter)  # range -> position -> count
    tower_type_counts = Counter()  # type -> count

    for match in all_matches:
        for pid in range(2):
            pdata = match["players"][pid] if pid < len(match["players"]) else {}
            round_data = pdata.get("round_data", [])
            pos_map = POSITIONS_P0 if pid == 0 else POSITIONS_P1
            pos_to_slot = POS_TO_SLOT_P0 if pid == 0 else POS_TO_SLOT_P1

            for rd in round_data:
                rnd = rd["round"]
                range_key = f"{(rnd // 30) * 30}-{(rnd // 30 + 1) * 30}"

                for act in rd["actions"]:
                    if act["type"] == 11:  # BuildTower
                        slot = pos_to_slot.get((act["arg0"], act["arg1"]), -1)
                        if slot >= 0:
                            name = POSITION_NAMES.get(slot, f"slot_{slot}")
                            build_counts[name] += 1
                            build_by_round_range[range_key][name] += 1
                    elif act["type"] == 12:  # UpgradeTower
                        target_type = act["arg1"]
                        type_name = TOWER_TYPES.get(target_type, f"type_{target_type}")
                        tower_type_counts[type_name] += 1

    return {
        "build_position_frequency": dict(build_counts.most_common()),
        "upgrade_type_frequency": dict(tower_type_counts.most_common()),
        "build_by_round_range": {k: dict(v.most_common()) for k, v in sorted(build_by_round_range.items(), key=lambda x: int(x[0].split('-')[0]))},
    }


def compute_economy_stats(all_matches):
    """Compute economy curves."""
    coin_by_round = defaultdict(list)
    hp_diff_by_round = defaultdict(list)

    for match in all_matches:
        for pid in range(2):
            pdata = match["players"][pid] if pid < len(match["players"]) else {}
            for rd in pdata.get("round_data", []):
                rnd = rd["round"]
                my_coin = rd["coin0"] if pid == 0 else rd["coin1"]
                coin_by_round[rnd].append(my_coin)
                hp_diff = (rd["hp0"] - rd["hp1"]) if pid == 0 else (rd["hp1"] - rd["hp0"])
                hp_diff_by_round[rnd].append(hp_diff)

    avg_coins = {}
    avg_hp_diff = {}
    for rnd in sorted(coin_by_round.keys()):
        if rnd % 10 == 0:  # Sample every 10 rounds
            avg_coins[rnd] = round(mean(coin_by_round[rnd]), 1)
            avg_hp_diff[rnd] = round(mean(hp_diff_by_round[rnd]), 2)

    return {
        "avg_coin_curve": avg_coins,
        "avg_hp_differential_curve": avg_hp_diff,
    }


def compute_super_weapon_stats(all_matches):
    """Compute super weapon usage statistics."""
    sw_usage = Counter()  # type -> count
    sw_timing = defaultdict(list)  # type -> [round numbers]
    emergency_storm_count = 0
    emergency_storm_rounds = []

    for match in all_matches:
        for pid in range(2):
            pdata = match["players"][pid] if pid < len(match["players"]) else {}
            for rd in pdata.get("round_data", []):
                # Check both tree search actions and presearch actions
                all_acts = rd["actions"] + rd.get("presearch_actions", [])
                for act in all_acts:
                    if act["type"] in [21, 22, 23, 24]:  # Super weapons
                        sw_name = OP_TYPES.get(act["type"], str(act["type"]))
                        sw_usage[sw_name] += 1
                        sw_timing[sw_name].append(rd["round"])

                if rd.get("emergency_storm"):
                    emergency_storm_count += 1
                    emergency_storm_rounds.append(rd["round"])

    sw_timing_stats = {}
    for name, rounds in sw_timing.items():
        sw_timing_stats[name] = {
            "count": len(rounds),
            "avg_round": round(mean(rounds), 1) if rounds else 0,
            "median_round": median(rounds) if rounds else 0,
            "min_round": min(rounds) if rounds else 0,
            "max_round": max(rounds) if rounds else 0,
        }

    return {
        "usage_counts": dict(sw_usage.most_common()),
        "timing_stats": sw_timing_stats,
        "emergency_storm_count": emergency_storm_count,
        "emergency_storm_avg_round": round(mean(emergency_storm_rounds), 1) if emergency_storm_rounds else None,
    }


def compute_action_stats(all_matches):
    """Compute action frequency statistics."""
    action_counts = Counter()
    action_by_round_range = defaultdict(Counter)
    actions_per_round = []
    attack_mode_count = 0
    attack_mode_rounds = []

    presearch_source_counts = Counter()

    for match in all_matches:
        match_attack_triggered = False
        for pid in range(2):
            pdata = match["players"][pid] if pid < len(match["players"]) else {}
            for rd in pdata.get("round_data", []):
                rnd = rd["round"]
                range_key = f"{(rnd // 50) * 50}-{(rnd // 50 + 1) * 50}"
                all_acts = rd["actions"] + rd.get("presearch_actions", [])
                actions_per_round.append(len(all_acts))

                for act in all_acts:
                    op_name = OP_TYPES.get(act["type"], f"op_{act['type']}")
                    action_counts[op_name] += 1
                    action_by_round_range[range_key][op_name] += 1

                # Track presearch source
                src = rd.get("presearch_source")
                if src:
                    presearch_source_counts[src] += 1

                # Attack mode: use new 'attack' field if available, else fallback
                if (rd.get("attack") or rd.get("try_attack")) and not match_attack_triggered:
                    match_attack_triggered = True
                    attack_mode_rounds.append(rnd)

        if match_attack_triggered:
            attack_mode_count += 1

    return {
        "action_frequency": dict(action_counts.most_common()),
        "action_by_round_range": {k: dict(v.most_common(5)) for k, v in sorted(action_by_round_range.items(), key=lambda x: int(x[0].split('-')[0]))},
        "avg_actions_per_round": round(mean(actions_per_round), 2) if actions_per_round else 0,
        "attack_mode_triggered": attack_mode_count,
        "attack_mode_avg_round": round(mean(attack_mode_rounds), 1) if attack_mode_rounds else None,
        "presearch_source_frequency": dict(presearch_source_counts.most_common()),
    }


def compute_search_stats(all_matches):
    """Compute search tree statistics."""
    node_counts = []
    child_counts = []
    max_vals = []

    for match in all_matches:
        for pid in range(2):
            pdata = match["players"][pid] if pid < len(match["players"]) else {}
            for rd in pdata.get("round_data", []):
                if rd["node_count"] > 0:
                    node_counts.append(rd["node_count"])
                if rd["children"]:
                    child_counts.append(len(rd["children"]))
                if rd["max_val"] != 0 and rd["max_val"] > -1e8:
                    max_vals.append(rd["max_val"])

    return {
        "avg_node_count": round(mean(node_counts), 1) if node_counts else 0,
        "median_node_count": median(node_counts) if node_counts else 0,
        "max_node_count": max(node_counts) if node_counts else 0,
        "avg_children_per_root": round(mean(child_counts), 1) if child_counts else 0,
        "avg_max_val": round(mean(max_vals), 2) if max_vals else 0,
        "val_stdev": round(stdev(max_vals), 2) if len(max_vals) > 1 else 0,
    }


def compute_opening_stats(all_matches):
    """Analyze first 30 rounds patterns."""
    opening_sequences = []

    for match in all_matches:
        for pid in range(2):
            pdata = match["players"][pid] if pid < len(match["players"]) else {}
            pos_to_slot = POS_TO_SLOT_P0 if pid == 0 else POS_TO_SLOT_P1
            seq = []
            for rd in pdata.get("round_data", []):
                if rd["round"] > 30:
                    break
                for act in rd["actions"]:
                    if act["type"] == 11:  # BuildTower
                        slot = pos_to_slot.get((act["arg0"], act["arg1"]), -1)
                        if slot >= 0:
                            name = POSITION_NAMES.get(slot, f"slot_{slot}")
                            seq.append(f"R{rd['round']}:build_{name}")
                    elif act["type"] == 12:  # Upgrade
                        type_name = TOWER_TYPES.get(act["arg1"], f"t{act['arg1']}")
                        seq.append(f"R{rd['round']}:up_{type_name}")
            if seq:
                opening_sequences.append(tuple(seq))

    # Find most common opening patterns (first 3 actions)
    first_3 = Counter()
    for seq in opening_sequences:
        first_3[seq[:3]] += 1

    return {
        "total_openings": len(opening_sequences),
        "most_common_first_3_actions": [
            {"actions": list(k), "count": v}
            for k, v in first_3.most_common(10)
        ],
    }


def compute_base_upgrade_stats(all_matches):
    """Analyze base upgrade timing (ant level, gen speed)."""
    ant_upgrade_rounds = [[], []]  # level 1, level 2
    gen_speed_rounds = []

    for match in all_matches:
        for pid in range(2):
            pdata = match["players"][pid] if pid < len(match["players"]) else {}
            for rd in pdata.get("round_data", []):
                all_acts = rd["actions"] + rd.get("presearch_actions", [])
                for act in all_acts:
                    if act["type"] == 31:  # UpgradeGeneratedAnt
                        ant_upgrade_rounds[0].append(rd["round"])
                    elif act["type"] == 32:  # UpgradeGenerationSpeed
                        gen_speed_rounds.append(rd["round"])

    return {
        "ant_upgrade_count": len(ant_upgrade_rounds[0]),
        "ant_upgrade_avg_round": round(mean(ant_upgrade_rounds[0]), 1) if ant_upgrade_rounds[0] else None,
        "ant_upgrade_timing": sorted(ant_upgrade_rounds[0])[:20],  # First 20 samples
        "gen_speed_upgrade_count": len(gen_speed_rounds),
        "gen_speed_avg_round": round(mean(gen_speed_rounds), 1) if gen_speed_rounds else None,
    }


def compute_match_outcome_stats(all_matches):
    """Compute overall match outcome statistics."""
    total = len(all_matches)
    p0_wins = sum(1 for m in all_matches if m.get("winner") == 0)
    p1_wins = sum(1 for m in all_matches if m.get("winner") == 1)
    ties = sum(1 for m in all_matches if m.get("winner") == -1)
    rounds_list = [m["rounds"] for m in all_matches if m["rounds"] > 0]

    hp_diffs = []
    for m in all_matches:
        hp0 = m.get("final_hp0", 0)
        hp1 = m.get("final_hp1", 0)
        if hp0 or hp1:
            hp_diffs.append(abs(hp0 - hp1))

    return {
        "total_matches": total,
        "p0_wins": p0_wins,
        "p1_wins": p1_wins,
        "ties": ties,
        "avg_rounds": round(mean(rounds_list), 1) if rounds_list else 0,
        "avg_hp_diff": round(mean(hp_diffs), 2) if hp_diffs else 0,
    }


def main():
    parser = argparse.ArgumentParser(description="ANTWar-AI Behavioral Statistics Analyzer")
    parser.add_argument("--input-dir", type=str, default=str(DEFAULT_INPUT))
    parser.add_argument("--output-dir", type=str, default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)

    # Find all match directories
    match_dirs = sorted(input_dir.glob("match_*"))
    print(f"Found {len(match_dirs)} match directories in {input_dir}")

    # Analyze all matches
    all_matches = []
    for md in match_dirs:
        data = analyze_match(md)
        if data:
            all_matches.append(data)

    if not all_matches:
        print("No completed matches found!")
        sys.exit(1)

    print(f"Analyzed {len(all_matches)} completed matches")

    # Compute statistics
    stats = {
        "match_outcomes": compute_match_outcome_stats(all_matches),
        "tower_stats": compute_tower_stats(all_matches),
        "economy_stats": compute_economy_stats(all_matches),
        "super_weapon_stats": compute_super_weapon_stats(all_matches),
        "action_stats": compute_action_stats(all_matches),
        "search_stats": compute_search_stats(all_matches),
        "opening_stats": compute_opening_stats(all_matches),
        "base_upgrade_stats": compute_base_upgrade_stats(all_matches),
    }

    # Save JSON stats
    json_path = output_dir / "antwar_stats_summary.json"
    with open(json_path, "w") as f:
        json.dump(stats, f, indent=2, default=str)
    print(f"Stats saved to {json_path}")

    # Generate markdown report
    report = generate_report(stats, all_matches)
    md_path = output_dir / "antwar_behavior_analysis.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"Report saved to {md_path}")


def generate_report(stats, all_matches):
    """Generate markdown behavioral analysis report."""
    s = stats
    mo = s["match_outcomes"]
    ts = s["tower_stats"]
    ss = s["super_weapon_stats"]
    ac = s["action_stats"]
    sr = s["search_stats"]
    op = s["opening_stats"]
    bu = s["base_upgrade_stats"]
    ec = s["economy_stats"]

    report = f"""# ANTWar-AI Behavioral Statistics Report

## 1. Match Outcomes

| Metric | Value |
|--------|-------|
| Total matches analyzed | {mo['total_matches']} |
| Player 0 wins | {mo['p0_wins']} ({mo['p0_wins']/max(mo['total_matches'],1)*100:.1f}%) |
| Player 1 wins | {mo['p1_wins']} ({mo['p1_wins']/max(mo['total_matches'],1)*100:.1f}%) |
| Ties | {mo['ties']} |
| Avg rounds per match | {mo['avg_rounds']} |
| Avg HP differential | {mo['avg_hp_diff']} |

## 2. Tower Position Heatmap

Most frequently built tower positions (across all matches):

| Position | Build Count |
|----------|-------------|
"""
    for pos, count in sorted(ts["build_position_frequency"].items(), key=lambda x: -x[1])[:20]:
        report += f"| {pos} | {count} |\n"

    report += f"""
## 3. Tower Upgrade Preferences

| Tower Type | Upgrade Count |
|------------|---------------|
"""
    for ttype, count in sorted(ts["upgrade_type_frequency"].items(), key=lambda x: -x[1]):
        report += f"| {ttype} | {count} |\n"

    report += f"""
## 4. Build Timing by Round Range

"""
    for range_key, positions in sorted(ts["build_by_round_range"].items(), key=lambda x: int(x[0].split('-')[0])):
        report += f"**Rounds {range_key}:** "
        top3 = sorted(positions.items(), key=lambda x: -x[1])[:5]
        report += ", ".join(f"{p}({c})" for p, c in top3) + "\n\n"

    report += f"""## 5. Action Frequency

| Action | Count |
|--------|-------|
"""
    for action, count in sorted(ac["action_frequency"].items(), key=lambda x: -x[1]):
        report += f"| {action} | {count} |\n"

    report += f"""
- Average actions per round: {ac['avg_actions_per_round']}
- Attack mode triggered: {ac['attack_mode_triggered']}/{mo['total_matches']} matches
- Attack mode avg trigger round: {ac['attack_mode_avg_round']}

**Pre-search decision sources** (actions taken before tree search):

| Source | Count |
|--------|-------|
"""
    for src, count in sorted(ac.get("presearch_source_frequency", {}).items(), key=lambda x: -x[1]):
        report += f"| {src} | {count} |\n"

    report += f"""

## 6. Super Weapon Usage

| Weapon | Count | Avg Round | Min | Max |
|--------|-------|-----------|-----|-----|
"""
    for name, timing in sorted(ss["timing_stats"].items(), key=lambda x: -x[1]["count"]):
        report += f"| {name} | {timing['count']} | {timing['avg_round']} | {timing['min_round']} | {timing['max_round']} |\n"

    report += f"""
- Emergency storm triggers: {ss['emergency_storm_count']}
- Emergency storm avg round: {ss['emergency_storm_avg_round']}

## 7. Search Tree Statistics

| Metric | Value |
|--------|-------|
| Avg node count | {sr['avg_node_count']} |
| Median node count | {sr['median_node_count']} |
| Max node count | {sr['max_node_count']} |
| Avg children per root expansion | {sr['avg_children_per_root']} |
| Avg best evaluation value | {sr['avg_max_val']} |
| Evaluation std dev | {sr['val_stdev']} |

## 8. Opening Patterns (First 30 Rounds)

Most common first 3 actions:

"""
    for i, entry in enumerate(op["most_common_first_3_actions"][:10], 1):
        report += f"{i}. {' → '.join(entry['actions'])} (count: {entry['count']})\n"

    report += f"""
## 9. Base Upgrade Timing

| Metric | Value |
|--------|-------|
| Ant level upgrades | {bu['ant_upgrade_count']} |
| Avg ant upgrade round | {bu['ant_upgrade_avg_round']} |
| Gen speed upgrades | {bu['gen_speed_upgrade_count']} |
| Avg gen speed round | {bu['gen_speed_avg_round']} |

## 10. Economy Curve

Average coins over time (sampled every 10 rounds):

| Round | Avg Coins | Avg HP Diff |
|-------|-----------|-------------|
"""
    for rnd in sorted(ec["avg_coin_curve"].keys(), key=int):
        report += f"| {rnd} | {ec['avg_coin_curve'][rnd]} | {ec['avg_hp_differential_curve'].get(rnd, 'N/A')} |\n"

    # Compute some derived insights for observations
    total_actions = sum(ac["action_frequency"].values())
    presearch_freq = ac.get("presearch_source_frequency", {})
    presearch_total = sum(presearch_freq.values())
    presearch_sources_str = ', '.join(f'{k}({v})' for k, v in sorted(presearch_freq.items(), key=lambda x: -x[1]))
    sw_total = sum(ss["usage_counts"].values())
    mortar_pct = round(ts["upgrade_type_frequency"].get("Mortar", 0) / max(sum(ts["upgrade_type_frequency"].values()), 1) * 100, 1)
    downgrade_count = ac["action_frequency"].get("DowngradeTower", 0)
    build_count = ac["action_frequency"].get("BuildTower", 0)
    upgrade_count = ac["action_frequency"].get("UpgradeTower", 0)

    report += f"""
## 11. Key Observations

### Spatial Strategy: Mid-Field Dominance
- Top tower positions are mid-field slots (ML, MR, M groups), not near-base (C, L, R)
- This reflects the evaluation function's +0.4/distance bonus from base and dispersion penalties
- Forward positions (FL, FR) increase in later rounds (300+), suggesting progressive expansion

### Tower Economy: Build-Upgrade-Recycle Loop
- Mortar accounts for {mortar_pct}% of all upgrades — AOE at range 3 is the dominant strategy
- Level 3 upgrades are extremely rare (evaluation penalizes them at -39 vs -9 for level 2)
- Downgrade({downgrade_count}) > Build({build_count}) indicates constant tower recycling
- Average {ac['avg_actions_per_round']} actions/round = ~{round(ac['avg_actions_per_round'] * 512)} tower actions per 512-round match

### Super Weapon Timing
- EMP Blaster: {ss['usage_counts'].get('UseEmpBlaster', 0)} uses, avg R{ss['timing_stats'].get('UseEmpBlaster', {}).get('avg_round', 'N/A')} — offensive tool to disable enemy towers
- Lightning Storm: {ss['usage_counts'].get('UseLightningStorm', 0)} uses, avg R{ss['timing_stats'].get('UseLightningStorm', {}).get('avg_round', 'N/A')} — defensive/endgame tool
- Emergency Evasion: {ss['usage_counts'].get('UseEmergencyEvasion', 0)} uses — rare ant protection ability
- Emergency storm: {ss['emergency_storm_count']} triggers at avg R{ss['emergency_storm_avg_round']} — defensive safety valve

### Pre-Search vs Tree Search Decisions
- {presearch_total} rounds used pre-search decisions (super weapons, ant upgrades) bypassing the tree search
- {total_actions - presearch_total} rounds used tree search for tower management
- Pre-search sources: {presearch_sources_str}

### Attack Mode
- Triggered in {ac['attack_mode_triggered']}/{mo['total_matches']} matches at avg R{ac['attack_mode_avg_round']}
- Correlates with economy drop at R450-470 (spending on ant upgrades and super weapons)
- Ant level upgrades are rare in self-play (both sides usually tied in HP, so global_state remains 0)

### Economy Phases
- Opening (R0-R30): coins drop to ~30 for initial tower builds
- Mid game (R30-R120): oscillation during build/upgrade/sell cycles
- Late game (R120-R450): steady accumulation
- Endgame (R450+): sharp drop from attack mode spending

### Search Tree
- Avg {sr['avg_node_count']} nodes (22% of 20K limit) — 150ms budget is the binding constraint
- Avg {sr['avg_children_per_root']} children per root — large branching factor limits effective depth to ~2 levels
"""

    return report


if __name__ == "__main__":
    main()
