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
DEFAULT_TARGET = "cpp_heavy_baseline"
TIMEOUT_SECONDS = 20.0

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
    sorted_values = sorted(values)
    if len(sorted_values) == 1:
        return float(sorted_values[0])
    position = q * (len(sorted_values) - 1)
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return float(sorted_values[lower])
    weight = position - lower
    return float(sorted_values[lower]) * (1.0 - weight) + float(sorted_values[upper]) * weight


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
        env["ANTGAME_CPP_BASELINE_DEBUG"] = "0"
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
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line.startswith("{") or not line.endswith("}"):
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            out.append(value)
    return out


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
    if isinstance(op, list) and op:
        op_type = int(op[0])
        if op_type in {11, 21, 22, 23, 24} and len(op) >= 3:
            return op_type, None, None, int(op[1]) * 1000 + int(op[2])
        if op_type == 12 and len(op) >= 3:
            return op_type, int(op[1]), int(op[2]), None
        if op_type == 13 and len(op) >= 2:
            return op_type, int(op[1]), None, None
        if op_type in {31, 32}:
            return op_type, None, None, None
    return None, None, None, None


def decode_xy(encoded: int | None) -> tuple[int | None, int | None]:
    if encoded is None:
        return None, None
    return encoded // 1000, encoded % 1000


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
    if not isinstance(camps, list) or len(camps) < 2:
        return None
    if all(isinstance(camp, (int, float)) for camp in camps[:2]):
        return [int(camps[0]), int(camps[1])]
    result: list[int] = []
    for camp in camps[:2]:
        if not isinstance(camp, dict):
            return None
        hp = camp.get("hp")
        if not isinstance(hp, (int, float)):
            return None
        result.append(int(hp))
    return result


def summarize_replay(replay_path: Path) -> dict[str, Any]:
    replay = json.loads(replay_path.read_text(encoding="utf-8"))
    per_player_ops = [Counter(), Counter()]
    per_player_builds = [Counter(), Counter()]
    per_player_lightning = [Counter(), Counter()]
    per_player_upgrade_targets = [Counter(), Counter()]
    hold_counts = [0, 0]
    coins_by_round: list[list[int]] = []
    camps_by_round: list[list[int]] = []

    for record in replay:
        round_state = record.get("round_state", {})
        if isinstance(round_state, dict):
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
                op_type, _op_id, op_args, encoded_xy = extract_operation(operation)
                if op_type is None:
                    per_player_ops[player]["unknown"] += 1
                    continue
                name = OP_NAMES.get(op_type, str(op_type))
                per_player_ops[player][name] += 1
                x, y = decode_xy(encoded_xy)
                if op_type == 11 and x is not None and y is not None:
                    per_player_builds[player][f"{x},{y}"] += 1
                elif op_type == 21 and x is not None and y is not None:
                    per_player_lightning[player][f"{x},{y}"] += 1
                elif op_type == 12 and op_args is not None:
                    per_player_upgrade_targets[player][str(op_args)] += 1

    last_round_state = replay[-1].get("round_state", {}) if replay else {}
    final_coins = extract_coins(last_round_state if isinstance(last_round_state, dict) else {}) or [0, 0]
    final_camps = extract_camp_hp(last_round_state if isinstance(last_round_state, dict) else {}) or [0, 0]

    return {
        "rounds_recorded": len(replay),
        "winner": last_round_state.get("winner") if isinstance(last_round_state, dict) else None,
        "message": last_round_state.get("message") if isinstance(last_round_state, dict) else None,
        "error": last_round_state.get("error") if isinstance(last_round_state, dict) else None,
        "final_coins": final_coins,
        "final_camp_hp": final_camps,
        "hold_counts": hold_counts,
        "operation_counts": [dict(per_player_ops[0]), dict(per_player_ops[1])],
        "build_positions": [dict(per_player_builds[0]), dict(per_player_builds[1])],
        "lightning_positions": [dict(per_player_lightning[0]), dict(per_player_lightning[1])],
        "upgrade_targets": [dict(per_player_upgrade_targets[0]), dict(per_player_upgrade_targets[1])],
        "coins_by_round": coins_by_round,
        "camp_hp_by_round": camps_by_round,
    }


