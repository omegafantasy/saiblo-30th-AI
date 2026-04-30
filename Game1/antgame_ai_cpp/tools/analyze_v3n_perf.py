#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
from pathlib import Path
from typing import Any


def parse_text(text: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or not line.startswith("{"):
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if item.get("kind") == "v3n_perf":
            rows.append(item)
    return rows


def decode_possible_base64(text: str) -> str:
    stripped = "".join(text.split())
    if not stripped:
        return text
    try:
        return base64.b64decode(stripped, validate=False).decode("utf-8", errors="replace")
    except Exception:
        return text


def parse_log(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    return parse_text(path.read_text(encoding="utf-8", errors="replace"))


def parse_match_detail(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    try:
        detail = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except json.JSONDecodeError:
        return []
    info = detail.get("info", [])
    if not isinstance(info, list):
        return []

    rows: list[dict[str, Any]] = []
    for player_index, player in enumerate(info):
        if not isinstance(player, dict):
            continue
        stderr = player.get("stderr")
        if not isinstance(stderr, str) or not stderr:
            continue
        parsed = parse_text(stderr)
        if not parsed:
            parsed = parse_text(decode_possible_base64(stderr))
        for row in parsed:
            row.setdefault("match_id", detail.get("id"))
            row.setdefault("info_index", player_index)
            rows.append(row)
    return rows


def summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    lure_simulations = sum(int(row.get("lure_simulations", 0)) for row in rows)
    lightning_simulations = sum(int(row.get("lightning_simulations", 0)) for row in rows)
    lure_elapsed_ns = sum(int(row.get("lure_elapsed_ns", 0)) for row in rows)
    lightning_elapsed_ns = sum(int(row.get("lightning_elapsed_ns", 0)) for row in rows)
    total_elapsed_ns = lure_elapsed_ns + lightning_elapsed_ns
    rounds = len(rows)
    return {
        "round_records": rounds,
        "lure_simulations": lure_simulations,
        "lightning_simulations": lightning_simulations,
        "total_simulations": lure_simulations + lightning_simulations,
        "lure_elapsed_ns": lure_elapsed_ns,
        "lightning_elapsed_ns": lightning_elapsed_ns,
        "total_elapsed_ns": total_elapsed_ns,
        "lure_avg_elapsed_ns": lure_elapsed_ns / rounds if rounds else 0.0,
        "lightning_avg_elapsed_ns": lightning_elapsed_ns / rounds if rounds else 0.0,
        "total_avg_elapsed_ns": total_elapsed_ns / rounds if rounds else 0.0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Summarize cpp_lure_v3n perf logs from eval_cpp_selfplay output.")
    parser.add_argument("eval_dir", type=Path)
    parser.add_argument("--json", action="store_true", help="emit JSON only")
    args = parser.parse_args()

    logs = sorted(args.eval_dir.glob("matches/seed_*/ai[01].stderr.log"))
    match_details = sorted(args.eval_dir.glob("match_*.json"))
    if not logs and not match_details:
        logs = sorted(args.eval_dir.rglob("*.log"))
        match_details = sorted(args.eval_dir.rglob("match_*.json"))
    rows: list[dict[str, Any]] = []
    by_player: dict[int, list[dict[str, Any]]] = {0: [], 1: []}
    for log in logs:
        parsed = parse_log(log)
        rows.extend(parsed)
        for row in parsed:
            player = int(row.get("player", -1))
            if player in by_player:
                by_player[player].append(row)
    for detail in match_details:
        parsed = parse_match_detail(detail)
        rows.extend(parsed)
        for row in parsed:
            player = int(row.get("player", -1))
            if player in by_player:
                by_player[player].append(row)

    summary = summarize_rows(rows)
    summary["players"] = {str(player): summarize_rows(player_rows) for player, player_rows in by_player.items()}
    summary["log_files"] = len(logs)
    summary["match_detail_files"] = len(match_details)
    summary["eval_dir"] = str(args.eval_dir)

    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0

    print(f"eval_dir={summary['eval_dir']}")
    print(
        f"log_files={summary['log_files']} "
        f"match_detail_files={summary['match_detail_files']} "
        f"round_records={summary['round_records']}"
    )
    print(
        "combined "
        f"simulations={summary['total_simulations']} "
        f"lure={summary['lure_simulations']} lightning={summary['lightning_simulations']} "
        f"elapsed_s={summary['total_elapsed_ns'] / 1_000_000_000:.6f} "
        f"avg_ms_per_record={summary['total_avg_elapsed_ns'] / 1_000_000:.6f}"
    )
    for player in (0, 1):
        item = summary["players"][str(player)]
        print(
            f"player={player} records={item['round_records']} "
            f"elapsed_s={item['total_elapsed_ns'] / 1_000_000_000:.6f} "
            f"avg_ms_per_record={item['total_avg_elapsed_ns'] / 1_000_000:.6f} "
            f"lure_ms={item['lure_avg_elapsed_ns'] / 1_000_000:.6f} "
            f"lightning_ms={item['lightning_avg_elapsed_ns'] / 1_000_000:.6f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
