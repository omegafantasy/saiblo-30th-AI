#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
import shutil
from statistics import mean
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
ANT_GAME_IMPORT_ROOT = REPO_ROOT / "Game1" / "Ant-Game"
if str(ANT_GAME_IMPORT_ROOT) not in sys.path:
    sys.path.insert(0, str(ANT_GAME_IMPORT_ROOT))

from autolab.common import ANT_GAME_DIR, ROOT_DIR, RUNTIME_DIR, current_ruleset_id, now_ts, write_json
from autolab.game1_match_runner import ensure_game_bin, run_match_task, stage_version
from SDK.utils.constants import PLAYER_BASES
from SDK.utils.geometry import hex_distance


HEAVY_TYPES = {1, 11}
PRODUCER_TYPES = {4, 41, 42, 43}

VERSION_DEFS: dict[str, dict[str, Any]] = {
    "cpp_v3_unified_online": {
        "id": "cpp_v3_unified_online",
        "kind": "cpp_protocol_exe",
        "exe": str((ROOT_DIR / "Game1" / "antgame_ai_cpp" / "v3" / "ai_v3").resolve()),
    },
    "random": {"id": "random", "kind": "antgame_py", "name": "random"},
    "heavy_points": {"id": "heavy_points", "kind": "antgame_py", "name": "heavy_points"},
    "heavy_points_ant2": {"id": "heavy_points_ant2", "kind": "antgame_py", "name": "heavy_points_ant2"},
    "heavy_core_quick_ant2": {"id": "heavy_core_quick_ant2", "kind": "antgame_py", "name": "heavy_core_quick_ant2"},
    "heavy_core_hold_ant2": {"id": "heavy_core_hold_ant2", "kind": "antgame_py", "name": "heavy_core_hold_ant2"},
    "heavy_flex_quick_salvage": {"id": "heavy_flex_quick_salvage", "kind": "antgame_py", "name": "heavy_flex_quick_salvage"},
    "heavy_emergency4_ant2": {"id": "heavy_emergency4_ant2", "kind": "antgame_py", "name": "heavy_emergency4_ant2"},
    "heavy_sparse_emergency_ant2": {"id": "heavy_sparse_emergency_ant2", "kind": "antgame_py", "name": "heavy_sparse_emergency_ant2"},
    "heavy_frontline": {"id": "heavy_frontline", "kind": "antgame_py", "name": "heavy_frontline"},
    "heavy_tempo": {"id": "heavy_tempo", "kind": "antgame_py", "name": "heavy_tempo"},
    "heavy_siege_mix": {"id": "heavy_siege_mix", "kind": "antgame_py", "name": "heavy_siege_mix"},
    "baseline_anchor_ant2": {
        "id": "baseline_anchor_ant2",
        "kind": "cpp_protocol_exe",
        "exe": str((ROOT_DIR / "Game1" / "antgame_ai_cpp" / "baselines" / "ai_baseline_anchor_ant2").resolve()),
    },
    "baseline_side_hplus": {
        "id": "baseline_side_hplus",
        "kind": "cpp_protocol_exe",
        "exe": str((ROOT_DIR / "Game1" / "antgame_ai_cpp" / "baselines" / "ai_baseline_side_hplus").resolve()),
    },
    "baseline_quick_salvage": {
        "id": "baseline_quick_salvage",
        "kind": "cpp_protocol_exe",
        "exe": str((ROOT_DIR / "Game1" / "antgame_ai_cpp" / "baselines" / "ai_baseline_quick_salvage").resolve()),
    },
    "baseline_anchor_salvage": {
        "id": "baseline_anchor_salvage",
        "kind": "cpp_protocol_exe",
        "exe": str((ROOT_DIR / "Game1" / "antgame_ai_cpp" / "baselines" / "ai_baseline_anchor_salvage").resolve()),
    },
    "baseline_eco_hold": {
        "id": "baseline_eco_hold",
        "kind": "cpp_protocol_exe",
        "exe": str((ROOT_DIR / "Game1" / "antgame_ai_cpp" / "baselines" / "ai_baseline_eco_hold").resolve()),
    },
}

DEFAULT_CANDIDATES = (
    "heavy_core_hold_ant2",
    "heavy_points_ant2",
    "heavy_flex_quick_salvage",
    "heavy_emergency4_ant2",
)
DEFAULT_BASELINES = (
    "cpp_v3_unified_online",
    "baseline_anchor_ant2",
    "baseline_side_hplus",
    "baseline_quick_salvage",
    "baseline_eco_hold",
)