def summarize_ai_log(stderr_path: Path) -> dict[str, Any]:
    text = read_text(stderr_path)
    entries = parse_json_lines(text)
    decisions = [entry for entry in entries if entry.get("kind") == "decision"]
    plans = [entry for entry in entries if entry.get("kind") == "plan"]
    elapsed = [int(entry["elapsed_us"]) for entry in decisions if isinstance(entry.get("elapsed_us"), (int, float))]
    plans_total = [int(entry["plans_total"]) for entry in decisions if isinstance(entry.get("plans_total"), (int, float))]
    plans_unique = [int(entry["plans_unique"]) for entry in decisions if isinstance(entry.get("plans_unique"), (int, float))]
    best_names = Counter(str(entry.get("best_name", "")) for entry in decisions)
    evasion_reasons = Counter(str(entry.get("v3_evasion_reason", "")) for entry in decisions if "v3_evasion_reason" in entry)
    evasion_used = [
        entry for entry in decisions
        if entry.get("v3_evasion_used") is True or str(entry.get("v3_evasion_used", "")).lower() == "true"
    ]
    evasion_worker_counts = [
        int(entry["v3_evasion_worker_count"])
        for entry in evasion_used
        if isinstance(entry.get("v3_evasion_worker_count"), (int, float))
    ]
    emp_reasons = Counter(str(entry.get("v3_emp_reason", "")) for entry in decisions if "v3_emp_reason" in entry)
    emp_used = [
        entry for entry in decisions
        if entry.get("v3_emp_used") is True or str(entry.get("v3_emp_used", "")).lower() == "true"
    ]
    emp_distances = [
        int(entry["v3_emp_distance"])
        for entry in emp_used
        if isinstance(entry.get("v3_emp_distance"), (int, float))
    ]
    return {
        "decision_count": len(decisions),
        "plan_line_count": len(plans),
        "elapsed_us": elapsed,
        "plans_total": plans_total,
        "plans_unique": plans_unique,
        "best_name_counts": dict(best_names),
        "v3_evasion_used_count": len(evasion_used),
        "v3_evasion_reason_counts": dict(evasion_reasons),
        "v3_evasion_worker_counts": evasion_worker_counts,
        "v3_emp_used_count": len(emp_used),
        "v3_emp_reason_counts": dict(emp_reasons),
        "v3_emp_distances": emp_distances,
        "raw_line_count": len(text.splitlines()),
    }


def run_match(
    seed: int,
    packaged_ai0_dir: Path,
    packaged_ai1_dir: Path,
    game_bin: Path,
    out_dir: Path,
    debug_mode: str | None,
    max_rounds: int | None,
) -> dict[str, Any]:
    workdir = out_dir / f"seed_{seed:04d}"
    if workdir.exists():
        shutil.rmtree(workdir)
    workdir.mkdir(parents=True)

    replay_path = workdir / "replay.json"
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
    }

    try:
        ai0, ai0_stderr_handle = launch_ai(packaged_ai0_dir, ai0_stderr_path, debug_mode)
        ai1, ai1_stderr_handle = launch_ai(packaged_ai1_dir, ai1_stderr_path, debug_mode)

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
            "replay": str(replay_path),
        }
        if max_rounds is not None:
            init["config"]["max_rounds"] = int(max_rounds)
        write_all(game.stdin, packet(init))

        while True:
            obj, payload = read_game_packet(game)
            if obj in (0, 1):
                target = ai0 if obj == 0 else ai1
                write_all(target.stdin, payload)
                continue

            message = json.loads(payload.decode("utf-8"))
            if isinstance(message, dict) and "player" in message and "content" in message:
                for player, content in zip(message["player"], message["content"]):
                    target = ai0 if int(player) == 0 else ai1
                    write_all(target.stdin, content.encode("utf-8"))
            if isinstance(message, dict) and message.get("listen"):
                for player in message["listen"]:
                    player_int = int(player)
                    target = ai0 if player_int == 0 else ai1
                    ai_packet = read_ai_packet(target, f"ai{player_int}")
                    reply = {
                        "player": player_int,
                        "content": ai_packet.decode("latin1"),
                        "time": 0,
                    }
                    write_all(game.stdin, packet(reply))
            if isinstance(message, dict) and "end_state" in message:
                result["end_state"] = message["end_state"]
                result["end_info"] = message.get("end_info")
                break

        game.wait(timeout=3)
        close_stdin(ai0)
        close_stdin(ai1)
        for proc in (ai0, ai1):
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                terminate(proc)

        result["game_returncode"] = game.returncode
        result["ai0_returncode"] = ai0.returncode
        result["ai1_returncode"] = ai1.returncode
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


def merge_counter_dict(target: Counter[str], payload: dict[str, Any]) -> None:
    for key, value in payload.items():
        if isinstance(value, (int, float)):
            target[str(key)] += int(value)


