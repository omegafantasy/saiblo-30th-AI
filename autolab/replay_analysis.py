from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List

from .common import RUNTIME_DIR, write_json

ACTION_LABELS: Dict[int, str] = {
    11: "build_tower",
    12: "upgrade_tower",
    13: "downgrade_tower",
    21: "lightning_storm",
    22: "emp_blaster",
    23: "deflector",
    24: "emergency_evasion",
    31: "upgrade_generation_speed",
    32: "upgrade_generated_ant",
}


@dataclass
class ReplayAnalysisConfig:
    runtime_scope: str = ""
    latest: bool = True
    matches_file: str = ""
    max_matches: int = 0
    top_matches: int = 12
    output_json: str = ""
    output_md: str = ""


def _runtime_dir(scope: str) -> Path:
    scope = str(scope or "").strip()
    return RUNTIME_DIR if not scope else (RUNTIME_DIR / "scopes" / scope)


def _load_latest(runtime_dir: Path) -> Dict[str, Any]:
    path = runtime_dir / "latest.json"
    if not path.is_file():
        raise RuntimeError(f"missing latest.json: {path}")
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise RuntimeError(f"invalid latest.json object: {path}")
    return obj


def _load_match_rows(matches_path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with matches_path.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            if isinstance(obj, dict):
                rows.append(obj)
    return rows


def _load_first_json_value(path: Path) -> Any:
    raw = path.read_text(encoding="utf-8", errors="ignore")
    decoder = json.JSONDecoder()
    obj, _ = decoder.raw_decode(raw.lstrip())
    return obj


def _count_sign_changes(series: Iterable[float]) -> int:
    prev = 0
    changes = 0
    for item in series:
        cur = 1 if item > 0 else -1 if item < 0 else 0
        if cur == 0:
            continue
        if prev and cur != prev:
            changes += 1
        prev = cur
    return changes


def _weighted_ant_value(ant: Dict[str, Any]) -> float:
    try:
        level = int(ant.get("level", 0))
        hp = int(ant.get("hp", 0))
    except Exception:
        return 0.0
    base = (1.0, 1.8, 2.8)[max(0, min(level, 2))]
    return base + hp * 0.03


def _op_type(op: Any) -> int:
    if isinstance(op, dict):
        try:
            return int(op.get("type", -1))
        except Exception:
            return -1
    if isinstance(op, list) and op:
        try:
            return int(op[0])
        except Exception:
            return -1
    return -1


def _label_action(op_type: int) -> str:
    return ACTION_LABELS.get(op_type, f"op_{op_type}")


def analyze_single_replay(replay_path: Path) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "replay_file": str(replay_path),
        "parsed": False,
    }
    if not replay_path.is_file():
        out["error"] = "missing replay file"
        return out

    try:
        payload = _load_first_json_value(replay_path)
    except Exception as exc:
        out["error"] = f"json parse failed: {exc}"
        return out
    if not isinstance(payload, list):
        out["error"] = f"unsupported replay root type: {type(payload).__name__}"
        return out

    base_hp_series = {0: [], 1: []}
    coins_series = {0: [], 1: []}
    tower_series = {0: [], 1: []}
    ant_series = {0: [], 1: []}
    ant_mass_series = {0: [], 1: []}
    action_counts = {0: defaultdict(int), 1: defaultdict(int)}
    behavior_final = {0: defaultdict(int), 1: defaultdict(int)}
    final_tower_types = {0: defaultdict(int), 1: defaultdict(int)}
    anthp_levels = [0, 0]
    speed_levels = [0, 0]
    winner = None

    for frame in payload:
        if not isinstance(frame, dict):
            continue
        for player_key, player in (("op0", 0), ("op1", 1)):
            ops = frame.get(player_key, [])
            if not isinstance(ops, list):
                continue
            for op in ops:
                action_counts[player][_label_action(_op_type(op))] += 1

        state = frame.get("round_state", {})
        if not isinstance(state, dict):
            continue
        camps = state.get("camps", [0, 0])
        coins = state.get("coins", [0, 0])
        anthp_levels = list(state.get("anthpLv", anthp_levels))[:2]
        speed_levels = list(state.get("speedLv", speed_levels))[:2]
        try:
            winner_value = int(state.get("winner", -1))
            winner = None if winner_value < 0 else winner_value
        except Exception:
            pass

        towers = state.get("towers", [])
        ants = state.get("ants", [])
        tower_counts = [0, 0]
        ant_counts = [0, 0]
        ant_mass = [0.0, 0.0]
        local_behavior = {0: defaultdict(int), 1: defaultdict(int)}
        local_tower_types = {0: defaultdict(int), 1: defaultdict(int)}

        if isinstance(towers, list):
            for tower in towers:
                if not isinstance(tower, dict):
                    continue
                try:
                    player = int(tower.get("player", -1))
                except Exception:
                    continue
                if player not in (0, 1):
                    continue
                tower_counts[player] += 1
                local_tower_types[player][str(tower.get("type", -1))] += 1

        if isinstance(ants, list):
            for ant in ants:
                if not isinstance(ant, dict):
                    continue
                try:
                    player = int(ant.get("player", -1))
                except Exception:
                    continue
                if player not in (0, 1):
                    continue
                ant_counts[player] += 1
                ant_mass[player] += _weighted_ant_value(ant)
                local_behavior[player][str(ant.get("behavior", -1))] += 1

        for player in (0, 1):
            base_hp_series[player].append(int(camps[player]) if len(camps) > player else 0)
            coins_series[player].append(int(coins[player]) if len(coins) > player else 0)
            tower_series[player].append(tower_counts[player])
            ant_series[player].append(ant_counts[player])
            ant_mass_series[player].append(round(ant_mass[player], 3))
            behavior_final[player] = local_behavior[player]
            final_tower_types[player] = local_tower_types[player]

    rounds = len(payload)
    base_hp_gap = [a - b for a, b in zip(base_hp_series[0], base_hp_series[1])]
    ant_mass_gap = [a - b for a, b in zip(ant_mass_series[0], ant_mass_series[1])]
    tower_gap = [a - b for a, b in zip(tower_series[0], tower_series[1])]
    coin_gap = [a - b for a, b in zip(coins_series[0], coins_series[1])]

    out.update(
        {
            "parsed": True,
            "format": "antgame2_json_array",
            "rounds": rounds,
            "winner": winner,
            "player_action_counts": {
                str(player): dict(sorted(counts.items())) for player, counts in action_counts.items()
            },
            "final_state": {
                "base_hp": [base_hp_series[0][-1] if base_hp_series[0] else 0, base_hp_series[1][-1] if base_hp_series[1] else 0],
                "coins": [coins_series[0][-1] if coins_series[0] else 0, coins_series[1][-1] if coins_series[1] else 0],
                "tower_counts": [tower_series[0][-1] if tower_series[0] else 0, tower_series[1][-1] if tower_series[1] else 0],
                "ant_counts": [ant_series[0][-1] if ant_series[0] else 0, ant_series[1][-1] if ant_series[1] else 0],
                "anthp_levels": anthp_levels,
                "speed_levels": speed_levels,
                "tower_types": {str(player): dict(sorted(types.items())) for player, types in final_tower_types.items()},
                "behavior_counts": {str(player): dict(sorted(types.items())) for player, types in behavior_final.items()},
            },
            "metrics": {
                "max_base_hp_gap": max((abs(x) for x in base_hp_gap), default=0),
                "max_ant_mass_gap": max((abs(x) for x in ant_mass_gap), default=0.0),
                "max_tower_gap": max((abs(x) for x in tower_gap), default=0),
                "max_coin_gap": max((abs(x) for x in coin_gap), default=0),
                "base_hp_lead_changes": _count_sign_changes(base_hp_gap),
                "ant_mass_lead_changes": _count_sign_changes(ant_mass_gap),
                "tower_lead_changes": _count_sign_changes(tower_gap),
                "coin_lead_changes": _count_sign_changes(coin_gap),
            },
        }
    )
    return out