@dataclass(frozen=True)
class ProbeConfig:
    tag: str
    jobs: int
    seeds: tuple[int, ...]
    include_round_robin: bool
    seat_swaps: bool
    candidates: tuple[str, ...]
    baselines: tuple[str, ...]
    output_root: Path
    keep_artifacts: bool


def _version_def(version_id: str) -> dict[str, Any]:
    try:
        return VERSION_DEFS[version_id]
    except KeyError as exc:
        raise RuntimeError(f"unknown strategy probe version: {version_id}") from exc


def _count_ops(raw_ops: Any) -> dict[str, int]:
    counts = {"build": 0, "upgrade": 0, "downgrade": 0, "base": 0, "weapon": 0}
    if not isinstance(raw_ops, list):
        return counts
    for item in raw_ops:
        if not isinstance(item, dict):
            continue
        try:
            op_type = int(item.get("type", -1))
        except Exception:
            continue
        if op_type == 11:
            counts["build"] += 1
        elif op_type == 12:
            counts["upgrade"] += 1
        elif op_type == 13:
            counts["downgrade"] += 1
        elif op_type in (31, 32):
            counts["base"] += 1
        elif 21 <= op_type <= 24:
            counts["weapon"] += 1
    return counts

def analyze_probe_replay(replay_path: Path) -> dict[str, Any]:
    replay = json.loads(replay_path.read_text(encoding="utf-8"))
    out: dict[str, Any] = {
        "rounds": 0,
        "winner": -1,
        "base_hp_end": [0, 0],
        "tower_losses": [0, 0],
        "first_tower_loss_round": [None, None],
        "first_base_damage_round": [None, None],
        "avg_tower_count": [0.0, 0.0],
        "peak_tower_count": [0, 0],
        "avg_heavy_share": [0.0, 0.0],
        "avg_producer_share": [0.0, 0.0],
        "avg_combat_count": [0.0, 0.0],
        "peak_combat_count": [0, 0],
        "peak_enemy_combat_near_base": [0, 0],
        "combat_contact_rounds": [0, 0],
        "avg_coins": [0.0, 0.0],
        "peak_coins": [0, 0],
        "first_ant_upgrade_round": [None, None],
        "first_gen_upgrade_round": [None, None],
        "op_counts": [
            {"build": 0, "upgrade": 0, "downgrade": 0, "base": 0, "weapon": 0},
            {"build": 0, "upgrade": 0, "downgrade": 0, "base": 0, "weapon": 0},
        ],
    }
    if not isinstance(replay, list) or not replay:
        return out

    live_towers: list[dict[int, dict[str, Any]]] = [{}, {}]
    tower_count_series = [[], []]
    heavy_share_series = [[], []]
    producer_share_series = [[], []]
    combat_count_series = [[], []]
    coin_series = [[], []]

    base_pos = tuple(tuple(item) for item in PLAYER_BASES)

    for round_index, frame in enumerate(replay):
        if not isinstance(frame, dict):
            continue
        state = frame.get("round_state", {})
        if not isinstance(state, dict):
            continue
        towers = state.get("towers", [])
        ants = state.get("ants", [])
        camps = state.get("camps", [0, 0])
        coins = state.get("coins", [0, 0])

        tower_positions = [[], []]
        for tower in towers if isinstance(towers, list) else []:
            if not isinstance(tower, dict):
                continue
            try:
                player = int(tower.get("player", -1))
                tower_id = int(tower.get("id", -1))
                tower_type = int(tower.get("type", -1))
                x = int(tower.get("pos", {}).get("x", tower.get("x", -1)))
                y = int(tower.get("pos", {}).get("y", tower.get("y", -1)))
            except Exception:
                continue
            if player not in (0, 1):
                continue
            if tower_type < 0:
                if tower_id in live_towers[player]:
                    out["tower_losses"][player] += 1
                    if out["first_tower_loss_round"][player] is None:
                        out["first_tower_loss_round"][player] = round_index
                    del live_towers[player][tower_id]
                continue
            live_towers[player][tower_id] = {"type": tower_type, "pos": (x, y)}

        for player in (0, 1):
            try:
                coin = int(coins[player])
            except Exception:
                coin = 0
            coin_series[player].append(coin)
            out["peak_coins"][player] = max(out["peak_coins"][player], coin)
            tower_count = len(live_towers[player])
            heavy_counts = sum(1 for tower in live_towers[player].values() if int(tower["type"]) in HEAVY_TYPES)
            producer_counts = sum(1 for tower in live_towers[player].values() if int(tower["type"]) in PRODUCER_TYPES)
            tower_positions[player] = [tuple(tower["pos"]) for tower in live_towers[player].values()]
            tower_count_series[player].append(tower_count)
            heavy_share_series[player].append(heavy_counts / tower_count if tower_count else 0.0)
            producer_share_series[player].append(producer_counts / tower_count if tower_count else 0.0)

        combat_counts = [0, 0]
        enemy_combat_near_base = [0, 0]
        combat_contact = [False, False]
        for ant in ants if isinstance(ants, list) else []:
            if not isinstance(ant, dict):
                continue
            try:
                player = int(ant.get("player", -1))
                kind = int(ant.get("kind", 0))
                x = int(ant.get("pos", {}).get("x", ant.get("x", -1)))
                y = int(ant.get("pos", {}).get("y", ant.get("y", -1)))
            except Exception:
                continue
            if player not in (0, 1) or kind != 1:
                continue
            combat_counts[player] += 1
            enemy = 1 - player
            if hex_distance(x, y, base_pos[enemy][0], base_pos[enemy][1]) <= 8:
                enemy_combat_near_base[enemy] += 1
            for tower_pos in tower_positions[enemy]:
                if hex_distance(x, y, tower_pos[0], tower_pos[1]) <= 1:
                    combat_contact[enemy] = True
                    break

        for player in (0, 1):
            combat_count_series[player].append(combat_counts[player])
            out["peak_combat_count"][player] = max(out["peak_combat_count"][player], combat_counts[player])
            out["peak_enemy_combat_near_base"][player] = max(out["peak_enemy_combat_near_base"][player], enemy_combat_near_base[player])
            if combat_contact[player]:
                out["combat_contact_rounds"][player] += 1

        for player in (0, 1):
            try:
                camp_hp = int(camps[player])
            except Exception:
                camp_hp = 0
            if camp_hp < 50 and out["first_base_damage_round"][player] is None:
                out["first_base_damage_round"][player] = round_index
            out["base_hp_end"][player] = camp_hp

        for player in (0, 1):
            frame_ops = _count_ops(frame.get(f"op{player}"))
            if frame_ops["base"] and out["first_ant_upgrade_round"][player] is None:
                for item in frame.get(f"op{player}") or []:
                    if isinstance(item, dict) and int(item.get("type", -1)) == 32:
                        out["first_ant_upgrade_round"][player] = round_index
                        break
            if out["first_gen_upgrade_round"][player] is None:
                for item in frame.get(f"op{player}") or []:
                    if isinstance(item, dict) and int(item.get("type", -1)) == 31:
                        out["first_gen_upgrade_round"][player] = round_index
                        break
            for key, value in frame_ops.items():
                out["op_counts"][player][key] += value

    out["rounds"] = len(replay)
    last_state = replay[-1].get("round_state", {}) if isinstance(replay[-1], dict) else {}
    if isinstance(last_state, dict):
        try:
            out["winner"] = int(last_state.get("winner", -1))
        except Exception:
            out["winner"] = -1

    for player in (0, 1):
        out["avg_tower_count"][player] = round(mean(tower_count_series[player]), 3) if tower_count_series[player] else 0.0
        out["peak_tower_count"][player] = max(tower_count_series[player], default=0)
        out["avg_heavy_share"][player] = round(mean(heavy_share_series[player]), 3) if heavy_share_series[player] else 0.0
        out["avg_producer_share"][player] = round(mean(producer_share_series[player]), 3) if producer_share_series[player] else 0.0
        out["avg_combat_count"][player] = round(mean(combat_count_series[player]), 3) if combat_count_series[player] else 0.0
        out["avg_coins"][player] = round(mean(coin_series[player]), 3) if coin_series[player] else 0.0

    return out