def aggregate(results: list[dict[str, Any]]) -> dict[str, Any]:
    winner_counts: Counter[str] = Counter()
    rounds: list[int] = []
    final_camp_hp = [[], []]
    final_coins = [[], []]
    operation_totals = [Counter(), Counter()]
    build_positions = [Counter(), Counter()]
    lightning_positions = [Counter(), Counter()]
    upgrade_targets = [Counter(), Counter()]
    hold_counts = [0, 0]
    turn_counts = [0, 0]
    elapsed_us = [[], []]
    plans_total = [[], []]
    plans_unique = [[], []]
    best_names = [Counter(), Counter()]
    v3_evasion_used_counts = [0, 0]
    v3_evasion_reasons = [Counter(), Counter()]
    v3_evasion_worker_counts = [[], []]
    v3_emp_used_counts = [0, 0]
    v3_emp_reasons = [Counter(), Counter()]
    v3_emp_distances = [[], []]

    for result in results:
        replay_summary = result.get("replay_summary", {})
        if not isinstance(replay_summary, dict):
            continue
        winner_counts[str(replay_summary.get("winner"))] += 1
        round_count = int(replay_summary.get("rounds_recorded", 0))
        rounds.append(round_count)
        for player in (0, 1):
            turn_counts[player] += round_count
            hold_counts[player] += int(replay_summary.get("hold_counts", [0, 0])[player])
            final_camp_hp[player].append(int(replay_summary.get("final_camp_hp", [0, 0])[player]))
            final_coins[player].append(int(replay_summary.get("final_coins", [0, 0])[player]))
            merge_counter_dict(operation_totals[player], replay_summary.get("operation_counts", [{}, {}])[player])
            merge_counter_dict(build_positions[player], replay_summary.get("build_positions", [{}, {}])[player])
            merge_counter_dict(lightning_positions[player], replay_summary.get("lightning_positions", [{}, {}])[player])
            merge_counter_dict(upgrade_targets[player], replay_summary.get("upgrade_targets", [{}, {}])[player])

        for player in (0, 1):
            log_key = f"ai{player}_log"
            log_summary = result.get(log_key, {})
            if not isinstance(log_summary, dict):
                continue
            elapsed_us[player].extend(int(x) for x in log_summary.get("elapsed_us", []))
            plans_total[player].extend(int(x) for x in log_summary.get("plans_total", []))
            plans_unique[player].extend(int(x) for x in log_summary.get("plans_unique", []))
            merge_counter_dict(best_names[player], log_summary.get("best_name_counts", {}))
            v3_evasion_used_counts[player] += int(log_summary.get("v3_evasion_used_count", 0))
            merge_counter_dict(v3_evasion_reasons[player], log_summary.get("v3_evasion_reason_counts", {}))
            v3_evasion_worker_counts[player].extend(
                int(x) for x in log_summary.get("v3_evasion_worker_counts", []) if isinstance(x, (int, float))
            )
            v3_emp_used_counts[player] += int(log_summary.get("v3_emp_used_count", 0))
            merge_counter_dict(v3_emp_reasons[player], log_summary.get("v3_emp_reason_counts", {}))
            v3_emp_distances[player].extend(
                int(x) for x in log_summary.get("v3_emp_distances", []) if isinstance(x, (int, float))
            )

    return {
        "match_count": len(results),
        "seeds": [result.get("seed") for result in results],
        "winner_counts": dict(winner_counts),
        "rounds": stats_summary(rounds),
        "final_camp_hp": [stats_summary(final_camp_hp[0]), stats_summary(final_camp_hp[1])],
        "final_coins": [stats_summary(final_coins[0]), stats_summary(final_coins[1])],
        "hold_rate": [
            (hold_counts[0] / turn_counts[0]) if turn_counts[0] else 0.0,
            (hold_counts[1] / turn_counts[1]) if turn_counts[1] else 0.0,
        ],
        "operation_totals": [dict(operation_totals[0]), dict(operation_totals[1])],
        "build_positions_top": [build_positions[0].most_common(12), build_positions[1].most_common(12)],
        "lightning_positions_top": [lightning_positions[0].most_common(12), lightning_positions[1].most_common(12)],
        "upgrade_targets_top": [upgrade_targets[0].most_common(12), upgrade_targets[1].most_common(12)],
        "elapsed_us": [stats_summary(elapsed_us[0]), stats_summary(elapsed_us[1])],
        "plans_total": [stats_summary(plans_total[0]), stats_summary(plans_total[1])],
        "plans_unique": [stats_summary(plans_unique[0]), stats_summary(plans_unique[1])],
        "best_name_top": [best_names[0].most_common(12), best_names[1].most_common(12)],
        "v3_evasion_used_counts": v3_evasion_used_counts,
        "v3_evasion_reason_counts": [dict(v3_evasion_reasons[0]), dict(v3_evasion_reasons[1])],
        "v3_evasion_worker_counts": [stats_summary(v3_evasion_worker_counts[0]), stats_summary(v3_evasion_worker_counts[1])],
        "v3_emp_used_counts": v3_emp_used_counts,
        "v3_emp_reason_counts": [dict(v3_emp_reasons[0]), dict(v3_emp_reasons[1])],
        "v3_emp_distances": [stats_summary(v3_emp_distances[0]), stats_summary(v3_emp_distances[1])],
    }


