#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import os
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
import select
import shutil
import statistics
import struct
import subprocess
import sys
import time
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
CPP_AI_ROOT = SCRIPT_DIR.parent
GAME1_ROOT = CPP_AI_ROOT.parent
ANT_GAME_ROOT = GAME1_ROOT / "Ant-Game"
GAME_DIR = ANT_GAME_ROOT / "game"
DEFAULT_GAME_BIN = GAME_DIR / "output" / "main"
PACKAGE_AI = CPP_AI_ROOT / "package_ai.sh"
DEFAULT_TARGET = "cpp_lure_v2"
TIMEOUT_SECONDS = 30.0
MAP_SIZE = 19
PLAYER_COUNT = 2
NO_MOVE = -1
TOWER_DESTROY_TYPE = -1
OFFSETS = (
    ((0, 1), (-1, 0), (0, -1), (1, -1), (1, 0), (1, 1)),
    ((-1, 1), (-1, 0), (-1, -1), (0, -1), (1, 0), (0, 1)),
)

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


def parse_seed_spec(text: str) -> list[int]:
    seeds: list[int] = []
    for chunk in text.split(","):
        item = chunk.strip()
        if not item:
            continue
        if ":" in item:
            start_text, end_text = item.split(":", 1)
            start = int(start_text)
            end = int(end_text)
            step = 1 if end >= start else -1
            seeds.extend(range(start, end + step, step))
        else:
            seeds.append(int(item))
    ordered: list[int] = []
    seen: set[int] = set()
    for seed in seeds:
        if seed in seen:
            continue
        seen.add(seed)
        ordered.append(seed)
    return ordered


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


def stats_summary(values: list[float | int]) -> dict[str, float]:
    numeric = [float(value) for value in values]
    if not numeric:
        return {"count": 0.0, "avg": 0.0, "p50": 0.0, "p95": 0.0, "max": 0.0}
    return {
        "count": float(len(numeric)),
        "avg": float(sum(numeric) / len(numeric)),
        "p50": percentile(numeric, 0.5),
        "p95": percentile(numeric, 0.95),
        "max": float(max(numeric)),
    }


def packet(payload: object) -> bytes:
    body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return struct.pack(">I", len(body)) + body


def read_exact(stream, size: int, proc: subprocess.Popen[bytes], label: str, timeout: float = TIMEOUT_SECONDS) -> bytes:
    fd = stream.fileno()
    data = bytearray()
    deadline = time.monotonic() + timeout
    while len(data) < size:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError(f"timed out while reading {label}")
        ready, _, _ = select.select([fd], [], [], remaining)
        if not ready:
            continue
        chunk = os.read(fd, size - len(data))
        if not chunk:
            code = proc.poll()
            if code is None:
                raise EOFError(f"unexpected EOF while reading {label}")
            raise EOFError(f"{label} closed with exit code {code}")
        data.extend(chunk)
    return bytes(data)


def read_game_packet(game: subprocess.Popen[bytes]) -> tuple[int, bytes]:
    size = struct.unpack(">I", read_exact(game.stdout, 4, game, "game packet length"))[0]
    obj = struct.unpack(">i", read_exact(game.stdout, 4, game, "game packet object"))[0]
    payload = read_exact(game.stdout, size, game, "game packet payload")
    return obj, payload


def read_ai_packet(ai: subprocess.Popen[bytes], name: str) -> bytes:
    size = struct.unpack(">I", read_exact(ai.stdout, 4, ai, f"{name} packet length"))[0]
    payload = read_exact(ai.stdout, size, ai, f"{name} packet payload")
    return struct.pack(">I", size) + payload


def write_all(stream, payload: bytes) -> None:
    stream.write(payload)
    stream.flush()


def terminate(proc: subprocess.Popen[bytes] | None) -> None:
    if proc is None or proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=3)


def close_stdin(proc: subprocess.Popen[bytes] | None) -> None:
    if proc is None or proc.stdin is None:
        return
    try:
        proc.stdin.close()
    except OSError:
        pass