def _perspective(match: dict[str, Any], version_id: str) -> tuple[int, dict[str, Any]] | None:
    if version_id == match.get("a"):
        seat = int(match.get("a_seat", 0))
    elif version_id == match.get("b"):
        seat = 1 - int(match.get("a_seat", 0))
    else:
        return None
    probe = match.get("probe", {})
    if not isinstance(probe, dict):
        return None
    return seat, probe


def aggregate_results(matches: list[dict[str, Any]], version_ids: list[str]) -> dict[str, Any]:
    per_version: dict[str, dict[str, Any]] = {
        version_id: {
            "games": 0,
            "wins": 0,
            "losses": 0,
            "draws": 0,
            "avg_rounds": [],
            "base_hp_end": [],
            "tower_losses": [],
            "avg_tower_count": [],
            "avg_heavy_share": [],
            "avg_producer_share": [],
            "avg_combat_count": [],
            "peak_enemy_combat_near_base": [],
            "combat_contact_rounds": [],
            "first_base_damage_round": [],
            "op_build": [],
            "op_upgrade": [],
            "op_downgrade": [],
            "op_base": [],
            "op_weapon": [],
            "avg_coins": [],
            "peak_coins": [],
            "first_ant_upgrade_round": [],
            "first_gen_upgrade_round": [],
        }
        for version_id in version_ids
    }
    pair_scores: dict[str, dict[str, float]] = defaultdict(lambda: {"games": 0.0, "score_left": 0.0})

    for match in matches:
        a = str(match.get("a", ""))
        b = str(match.get("b", ""))
        winner = int(match.get("winner_seat", -1))
        key = f"{a} vs {b}"
        pair_scores[key]["games"] += 1.0
        if winner == int(match.get("a_seat", 0)):
            pair_scores[key]["score_left"] += 1.0
        elif winner not in (0, 1):
            pair_scores[key]["score_left"] += 0.5

        for version_id in version_ids:
            seat_probe = _perspective(match, version_id)
            if seat_probe is None:
                continue
            seat, probe = seat_probe
            stats = per_version[version_id]
            stats["games"] += 1
            if winner == seat:
                stats["wins"] += 1
            elif winner in (0, 1):
                stats["losses"] += 1
            else:
                stats["draws"] += 1
            stats["avg_rounds"].append(float(match.get("rounds_played", probe.get("rounds", 0)) or 0))
            stats["base_hp_end"].append(float(probe["base_hp_end"][seat]))
            stats["tower_losses"].append(float(probe["tower_losses"][seat]))
            stats["avg_tower_count"].append(float(probe["avg_tower_count"][seat]))
            stats["avg_heavy_share"].append(float(probe["avg_heavy_share"][seat]))
            stats["avg_producer_share"].append(float(probe["avg_producer_share"][seat]))
            stats["avg_combat_count"].append(float(probe["avg_combat_count"][seat]))
            stats["peak_enemy_combat_near_base"].append(float(probe["peak_enemy_combat_near_base"][seat]))
            stats["combat_contact_rounds"].append(float(probe["combat_contact_rounds"][seat]))
            stats["avg_coins"].append(float(probe["avg_coins"][seat]))
            stats["peak_coins"].append(float(probe["peak_coins"][seat]))
            if probe["first_base_damage_round"][seat] is not None:
                stats["first_base_damage_round"].append(float(probe["first_base_damage_round"][seat]))
            if probe["first_ant_upgrade_round"][seat] is not None:
                stats["first_ant_upgrade_round"].append(float(probe["first_ant_upgrade_round"][seat]))
            if probe["first_gen_upgrade_round"][seat] is not None:
                stats["first_gen_upgrade_round"].append(float(probe["first_gen_upgrade_round"][seat]))
            op_counts = probe["op_counts"][seat]
            stats["op_build"].append(float(op_counts["build"]))
            stats["op_upgrade"].append(float(op_counts["upgrade"]))
            stats["op_downgrade"].append(float(op_counts["downgrade"]))
            stats["op_base"].append(float(op_counts["base"]))
            stats["op_weapon"].append(float(op_counts["weapon"]))

    def _avg(values: list[float]) -> float:
        return round(mean(values), 3) if values else 0.0

    return {
        "per_version": {
            version_id: {
                "games": stats["games"],
                "wins": stats["wins"],
                "losses": stats["losses"],
                "draws": stats["draws"],
                "win_rate": round(stats["wins"] / stats["games"], 3) if stats["games"] else 0.0,
                "avg_rounds": _avg(stats["avg_rounds"]),
                "avg_base_hp_end": _avg(stats["base_hp_end"]),
                "avg_tower_losses": _avg(stats["tower_losses"]),
                "avg_tower_count": _avg(stats["avg_tower_count"]),
                "avg_heavy_share": _avg(stats["avg_heavy_share"]),
                "avg_producer_share": _avg(stats["avg_producer_share"]),
                "avg_combat_count": _avg(stats["avg_combat_count"]),
                "avg_peak_enemy_combat_near_base": _avg(stats["peak_enemy_combat_near_base"]),
                "avg_combat_contact_rounds": _avg(stats["combat_contact_rounds"]),
                "avg_coins": _avg(stats["avg_coins"]),
                "avg_peak_coins": _avg(stats["peak_coins"]),
                "avg_first_base_damage_round": _avg(stats["first_base_damage_round"]),
                "avg_first_ant_upgrade_round": _avg(stats["first_ant_upgrade_round"]),
                "avg_first_gen_upgrade_round": _avg(stats["first_gen_upgrade_round"]),
                "avg_build_ops": _avg(stats["op_build"]),
                "avg_upgrade_ops": _avg(stats["op_upgrade"]),
                "avg_downgrade_ops": _avg(stats["op_downgrade"]),
                "avg_base_ops": _avg(stats["op_base"]),
                "avg_weapon_ops": _avg(stats["op_weapon"]),
            }
            for version_id, stats in per_version.items()
        },
        "pair_scores": {
            key: {
                "games": int(value["games"]),
                "score_left": round(value["score_left"], 3),
                "win_rate_left": round(value["score_left"] / value["games"], 3) if value["games"] else 0.0,
            }
            for key, value in sorted(pair_scores.items())
        },
    }


