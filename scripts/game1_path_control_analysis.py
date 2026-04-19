#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter, deque
from functools import lru_cache
from pathlib import Path
import sys
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]
ANT_GAME_ROOT = REPO_ROOT / "Game1" / "Ant-Game"
if str(ANT_GAME_ROOT) not in sys.path:
    sys.path.insert(0, str(ANT_GAME_ROOT))

from SDK.utils.constants import HIGHLAND_CELLS, MAP_SIZE, PATH_CELLS, PLAYER_BASES
from SDK.utils.geometry import hex_distance, neighbors


WALKABLE_CELLS = tuple(sorted(set(PATH_CELLS + PLAYER_BASES)))
WALKABLE_SET = set(WALKABLE_CELLS)
DEFAULT_REPLAY_ROOTS = (
    REPO_ROOT / "autolab" / "runtime" / "strategy_probe" / "strategy_probe_macro_v1" / "replays",
    REPO_ROOT / "autolab" / "runtime" / "strategy_probe" / "strategy_probe_sparse_focus" / "replays",
)


def own_half_path_cells(player: int) -> tuple[tuple[int, int], ...]:
    own_base = PLAYER_BASES[player]
    enemy_base = PLAYER_BASES[1 - player]
    return tuple(
        (x, y)
        for x, y in PATH_CELLS
        if hex_distance(x, y, *own_base) <= hex_distance(x, y, *enemy_base)
    )


def shortest_distances_to_base(player: int) -> dict[tuple[int, int], int]:
    base = PLAYER_BASES[player]
    dist = {base: 0}
    queue: deque[tuple[int, int]] = deque([base])
    while queue:
        x, y = queue.popleft()
        for _, nx, ny in neighbors(x, y):
            if (nx, ny) not in WALKABLE_SET or (nx, ny) in dist:
                continue
            dist[nx, ny] = dist[x, y] + 1
            queue.append((nx, ny))
    return dist


def boundary_entries(player: int, dist: dict[tuple[int, int], int]) -> list[tuple[int, int]]:
    own_half = set(own_half_path_cells(player))
    entries: list[tuple[int, int]] = []
    for x, y in own_half:
        if (x, y) not in dist:
            continue
        for _, nx, ny in neighbors(x, y):
            if (nx, ny) in WALKABLE_SET and (nx, ny) not in own_half:
                entries.append((x, y))
                break
    entries.sort(key=lambda cell: (dist[cell], cell[0], cell[1]))
    return entries


def cells_in_tower_range(slot: tuple[int, int], attack_range: int) -> set[tuple[int, int]]:
    sx, sy = slot
    return {(x, y) for x, y in WALKABLE_CELLS if hex_distance(x, y, sx, sy) <= attack_range}


def shortest_path_successors(
    cell: tuple[int, int],
    dist: dict[tuple[int, int], int],
) -> list[tuple[int, int]]:
    x, y = cell
    current = dist[cell]
    out: list[tuple[int, int]] = []
    for _, nx, ny in neighbors(x, y):
        if (nx, ny) not in dist:
            continue
        if dist[nx, ny] == current - 1:
            out.append((nx, ny))
    out.sort()
    return out


def count_shortest_paths(
    start: tuple[int, int],
    base: tuple[int, int],
    dist: dict[tuple[int, int], int],
    blocked: set[tuple[int, int]] | None = None,
) -> int:
    blocked = blocked or set()

    @lru_cache(maxsize=None)
    def dfs(cell: tuple[int, int]) -> int:
        if cell in blocked:
            return 0
        if cell == base:
            return 1
        return sum(dfs(next_cell) for next_cell in shortest_path_successors(cell, dist))

    return dfs(start)


