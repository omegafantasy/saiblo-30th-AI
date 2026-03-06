from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from .common import RUNTIME_DIR, write_json

ACTION_LABELS: Dict[int, str] = {
    1: "army_move",
    2: "general_move",
    3: "general_upgrade",
    4: "general_skill",
    5: "tech_upgrade",
    6: "super_weapon",
    7: "call_general",
    8: "end_turn",
    255: "surrender",
}

REPLAY_NAME_RE = re.compile(
    r"_p0-(?P<p0>.+?)_p1-(?P<p1>.+?)_seed-(?P<seed>[^_]+)_rounds-(?P<rounds>\d+)\.jsonl(?:\.gz)?$"
)


@dataclass
class ReplayAnalysisConfig:
    runtime_scope: str = ""
    latest: bool = True
    matches_file: str = ""
    max_matches: int = 0
    top_matches: int = 12
    output_json: str = ""
    output_md: str = ""


def _cmd_label(cmd: int) -> str:
    if cmd in ACTION_LABELS:
        return ACTION_LABELS[cmd]
    return f"cmd_{cmd}"


def _to_int(v: Any, default: int = 0) -> int:
    try:
        return int(v)
    except Exception:
        return default


def _safe_json_loads(line: str) -> Dict[str, Any] | None:
    try:
        obj = json.loads(line)
    except Exception:
        return None
    if isinstance(obj, dict):
        return obj
    return None


def _runtime_dir(scope: str) -> Path:
    s = str(scope or "").strip()
    if not s:
        return RUNTIME_DIR
    return RUNTIME_DIR / "scopes" / s


def _load_latest(runtime_dir: Path) -> Dict[str, Any]:
    p = runtime_dir / "latest.json"
    if not p.is_file():
        raise RuntimeError(f"missing latest.json: {p}")
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        raise RuntimeError(f"invalid latest.json: {p}: {e}") from e
    if not isinstance(data, dict):
        raise RuntimeError(f"invalid latest.json object: {p}")
    return data