def render_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# Game1 Strategy Probe",
        "",
        f"- tag: `{summary['tag']}`",
        f"- ruleset_id: `{summary['ruleset_id']}`",
        f"- matches: `{summary['match_count']}`",
        "",
        "## Versions",
        "",
        "| version | W-L-D | win_rate | avg_base_hp | avg_tower_losses | avg_heavy_share | avg_coins | first_ant2 | avg_downgrade_ops | avg_enemy_combat_near_base |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for version_id, stats in summary["aggregate"]["per_version"].items():
        lines.append(
            f"| {version_id} | {stats['wins']}-{stats['losses']}-{stats['draws']} | "
            f"{stats['win_rate']:.3f} | {stats['avg_base_hp_end']:.2f} | {stats['avg_tower_losses']:.2f} | "
            f"{stats['avg_heavy_share']:.2f} | {stats['avg_coins']:.2f} | {stats['avg_first_ant_upgrade_round']:.2f} | "
            f"{stats['avg_downgrade_ops']:.2f} | {stats['avg_peak_enemy_combat_near_base']:.2f} |"
        )
    lines.extend(
        [
            "",
            "## Pair Scores",
            "",
            "| pairing | games | left_score | left_win_rate |",
            "|---|---:|---:|---:|",
        ]
    )
    for key, value in summary["aggregate"]["pair_scores"].items():
        lines.append(f"| {key} | {value['games']} | {value['score_left']:.2f} | {value['win_rate_left']:.3f} |")
    return "\n".join(lines) + "\n"


