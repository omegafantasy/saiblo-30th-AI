from __future__ import annotations

import json
import os
import multiprocessing as mp
import time
from concurrent.futures import ThreadPoolExecutor
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

from .common import ANT_GAME_DIR, RUNTIME_DIR, ROOT_DIR, ensure_dirs, now_ts, write_json
from .elo import compute_elo
from .policy_adapters import close_policy, make_policy
from .registry import get_version, load_registry, set_champion

MAX_PARALLEL_JOBS = 16


def _build_pairs(version_ids: List[str], mode: str, reg: Dict[str, Any], challengers: List[str], opponents: List[str]) -> List[tuple[str, str]]:
    if mode == "round_robin":
        pairs: List[tuple[str, str]] = []
        for i in range(len(version_ids)):
            for j in range(i + 1, len(version_ids)):
                pairs.append((version_ids[i], version_ids[j]))
        return pairs

    if mode == "gauntlet":
        champ = str(reg.get("champion", "")).strip()
        all_versions = reg.get("versions", [])
        if not isinstance(all_versions, list):
            all_versions = []
        anchors = [str(v.get("id")) for v in all_versions if isinstance(v, dict) and v.get("anchor", False) and v.get("enabled", True)]

        chals = challengers if challengers else [vid for vid in version_ids if vid != champ and vid not in anchors]
        if not chals and champ in version_ids:
            # Fallback for early stage: evaluate champion against anchors.
            chals = [champ]
        opps = opponents if opponents else ([champ] if champ else []) + anchors
        opps = [x for x in opps if x in version_ids]

        pairs = []
        for a in chals:
            for b in opps:
                if a == b:
                    continue
                pairs.append((a, b))
        return pairs

    raise ValueError(f"unsupported mode: {mode}")


def _single_match(task: Dict[str, Any]) -> Dict[str, Any]:
    import random
    import sys
    from pathlib import Path

    ant_dir = Path(task["ant_game_dir"])
    if str(ant_dir) not in sys.path:
        sys.path.insert(0, str(ant_dir))

    from logic.runner import run_match

    a = task["a"]
    b = task["b"]
    a_spec = task["a_spec"]
    b_spec = task["b_spec"]
    seed = int(task["seed"])
    max_rounds = int(task["max_rounds"])
    a_on_seat0 = bool(task["a_on_seat0"])
    replay_dir = str(task["replay_dir"])

    random.seed(seed)

    pa = make_policy(a_spec, base_seed=seed * 17 + 101)
    pb = make_policy(b_spec, base_seed=seed * 17 + 307)

    try:
        if a_on_seat0:
            winner, state = run_match(
                pa,
                pb,
                seed=seed,
                max_rounds=max_rounds,
                replay_dir=replay_dir,
                p0_name=a,
                p1_name=b,
            )
            score_a = 1.0 if winner == 0 else 0.0 if winner == 1 else 0.5
            a_seat = 0
        else:
            winner, state = run_match(
                pb,
                pa,
                seed=seed,
                max_rounds=max_rounds,
                replay_dir=replay_dir,
                p0_name=b,
                p1_name=a,
            )
            score_a = 1.0 if winner == 1 else 0.0 if winner == 0 else 0.5
            a_seat = 1

        replay_file = getattr(state, "replay_file", "")
        if replay_file and os.path.isfile(replay_file):
            try:
                os.remove(replay_file)
            except Exception:
                pass
        return {
            "a": a,
            "b": b,
            "seed": seed,
            "a_seat": a_seat,
            "score_a": score_a,
            "winner_seat": winner,
        }
    finally:
        close_policy(pa)
        close_policy(pb)


def _read_cpu_stat() -> Dict[int, tuple[int, int]]:
    """
    Return per-core (idle_total, total) from /proc/stat.
    idle_total includes idle + iowait.
    """
    data: Dict[int, tuple[int, int]] = {}
    try:
        with open("/proc/stat", "r", encoding="utf-8") as f:
            for line in f:
                if not line.startswith("cpu") or line.startswith("cpu "):
                    continue
                parts = line.split()
                if len(parts) < 6:
                    continue
                name = parts[0]
                if not name[3:].isdigit():
                    continue
                idx = int(name[3:])
                vals = [int(x) for x in parts[1:]]
                total = sum(vals)
                idle = vals[3] + (vals[4] if len(vals) > 4 else 0)
                data[idx] = (idle, total)
    except Exception:
        return {}
    return data


def detect_idle_cores(sample_sec: float = 0.8, idle_threshold: float = 0.02) -> List[int]:
    """
    idle_threshold is max busy ratio; 0.02 means <=2% busy is considered idle.
    """
    s1 = _read_cpu_stat()
    if not s1:
        return []
    time.sleep(max(0.05, float(sample_sec)))
    s2 = _read_cpu_stat()
    if not s2:
        return []

    idle_cores: List[int] = []
    for idx, (idle1, total1) in s1.items():
        if idx not in s2:
            continue
        idle2, total2 = s2[idx]
        dt = total2 - total1
        di = idle2 - idle1
        if dt <= 0:
            continue
        busy = 1.0 - (di / dt)
        if busy <= idle_threshold:
            idle_cores.append(idx)
    return sorted(idle_cores)