def _load_match_rows(matches_path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with matches_path.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = _safe_json_loads(line)
            if obj is not None:
                rows.append(obj)
    return rows


def _seat_mapping(row: Dict[str, Any]) -> Tuple[Dict[int, str], Dict[int, float], str]:
    a = str(row.get("a", ""))
    b = str(row.get("b", ""))
    a_seat = _to_int(row.get("a_seat", 0), 0)
    score_a = float(row.get("score_a", 0.5))
    if score_a < 0.0:
        score_a = 0.0
    elif score_a > 1.0:
        score_a = 1.0

    seat_to_id: Dict[int, str]
    score_by_seat: Dict[int, float]
    if a_seat == 0:
        seat_to_id = {0: a, 1: b}
        score_by_seat = {0: score_a, 1: 1.0 - score_a}
    else:
        seat_to_id = {0: b, 1: a}
        score_by_seat = {0: 1.0 - score_a, 1: score_a}

    winner_id = ""
    if score_a > 0.5:
        winner_id = a
    elif score_a < 0.5:
        winner_id = b

    return seat_to_id, score_by_seat, winner_id


def _parse_replay_name(replay_file: str) -> Dict[str, Any]:
    name = Path(replay_file).name
    m = REPLAY_NAME_RE.search(name)
    if not m:
        return {"name": name}
    return {
        "name": name,
        "p0": m.group("p0"),
        "p1": m.group("p1"),
        "seed": m.group("seed"),
        "rounds_limit": _to_int(m.group("rounds"), 0),
    }


def _update_totals_for_cell(
    totals_territory: Dict[int, int],
    totals_army: Dict[int, int],
    old_owner: int,
    old_army: int,
    new_owner: int,
    new_army: int,
) -> None:
    if old_owner in (0, 1):
        totals_army[old_owner] -= old_army
    if new_owner in (0, 1):
        totals_army[new_owner] += new_army
    if old_owner != new_owner:
        if old_owner in (0, 1):
            totals_territory[old_owner] -= 1
        if new_owner in (0, 1):
            totals_territory[new_owner] += 1


def _sign(x: float) -> int:
    if x > 0:
        return 1
    if x < 0:
        return -1
    return 0


def _count_sign_changes(series: Iterable[float]) -> int:
    prev = 0
    changes = 0
    for x in series:
        s = _sign(float(x))
        if s == 0:
            continue
        if prev != 0 and s != prev:
            changes += 1
        prev = s
    return changes


def analyze_single_replay(replay_path: Path) -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "replay_file": str(replay_path),
        "replay_meta": _parse_replay_name(str(replay_path)),
        "parsed": False,
        "line_count": 0,
        "parse_errors": 0,
    }
    if not replay_path.is_file():
        out["error"] = "missing replay file"
        return out

    board: Dict[Tuple[int, int], Tuple[int, int]] = {}
    totals_territory: Dict[int, int] = {0: 0, 1: 0}
    totals_army: Dict[int, int] = {0: 0, 1: 0}

    player_action_counts: Dict[int, Dict[int, int]] = {
        0: defaultdict(int),
        1: defaultdict(int),
    }
    player_non_end_actions: Dict[int, int] = {0: 0, 1: 0}
    player_no_effect_actions: Dict[int, int] = {0: 0, 1: 0}
    player_changed_cells: Dict[int, int] = {0: 0, 1: 0}
    player_rounds: Dict[int, set[int]] = {0: set(), 1: set()}

    cell_events: Dict[int, Dict[str, int]] = {
        0: {"gain": 0, "loss": 0, "enemy_capture": 0, "neutral_capture": 0},
        1: {"gain": 0, "loss": 0, "enemy_capture": 0, "neutral_capture": 0},
    }

    general_prev: Dict[int, Dict[str, int]] = {}
    general_events: List[Dict[str, Any]] = []
    general_capture_count: Dict[int, int] = {0: 0, 1: 0}
    general_lost_count: Dict[int, int] = {0: 0, 1: 0}
    general_death_count: Dict[int, int] = {0: 0, 1: 0}

    round_snapshots: Dict[int, Dict[str, Any]] = {}

    lines = replay_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    out["line_count"] = len(lines)

    for raw in lines:
        frame = _safe_json_loads(raw)
        if frame is None:
            out["parse_errors"] += 1
            continue

        rnd = _to_int(frame.get("Round", -1), -1)
        player = _to_int(frame.get("Player", -1), -1)

        action = frame.get("Action", [])
        cmd = -1
        if isinstance(action, list) and action:
            cmd = _to_int(action[0], -1)

        cells = frame.get("Cells", [])
        if not isinstance(cells, list):
            cells = []

        if player in (0, 1):
            player_action_counts[player][cmd] += 1
            if rnd >= 0:
                player_rounds[player].add(rnd)
            if cmd not in (8, 255):
                player_non_end_actions[player] += 1
                if len(cells) == 0:
                    player_no_effect_actions[player] += 1
            player_changed_cells[player] += len(cells)

        for c in cells:
            if not isinstance(c, list) or len(c) < 3:
                continue
            pos = c[0]
            if not isinstance(pos, list) or len(pos) < 2:
                continue
            x = _to_int(pos[0], -1)
            y = _to_int(pos[1], -1)
            if x < 0 or y < 0:
                continue

            new_owner = _to_int(c[1], -1)
            new_army = _to_int(c[2], 0)
            key = (x, y)
            old_owner, old_army = board.get(key, (-1, 0))

            _update_totals_for_cell(
                totals_territory=totals_territory,
                totals_army=totals_army,
                old_owner=old_owner,
                old_army=old_army,
                new_owner=new_owner,
                new_army=new_army,
            )

            board[key] = (new_owner, new_army)

            if player in (0, 1):
                if new_owner == player and old_owner != player:
                    cell_events[player]["gain"] += 1
                    if old_owner == (1 - player):
                        cell_events[player]["enemy_capture"] += 1
                    elif old_owner == -1:
                        cell_events[player]["neutral_capture"] += 1
                if old_owner == player and new_owner != player:
                    cell_events[player]["loss"] += 1

        generals = frame.get("Generals", [])
        if isinstance(generals, list):
            for g in generals:
                if not isinstance(g, dict):
                    continue
                gid = _to_int(g.get("Id", -1), -1)
                if gid < 0:
                    continue
                owner = _to_int(g.get("Player", -1), -1)
                alive = _to_int(g.get("Alive", 0), 0)
                gtype = _to_int(g.get("Type", -1), -1)
                prev = general_prev.get(gid)
                if prev is not None:
                    prev_owner = _to_int(prev.get("owner", -1), -1)
                    prev_alive = _to_int(prev.get("alive", 0), 0)
                    if prev_owner != owner and owner in (0, 1):
                        general_capture_count[owner] += 1
                        if prev_owner in (0, 1):
                            general_lost_count[prev_owner] += 1
                        if len(general_events) < 256:
                            general_events.append(
                                {
                                    "round": rnd,
                                    "general_id": gid,
                                    "type": gtype,
                                    "from": prev_owner,
                                    "to": owner,
                                    "event": "ownership_change",
                                }
                            )
                    if prev_alive == 1 and alive == 0 and prev_owner in (0, 1):
                        general_death_count[prev_owner] += 1
                        if len(general_events) < 256:
                            general_events.append(
                                {
                                    "round": rnd,
                                    "general_id": gid,
                                    "type": gtype,
                                    "owner": prev_owner,
                                    "event": "death",
                                }
                            )
                general_prev[gid] = {"owner": owner, "alive": alive, "type": gtype}

        if rnd >= 0:
            coins = frame.get("Coins", [0, 0])
            if not isinstance(coins, list) or len(coins) < 2:
                coins = [0, 0]
            main_alive = {0: 0, 1: 0}
            if isinstance(generals, list):
                for g in generals:
                    if not isinstance(g, dict):
                        continue
                    if _to_int(g.get("Type", -1), -1) != 1:
                        continue
                    own = _to_int(g.get("Player", -1), -1)
                    alv = _to_int(g.get("Alive", 0), 0)
                    if own in (0, 1) and alv == 1:
                        main_alive[own] = 1
            round_snapshots[rnd] = {
                "round": rnd,
                "territory_0": int(totals_territory[0]),
                "territory_1": int(totals_territory[1]),
                "army_0": int(totals_army[0]),
                "army_1": int(totals_army[1]),
                "coins_0": _to_int(coins[0], 0),
                "coins_1": _to_int(coins[1], 0),
                "main_alive_0": int(main_alive[0]),
                "main_alive_1": int(main_alive[1]),
            }

    if not round_snapshots:
        out["error"] = "no valid replay frames"
        return out

    rounds = sorted(round_snapshots.keys())
    terr_leads: List[int] = []
    army_leads: List[int] = []
    turning_points: List[Dict[str, Any]] = []

    prev_round = None
    prev_terr = 0
    prev_army = 0
    for r in rounds:
        snap = round_snapshots[r]
        terr_lead = int(snap["territory_0"]) - int(snap["territory_1"])
        army_lead = int(snap["army_0"]) - int(snap["army_1"])
        terr_leads.append(terr_lead)
        army_leads.append(army_lead)

        if prev_round is not None:
            dterr = terr_lead - prev_terr
            darmy = army_lead - prev_army
            score = abs(dterr) * 4 + abs(darmy)
            if score > 0:
                turning_points.append(
                    {
                        "round": r,
                        "from_round": prev_round,
                        "delta_territory_lead_p0": dterr,
                        "delta_army_lead_p0": darmy,
                        "impact_score": score,
                    }
                )
        prev_round = r
        prev_terr = terr_lead
        prev_army = army_lead

    turning_points.sort(key=lambda x: int(x.get("impact_score", 0)), reverse=True)
    turning_points = turning_points[:8]

    final_round = rounds[-1]
    final_snap = round_snapshots[final_round]

    player_out: Dict[str, Dict[str, Any]] = {}
    for p in (0, 1):
        non_end = int(player_non_end_actions[p])
        no_effect = int(player_no_effect_actions[p])
        cmd_counts = player_action_counts[p]
        labeled_counts = {k: int(v) for k, v in sorted(cmd_counts.items(), key=lambda kv: kv[0])}
        labeled_name_counts = { _cmd_label(int(k)): int(v) for k, v in labeled_counts.items() }
        player_out[str(p)] = {
            "actions_total": int(sum(cmd_counts.values())),
            "actions_non_end": non_end,
            "no_effect_actions": no_effect,
            "no_effect_rate": (float(no_effect) / float(non_end)) if non_end > 0 else 0.0,
            "changed_cells": int(player_changed_cells[p]),
            "active_rounds": int(len(player_rounds[p])),
            "action_counts": labeled_counts,
            "action_counts_named": labeled_name_counts,
            "cell_events": {
                "gain": int(cell_events[p]["gain"]),
                "loss": int(cell_events[p]["loss"]),
                "enemy_capture": int(cell_events[p]["enemy_capture"]),
                "neutral_capture": int(cell_events[p]["neutral_capture"]),
            },
            "general_events": {
                "capture": int(general_capture_count[p]),
                "lost": int(general_lost_count[p]),
                "death": int(general_death_count[p]),
            },
            "final": {
                "territory": int(final_snap[f"territory_{p}"]),
                "army": int(final_snap[f"army_{p}"]),
                "coins": int(final_snap[f"coins_{p}"]),
                "main_alive": int(final_snap[f"main_alive_{p}"]),
            },
        }

    out.update(
        {
            "parsed": True,
            "max_round": int(final_round),
            "players": player_out,
            "lead": {
                "territory": {
                    "sign_changes": int(_count_sign_changes(terr_leads)),
                    "max_p0": int(max(terr_leads)),
                    "max_p1": int(-min(terr_leads)),
                    "max_abs": int(max(abs(x) for x in terr_leads)),
                    "final_p0": int(terr_leads[-1]),
                },
                "army": {
                    "sign_changes": int(_count_sign_changes(army_leads)),
                    "max_p0": int(max(army_leads)),
                    "max_p1": int(-min(army_leads)),
                    "max_abs": int(max(abs(x) for x in army_leads)),
                    "final_p0": int(army_leads[-1]),
                },
            },
            "turning_points": turning_points,
            "general_event_timeline": general_events,
        }
    )
    return out