def _row_summary(row: Dict[str, Any], replay: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "a": str(row.get("a", "")),
        "b": str(row.get("b", "")),
        "seed": int(row.get("seed", 0) or 0),
        "a_seat": int(row.get("a_seat", 0) or 0),
        "score_a": float(row.get("score_a", 0.5) or 0.5),
        "winner_seat": replay.get("winner"),
        "replay_file": replay.get("replay_file", ""),
        "rounds": int(replay.get("rounds", 0) or 0),
        "base_hp": replay.get("final_state", {}).get("base_hp", [0, 0]),
        "coins": replay.get("final_state", {}).get("coins", [0, 0]),
        "tower_counts": replay.get("final_state", {}).get("tower_counts", [0, 0]),
        "ant_counts": replay.get("final_state", {}).get("ant_counts", [0, 0]),
        "metrics": replay.get("metrics", {}),
        "player_action_counts": replay.get("player_action_counts", {}),
    }


def _pick_top(matches: List[Dict[str, Any]], key: str, limit: int) -> List[Dict[str, Any]]:
    def value(item: Dict[str, Any]) -> float:
        cur: Any = item
        for part in key.split("."):
            if not isinstance(cur, dict):
                return 0.0
            cur = cur.get(part)
        try:
            return float(cur)
        except Exception:
            return 0.0

    return sorted(matches, key=value, reverse=True)[:limit]