def build_tasks(cfg: ProbeConfig, staged: dict[str, Path], game_bin: Path, run_dir: Path) -> list[dict[str, Any]]:
    pairings: list[tuple[str, str]] = []
    for candidate in cfg.candidates:
        for baseline in cfg.baselines:
            pairings.append((candidate, baseline))
    if cfg.include_round_robin:
        candidates = list(cfg.candidates)
        for index, left in enumerate(candidates[:-1]):
            for right in candidates[index + 1 :]:
                pairings.append((left, right))

    tasks: list[dict[str, Any]] = []
    replay_dir = run_dir / "replays"
    match_dir = run_dir / "match_work"
    for left, right in pairings:
        for seed in cfg.seeds:
            seats = ((False, seed), (True, seed + 911)) if cfg.seat_swaps else ((False, seed),)
            for flip, actual_seed in seats:
                a_on_seat0 = not flip
                p0 = left if a_on_seat0 else right
                p1 = right if a_on_seat0 else left
                label = f"p0-{p0}_p1-{p1}_seed-{actual_seed}"
                tasks.append(
                    {
                        "a": left,
                        "b": right,
                        "seed": actual_seed,
                        "a_on_seat0": a_on_seat0,
                        "ai0_dir": str(staged[p0]),
                        "ai1_dir": str(staged[p1]),
                        "game_bin": str(game_bin),
                        "work_dir": str(match_dir / label),
                        "replay_file": str(replay_dir / f"{label}.json"),
                        "max_rounds": 160,
                    }
                )
    return tasks