def _pool_init_affinity(core_list: List[int], pin_cpu: bool) -> None:
    if not pin_cpu:
        return
    if not core_list:
        return
    try:
        ident = mp.current_process()._identity
        wid = int(ident[0]) - 1 if ident else 0
        core = core_list[wid % len(core_list)]
        os.sched_setaffinity(0, {int(core)})
    except Exception:
        # Best effort: do not fail evaluation due to affinity setup.
        return


@dataclass
class EvalConfig:
    mode: str = "gauntlet"
    versions: List[str] | None = None
    challengers: List[str] | None = None
    opponents: List[str] | None = None
    games_per_pair: int = 20
    max_rounds: int = 160
    jobs: int = 14
    seed: int = 0
    k_factor: float = 20.0
    base_rating: float = 1500.0
    auto_promote: bool = True
    promote_min_delta: float = 35.0
    doc_out: str = ""
    cpu_policy: str = "all"  # all | idle_only
    idle_threshold: float = 0.02
    idle_sample_sec: float = 0.8
    pin_cpu: bool = True
    runtime_scope: str = ""
    write_latest: bool = True


def _split_csv(value: str) -> List[str]:
    return [x.strip() for x in value.split(",") if x.strip()]


def run_evaluation(cfg: EvalConfig) -> Dict[str, Any]:
    ensure_dirs()
    scope = str(cfg.runtime_scope or "").strip()
    runtime_dir = RUNTIME_DIR if not scope else (RUNTIME_DIR / "scopes" / scope)
    runtime_dir.mkdir(parents=True, exist_ok=True)
    reg = load_registry()
    all_versions = [v for v in reg.get("versions", []) if isinstance(v, dict) and v.get("enabled", True)]
    all_ids = [str(v.get("id")) for v in all_versions]

    selected_ids = cfg.versions if cfg.versions else all_ids
    selected_ids = [vid for vid in selected_ids if vid in all_ids]
    if len(selected_ids) < 2:
        raise RuntimeError("need at least two enabled versions to evaluate")

    pairs = _build_pairs(
        selected_ids,
        mode=cfg.mode,
        reg=reg,
        challengers=cfg.challengers or [],
        opponents=cfg.opponents or [],
    )
    if not pairs:
        raise RuntimeError("empty pair list after applying mode/filters")

    tasks: List[Dict[str, Any]] = []
    seed_base = int(cfg.seed)
    replay_dir = str(runtime_dir / "tmp_replays")
    Path(replay_dir).mkdir(parents=True, exist_ok=True)
    serial = 0
    for (a, b) in pairs:
        a_spec = get_version(a)
        b_spec = get_version(b)
        if a_spec is None or b_spec is None:
            continue
        for g in range(cfg.games_per_pair):
            s = seed_base + serial * 1009 + g
            tasks.append(
                {
                    "a": a,
                    "b": b,
                    "a_spec": a_spec,
                    "b_spec": b_spec,
                    "seed": s,
                    "max_rounds": cfg.max_rounds,
                    "a_on_seat0": True,
                    "replay_dir": replay_dir,
                    "ant_game_dir": str(ANT_GAME_DIR),
                }
            )
            tasks.append(
                {
                    "a": a,
                    "b": b,
                    "a_spec": a_spec,
                    "b_spec": b_spec,
                    "seed": s + 911,
                    "max_rounds": cfg.max_rounds,
                    "a_on_seat0": False,
                    "replay_dir": replay_dir,
                    "ant_game_dir": str(ANT_GAME_DIR),
                }
            )
        serial += 1

    cpu_cnt = os.cpu_count() or 1
    all_cores = list(range(cpu_cnt))
    if cfg.cpu_policy == "idle_only":
        selected_cores = detect_idle_cores(sample_sec=cfg.idle_sample_sec, idle_threshold=cfg.idle_threshold)
        if not selected_cores:
            raise RuntimeError(
                "no idle cores detected under current threshold; "
                "use --cpu-policy all or relax --idle-threshold"
            )
    else:
        selected_cores = all_cores

    requested_jobs = max(1, int(cfg.jobs))
    workers = max(1, min(requested_jobs, len(selected_cores), MAX_PARALLEL_JOBS))
    backend = "serial"
    if workers == 1:
        backend = "serial"
        if cfg.pin_cpu and selected_cores:
            try:
                os.sched_setaffinity(0, {selected_cores[0]})
            except Exception:
                pass
        rows = [_single_match(t) for t in tasks]
    else:
        try:
            with mp.Pool(
                processes=workers,
                initializer=_pool_init_affinity,
                initargs=(selected_cores[:workers], bool(cfg.pin_cpu)),
            ) as pool:
                rows = pool.map(_single_match, tasks)
            backend = "multiprocessing"
        except (PermissionError, OSError):
            # Some sandboxes block SemLock for multiprocessing; preserve concurrency via threads.
            with ThreadPoolExecutor(max_workers=workers) as ex:
                rows = list(ex.map(_single_match, tasks))
            backend = "thread_fallback"

    ratings = compute_elo(rows, base_rating=cfg.base_rating, k_factor=cfg.k_factor)
    ranking = sorted(ratings.items(), key=lambda kv: kv[1], reverse=True)

    stats = defaultdict(lambda: {"games": 0, "wins": 0.0, "losses": 0.0, "draws": 0.0, "score": 0.0})
    for r in rows:
        a = r["a"]
        b = r["b"]
        sa = float(r["score_a"])
        sb = 1.0 - sa
        for vid, sc in ((a, sa), (b, sb)):
            stats[vid]["games"] += 1
            stats[vid]["score"] += sc
            if sc > 0.5:
                stats[vid]["wins"] += 1
            elif sc < 0.5:
                stats[vid]["losses"] += 1
            else:
                stats[vid]["draws"] += 1

    champ_old = str(reg.get("champion", ""))
    champ_new = champ_old
    promoted = False
    if cfg.auto_promote and ranking:
        top_id, top_elo = ranking[0]
        old_elo = ratings.get(champ_old, cfg.base_rating)
        if top_id != champ_old and (top_elo - old_elo) >= cfg.promote_min_delta:
            set_champion(top_id)
            champ_new = top_id
            promoted = True

    ts = now_ts()
    tag = f"eval_{ts}"
    matches_path = runtime_dir / f"{tag}_matches.jsonl"
    summary_path = runtime_dir / f"{tag}_summary.json"
    for r in rows:
        with matches_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    out = {
        "tag": tag,
        "config": {
            "mode": cfg.mode,
            "games_per_pair": cfg.games_per_pair,
            "max_rounds": cfg.max_rounds,
            "jobs_requested": requested_jobs,
            "jobs": workers,
            "cpu_policy": cfg.cpu_policy,
            "pin_cpu": bool(cfg.pin_cpu),
            "selected_cores": selected_cores[:workers],
            "backend": backend,
            "seed": cfg.seed,
            "k_factor": cfg.k_factor,
            "base_rating": cfg.base_rating,
            "runtime_scope": scope,
            "versions": selected_ids,
            "pairs": pairs,
        },
        "champion": {"old": champ_old, "new": champ_new, "promoted": promoted},
        "ratings": [{"id": vid, "elo": elo} for vid, elo in ranking],
        "stats": stats,
        "paths": {"matches": str(matches_path), "summary": str(summary_path)},
        "matches": len(rows),
    }
    write_json(summary_path, out)
    if cfg.write_latest:
        write_json(runtime_dir / "latest.json", out)

    if cfg.doc_out:
        _write_markdown_report(Path(cfg.doc_out), out)

    return out


