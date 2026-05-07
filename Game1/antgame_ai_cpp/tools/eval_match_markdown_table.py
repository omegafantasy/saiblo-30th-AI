#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path
from typing import Any


LURE_SELL_BASE_RE = re.compile(r"^lure_(?:forced_)?sell_.*\+base_")
C23_RE = re.compile(r"(?:^|[^A-Za-z0-9])C[23](?:$|[^A-Za-z0-9])")


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


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_decisions(log_path: Path) -> list[dict[str, Any]]:
    if not log_path.is_file():
        return []
    out: list[dict[str, Any]] = []
    for raw in log_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line.startswith("{") or not line.endswith("}"):
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if item.get("kind") == "decision":
            out.append(item)
    return out


def target_player(config: dict[str, Any], target: str) -> int | None:
    if config.get("target0") == target:
        return 0
    if config.get("target1") == target:
        return 1
    return None


def op_count(ops: dict[str, Any], name: str) -> int:
    return int(ops.get(name, 0))


def collect_rows(eval_dirs: list[Path], target: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for eval_dir in eval_dirs:
        summary_path = eval_dir / "summary.json"
        if not summary_path.is_file():
            raise FileNotFoundError(f"missing {summary_path}")
        summary = load_json(summary_path)
        player = target_player(summary.get("config", {}), target)
        if player is None:
            continue
        other = 1 - player
        opponent = summary.get("config", {}).get(f"target{other}", f"p{other}")

        for match_path in sorted((eval_dir / "matches").glob("seed_*/match_summary.json")):
            match = load_json(match_path)
            replay_summary = match.get("replay_summary", {})
            seed = int(match.get("seed", match_path.parent.name.removeprefix("seed_")))
            hp = replay_summary.get("final_camp_hp", [0, 0])
            coins = replay_summary.get("final_coins", [0, 0])
            winner = replay_summary.get("winner")
            if winner == player:
                result = "W"
            elif winner == other:
                result = "L"
            else:
                result = "D"

            op_counts = replay_summary.get("operation_counts", [{}, {}])
            target_ops = op_counts[player] if player < len(op_counts) else {}
            hold_counts = replay_summary.get("hold_counts", [0, 0])
            hold = int(hold_counts[player]) if player < len(hold_counts) else 0

            decisions = parse_decisions(match_path.parent / f"ai{player}.stderr.log")
            elapsed_s = [float(item.get("elapsed_us", 0)) / 1_000_000.0 for item in decisions]
            plans_unique = [float(item.get("plans_unique", 0)) for item in decisions]
            best_names = [str(item.get("best_name", "")) for item in decisions]

            rows.append(
                {
                    "eval_dir": str(eval_dir),
                    "seat": f"p{player}",
                    "opponent": opponent,
                    "seed": seed,
                    "result": result,
                    "rounds": int(replay_summary.get("rounds_recorded", 0)),
                    "hp_target": int(hp[player]),
                    "hp_other": int(hp[other]),
                    "hp_diff": int(hp[player]) - int(hp[other]),
                    "coin_target": int(coins[player]),
                    "coin_other": int(coins[other]),
                    "coin_diff": int(coins[player]) - int(coins[other]),
                    "hold": hold,
                    "build": op_count(target_ops, "build"),
                    "upgrade": op_count(target_ops, "upgrade"),
                    "downgrade": op_count(target_ops, "downgrade"),
                    "lightning": op_count(target_ops, "lightning"),
                    "emp": op_count(target_ops, "emp"),
                    "evasion": op_count(target_ops, "evasion"),
                    "ant_up": op_count(target_ops, "upgrade_ant"),
                    "lure_sell_base": sum(1 for name in best_names if LURE_SELL_BASE_RE.search(name)),
                    "double_build": sum(1 for name in best_names if name.startswith("base_double_build_")),
                    "c2c3": sum(1 for name in best_names if C23_RE.search(name)),
                    "avg_s": mean(elapsed_s),
                    "p95_s": percentile(elapsed_s, 0.95),
                    "max_s": max(elapsed_s) if elapsed_s else 0.0,
                    "plans_avg": mean(plans_unique),
                    "error": str(replay_summary.get("error", "")),
                }
            )
    rows.sort(key=lambda item: (item["seat"], item["seed"], item["eval_dir"]))
    return rows


def fmt_float(value: float, digits: int = 2) -> str:
    return f"{value:.{digits}f}"


def markdown_table(rows: list[dict[str, Any]], target: str) -> str:
    headers = [
        "seat",
        "seed",
        "res",
        "rounds",
        "HP",
        "dHP",
        "coins",
        "dCoin",
        "Lgt",
        "EMP",
        "Eva",
        "AntUp",
        "avg_s",
        "p95_s",
        "max_s",
        "plans",
    ]
    lines = [
        f"# Eval match table for `{target}`",
        "",
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        values = [
            row["seat"],
            str(row["seed"]),
            row["result"],
            str(row["rounds"]),
            f"{row['hp_target']}-{row['hp_other']}",
            f"{row['hp_diff']:+d}",
            f"{row['coin_target']}-{row['coin_other']}",
            f"{row['coin_diff']:+d}",
            str(row["lightning"]),
            str(row["emp"]),
            str(row["evasion"]),
            str(row["ant_up"]),
            fmt_float(row["avg_s"]),
            fmt_float(row["p95_s"]),
            fmt_float(row["max_s"]),
            fmt_float(row["plans_avg"], 1),
        ]
        lines.append("| " + " | ".join(values) + " |")

    wins = sum(1 for row in rows if row["result"] == "W")
    losses = sum(1 for row in rows if row["result"] == "L")
    draws = sum(1 for row in rows if row["result"] == "D")
    hp_diff = sum(int(row["hp_diff"]) for row in rows)
    coin_diff = sum(int(row["coin_diff"]) for row in rows)
    avg_s = mean([float(row["avg_s"]) for row in rows])
    p95_s = mean([float(row["p95_s"]) for row in rows])
    max_s = max([float(row["max_s"]) for row in rows], default=0.0)
    lines.extend(
        [
            "",
            "## Aggregate",
            "",
            f"- games: {len(rows)}",
            f"- W-L-D: {wins}-{losses}-{draws}",
            f"- total dHP: {hp_diff:+d}, avg dHP: {hp_diff / len(rows):+.3f}" if rows else "- total dHP: +0",
            f"- total dCoin: {coin_diff:+d}, avg dCoin: {coin_diff / len(rows):+.3f}" if rows else "- total dCoin: +0",
            f"- Lgt/EMP/Eva/AntUp totals: {sum(int(row['lightning']) for row in rows)}/"
            f"{sum(int(row['emp']) for row in rows)}/{sum(int(row['evasion']) for row in rows)}/"
            f"{sum(int(row['ant_up']) for row in rows)}",
            f"- avg per-match decision time avg_s: {avg_s:.3f}, mean p95_s: {p95_s:.3f}, max_s: {max_s:.3f}",
        ]
    )
    errors = [row for row in rows if row["error"]]
    if errors:
        lines.extend(["", "## Errors", ""])
        for row in errors:
            lines.append(f"- {row['seat']} seed {row['seed']}: {row['error']}")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Emit a Markdown per-match table for eval_cpp_selfplay results.")
    parser.add_argument("eval_dirs", nargs="+", type=Path)
    parser.add_argument("--target", default="cpp_lure_v4", help="target AI name to report from its own perspective")
    parser.add_argument("--output", type=Path, help="write Markdown to this path instead of stdout")
    args = parser.parse_args()

    rows = collect_rows(args.eval_dirs, args.target)
    if not rows:
        raise SystemExit(f"no matches found for target {args.target!r}")
    text = markdown_table(rows, args.target)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