def run_probe(cfg: ProbeConfig) -> dict[str, Any]:
    run_dir = cfg.output_root / cfg.tag
    run_dir.mkdir(parents=True, exist_ok=True)
    packages_dir = run_dir / "packages"
    packages_dir.mkdir(parents=True, exist_ok=True)

    game_bin = ensure_game_bin(ANT_GAME_DIR)
    staged: dict[str, Path] = {}
    version_ids = list(dict.fromkeys([*cfg.candidates, *cfg.baselines]))
    for version_id in version_ids:
        staged[version_id] = stage_version(ANT_GAME_DIR, _version_def(version_id), packages_dir / version_id)

    tasks = build_tasks(cfg, staged, game_bin, run_dir)
    matches: list[dict[str, Any]] = []

    if cfg.jobs <= 1:
        for task in tasks:
            match = run_match_task(task)
            match["probe"] = analyze_probe_replay(Path(match["replay_file"]))
            if not cfg.keep_artifacts:
                match["replay_file"] = ""
            matches.append(match)
    else:
        with ProcessPoolExecutor(max_workers=cfg.jobs) as pool:
            future_to_task = {pool.submit(run_match_task, task): task for task in tasks}
            for future in as_completed(future_to_task):
                match = future.result()
                match["probe"] = analyze_probe_replay(Path(match["replay_file"]))
                if not cfg.keep_artifacts:
                    match["replay_file"] = ""
                matches.append(match)

    matches.sort(key=lambda item: (str(item.get("a", "")), str(item.get("b", "")), int(item.get("seed", 0))))
    matches_path = run_dir / "matches.jsonl"
    with matches_path.open("w", encoding="utf-8") as handle:
        for match in matches:
            handle.write(json.dumps(match, ensure_ascii=False) + "\n")

    summary = {
        "tag": cfg.tag,
        "ruleset_id": current_ruleset_id(),
        "match_count": len(matches),
        "candidates": list(cfg.candidates),
        "baselines": list(cfg.baselines),
        "jobs": cfg.jobs,
        "seeds": list(cfg.seeds),
        "aggregate": aggregate_results(matches, version_ids),
        "paths": {
            "run_dir": str(run_dir),
            "matches": str(matches_path),
        },
    }
    summary_path = run_dir / "summary.json"
    write_json(summary_path, summary)
    md_path = run_dir / "summary.md"
    md_path.write_text(render_markdown(summary), encoding="utf-8")

    latest = dict(summary)
    latest["paths"] = dict(summary["paths"])
    latest["paths"]["summary"] = str(summary_path)
    latest["paths"]["markdown"] = str(md_path)
    write_json(cfg.output_root / "latest.json", latest)
    (cfg.output_root / "latest.md").write_text(render_markdown(summary), encoding="utf-8")
    generated_md = ROOT_DIR / "docs" / "generated" / "game1_strategy_probe_latest.md"
    generated_md.parent.mkdir(parents=True, exist_ok=True)
    generated_md.write_text(render_markdown(summary), encoding="utf-8")
    if not cfg.keep_artifacts:
        shutil.rmtree(run_dir / "replays", ignore_errors=True)
        shutil.rmtree(run_dir / "match_work", ignore_errors=True)
        shutil.rmtree(run_dir / "packages", ignore_errors=True)
    return latest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Probe simple Game1 strategies under the current ruleset")
    parser.add_argument("--tag", default="", help="explicit run tag")
    parser.add_argument("--jobs", type=int, default=4, help="parallel match workers")
    parser.add_argument("--seeds", default="0", help="comma-separated base seeds; seat-swapped games add +911")
    parser.add_argument("--include-round-robin", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--seat-swaps", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--candidates", default=",".join(DEFAULT_CANDIDATES))
    parser.add_argument("--baselines", default=",".join(DEFAULT_BASELINES))
    parser.add_argument("--keep-artifacts", action=argparse.BooleanOptionalAction, default=True)
    return parser


def _split_csv(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())


def _parse_seeds(value: str) -> tuple[int, ...]:
    out: list[int] = []
    for item in _split_csv(value):
        out.append(int(item))
    return tuple(out or [0])


def main() -> int:
    args = build_parser().parse_args()
    cfg = ProbeConfig(
        tag=args.tag or f"strategy_probe_{now_ts()}",
        jobs=max(1, args.jobs),
        seeds=_parse_seeds(args.seeds),
        include_round_robin=bool(args.include_round_robin),
        seat_swaps=bool(args.seat_swaps),
        candidates=_split_csv(args.candidates),
        baselines=_split_csv(args.baselines),
        output_root=RUNTIME_DIR / "strategy_probe",
        keep_artifacts=bool(args.keep_artifacts),
    )
    result = run_probe(cfg)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