def _new_version_bucket() -> Dict[str, Any]:
    return {
        "games": 0,
        "wins": 0,
        "losses": 0,
        "draws": 0,
        "score_sum": 0.0,
        "round_sum": 0,
        "actions_sum": 0,
        "non_end_actions_sum": 0,
        "no_effect_sum": 0,
        "changed_cells_sum": 0,
        "final_territory_sum": 0,
        "final_army_sum": 0,
        "general_capture_sum": 0,
        "general_lost_sum": 0,
        "general_death_sum": 0,
        "cell_gain_sum": 0,
        "cell_loss_sum": 0,
        "enemy_capture_sum": 0,
        "neutral_capture_sum": 0,
        "action_counts": defaultdict(int),
    }


def _finalize_version_bucket(bucket: Dict[str, Any]) -> Dict[str, Any]:
    games = int(bucket["games"])
    non_end = int(bucket["non_end_actions_sum"])
    out: Dict[str, Any] = {
        "games": games,
        "wins": int(bucket["wins"]),
        "losses": int(bucket["losses"]),
        "draws": int(bucket["draws"]),
        "win_rate": (float(bucket["wins"]) / games) if games > 0 else 0.0,
        "score_rate": (float(bucket["score_sum"]) / games) if games > 0 else 0.0,
        "avg_rounds": (float(bucket["round_sum"]) / games) if games > 0 else 0.0,
        "avg_actions": (float(bucket["actions_sum"]) / games) if games > 0 else 0.0,
        "avg_non_end_actions": (float(bucket["non_end_actions_sum"]) / games) if games > 0 else 0.0,
        "no_effect_rate": (float(bucket["no_effect_sum"]) / non_end) if non_end > 0 else 0.0,
        "avg_changed_cells": (float(bucket["changed_cells_sum"]) / games) if games > 0 else 0.0,
        "avg_final_territory": (float(bucket["final_territory_sum"]) / games) if games > 0 else 0.0,
        "avg_final_army": (float(bucket["final_army_sum"]) / games) if games > 0 else 0.0,
        "avg_general_capture": (float(bucket["general_capture_sum"]) / games) if games > 0 else 0.0,
        "avg_general_lost": (float(bucket["general_lost_sum"]) / games) if games > 0 else 0.0,
        "avg_general_death": (float(bucket["general_death_sum"]) / games) if games > 0 else 0.0,
        "avg_cell_gain": (float(bucket["cell_gain_sum"]) / games) if games > 0 else 0.0,
        "avg_cell_loss": (float(bucket["cell_loss_sum"]) / games) if games > 0 else 0.0,
        "avg_enemy_capture": (float(bucket["enemy_capture_sum"]) / games) if games > 0 else 0.0,
        "avg_neutral_capture": (float(bucket["neutral_capture_sum"]) / games) if games > 0 else 0.0,
    }

    action_counts = bucket.get("action_counts", {})
    if isinstance(action_counts, dict):
        named = {}
        for cmd, cnt in sorted(action_counts.items(), key=lambda kv: int(kv[0])):
            named[_cmd_label(int(cmd))] = int(cnt)
        out["action_counts_named"] = named
    else:
        out["action_counts_named"] = {}
    return out