def observed_danger_teleports(
    player: int,
    replay_roots: Iterable[Path],
    max_base_distance: int = 3,
) -> Counter[tuple[int, int]]:
    base = PLAYER_BASES[player]
    enemy_player = 1 - player
    counts: Counter[tuple[int, int]] = Counter()
    for root in replay_roots:
        if not root.exists():
            continue
        for path in sorted(root.glob("*.json")):
            replay = json.loads(path.read_text())
            prev_by_id: dict[int, dict] = {}
            for frame in replay:
                ants = frame.get("round_state", {}).get("ants", [])
                cur_by_id = {int(ant["id"]): ant for ant in ants if isinstance(ant, dict)}
                for ant_id, ant in cur_by_id.items():
                    prev = prev_by_id.get(ant_id)
                    if prev is None:
                        continue
                    if int(ant.get("player", -1)) != enemy_player:
                        continue
                    if int(prev.get("status", -1)) not in (0, 1) or int(ant.get("status", -1)) not in (0, 1):
                        continue
                    px, py = int(prev["pos"]["x"]), int(prev["pos"]["y"])
                    x, y = int(ant["pos"]["x"]), int(ant["pos"]["y"])
                    if hex_distance(px, py, x, y) <= 1:
                        continue
                    if hex_distance(x, y, *base) <= max_base_distance:
                        counts[(x, y)] += 1
                prev_by_id = cur_by_id
    return counts


def find_direct_base_teleport_seed(
    player: int,
    *,
    source: tuple[int, int],
    seed_limit: int = 20000,
) -> int | None:
    from SDK.backend.engine import GameState
    from SDK.backend.model import Ant
    from SDK.utils.constants import ANT_TELEPORT_INTERVAL, AntBehavior

    target_base = PLAYER_BASES[1 - player]
    for seed in range(seed_limit + 1):
        state = GameState.initial(seed=seed)
        ant = Ant(0, player, source[0], source[1], hp=10, level=0, behavior=AntBehavior.DEFAULT)
        state.ants = [ant]
        state.round_index = ANT_TELEPORT_INTERVAL - 1
        state._teleport_ants()
        if (ant.x, ant.y) == target_base:
            return seed
    return None


def build_analysis(player: int, replay_roots: Iterable[Path]) -> dict:
    base = PLAYER_BASES[player]
    dist = shortest_distances_to_base(player)
    entries = boundary_entries(player, dist)
    total_path_counts: dict[tuple[int, int], int] = {}
    for entry in entries:
        total_path_counts[entry] = count_shortest_paths(entry, base, dist)

    near_base_cells = [(x, y) for x, y in WALKABLE_CELLS if hex_distance(x, y, *base) <= 3]
    danger_counter = observed_danger_teleports(player, replay_roots)

    slots = []
    for slot in sorted(HIGHLAND_CELLS[player]):
        slot_summary = {"slot": slot}
        for attack_range in (1, 2):
            covered = cells_in_tower_range(slot, attack_range)
            entries_any = 0
            entries_all = 0
            for entry in entries:
                total_paths = total_path_counts[entry]
                avoid_paths = count_shortest_paths(entry, base, dist, covered)
                if avoid_paths < total_paths:
                    entries_any += 1
                if avoid_paths == 0:
                    entries_all += 1
            near_base_cover = sum(1 for cell in near_base_cells if cell in covered)
            danger_cover = sum(weight for cell, weight in danger_counter.items() if cell in covered)
            slot_summary[f"range{attack_range}"] = {
                "entries_any": entries_any,
                "entries_all": entries_all,
                "near_base_cells_covered": near_base_cover,
                "danger_teleports_covered": danger_cover,
            }
        slots.append(slot_summary)

    top_slots_by_danger = {
        "range1": sorted(slots, key=lambda item: (-item["range1"]["danger_teleports_covered"], item["slot"]))[:10],
        "range2": sorted(slots, key=lambda item: (-item["range2"]["danger_teleports_covered"], item["slot"]))[:10],
    }
    top_slots_by_entries_all = {
        "range1": sorted(slots, key=lambda item: (-item["range1"]["entries_all"], item["slot"]))[:10],
        "range2": sorted(slots, key=lambda item: (-item["range2"]["entries_all"], item["slot"]))[:10],
    }

    return {
        "player": player,
        "base": base,
        "entry_count": len(entries),
        "entries": [
            {"cell": entry, "graph_distance": dist[entry], "shortest_path_count": total_path_counts[entry]}
            for entry in entries
        ],
        "near_base_cells": near_base_cells,
        "danger_teleports": {
            "total": int(sum(danger_counter.values())),
            "cells": [
                {"cell": cell, "count": count}
                for cell, count in sorted(danger_counter.items(), key=lambda item: (-item[1], item[0]))
            ],
        },
        "slots": slots,
        "top_slots_by_danger": top_slots_by_danger,
        "top_slots_by_entries_all": top_slots_by_entries_all,
    }


