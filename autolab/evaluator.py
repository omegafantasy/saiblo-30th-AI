from __future__ import annotations

import json
import os
import multiprocessing as mp
import random
import shutil
import time
from concurrent.futures import ThreadPoolExecutor
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from .common import ANT_GAME_DIR, RUNTIME_DIR, current_ruleset_id, ensure_dirs, now_ts, write_json
from .elo import compute_elo
from .game1_match_runner import ensure_game_bin, run_match_task, stage_version
from .registry import get_version, load_registry, set_champion

MAX_PARALLEL_JOBS = 24


def _version_is_usable(v: Dict[str, Any]) -> bool:
    if not isinstance(v, dict):
        return False
    if not bool(v.get("enabled", True)):
        return False
    kind = str(v.get("kind", "")).strip()
    if kind == "cpp_exe":
        exe = str(v.get("exe", "")).strip()
        if not exe:
            return False
        p = Path(exe)
        return p.is_file() and os.access(str(p), os.X_OK)
    if kind == "cpp_protocol_exe":
        exe = str(v.get("exe", "")).strip()
        if not exe:
            return False
        p = Path(exe)
        return p.is_file() and os.access(str(p), os.X_OK)
    if kind == "antgame_py":
        # Built-in Ant-Game python policies are resolved by name at runtime.
        return bool(str(v.get("name", "")).strip())
    return False


def _iter_completed_match_files(runtime_dir: Path) -> List[Path]:
    files: List[Path] = []
    for summary in sorted(runtime_dir.glob("eval_*_summary.json")):
        name = summary.name
        if not name.startswith("eval_") or not name.endswith("_summary.json"):
            continue
        tag = name[len("eval_") : -len("_summary.json")]
        m = runtime_dir / f"eval_{tag}_matches.jsonl"
        if m.is_file():
            files.append(m)
    return files


def _accumulate_elo_and_stats(
    rows: Iterable[Dict[str, Any]],
    base_rating: float,
    k_factor: float,
    allowed_ids: set[str] | None = None,
) -> Tuple[Dict[str, float], Dict[str, Dict[str, float]], int]:
    ratings: Dict[str, float] = {}
    if allowed_ids:
        for vid in allowed_ids:
            ratings[vid] = float(base_rating)

    stats: Dict[str, Dict[str, float]] = defaultdict(
        lambda: {"games": 0.0, "wins": 0.0, "losses": 0.0, "draws": 0.0, "score": 0.0}
    )

    # Keep Elo update semantics exactly aligned with autolab.elo.compute_elo.
    def expected_score(ra: float, rb: float) -> float:
        return 1.0 / (1.0 + 10.0 ** ((rb - ra) / 400.0))

    count = 0
    for r in rows:
        a = str(r.get("a", ""))
        b = str(r.get("b", ""))
        if not a or not b:
            continue
        if allowed_ids is not None and (a not in allowed_ids or b not in allowed_ids):
            continue
        sa = float(r.get("score_a", 0.5))
        if sa < 0.0:
            sa = 0.0
        elif sa > 1.0:
            sa = 1.0
        sb = 1.0 - sa

        if a not in ratings:
            ratings[a] = float(base_rating)
        if b not in ratings:
            ratings[b] = float(base_rating)
        ra = ratings[a]
        rb = ratings[b]
        ea = expected_score(ra, rb)
        delta = float(k_factor) * (sa - ea)
        ratings[a] = ra + delta
        ratings[b] = rb - delta

        count += 1
        for vid, sc in ((a, sa), (b, sb)):
            s = stats[vid]
            s["games"] += 1.0
            s["score"] += float(sc)
            if sc > 0.5:
                s["wins"] += 1.0
            elif sc < 0.5:
                s["losses"] += 1.0
            else:
                s["draws"] += 1.0

    # Ensure all allowed ids have a stats entry for stable downstream rendering.
    if allowed_ids:
        for vid in allowed_ids:
            _ = stats[vid]
    return ratings, stats, count


def _iter_rows_from_match_files(files: List[Path], ruleset_id: str | None = None) -> Iterable[Dict[str, Any]]:
    for f in files:
        with f.open("r", encoding="utf-8", errors="ignore") as fp:
            for line in fp:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                if isinstance(obj, dict):
                    if ruleset_id is not None and str(obj.get("ruleset_id", "")) != ruleset_id:
                        continue
                    yield obj


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


