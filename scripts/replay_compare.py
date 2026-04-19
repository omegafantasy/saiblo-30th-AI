#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from autolab.replay_analysis import analyze_single_replay


FILENAME_RE = re.compile(r".*_p0-(?P<p0>.+)_p1-(?P<p1>.+)_seed-(?P<seed>-?\d+)\.json$")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Compare a small set of local Game1 replay json files")
    parser.add_argument("--replay", action="append", required=True, help="replay json path; may be repeated")
    parser.add_argument("--output", default="", help="optional json output path")
    parser.add_argument("--markdown-out", default="", help="optional markdown output path")
    parser.add_argument("--top-samples", type=int, default=5, help="number of per-player sample rounds to keep")
    return parser


def _parse_filename_meta(path: Path) -> Dict[str, Any]:
    match = FILENAME_RE.match(path.name)
    if not match:
        return {
            "p0_id": "",
            "p1_id": "",
            "seed": 0,
        }
    try:
        seed = int(match.group("seed"))
    except Exception:
        seed = 0
    return {
        "p0_id": match.group("p0"),
        "p1_id": match.group("p1"),
        "seed": seed,
    }


def _window_summary(window: Dict[str, Any], top_samples: int) -> Dict[str, Any]:
    if not isinstance(window, dict):
        return {
            "idle_rounds": 0,
            "build_rounds": 0,
            "other_rounds": 0,
            "max_idle_streak": 0,
            "max_idle_streak_start_round": None,
            "max_idle_streak_end_round": None,
            "samples": [],
        }
    samples = window.get("samples", [])
    if not isinstance(samples, list):
        samples = []
    return {
        "idle_rounds": int(window.get("rich_zero_tower_idle_rounds", 0) or 0),
        "build_rounds": int(window.get("rich_zero_tower_build_rounds", 0) or 0),
        "other_rounds": int(window.get("rich_zero_tower_other_rounds", 0) or 0),
        "max_idle_streak": int(window.get("max_rich_zero_tower_idle_streak", 0) or 0),
        "max_idle_streak_start_round": window.get("max_rich_zero_tower_idle_streak_start_round"),
        "max_idle_streak_end_round": window.get("max_rich_zero_tower_idle_streak_end_round"),
        "samples": samples[: max(0, int(top_samples))],
    }


def _first_sample_round(summary: Dict[str, Any]) -> int | None:
    samples = summary.get("samples", [])
    if not isinstance(samples, list) or not samples:
        return None
    sample = samples[0]
    if not isinstance(sample, dict):
        return None
    try:
        return int(sample.get("round"))
    except Exception:
        return None


def _format_sample(sample: Dict[str, Any]) -> str:
    try:
        round_index = int(sample.get("round"))
    except Exception:
        round_index = -1
    action = str(sample.get("action", "idle") or "idle")
    ops = sample.get("ops", [])
    if not isinstance(ops, list):
        ops = []
    ops_text = ",".join(str(op) for op in ops[:2] if str(op))
    if ops_text:
        return f"{round_index}:{action}[{ops_text}]"
    return f"{round_index}:{action}"


def _format_samples(summary: Dict[str, Any]) -> str:
    samples = summary.get("samples", [])
    if not isinstance(samples, list) or not samples:
        return "-"
    return ", ".join(_format_sample(sample) for sample in samples if isinstance(sample, dict))


def _format_first_round(value: Any) -> str:
    if value is None:
        return "-"
    try:
        return str(int(value))
    except Exception:
        return "-"


def _format_streak(summary: Dict[str, Any]) -> str:
    try:
        length = int(summary.get("max_idle_streak", 0) or 0)
    except Exception:
        length = 0
    if length <= 0:
        return "-"
    start = _format_first_round(summary.get("max_idle_streak_start_round"))
    end = _format_first_round(summary.get("max_idle_streak_end_round"))
    return f"{length}@{start}-{end}"


def _single_compare_row(replay_path: Path, top_samples: int) -> Dict[str, Any]:
    analysis = analyze_single_replay(replay_path)
    meta = _parse_filename_meta(replay_path)
    preturn = analysis.get("preturn_windows", {})
    p0_window = preturn.get("0", {}) if isinstance(preturn, dict) else {}
    p1_window = preturn.get("1", {}) if isinstance(preturn, dict) else {}
    p0_mid = p0_window.get("midgame_not_ahead", {}) if isinstance(p0_window, dict) else {}
    p1_mid = p1_window.get("midgame_not_ahead", {}) if isinstance(p1_window, dict) else {}

    p0_summary = _window_summary(p0_mid, top_samples)
    p1_summary = _window_summary(p1_mid, top_samples)
    max_idle = max(p0_summary["idle_rounds"], p1_summary["idle_rounds"])
    winner = analysis.get("winner")
    if winner == 0:
        winner_id = meta["p0_id"]
        loser_id = meta["p1_id"]
        winner_summary = p0_summary
        loser_summary = p1_summary
    elif winner == 1:
        winner_id = meta["p1_id"]
        loser_id = meta["p0_id"]
        winner_summary = p1_summary
        loser_summary = p0_summary
    else:
        winner_id = ""
        loser_id = ""
        winner_summary = {"idle_rounds": 0, "build_rounds": 0, "other_rounds": 0}
        loser_summary = {"idle_rounds": 0, "build_rounds": 0, "other_rounds": 0}

    return {
        **meta,
        "replay_file": str(replay_path),
        "parsed": bool(analysis.get("parsed", False)),
        "winner": winner,
        "rounds": int(analysis.get("rounds", 0) or 0),
        "final_state": analysis.get("final_state", {}),
        "player_action_counts": analysis.get("player_action_counts", {}),
        "p0_midgame_not_ahead": p0_summary,
        "p1_midgame_not_ahead": p1_summary,
        "max_midgame_not_ahead_idle_rounds": max_idle,
        "winner_id": winner_id,
        "loser_id": loser_id,
        "winner_midgame_not_ahead": winner_summary,
        "loser_midgame_not_ahead": loser_summary,
        "winner_first_midgame_not_ahead_round": _first_sample_round(winner_summary),
        "loser_first_midgame_not_ahead_round": _first_sample_round(loser_summary),
        "winner_midgame_not_ahead_idle_rounds": int(winner_summary["idle_rounds"]),
        "loser_midgame_not_ahead_idle_rounds": int(loser_summary["idle_rounds"]),
        "winner_midgame_not_ahead_build_rounds": int(winner_summary["build_rounds"]),
        "loser_midgame_not_ahead_build_rounds": int(loser_summary["build_rounds"]),
        "winner_midgame_not_ahead_max_idle_streak": int(winner_summary["max_idle_streak"]),
        "loser_midgame_not_ahead_max_idle_streak": int(loser_summary["max_idle_streak"]),
    }