def launch_ai(ai_dir: Path, stderr_path: Path, debug_mode: str | None) -> tuple[subprocess.Popen[bytes], Any]:
    stderr_handle = stderr_path.open("wb")
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    if debug_mode:
        env["ANTGAME_CPP_BASELINE_DEBUG"] = debug_mode
    else:
        env.pop("ANTGAME_CPP_BASELINE_DEBUG", None)
    proc = subprocess.Popen(
        [sys.executable, "main.py"],
        cwd=ai_dir,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=stderr_handle,
        env=env,
    )
    return proc, stderr_handle


def read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def parse_json_lines(text: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for raw in text.splitlines():
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


def summarize_ai_log(stderr_path: Path) -> dict[str, Any]:
    text = read_text(stderr_path)
    entries = parse_json_lines(text)
    decisions = [entry for entry in entries if entry.get("kind") == "decision"]
    plans = [entry for entry in entries if entry.get("kind") == "plan"]
    elapsed = [int(entry["elapsed_us"]) for entry in decisions if isinstance(entry.get("elapsed_us"), (int, float))]
    plans_total = [int(entry["plans_total"]) for entry in decisions if isinstance(entry.get("plans_total"), (int, float))]
    plans_unique = [int(entry["plans_unique"]) for entry in decisions if isinstance(entry.get("plans_unique"), (int, float))]
    best_names = Counter(str(entry.get("best_name", "")) for entry in decisions)
    return {
        "decision_count": len(decisions),
        "plan_line_count": len(plans),
        "elapsed_us": elapsed,
        "plans_total": plans_total,
        "plans_unique": plans_unique,
        "best_name_counts": dict(best_names),
        "raw_line_count": len(text.splitlines()),
    }


def parse_operation_payload(text: str) -> list[dict[str, Any]]:
    lines = text.splitlines()
    if not lines:
        return []
    count = int(lines[0].strip() or "0")
    operations: list[dict[str, Any]] = []
    for index in range(1, 1 + count):
        parts = [int(token) for token in lines[index].split()]
        op_type = parts[0]
        if len(parts) == 1:
            operations.append({"type": op_type})
        elif len(parts) == 2:
            operations.append({"type": op_type, "id": parts[1]})
        else:
            if op_type in {11, 21, 22, 23, 24}:
                operations.append({"type": op_type, "pos": {"x": parts[1], "y": parts[2]}})
            elif op_type == 12:
                operations.append({"type": op_type, "id": parts[1], "args": parts[2]})
            else:
                operations.append({"type": op_type, "id": parts[1], "args": parts[2]})
    return operations


def parse_ai_packet(ai_packet: bytes) -> list[dict[str, Any]]:
    if len(ai_packet) < 4:
        return []
    size = struct.unpack(">I", ai_packet[:4])[0]
    payload = ai_packet[4:4 + size].decode("utf-8", errors="replace")
    return parse_operation_payload(payload)


def normalize_operation_for_replay(operation: dict[str, Any]) -> dict[str, Any]:
    op_type = int(operation.get("type", -1))
    op_id = int(operation.get("id", -1)) if isinstance(operation.get("id"), (int, float)) else -1
    op_args = int(operation.get("args", -1)) if isinstance(operation.get("args"), (int, float)) else -1
    pos = operation.get("pos") if isinstance(operation.get("pos"), dict) else {}
    x = int(pos.get("x", -1)) if isinstance(pos.get("x"), (int, float)) else -1
    y = int(pos.get("y", -1)) if isinstance(pos.get("y"), (int, float)) else -1
    return {
        "type": op_type,
        "id": op_id,
        "args": op_args,
        "pos": {"x": x, "y": y},
    }


def zero_pheromone() -> list[list[list[float]]]:
    return [
        [[0.0 for _ in range(MAP_SIZE)] for _ in range(MAP_SIZE)]
        for _ in range(PLAYER_COUNT)
    ]


def direction_between(x0: int, y0: int, x1: int, y1: int) -> int:
    parity = y0 % 2
    for direction, (dx, dy) in enumerate(OFFSETS[parity]):
        if x0 + dx == x1 and y0 + dy == y1:
            return direction
    return NO_MOVE


def normalize_ant_for_replay(ant: dict[str, Any], previous_ant: dict[str, Any] | None) -> dict[str, Any]:
    ant_out = {
        "id": int(ant["id"]),
        "player": int(ant["player"]),
        "pos": {"x": int(ant["pos"]["x"]), "y": int(ant["pos"]["y"])},
        "hp": int(ant["hp"]),
        "move": NO_MOVE,
        "level": int(ant["level"]),
        "age": int(ant["age"]),
        "status": int(ant["status"]),
        "behavior": int(ant["behavior"]),
        "kind": int(ant["kind"]),
    }
    if previous_ant is not None:
        prev_x = int(previous_ant["pos"]["x"])
        prev_y = int(previous_ant["pos"]["y"])
        cur_x = ant_out["pos"]["x"]
        cur_y = ant_out["pos"]["y"]
        ant_out["move"] = direction_between(prev_x, prev_y, cur_x, cur_y)
    return ant_out


def delta_towers_for_replay(
    previous_towers: dict[int, dict[str, Any]],
    current_towers: dict[int, dict[str, Any]],
) -> list[dict[str, Any]]:
    delta: list[dict[str, Any]] = []
    for tower_id in sorted(previous_towers):
        if tower_id in current_towers:
            continue
        removed = {
            "player": int(previous_towers[tower_id]["player"]),
            "id": int(previous_towers[tower_id]["id"]),
            "pos": {
                "x": int(previous_towers[tower_id]["pos"]["x"]),
                "y": int(previous_towers[tower_id]["pos"]["y"]),
            },
            "cd": int(previous_towers[tower_id]["cd"]),
            "hp": int(previous_towers[tower_id]["hp"]),
            "type": TOWER_DESTROY_TYPE,
        }
        delta.append(removed)
    for tower_id in sorted(current_towers):
        current = current_towers[tower_id]
        previous = previous_towers.get(tower_id)
        if previous == current:
            continue
        delta.append({
            "player": int(current["player"]),
            "id": int(current["id"]),
            "pos": {"x": int(current["pos"]["x"]), "y": int(current["pos"]["y"])},
            "cd": int(current["cd"]),
            "hp": int(current["hp"]),
            "type": int(current["type"]),
        })
    return delta


def official_replay_from_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    replay: list[dict[str, Any]] = []
    previous_towers: dict[int, dict[str, Any]] = {}
    previous_ants: dict[int, dict[str, Any]] = {}
    for index, record in enumerate(records):
        round_state = record.get("round_state", {})
        towers = round_state.get("towers", []) if isinstance(round_state, dict) else []
        ants = round_state.get("ants", []) if isinstance(round_state, dict) else []
        current_towers = {
            int(tower["id"]): {
                "player": int(tower["player"]),
                "id": int(tower["id"]),
                "pos": {"x": int(tower["pos"]["x"]), "y": int(tower["pos"]["y"])},
                "cd": int(tower["cd"]),
                "hp": int(tower["hp"]),
                "type": int(tower["type"]),
            }
            for tower in towers
        }
        replay_round_state = {
            "towers": delta_towers_for_replay(previous_towers, current_towers),
            "ants": [],
            "coins": [int(value) for value in round_state.get("coins", [0, 0])[:2]],
            "camps": [int(value) for value in round_state.get("camps", [0, 0])[:2]],
            "speedLv": [int(value) for value in round_state.get("speedLv", [0, 0])[:2]],
            "anthpLv": [int(value) for value in round_state.get("anthpLv", [0, 0])[:2]],
            "weaponCooldowns": [[int(value) for value in row] for row in round_state.get("weaponCooldowns", [])],
            "activeEffects": [
                {
                    "type": int(effect["type"]),
                    "player": int(effect["player"]),
                    "x": int(effect["x"]),
                    "y": int(effect["y"]),
                    "duration": int(effect["duration"]),
                }
                for effect in round_state.get("activeEffects", [])
            ],
            "pheromone": zero_pheromone(),
            "winner": int(round_state.get("winner", -1)),
            "message": str(round_state.get("message", "")),
        }
        current_ants: dict[int, dict[str, Any]] = {}
        for ant in ants:
            ant_id = int(ant["id"])
            normalized_ant = normalize_ant_for_replay(ant, previous_ants.get(ant_id))
            replay_round_state["ants"].append(normalized_ant)
            current_ants[ant_id] = normalized_ant
        replay_record = {
            "op0": [normalize_operation_for_replay(op) for op in record.get("op0", [])],
            "op1": [normalize_operation_for_replay(op) for op in record.get("op1", [])],
            "round_state": replay_round_state,
        }
        if index == 0 and "seed" in record:
            replay_record["seed"] = int(record["seed"])
        replay.append(replay_record)
        previous_towers = current_towers
        previous_ants = current_ants
    return replay


def try_parse_round_state_text(text: str) -> dict[str, Any] | None:
    lines = text.splitlines()
    if len(lines) < 7:
        return None
    if len(lines[0].split()) != 1:
        return None
    cursor = 0

    def next_line() -> str:
        nonlocal cursor
        if cursor >= len(lines):
            raise ValueError("unexpected EOF")
        value = lines[cursor]
        cursor += 1
        return value

    try:
        round_index = int(next_line())
        tower_count = int(next_line())
        towers: list[dict[str, Any]] = []
        for _ in range(tower_count):
            parts = [int(token) for token in next_line().split()]
            if len(parts) < 6:
                raise ValueError("invalid tower row")
            tower_id, player, x, y, tower_type, cooldown = parts[:6]
            hp = parts[6] if len(parts) >= 7 else 0
            towers.append({
                "id": tower_id,
                "player": player,
                "pos": {"x": x, "y": y},
                "type": tower_type,
                "cd": cooldown,
                "hp": hp,
            })

        ant_count = int(next_line())
        ants: list[dict[str, Any]] = []
        for _ in range(ant_count):
            parts = [int(token) for token in next_line().split()]
            if len(parts) < 8:
                raise ValueError("invalid ant row")
            ant_id, player, x, y, hp, level, age, status = parts[:8]
            behavior = parts[8] if len(parts) >= 9 else 0
            kind = parts[9] if len(parts) >= 10 else 0
            ants.append({
                "id": ant_id,
                "player": player,
                "pos": {"x": x, "y": y},
                "hp": hp,
                "level": level,
                "age": age,
                "status": status,
                "behavior": behavior,
                "kind": kind,
                "move": -1,
            })

        coins = [int(token) for token in next_line().split()[:2]]
        camp_fields = [int(token) for token in next_line().split()]
        camps = camp_fields[:2]
        speed_lv = camp_fields[2:4] if len(camp_fields) >= 4 else [0, 0]
        anthp_lv = camp_fields[4:6] if len(camp_fields) >= 6 else [0, 0]

        cooldown_row_count = int(next_line())
        weapon_cooldowns: list[list[int]] = []
        for _ in range(cooldown_row_count):
            weapon_cooldowns.append([int(token) for token in next_line().split()])

        active_effect_count = int(next_line())
        active_effects: list[dict[str, Any]] = []
        for _ in range(active_effect_count):
            effect_type, player, x, y, duration = [int(token) for token in next_line().split()]
            active_effects.append({
                "type": effect_type,
                "player": player,
                "x": x,
                "y": y,
                "duration": duration,
            })
    except (ValueError, IndexError):
        return None

    return {
        "round": round_index,
        "towers": towers,
        "ants": ants,
        "coins": coins,
        "camps": camps,
        "speedLv": speed_lv,
        "anthpLv": anthp_lv,
        "weaponCooldowns": weapon_cooldowns,
        "activeEffects": active_effects,
        "winner": -1,
        "message": "",
    }


def extract_operation(op: Any) -> tuple[int | None, int | None, int | None, int | None]:
    if isinstance(op, dict):
        op_type = op.get("type")
        op_id = op.get("id")
        op_args = op.get("args")
        pos = op.get("pos") if isinstance(op.get("pos"), dict) else {}
        x = pos.get("x")
        y = pos.get("y")
        return (
            int(op_type) if isinstance(op_type, (int, float)) else None,
            int(op_id) if isinstance(op_id, (int, float)) else None,
            int(op_args) if isinstance(op_args, (int, float)) else None,
            (int(x) if isinstance(x, (int, float)) else None) * 1000 +
            (int(y) if isinstance(y, (int, float)) else None)
            if isinstance(x, (int, float)) and isinstance(y, (int, float))
            else None,
        )
    return None, None, None, None


def decode_xy(encoded_xy: int | None) -> tuple[int | None, int | None]:
    if encoded_xy is None:
        return None, None
    return encoded_xy // 1000, encoded_xy % 1000


def extract_coins(round_state: dict[str, Any]) -> list[int] | None:
    coins = round_state.get("coins")
    if isinstance(coins, list) and len(coins) >= 2:
        try:
            return [int(coins[0]), int(coins[1])]
        except (TypeError, ValueError):
            return None
    return None


def extract_camp_hp(round_state: dict[str, Any]) -> list[int] | None:
    camps = round_state.get("camps")
    if isinstance(camps, list) and len(camps) >= 2:
        try:
            return [int(camps[0]), int(camps[1])]
        except (TypeError, ValueError):
            return None
    return None


def summarize_replay(replay_path: Path) -> dict[str, Any]:
    replay = json.loads(replay_path.read_text(encoding="utf-8"))
    per_player_ops = [Counter(), Counter()]
    hold_counts = [0, 0]
    coins_by_round: list[list[int]] = []
    camps_by_round: list[list[int]] = []
    valid_rounds = 0
    last_valid_round_state: dict[str, Any] | None = None
    for record in replay:
        if not isinstance(record, dict):
            continue
        round_state = record.get("round_state", {})
        if not isinstance(round_state, dict):
            continue
        valid_rounds += 1
        last_valid_round_state = round_state
        coins = extract_coins(round_state)
        if coins is not None:
            coins_by_round.append(coins)
        camps = extract_camp_hp(round_state)
        if camps is not None:
            camps_by_round.append(camps)
        for player in (0, 1):
            operations = record.get(f"op{player}", [])
            if not isinstance(operations, list) or not operations:
                hold_counts[player] += 1
                continue
            for operation in operations:
                op_type, _op_id, _op_args, _encoded_xy = extract_operation(operation)
                if op_type is None:
                    per_player_ops[player]["unknown"] += 1
                    continue
                per_player_ops[player][OP_NAMES.get(op_type, str(op_type))] += 1
    final_coins = extract_coins(last_valid_round_state or {}) or [0, 0]
    final_camps = extract_camp_hp(last_valid_round_state or {}) or [0, 0]
    return {
        "rounds_recorded": valid_rounds,
        "final_coins": final_coins,
        "final_camp_hp": final_camps,
        "hold_counts": hold_counts,
        "operation_counts": [dict(per_player_ops[0]), dict(per_player_ops[1])],
        "coins_by_round": coins_by_round,
        "camp_hp_by_round": camps_by_round,
    }


def _clean_replay_operation_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    cleaned: list[dict[str, Any]] = []
    for operation in value:
        if not isinstance(operation, dict):
            continue
        cleaned.append(normalize_operation_for_replay(operation))
    return cleaned


def _clean_replay_round_state(round_state: Any) -> dict[str, Any] | None:
    if not isinstance(round_state, dict):
        return None

    towers_raw = round_state.get("towers", [])
    towers: list[dict[str, Any]] = []
    if isinstance(towers_raw, list):
        for tower in towers_raw:
            if not isinstance(tower, dict):
                continue
            try:
                tower_id = int(tower["id"])
                tower_type = int(tower["type"])
                player = int(tower["player"])
                pos_x = int(tower["pos"]["x"])
                pos_y = int(tower["pos"]["y"])
            except (KeyError, TypeError, ValueError):
                continue
            cleaned_tower = {
                "player": player,
                "id": tower_id,
                "pos": {"x": pos_x, "y": pos_y},
                "cd": int(tower.get("cd", 0)),
                "hp": int(tower.get("hp", 0)),
                "type": tower_type,
            }
            attack = tower.get("attack")
            if tower_type != TOWER_DESTROY_TYPE and isinstance(attack, list):
                cleaned_tower["attack"] = [
                    int(ant_id)
                    for ant_id in attack
                    if isinstance(ant_id, (int, float))
                ]
            towers.append(cleaned_tower)

    ants_raw = round_state.get("ants", [])
    ants: list[dict[str, Any]] = []
    if isinstance(ants_raw, list):
        for ant in ants_raw:
            if not isinstance(ant, dict):
                continue
            try:
                ants.append({
                    "id": int(ant["id"]),
                    "player": int(ant["player"]),
                    "pos": {"x": int(ant["pos"]["x"]), "y": int(ant["pos"]["y"])},
                    "hp": int(ant["hp"]),
                    "move": int(ant.get("move", NO_MOVE)),
                    "level": int(ant["level"]),
                    "age": int(ant["age"]),
                    "status": int(ant["status"]),
                    "behavior": int(ant["behavior"]),
                    "kind": int(ant["kind"]),
                })
            except (KeyError, TypeError, ValueError):
                continue

    cleaned: dict[str, Any] = {
        "towers": towers,
        "ants": ants,
        "coins": [int(value) for value in round_state.get("coins", [0, 0])[:2]],
        "camps": [int(value) for value in round_state.get("camps", [0, 0])[:2]],
        "speedLv": [int(value) for value in round_state.get("speedLv", [0, 0])[:2]],
        "anthpLv": [int(value) for value in round_state.get("anthpLv", [0, 0])[:2]],
        "weaponCooldowns": [
            [int(value) for value in row]
            for row in round_state.get("weaponCooldowns", [])
            if isinstance(row, list)
        ],
        "activeEffects": [
            {
                "type": int(effect["type"]),
                "player": int(effect["player"]),
                "x": int(effect["x"]),
                "y": int(effect["y"]),
                "duration": int(effect["duration"]),
            }
            for effect in round_state.get("activeEffects", [])
            if isinstance(effect, dict)
            and isinstance(effect.get("type"), (int, float))
            and isinstance(effect.get("player"), (int, float))
            and isinstance(effect.get("x"), (int, float))
            and isinstance(effect.get("y"), (int, float))
            and isinstance(effect.get("duration"), (int, float))
        ],
        "pheromone": round_state.get("pheromone", zero_pheromone()),
        "winner": int(round_state.get("winner", -1)),
        "message": str(round_state.get("message", "")),
    }
    if "error" in round_state:
        cleaned["error"] = round_state.get("error")
    return cleaned


def load_official_replay(replay_path: Path, max_rounds: int, seed: int) -> list[dict[str, Any]] | None:
    if not replay_path.exists():
        return None
    try:
        replay = json.loads(replay_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    if not isinstance(replay, list):
        return None
    normalized: list[dict[str, Any]] = []
    for record in replay:
        if not isinstance(record, dict):
            continue
        # Preserve the official delta replay contract so tower removals remain
        # visible as `type = -1` events instead of being flattened away.
        round_state = _clean_replay_round_state(record.get("round_state"))
        if round_state is None:
            continue
        cleaned_record = {
            "op0": _clean_replay_operation_list(record.get("op0")),
            "op1": _clean_replay_operation_list(record.get("op1")),
            "round_state": round_state,
        }
        if not normalized:
            cleaned_record["seed"] = seed
        normalized.append(cleaned_record)
        if len(normalized) >= max_rounds:
            break
    return normalized if normalized else None


def run_partial_match(
    seed: int,
    packaged_ai_dir: Path,
    game_bin: Path,
    out_dir: Path,
    debug_mode: str | None,
    max_rounds: int,
) -> dict[str, Any]:
    workdir = out_dir / f"seed_{seed:04d}"
    if workdir.exists():
        shutil.rmtree(workdir)
    workdir.mkdir(parents=True)

    replay_path = workdir / "replay.json"
    official_replay_path = workdir / "unused_game_replay.json"
    game_stderr_path = workdir / "game.stderr.log"
    ai0_stderr_path = workdir / "ai0.stderr.log"
    ai1_stderr_path = workdir / "ai1.stderr.log"

    game_stderr_handle = game_stderr_path.open("wb")
    game = None
    ai0 = None
    ai1 = None
    ai0_stderr_handle = None
    ai1_stderr_handle = None

    result: dict[str, Any] = {
        "seed": seed,
        "debug_mode": debug_mode or "",
        "workdir": str(workdir),
        "replay": str(replay_path),
        "max_rounds": max_rounds,
    }

    records: list[dict[str, Any]] = []
    active_round_state: dict[str, Any] | None = None
    active_round_ops = {0: [], 1: []}
    cutoff_reached = False
    stop_after_round: int | None = None

    def flush_active_round() -> None:
        nonlocal active_round_state, active_round_ops
        if active_round_state is None:
            return
        record = {
            "op0": list(active_round_ops[0]),
            "op1": list(active_round_ops[1]),
            "round_state": active_round_state,
        }
        if not records:
            record["seed"] = seed
        records.append(record)
        active_round_state = None
        active_round_ops = {0: [], 1: []}

    try:
        ai0, ai0_stderr_handle = launch_ai(packaged_ai_dir, ai0_stderr_path, debug_mode)
        ai1, ai1_stderr_handle = launch_ai(packaged_ai_dir, ai1_stderr_path, debug_mode)

        game = subprocess.Popen(
            [str(game_bin)],
            cwd=GAME_DIR,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=game_stderr_handle,
        )

        init = {
            "player_list": [1, 1],
            "player_num": 2,
            "config": {"random_seed": seed},
            "replay": str(workdir / "unused_game_replay.json"),
        }
        write_all(game.stdin, packet(init))

        while True:
            obj, payload = read_game_packet(game)
            if obj in (0, 1):
                target = ai0 if obj == 0 else ai1
                write_all(target.stdin, payload)
                continue

            message = json.loads(payload.decode("utf-8"))
            if isinstance(message, dict) and "player" in message and "content" in message:
                recorded_in_message = False
                for player, content in zip(message["player"], message["content"]):
                    round_state = None if recorded_in_message else try_parse_round_state_text(content)
                    if round_state is not None:
                        flush_active_round()
                        active_round_state = round_state
                        active_round_ops = {0: [], 1: []}
                        recorded_in_message = True
                        if int(round_state["round"]) >= max_rounds:
                            stop_after_round = int(round_state["round"])
                    target = ai0 if int(player) == 0 else ai1
                    write_all(target.stdin, content.encode("utf-8"))

            if isinstance(message, dict) and message.get("listen"):
                for player in message["listen"]:
                    player_int = int(player)
                    target = ai0 if player_int == 0 else ai1
                    ai_packet = read_ai_packet(target, f"ai{player_int}")
                    active_round_ops[player_int] = parse_ai_packet(ai_packet)
                    reply = {
                        "player": player_int,
                        "content": ai_packet.decode("latin1"),
                        "time": 0,
                    }
                    write_all(game.stdin, packet(reply))
                if stop_after_round is not None and active_round_state is not None:
                    if int(active_round_state["round"]) >= stop_after_round:
                        cutoff_reached = True
                        flush_active_round()
                        break
            if isinstance(message, dict) and "end_state" in message:
                flush_active_round()
                result["end_state"] = message["end_state"]
                result["end_info"] = message.get("end_info")
                break

        close_stdin(ai0)
        close_stdin(ai1)
        terminate(game)
        terminate(ai0)
        terminate(ai1)
        if ai0_stderr_handle is not None:
            ai0_stderr_handle.close()
            ai0_stderr_handle = None
        if ai1_stderr_handle is not None:
            ai1_stderr_handle.close()
            ai1_stderr_handle = None
        game_stderr_handle.close()

        flush_active_round()
        replay = load_official_replay(official_replay_path, max_rounds, seed)
        if replay is None:
            replay = official_replay_from_records(records)
        replay_path.write_text(json.dumps(replay, ensure_ascii=False, indent=2), encoding="utf-8")

        result["cutoff_reached"] = cutoff_reached
        result["game_stderr"] = read_text(game_stderr_path)
        result["ai0_log"] = summarize_ai_log(ai0_stderr_path)
        result["ai1_log"] = summarize_ai_log(ai1_stderr_path)
        result["replay_summary"] = summarize_replay(replay_path)
        (workdir / "match_summary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        return result
    finally:
        terminate(ai0)
        terminate(ai1)
        terminate(game)
        if ai0_stderr_handle is not None:
            ai0_stderr_handle.close()
        if ai1_stderr_handle is not None:
            ai1_stderr_handle.close()
        game_stderr_handle.close()


def aggregate(results: list[dict[str, Any]]) -> dict[str, Any]:
    rounds: list[int] = []
    final_camp_hp = [[], []]
    final_coins = [[], []]
    elapsed_us = [[], []]
    plans_unique = [[], []]
    for result in results:
        replay_summary = result.get("replay_summary", {})
        if isinstance(replay_summary, dict):
            rounds.append(int(replay_summary.get("rounds_recorded", 0)))
            for player in (0, 1):
                final_camp_hp[player].append(int(replay_summary.get("final_camp_hp", [0, 0])[player]))
                final_coins[player].append(int(replay_summary.get("final_coins", [0, 0])[player]))
        for player in (0, 1):
            log_summary = result.get(f"ai{player}_log", {})
            if not isinstance(log_summary, dict):
                continue
            elapsed_us[player].extend(int(x) for x in log_summary.get("elapsed_us", []))
            plans_unique[player].extend(int(x) for x in log_summary.get("plans_unique", []))
    return {
        "match_count": len(results),
        "rounds": stats_summary(rounds),
        "final_camp_hp": [stats_summary(final_camp_hp[0]), stats_summary(final_camp_hp[1])],
        "final_coins": [stats_summary(final_coins[0]), stats_summary(final_coins[1])],
        "elapsed_us": [stats_summary(elapsed_us[0]), stats_summary(elapsed_us[1])],
        "plans_unique": [stats_summary(plans_unique[0]), stats_summary(plans_unique[1])],
    }


def print_human_summary(summary: dict[str, Any]) -> None:
    print(f"matches={summary['match_count']}")
    print(f"rounds={summary['rounds']}")
    for player in (0, 1):
        print(
            f"player={player} final_camp_hp={summary['final_camp_hp'][player]} "
            f"final_coins={summary['final_coins'][player]} "
            f"elapsed_us={summary['elapsed_us'][player]} "
            f"plans_unique={summary['plans_unique'][player]}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run parallel cpp baseline self-play and stop at a fixed round with partial replay.")
    parser.add_argument("--seeds", default="7,20,24")
    parser.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 1) - 1))
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--target", default=DEFAULT_TARGET)
    parser.add_argument("--debug-seeds", default="")
    parser.add_argument("--game-bin", type=Path, default=DEFAULT_GAME_BIN)
    parser.add_argument("--max-rounds", type=int, default=200)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    seeds = parse_seed_spec(args.seeds)
    if not seeds:
        raise SystemExit("no seeds selected")
    debug_seeds = set(parse_seed_spec(args.debug_seeds)) if args.debug_seeds.strip() else set()

    output_dir = args.output_dir.resolve()
    if output_dir.exists():
        if not args.force:
            raise SystemExit(f"output directory exists: {output_dir}")
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)

    game_bin = args.game_bin.resolve()
    if not game_bin.exists():
        subprocess.run(["make"], cwd=GAME_DIR, check=True)

    packaged_ai_dir = output_dir / "packaged_ai"
    subprocess.run([str(PACKAGE_AI), args.target, str(packaged_ai_dir)], cwd=GAME1_ROOT, check=True)

    jobs = max(1, min(args.jobs, len(seeds)))
    results: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []

    with ProcessPoolExecutor(max_workers=jobs) as executor:
        future_map = {}
        for seed in seeds:
            debug_mode = "plans" if seed in debug_seeds else "summary"
            future = executor.submit(run_partial_match, seed, packaged_ai_dir, game_bin, output_dir / "matches", debug_mode, args.max_rounds)
            future_map[future] = seed
        for future in as_completed(future_map):
            seed = future_map[future]
            try:
                result = future.result()
            except Exception as exc:
                failures.append({"seed": seed, "error": f"{type(exc).__name__}: {exc}"})
                print(f"seed={seed} failed: {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
                continue
            results.append(result)
            replay_summary = result["replay_summary"]
            print(
                f"seed={seed} rounds={replay_summary.get('rounds_recorded')} "
                f"camp_hp={replay_summary.get('final_camp_hp')} "
                f"coins={replay_summary.get('final_coins')} "
                f"cutoff={result.get('cutoff_reached')}",
                flush=True,
            )

    results.sort(key=lambda item: int(item.get("seed", 0)))
    aggregate_summary = aggregate(results)
    report = {
        "config": {
            "seeds": seeds,
            "jobs": jobs,
            "debug_seeds": sorted(debug_seeds),
            "target": args.target,
            "game_bin": str(game_bin),
            "packaged_ai_dir": str(packaged_ai_dir),
            "max_rounds": args.max_rounds,
        },
        "aggregate": aggregate_summary,
        "failures": failures,
        "matches": results,
    }
    report_path = output_dir / "summary.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print_human_summary(aggregate_summary)
    print(f"summary_json={report_path}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