def _write_markdown_report(path: Path, result: Dict[str, Any]) -> None:
    lines = []
    lines.append("# 自动评测轮次报告")
    lines.append("")
    lines.append(f"- tag: `{result['tag']}`")
    lines.append(f"- mode: `{result['config']['mode']}`")
    lines.append(f"- matches: `{result['matches']}`")
    lines.append(f"- jobs: `{result['config']['jobs']}`")
    lines.append(f"- champion(old->new): `{result['champion']['old']} -> {result['champion']['new']}`")
    lines.append("")
    lines.append("## Elo 排名")
    lines.append("")
    lines.append("| rank | version | elo |")
    lines.append("| --- | --- | --- |")
    for i, item in enumerate(result["ratings"], start=1):
        lines.append(f"| {i} | {item['id']} | {item['elo']:.2f} |")
    lines.append("")
    lines.append("## 路径")
    lines.append("")
    lines.append(f"- matches: `{result['paths']['matches']}`")
    lines.append(f"- summary: `{result['paths']['summary']}`")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_from_args(args: Any) -> Dict[str, Any]:
    cfg = EvalConfig(
        mode=args.mode,
        versions=_split_csv(args.versions) if args.versions else None,
        challengers=_split_csv(args.challengers) if args.challengers else None,
        opponents=_split_csv(args.opponents) if args.opponents else None,
        games_per_pair=args.games_per_pair,
        max_rounds=args.max_rounds,
        jobs=args.jobs,
        seed=args.seed,
        k_factor=args.k_factor,
        base_rating=args.base_rating,
        auto_promote=args.auto_promote,
        promote_min_delta=args.promote_min_delta,
        doc_out=args.doc_out,
        cpu_policy=args.cpu_policy,
        idle_threshold=args.idle_threshold,
        idle_sample_sec=args.idle_sample_sec,
        pin_cpu=args.pin_cpu,
        runtime_scope=args.runtime_scope,
        write_latest=args.write_latest,
    )
    return run_evaluation(cfg)