def _write_markdown(path: Path, result: Dict[str, Any]) -> None:
    lines = []
    lines.append("# Replay Compare")
    lines.append("")
    lines.append(f"- replay_count: `{result.get('replay_count', 0)}`")
    lines.append(f"- top_samples: `{result.get('top_samples', 0)}`")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append("| seed | p0 | p1 | winner | loser | winner_idle | loser_idle | winner_streak | loser_streak | winner_first | loser_first | winner_build | loser_build | base_hp | replay |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for row in result.get("replays", []):
        lines.append(
            "| {seed} | {p0} | {p1} | {winner_id} | {loser_id} | {winner_idle} | {loser_idle} | {winner_streak} | {loser_streak} | {winner_first} | {loser_first} | {winner_build} | {loser_build} | {base_hp} | `{replay}` |".format(
                seed=row.get("seed", 0),
                p0=row.get("p0_id", ""),
                p1=row.get("p1_id", ""),
                winner_id=row.get("winner_id", ""),
                loser_id=row.get("loser_id", ""),
                winner_idle=row.get("winner_midgame_not_ahead_idle_rounds", 0),
                loser_idle=row.get("loser_midgame_not_ahead_idle_rounds", 0),
                winner_streak=_format_streak(row.get("winner_midgame_not_ahead", {})),
                loser_streak=_format_streak(row.get("loser_midgame_not_ahead", {})),
                winner_first=_format_first_round(row.get("winner_first_midgame_not_ahead_round")),
                loser_first=_format_first_round(row.get("loser_first_midgame_not_ahead_round")),
                winner_build=row.get("winner_midgame_not_ahead_build_rounds", 0),
                loser_build=row.get("loser_midgame_not_ahead_build_rounds", 0),
                base_hp=row.get("final_state", {}).get("base_hp", [0, 0]),
                replay=row.get("replay_file", ""),
            )
        )
    lines.append("")
    lines.append("## Sample Windows")
    lines.append("")
    for row in result.get("replays", []):
        lines.append(f"### Seed {row.get('seed', 0)}")
        lines.append("")
        lines.append(
            "- winner: `{winner}` idle=`{idle}` streak=`{streak}` build=`{build}` other=`{other}` first_round=`{first_round}` samples=`{samples}`".format(
                winner=row.get("winner_id", ""),
                idle=row.get("winner_midgame_not_ahead_idle_rounds", 0),
                streak=_format_streak(row.get("winner_midgame_not_ahead", {})),
                build=row.get("winner_midgame_not_ahead_build_rounds", 0),
                other=row.get("winner_midgame_not_ahead", {}).get("other_rounds", 0),
                first_round=_format_first_round(row.get("winner_first_midgame_not_ahead_round")),
                samples=_format_samples(row.get("winner_midgame_not_ahead", {})),
            )
        )
        lines.append(
            "- loser: `{loser}` idle=`{idle}` streak=`{streak}` build=`{build}` other=`{other}` first_round=`{first_round}` samples=`{samples}`".format(
                loser=row.get("loser_id", ""),
                idle=row.get("loser_midgame_not_ahead_idle_rounds", 0),
                streak=_format_streak(row.get("loser_midgame_not_ahead", {})),
                build=row.get("loser_midgame_not_ahead_build_rounds", 0),
                other=row.get("loser_midgame_not_ahead", {}).get("other_rounds", 0),
                first_round=_format_first_round(row.get("loser_first_midgame_not_ahead_round")),
                samples=_format_samples(row.get("loser_midgame_not_ahead", {})),
            )
        )
        lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = build_parser().parse_args()
    rows: List[Dict[str, Any]] = []
    for raw in args.replay:
        replay_path = Path(raw).resolve()
        rows.append(_single_compare_row(replay_path, args.top_samples))
    rows.sort(
        key=lambda item: (
            int(item.get("max_midgame_not_ahead_idle_rounds", 0) or 0),
            int(item.get("seed", 0) or 0),
        ),
        reverse=True,
    )

    result = {
        "replay_count": len(rows),
        "top_samples": int(args.top_samples),
        "replays": rows,
    }

    if args.output:
        output_path = Path(args.output).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.markdown_out:
        markdown_path = Path(args.markdown_out).resolve()
        _write_markdown(markdown_path, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