def _pair_key(a: str, b: str) -> str:
    x, y = sorted([a, b])
    return f"{x}__vs__{y}"


def _analyze_rows(rows: List[Dict[str, Any]], top_matches: int) -> Dict[str, Any]:
    matches_out: List[Dict[str, Any]] = []
    parse_errors = 0
    missing_replay = 0

    per_version: Dict[str, Dict[str, Any]] = defaultdict(_new_version_bucket)
    pair_stats: Dict[str, Dict[str, Any]] = defaultdict(
        lambda: {
            "games": 0,
            "draws": 0,
            "wins": defaultdict(int),
            "score_sum": defaultdict(float),
            "round_sum": 0,
        }
    )

    for row in rows:
        replay_file = str(row.get("replay_file", "") or "")
        if not replay_file:
            missing_replay += 1
            continue

        replay_path = Path(replay_file)
        replay = analyze_single_replay(replay_path)
        if not replay.get("parsed", False):
            parse_errors += 1
            continue

        seat_to_id, score_by_seat, winner_id = _seat_mapping(row)
        a = str(row.get("a", ""))
        b = str(row.get("b", ""))
        pair_key = _pair_key(a, b)

        max_round = int(replay.get("max_round", 0))
        terr_max_abs = int(replay.get("lead", {}).get("territory", {}).get("max_abs", 0))
        army_max_abs = int(replay.get("lead", {}).get("army", {}).get("max_abs", 0))

        detail = {
            "a": a,
            "b": b,
            "a_seat": _to_int(row.get("a_seat", 0), 0),
            "score_a": float(row.get("score_a", 0.5)),
            "winner": winner_id,
            "seed": row.get("seed"),
            "replay_file": replay_file,
            "max_round": max_round,
            "territory_lead_abs_max": terr_max_abs,
            "army_lead_abs_max": army_max_abs,
            "turning_points": replay.get("turning_points", [])[:5],
        }
        matches_out.append(detail)

        pst = pair_stats[pair_key]
        pst["games"] += 1
        pst["round_sum"] += max_round

        for seat in (0, 1):
            vid = seat_to_id.get(seat, "")
            if not vid:
                continue
            score = float(score_by_seat.get(seat, 0.5))

            vb = per_version[vid]
            vb["games"] += 1
            vb["score_sum"] += score
            vb["round_sum"] += max_round

            seat_stats = replay.get("players", {}).get(str(seat), {})
            actions_total = _to_int(seat_stats.get("actions_total", 0), 0)
            non_end_actions = _to_int(seat_stats.get("actions_non_end", 0), 0)
            no_effect_actions = _to_int(seat_stats.get("no_effect_actions", 0), 0)
            changed_cells = _to_int(seat_stats.get("changed_cells", 0), 0)
            vb["actions_sum"] += actions_total
            vb["non_end_actions_sum"] += non_end_actions
            vb["no_effect_sum"] += no_effect_actions
            vb["changed_cells_sum"] += changed_cells

            fin = seat_stats.get("final", {})
            vb["final_territory_sum"] += _to_int(fin.get("territory", 0), 0)
            vb["final_army_sum"] += _to_int(fin.get("army", 0), 0)

            gen = seat_stats.get("general_events", {})
            vb["general_capture_sum"] += _to_int(gen.get("capture", 0), 0)
            vb["general_lost_sum"] += _to_int(gen.get("lost", 0), 0)
            vb["general_death_sum"] += _to_int(gen.get("death", 0), 0)

            ce = seat_stats.get("cell_events", {})
            vb["cell_gain_sum"] += _to_int(ce.get("gain", 0), 0)
            vb["cell_loss_sum"] += _to_int(ce.get("loss", 0), 0)
            vb["enemy_capture_sum"] += _to_int(ce.get("enemy_capture", 0), 0)
            vb["neutral_capture_sum"] += _to_int(ce.get("neutral_capture", 0), 0)

            ac = seat_stats.get("action_counts", {})
            if isinstance(ac, dict):
                for cmd, cnt in ac.items():
                    vb["action_counts"][_to_int(cmd, -1)] += _to_int(cnt, 0)

            if score > 0.5:
                vb["wins"] += 1
                pst["wins"][vid] += 1
            elif score < 0.5:
                vb["losses"] += 1
            else:
                vb["draws"] += 1

            pst["score_sum"][vid] += score

        if not winner_id:
            pst["draws"] += 1

    version_out: Dict[str, Any] = {}
    for vid, bucket in per_version.items():
        version_out[vid] = _finalize_version_bucket(bucket)

    pair_out: Dict[str, Any] = {}
    for pkey, b in pair_stats.items():
        games = int(b["games"])
        wins = b["wins"]
        scores = b["score_sum"]
        pair_out[pkey] = {
            "games": games,
            "draws": int(b["draws"]),
            "avg_rounds": (float(b["round_sum"]) / games) if games > 0 else 0.0,
            "wins": {k: int(v) for k, v in sorted(wins.items())},
            "score_rate": {k: (float(v) / games if games > 0 else 0.0) for k, v in sorted(scores.items())},
        }

    longest = sorted(matches_out, key=lambda m: int(m.get("max_round", 0)), reverse=True)[:top_matches]
    by_army_swing = sorted(matches_out, key=lambda m: int(m.get("army_lead_abs_max", 0)), reverse=True)[:top_matches]
    by_terr_swing = sorted(matches_out, key=lambda m: int(m.get("territory_lead_abs_max", 0)), reverse=True)[:top_matches]

    return {
        "summary": {
            "rows_in_matches_file": len(rows),
            "analyzed_matches": len(matches_out),
            "missing_replay": missing_replay,
            "replay_parse_errors": parse_errors,
        },
        "per_version": version_out,
        "pair_stats": pair_out,
        "notable_matches": {
            "longest": longest,
            "largest_army_swing": by_army_swing,
            "largest_territory_swing": by_terr_swing,
        },
        "matches": matches_out,
    }