def render_markdown(analysis: dict, direct_base_seed: int | None) -> str:
    lines = [
        "# Game1 Path Control Analysis",
        "",
        f"- player: `{analysis['player']}`",
        f"- base: `{tuple(analysis['base'])}`",
        f"- own-half boundary entry cells: `{analysis['entry_count']}`",
        f"- dangerous observed teleport landings within 3 of base: `{analysis['danger_teleports']['total']}`",
        "",
        "## Boundary Entries",
        "",
        "| entry | graph_dist_to_base | shortest_paths |",
        "|---|---:|---:|",
    ]
    for item in analysis["entries"]:
        lines.append(f"| {tuple(item['cell'])} | {item['graph_distance']} | {item['shortest_path_count']} |")

    lines.extend(
        [
            "",
            "## Observed Dangerous Teleport Cells",
            "",
            "| cell | count |",
            "|---|---:|",
        ]
    )
    for item in analysis["danger_teleports"]["cells"][:20]:
        lines.append(f"| {tuple(item['cell'])} | {item['count']} |")

    lines.extend(
        [
            "",
            "## Top Slots By Observed Danger Coverage",
            "",
            "### Range 1",
            "",
            "| slot | danger_cover | entries_any | entries_all | near_base_cover |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for item in analysis["top_slots_by_danger"]["range1"]:
        stats = item["range1"]
        lines.append(
            f"| {tuple(item['slot'])} | {stats['danger_teleports_covered']} | "
            f"{stats['entries_any']} | {stats['entries_all']} | {stats['near_base_cells_covered']} |"
        )

    lines.extend(
        [
            "",
            "### Range 2",
            "",
            "| slot | danger_cover | entries_any | entries_all | near_base_cover |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for item in analysis["top_slots_by_danger"]["range2"]:
        stats = item["range2"]
        lines.append(
            f"| {tuple(item['slot'])} | {stats['danger_teleports_covered']} | "
            f"{stats['entries_any']} | {stats['entries_all']} | {stats['near_base_cells_covered']} |"
        )

    lines.extend(
        [
            "",
            "## Direct Base Teleport Check",
            "",
            (
                f"- Found a seed that directly teleports a beyond-midline ant onto the enemy base: `{direct_base_seed}`"
                if direct_base_seed is not None
                else "- No direct-to-base seed found within the search limit."
            ),
            "- Direct-to-enemy-base teleport becomes possible once an ant is already outside its own half; while still in its own half, teleport destinations stay within its own-half path set.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze shortest base-entry corridors and tower-slot control")
    parser.add_argument("--player", type=int, default=0)
    parser.add_argument("--output-json", default="")
    parser.add_argument("--output-md", default="")
    args = parser.parse_args()

    replay_roots = [path for path in DEFAULT_REPLAY_ROOTS if path.exists()]
    analysis = build_analysis(args.player, replay_roots)
    direct_seed = find_direct_base_teleport_seed(args.player, source=(12, 9) if args.player == 0 else (6, 9))

    output_json = Path(args.output_json) if args.output_json else REPO_ROOT / "docs" / "generated" / f"game1_path_control_player{args.player}.json"
    output_md = Path(args.output_md) if args.output_md else REPO_ROOT / "docs" / "generated" / f"game1_path_control_player{args.player}.md"
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps({"analysis": analysis, "direct_base_seed": direct_seed}, ensure_ascii=False, indent=2), encoding="utf-8")
    output_md.write_text(render_markdown(analysis, direct_seed), encoding="utf-8")
    print(json.dumps({"json": str(output_json), "md": str(output_md)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