def _build_adaptive_pairs(
    version_ids: List[str],
    runtime_dir: Path,
    cfg: "EvalConfig",
) -> tuple[List[tuple[str, str]], Dict[str, Any]]:
    if len(version_ids) < 2:
        return [], {}

    latest_path = runtime_dir / "latest.json"
    latest: Dict[str, Any] = {}
    if latest_path.is_file():
        try:
            with latest_path.open("r", encoding="utf-8") as f:
                obj = json.load(f)
            if isinstance(obj, dict):
                latest = obj
        except Exception:
            latest = {}

    ratings = latest.get("ratings", [])
    if not isinstance(ratings, list):
        ratings = []
    stats = latest.get("stats", {})
    if not isinstance(stats, dict):
        stats = {}

    rank_map: Dict[str, int] = {}
    for i, item in enumerate(ratings, start=1):
        if isinstance(item, dict):
            vid = str(item.get("id", ""))
            if vid:
                rank_map[vid] = i

    games_map: Dict[str, float] = {}
    for vid, st in stats.items():
        if isinstance(st, dict):
            games_map[str(vid)] = float(st.get("games", 0.0))

    top_k = max(0, int(cfg.adaptive_top_k))
    top_boost = max(0.0, float(cfg.adaptive_top_boost))
    new_target = max(1.0, float(cfg.adaptive_new_target_games))
    new_boost = max(0.0, float(cfg.adaptive_new_boost))

    def version_weight(vid: str) -> float:
        w = 1.0  # baseline uniform random
        rank = rank_map.get(vid, 10**9)
        if top_k > 0 and rank <= top_k:
            # rank=1 gets full boost; rank=top_k gets small positive boost
            frac = (top_k - rank + 1) / float(top_k)
            w += top_boost * frac
        g = float(games_map.get(vid, 0.0))
        under = max(0.0, new_target - g) / new_target
        w += new_boost * under
        return max(1e-6, w)

    all_pairs: List[tuple[str, str]] = []
    pair_weights: List[float] = []
    for i in range(len(version_ids)):
        for j in range(i + 1, len(version_ids)):
            a = version_ids[i]
            b = version_ids[j]
            all_pairs.append((a, b))
            pair_weights.append(0.5 * (version_weight(a) + version_weight(b)))

    if not all_pairs:
        return [], {}

    pair_count = max(1, int(cfg.adaptive_pair_count))
    rng_seed = int(cfg.seed) if int(cfg.seed) != 0 else int(time.time_ns() & 0xFFFFFFFF)
    rng = random.Random(rng_seed)
    sampled = rng.choices(all_pairs, weights=pair_weights, k=pair_count)

    hist: Dict[str, int] = defaultdict(int)
    for a, b in sampled:
        hist[f"{a}__vs__{b}"] += 1
    hist_sorted = sorted(hist.items(), key=lambda kv: kv[1], reverse=True)
    meta = {
        "seed_used": rng_seed,
        "pair_space_size": len(all_pairs),
        "pair_count": pair_count,
        "top_pair_freq": [{"pair": k, "count": v} for k, v in hist_sorted[:10]],
    }
    return sampled, meta


def _single_match(task: Dict[str, Any]) -> Dict[str, Any]:
    return run_match_task(task)


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
    mode: str = "gauntlet"  # gauntlet | round_robin | adaptive
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
    anchor_games_per_pair: int = 0  # for gauntlet anchors; 0 means use games_per_pair
    adaptive_pair_count: int = 45
    adaptive_top_k: int = 6
    adaptive_top_boost: float = 1.5
    adaptive_new_target_games: int = 600
    adaptive_new_boost: float = 2.0
    save_replays: bool = False


def _split_csv(value: str) -> List[str]:
    return [x.strip() for x in value.split(",") if x.strip()]