def _auto_output_paths(runtime_dir: Path, tag: str, cfg: ReplayAnalysisConfig) -> Tuple[Path, Path]:
    j = str(cfg.output_json or "").strip()
    m = str(cfg.output_md or "").strip()
    replay_dir = runtime_dir / "replay_analysis"
    replay_dir.mkdir(parents=True, exist_ok=True)
    if j:
        json_out = Path(j)
    else:
        json_out = replay_dir / f"{tag}_replay_analysis.json"
    if m:
        md_out = Path(m)
    else:
        md_out = replay_dir / f"{tag}_replay_analysis.md"
    return json_out, md_out


def _write_markdown_report(path: Path, data: Dict[str, Any]) -> None:
    lines: List[str] = []
    lines.append("# Replay 批量分析报告")
    lines.append("")
    lines.append(f"- generated_at: `{data.get('generated_at', '')}`")
    lines.append(f"- scope: `{data.get('runtime_scope', '') or 'production'}`")
    lines.append(f"- tag: `{data.get('tag', '')}`")
    lines.append(f"- matches_file: `{data.get('matches_file', '')}`")

    s = data.get("summary", {})
    lines.append(f"- rows_in_matches_file: `{s.get('rows_in_matches_file', 0)}`")
    lines.append(f"- analyzed_matches: `{s.get('analyzed_matches', 0)}`")
    lines.append(f"- missing_replay: `{s.get('missing_replay', 0)}`")
    lines.append(f"- replay_parse_errors: `{s.get('replay_parse_errors', 0)}`")
    lines.append("")

    per_version = data.get("per_version", {})
    lines.append("## 版本聚合统计")
    lines.append("")
    lines.append("| version | games | win_rate | score_rate | avg_rounds | no_effect_rate | avg_final_territory | avg_final_army |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- | --- |")
    rows = []
    for vid, st in per_version.items():
        if not isinstance(st, dict):
            continue
        rows.append((vid, float(st.get("score_rate", 0.0)), int(st.get("games", 0))))
    rows.sort(key=lambda x: (x[1], x[2]), reverse=True)
    for vid, _, _ in rows:
        st = per_version[vid]
        lines.append(
            "| {vid} | {games} | {wr:.3f} | {sr:.3f} | {ar:.1f} | {ner:.3f} | {ft:.1f} | {fa:.1f} |".format(
                vid=vid,
                games=int(st.get("games", 0)),
                wr=float(st.get("win_rate", 0.0)),
                sr=float(st.get("score_rate", 0.0)),
                ar=float(st.get("avg_rounds", 0.0)),
                ner=float(st.get("no_effect_rate", 0.0)),
                ft=float(st.get("avg_final_territory", 0.0)),
                fa=float(st.get("avg_final_army", 0.0)),
            )
        )

    lines.append("")
    lines.append("## 版本动作分布（聚合）")
    lines.append("")
    for vid, _, _ in rows[:12]:
        st = per_version[vid]
        action_named = st.get("action_counts_named", {})
        if not isinstance(action_named, dict):
            continue
        items = sorted(action_named.items(), key=lambda kv: kv[1], reverse=True)
        action_text = ", ".join(f"{k}:{v}" for k, v in items[:10])
        lines.append(f"- `{vid}`: {action_text}")

    lines.append("")
    lines.append("## 关键对局")
    lines.append("")

    nm = data.get("notable_matches", {})

    def write_match_list(title: str, items: List[Dict[str, Any]]) -> None:
        lines.append(f"### {title}")
        lines.append("")
        lines.append("| a | b | winner | score_a | max_round | terr_swing | army_swing | replay |")
        lines.append("| --- | --- | --- | --- | --- | --- | --- | --- |")
        for m in items:
            lines.append(
                "| {a} | {b} | {w} | {sa:.2f} | {r} | {ts} | {asw} | `{rp}` |".format(
                    a=str(m.get("a", "")),
                    b=str(m.get("b", "")),
                    w=str(m.get("winner", "draw") or "draw"),
                    sa=float(m.get("score_a", 0.5)),
                    r=int(m.get("max_round", 0)),
                    ts=int(m.get("territory_lead_abs_max", 0)),
                    asw=int(m.get("army_lead_abs_max", 0)),
                    rp=str(m.get("replay_file", "")),
                )
            )
        lines.append("")

    write_match_list("最长对局", list(nm.get("longest", []))[:12])
    write_match_list("兵力波动最大", list(nm.get("largest_army_swing", []))[:12])
    write_match_list("地盘波动最大", list(nm.get("largest_territory_swing", []))[:12])

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_replay_analysis(cfg: ReplayAnalysisConfig) -> Dict[str, Any]:
    runtime_dir = _runtime_dir(cfg.runtime_scope)
    runtime_dir.mkdir(parents=True, exist_ok=True)

    latest_obj: Dict[str, Any] = {}
    if cfg.matches_file:
        matches_path = Path(cfg.matches_file)
        if not matches_path.is_file():
            raise RuntimeError(f"matches file not found: {matches_path}")
        tag = matches_path.name.replace("_matches.jsonl", "")
    else:
        latest_obj = _load_latest(runtime_dir)
        paths = latest_obj.get("paths", {}) if isinstance(latest_obj, dict) else {}
        matches_path = Path(str(paths.get("matches", "")))
        if not matches_path.is_file():
            raise RuntimeError(f"latest.json points to missing matches file: {matches_path}")
        tag = str(latest_obj.get("tag", "")).strip() or matches_path.name.replace("_matches.jsonl", "")

    rows = _load_match_rows(matches_path)
    if cfg.max_matches > 0 and len(rows) > int(cfg.max_matches):
        rows = rows[-int(cfg.max_matches) :]

    analyzed = _analyze_rows(rows=rows, top_matches=max(1, int(cfg.top_matches)))

    result: Dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "runtime_scope": str(cfg.runtime_scope or ""),
        "tag": tag,
        "matches_file": str(matches_path),
        "latest_tag": str(latest_obj.get("tag", "")) if latest_obj else "",
        **analyzed,
    }

    json_out, md_out = _auto_output_paths(runtime_dir=runtime_dir, tag=tag, cfg=cfg)
    latest_json_out = json_out.parent / "latest.json"
    latest_md_out = md_out.parent / "latest.md"
    result["output_json"] = str(json_out)
    result["output_md"] = str(md_out)
    result["output_latest_json"] = str(latest_json_out)
    result["output_latest_md"] = str(latest_md_out)

    write_json(json_out, result)
    _write_markdown_report(md_out, result)

    write_json(latest_json_out, result)
    latest_md_out.write_text(md_out.read_text(encoding="utf-8"), encoding="utf-8")
    return result