def print_human_summary(summary: dict[str, Any]) -> None:
    print(f"matches={summary['match_count']} seeds={summary['seeds']}")
    print(f"winner_counts={summary['winner_counts']}")
    print(f"rounds={summary['rounds']}")
    for player in (0, 1):
        print(
            f"player={player} hold_rate={summary['hold_rate'][player]:.4f} "
            f"elapsed_us={summary['elapsed_us'][player]} "
            f"plans_unique={summary['plans_unique'][player]}"
        )
        print(f"player={player} operation_totals={summary['operation_totals'][player]}")
        print(f"player={player} best_name_top={summary['best_name_top'][player]}")
        if any(summary.get("v3_evasion_reason_counts", [{}, {}])):
            print(
                f"player={player} v3_evasion_used={summary['v3_evasion_used_counts'][player]} "
                f"workers={summary['v3_evasion_worker_counts'][player]} "
                f"reasons={summary['v3_evasion_reason_counts'][player]}"
            )
        if any(summary.get("v3_emp_reason_counts", [{}, {}])):
            print(
                f"player={player} v3_emp_used={summary['v3_emp_used_counts'][player]} "
                f"distances={summary['v3_emp_distances'][player]} "
                f"reasons={summary['v3_emp_reason_counts'][player]}"
            )
        print(f"player={player} build_positions_top={summary['build_positions_top'][player]}")
        print(f"player={player} lightning_positions_top={summary['lightning_positions_top'][player]}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run parallel cpp baseline self-play with replay/log summaries.")
    parser.add_argument("--seeds", default="1:8", help="Comma list or inclusive ranges, e.g. 1:16,42,99")
    parser.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 1) - 1))
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--target", default=DEFAULT_TARGET)
    parser.add_argument("--target0", default=None, help="AI target for player 0; defaults to --target")
    parser.add_argument("--target1", default=None, help="AI target for player 1; defaults to --target0")
    parser.add_argument("--debug-seeds", default="", help="Seeds that use full per-plan debug logging")
    parser.add_argument("--debug-mode", choices=("summary", "none"), default="summary")
    parser.add_argument("--game-bin", type=Path, default=DEFAULT_GAME_BIN)
    parser.add_argument("--max-rounds", type=int, default=None)
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

    target0 = args.target0 or args.target
    target1 = args.target1 or target0
    packaged_ai0_dir = output_dir / "packaged_ai_p0"
    packaged_ai1_dir = output_dir / "packaged_ai_p1"
    subprocess.run([str(PACKAGE_AI), target0, str(packaged_ai0_dir)], cwd=GAME1_ROOT, check=True)
    if target1 == target0:
        packaged_ai1_dir = packaged_ai0_dir
    else:
        subprocess.run([str(PACKAGE_AI), target1, str(packaged_ai1_dir)], cwd=GAME1_ROOT, check=True)

    jobs = max(1, min(args.jobs, len(seeds)))
    results: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []

    with ProcessPoolExecutor(max_workers=jobs) as executor:
        future_map = {}
        for seed in seeds:
            debug_mode = "plans" if seed in debug_seeds else (None if args.debug_mode == "none" else "summary")
            future = executor.submit(
                run_match,
                seed,
                packaged_ai0_dir,
                packaged_ai1_dir,
                game_bin,
                output_dir / "matches",
                debug_mode,
                args.max_rounds,
            )
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
                f"seed={seed} winner={replay_summary.get('winner')} "
                f"rounds={replay_summary.get('rounds_recorded')} "
                f"camp_hp={replay_summary.get('final_camp_hp')} "
                f"coins={replay_summary.get('final_coins')}",
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
            "target0": target0,
            "target1": target1,
            "game_bin": str(game_bin),
            "packaged_ai0_dir": str(packaged_ai0_dir),
            "packaged_ai1_dir": str(packaged_ai1_dir),
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
    if failures:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