def _write_markdown(path: Path, result: Dict[str, Any]) -> None:
    lines: List[str] = []
    lines.append("# Game1 Replay Analysis")
    lines.append("")
    lines.append(f"- generated_at: `{result['generated_at']}`")
    lines.append(f"- scope: `{result['runtime_scope'] or 'production'}`")
    lines.append(f"- tag: `{result['tag']}`")
    lines.append(f"- matches_analyzed: `{result['matches_analyzed']}`")
    lines.append("")
    lines.append("## Overview")
    lines.append("")
    overview = result.get("overview", {})
    lines.append(f"- total_rounds: `{overview.get('total_rounds', 0)}`")
    lines.append(f"- average_rounds: `{overview.get('average_rounds', 0):.1f}`")
    lines.append(f"- player0_wins: `{overview.get('player0_wins', 0)}`")
    lines.append(f"- player1_wins: `{overview.get('player1_wins', 0)}`")
    lines.append(f"- draws_or_unknown: `{overview.get('draws_or_unknown', 0)}`")
    lines.append("")

    for title, key in (
        ("Longest Matches", "longest"),
        ("Largest Base HP Swings", "largest_base_hp_gap"),
        ("Largest Ant Mass Swings", "largest_ant_mass_gap"),
    ):
        lines.append(f"## {title}")
        lines.append("")
        lines.append("| a | b | seed | rounds | winner | base_hp | towers | ants | replay |")
        lines.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- |")
        for item in result.get("notable", {}).get(key, []):
            lines.append(
                "| {a} | {b} | {seed} | {rounds} | {winner} | {base_hp} | {towers} | {ants} | `{replay}` |".format(
                    a=item.get("a", ""),
                    b=item.get("b", ""),
                    seed=item.get("seed", 0),
                    rounds=item.get("rounds", 0),
                    winner=item.get("winner_seat", "?"),
                    base_hp=item.get("base_hp", [0, 0]),
                    towers=item.get("tower_counts", [0, 0]),
                    ants=item.get("ant_counts", [0, 0]),
                    replay=item.get("replay_file", ""),
                )
            )
        lines.append("")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_replay_analysis(cfg: ReplayAnalysisConfig) -> Dict[str, Any]:
    runtime_dir = _runtime_dir(cfg.runtime_scope)
    if cfg.matches_file:
        matches_path = Path(cfg.matches_file).resolve()
        latest_obj = {}
        tag = matches_path.name.replace("_matches.jsonl", "")
    else:
        latest_obj = _load_latest(runtime_dir)
        matches_path = Path(str(latest_obj.get("paths", {}).get("matches", ""))).resolve()
        if not matches_path.is_file():
            raise RuntimeError(f"latest.json points to missing matches file: {matches_path}")
        tag = str(latest_obj.get("tag", "")).strip() or matches_path.name.replace("_matches.jsonl", "")

    rows = _load_match_rows(matches_path)
    if cfg.max_matches > 0:
        rows = rows[-int(cfg.max_matches):]

    analyzed: List[Dict[str, Any]] = []
    total_rounds = 0
    win_counts = {0: 0, 1: 0, -1: 0}
    for row in rows:
        replay_file = str(row.get("replay_file", "") or "")
        if not replay_file:
            continue
        replay = analyze_single_replay(Path(replay_file))
        if not replay.get("parsed", False):
            continue
        summary = _row_summary(row, replay)
        analyzed.append(summary)
        total_rounds += int(summary.get("rounds", 0) or 0)
        winner = summary.get("winner_seat")
        if winner in (0, 1):
            win_counts[int(winner)] += 1
        else:
            win_counts[-1] += 1

    top = max(1, int(cfg.top_matches))
    result = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "runtime_scope": str(cfg.runtime_scope or ""),
        "tag": tag,
        "matches_file": str(matches_path),
        "matches_analyzed": len(analyzed),
        "overview": {
            "total_rounds": total_rounds,
            "average_rounds": (total_rounds / len(analyzed)) if analyzed else 0.0,
            "player0_wins": win_counts[0],
            "player1_wins": win_counts[1],
            "draws_or_unknown": win_counts[-1],
        },
        "notable": {
            "longest": _pick_top(analyzed, "rounds", top),
            "largest_base_hp_gap": _pick_top(analyzed, "metrics.max_base_hp_gap", top),
            "largest_ant_mass_gap": _pick_top(analyzed, "metrics.max_ant_mass_gap", top),
        },
        "matches": analyzed,
    }

    report_dir = runtime_dir / "replay_analysis"
    report_dir.mkdir(parents=True, exist_ok=True)
    json_out = Path(cfg.output_json).resolve() if cfg.output_json else (report_dir / f"{tag}_replay_analysis.json")
    md_out = Path(cfg.output_md).resolve() if cfg.output_md else (report_dir / f"{tag}_replay_analysis.md")
    latest_json_out = report_dir / "latest.json"
    latest_md_out = report_dir / "latest.md"

    write_json(json_out, result)
    _write_markdown(md_out, result)
    write_json(latest_json_out, result)
    _write_markdown(latest_md_out, result)

    result["output_json"] = str(json_out)
    result["output_md"] = str(md_out)
    result["output_latest_json"] = str(latest_json_out)
    result["output_latest_md"] = str(latest_md_out)
    return result