def run_evaluation(cfg: EvalConfig) -> Dict[str, Any]:
    ensure_dirs()
    ruleset_id = current_ruleset_id()
    scope = str(cfg.runtime_scope or "").strip()
    runtime_dir = RUNTIME_DIR if not scope else (RUNTIME_DIR / "scopes" / scope)
    runtime_dir.mkdir(parents=True, exist_ok=True)
    reg = load_registry()
    all_versions = [v for v in reg.get("versions", []) if _version_is_usable(v)]
    all_ids = [str(v.get("id")) for v in all_versions]
    anchor_ids = {
        str(v.get("id"))
        for v in all_versions
        if isinstance(v, dict) and bool(v.get("anchor", False))
    }

    selected_ids = cfg.versions if cfg.versions else all_ids
    selected_ids = [vid for vid in selected_ids if vid in all_ids]
    if len(selected_ids) < 2:
        raise RuntimeError("need at least two enabled versions to evaluate")

    adaptive_meta: Dict[str, Any] = {}
    if cfg.mode == "adaptive":
        pairs, adaptive_meta = _build_adaptive_pairs(
            version_ids=selected_ids,
            runtime_dir=runtime_dir,
            cfg=cfg,
        )
    else:
        pairs = _build_pairs(
            selected_ids,
            mode=cfg.mode,
            reg=reg,
            challengers=cfg.challengers or [],
            opponents=cfg.opponents or [],
        )
    if not pairs:
        raise RuntimeError("empty pair list after applying mode/filters")

    ts = now_ts()
    tag = f"eval_{ts}"
    game_bin = ensure_game_bin(ANT_GAME_DIR)
    package_root = runtime_dir / "packages" / tag
    match_root = runtime_dir / "match_work" / tag
    package_root.mkdir(parents=True, exist_ok=True)
    packaged_dirs: Dict[str, str] = {}
    for version in all_versions:
        vid = str(version.get("id", "")).strip()
        if vid not in selected_ids:
            continue
        packaged_dirs[vid] = str(stage_version(ANT_GAME_DIR, version, package_root / vid))

    tasks: List[Dict[str, Any]] = []
    seed_base = int(cfg.seed)
    if bool(cfg.save_replays):
        replay_dir = runtime_dir / "replays" / tag
    else:
        replay_dir = runtime_dir / "tmp_replays" / tag
    replay_dir.mkdir(parents=True, exist_ok=True)
    serial = 0
    for (a, b) in pairs:
        a_spec = get_version(a)
        b_spec = get_version(b)
        if a_spec is None or b_spec is None or (not _version_is_usable(a_spec)) or (not _version_is_usable(b_spec)):
            continue
        pair_games = int(cfg.games_per_pair)
        if (
            cfg.mode == "gauntlet"
            and int(cfg.anchor_games_per_pair) > 0
            and (a in anchor_ids or b in anchor_ids)
        ):
            pair_games = int(cfg.anchor_games_per_pair)
        for g in range(pair_games):
            s = seed_base + serial * 1009 + g
            p0_name = a
            p1_name = b
            replay_path = replay_dir / f"{tag}_p0-{p0_name}_p1-{p1_name}_seed-{s}.json"
            work_dir = match_root / f"p0-{p0_name}_p1-{p1_name}_seed-{s}"
            tasks.append(
                {
                    "a": a,
                    "b": b,
                    "seed": s,
                    "max_rounds": cfg.max_rounds,
                    "a_on_seat0": True,
                    "ai0_dir": packaged_dirs[a],
                    "ai1_dir": packaged_dirs[b],
                    "game_bin": str(game_bin),
                    "work_dir": str(work_dir),
                    "replay_file": str(replay_path),
                }
            )
            p0_name = b
            p1_name = a
            replay_path = replay_dir / f"{tag}_p0-{p0_name}_p1-{p1_name}_seed-{s + 911}.json"
            work_dir = match_root / f"p0-{p0_name}_p1-{p1_name}_seed-{s + 911}"
            tasks.append(
                {
                    "a": a,
                    "b": b,
                    "seed": s + 911,
                    "max_rounds": cfg.max_rounds,
                    "a_on_seat0": False,
                    "ai0_dir": packaged_dirs[b],
                    "ai1_dir": packaged_dirs[a],
                    "game_bin": str(game_bin),
                    "work_dir": str(work_dir),
                    "replay_file": str(replay_path),
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

    round_ratings = compute_elo(rows, base_rating=cfg.base_rating, k_factor=cfg.k_factor)
    round_ranking = sorted(round_ratings.items(), key=lambda kv: kv[1], reverse=True)
    round_stats: Dict[str, Dict[str, float]] = defaultdict(
        lambda: {"games": 0.0, "wins": 0.0, "losses": 0.0, "draws": 0.0, "score": 0.0}
    )
    for r in rows:
        a = str(r["a"])
        b = str(r["b"])
        sa = float(r["score_a"])
        sb = 1.0 - sa
        for vid, sc in ((a, sa), (b, sb)):
            round_stats[vid]["games"] += 1.0
            round_stats[vid]["score"] += float(sc)
            if sc > 0.5:
                round_stats[vid]["wins"] += 1.0
            elif sc < 0.5:
                round_stats[vid]["losses"] += 1.0
            else:
                round_stats[vid]["draws"] += 1.0

    matches_path = runtime_dir / f"{tag}_matches.jsonl"
    summary_path = runtime_dir / f"{tag}_summary.json"
    if not bool(cfg.save_replays):
        for r in rows:
            r["replay_file"] = ""
    for r in rows:
        r["ruleset_id"] = ruleset_id
        with matches_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    round_out = {
        "tag": tag,
        "ruleset_id": ruleset_id,
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
            "rating_mode": "round",
            "anchor_games_per_pair": int(cfg.anchor_games_per_pair),
            "adaptive_pair_count": int(cfg.adaptive_pair_count),
            "adaptive_top_k": int(cfg.adaptive_top_k),
            "adaptive_top_boost": float(cfg.adaptive_top_boost),
            "adaptive_new_target_games": int(cfg.adaptive_new_target_games),
            "adaptive_new_boost": float(cfg.adaptive_new_boost),
            "save_replays": bool(cfg.save_replays),
            "versions": selected_ids,
            "pairs": pairs,
        },
        "champion": {"old": str(reg.get("champion", "")), "new": str(reg.get("champion", "")), "promoted": False},
        "ratings": [{"id": vid, "elo": elo} for vid, elo in round_ranking],
        "stats": round_stats,
        "paths": {
            "matches": str(matches_path),
            "summary": str(summary_path),
            "replays_dir": str(replay_dir) if bool(cfg.save_replays) else "",
        },
        "matches": len(rows),
    }
    write_json(summary_path, round_out)

    # Production scope uses cumulative Elo for latest/champion decisions.
    out = round_out
    if scope == "":
        allowed_ids = set(all_ids)
        completed_files = _iter_completed_match_files(runtime_dir)
        cum_ratings, cum_stats, cum_matches = _accumulate_elo_and_stats(
            rows=_iter_rows_from_match_files(completed_files, ruleset_id=ruleset_id),
            base_rating=cfg.base_rating,
            k_factor=cfg.k_factor,
            allowed_ids=allowed_ids,
        )
        cum_ranking = sorted(cum_ratings.items(), key=lambda kv: kv[1], reverse=True)

        champ_old = str(reg.get("champion", ""))
        champ_new = champ_old
        promoted = False
        if cfg.auto_promote and cum_ranking:
            top_id, top_elo = cum_ranking[0]
            old_elo = float(cum_ratings.get(champ_old, cfg.base_rating))
            if top_id != champ_old and (top_elo - old_elo) >= cfg.promote_min_delta:
                set_champion(top_id)
                champ_new = top_id
                promoted = True

        out = {
            "tag": tag,
            "ruleset_id": ruleset_id,
            "config": {
                **round_out["config"],
                "rating_mode": "cumulative",
                "active_version_ids": sorted(allowed_ids),
            },
            "champion": {"old": champ_old, "new": champ_new, "promoted": promoted},
            "ratings": [{"id": vid, "elo": elo} for vid, elo in cum_ranking],
            "stats": cum_stats,
            "paths": {
                "matches": str(matches_path),
                "summary": str(summary_path),
                "latest_round_summary": str(summary_path),
            },
            "matches": cum_matches,
            "cumulative": {
                "round_files": len(completed_files),
                "latest_round_tag": tag,
                "latest_round_matches": len(rows),
            },
        }
        if adaptive_meta:
            out["config"]["adaptive"] = adaptive_meta

    if cfg.write_latest:
        write_json(runtime_dir / "latest.json", out)

    if cfg.doc_out:
        _write_markdown_report(Path(cfg.doc_out), out)

    if not bool(cfg.save_replays):
        shutil.rmtree(replay_dir, ignore_errors=True)
        shutil.rmtree(match_root, ignore_errors=True)
        shutil.rmtree(package_root, ignore_errors=True)

    return out


def _write_markdown_report(path: Path, result: Dict[str, Any]) -> None:
    lines = []
    lines.append("# 自动评测轮次报告")
    lines.append("")
    lines.append(f"- tag: `{result['tag']}`")
    lines.append(f"- ruleset_id: `{result.get('ruleset_id', '')}`")
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
    replays_dir = str(result.get("paths", {}).get("replays_dir", "") or "")
    if replays_dir:
        lines.append(f"- replays_dir: `{replays_dir}`")
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
        anchor_games_per_pair=args.anchor_games_per_pair,
        adaptive_pair_count=args.adaptive_pair_count,
        adaptive_top_k=args.adaptive_top_k,
        adaptive_top_boost=args.adaptive_top_boost,
        adaptive_new_target_games=args.adaptive_new_target_games,
        adaptive_new_boost=args.adaptive_new_boost,
        save_replays=args.save_replays,
    )
    return run_evaluation(cfg)
