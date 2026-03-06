#!/usr/bin/env python3
"""
Replay stability harness for Saiblo stdinRecords.

Purpose:
- Quantify run-to-run drift of one binary on identical replay streams.
- Optionally compare one run of baseline vs candidate binary.
"""

from __future__ import annotations

import argparse
import base64
import glob
import hashlib
import json
import statistics
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple


@dataclass
class StreamResult:
    out_hash: str
    non_end_actions: int
    frame_count: int


@dataclass
class RunSummary:
    stream_results: List[StreamResult]
    elapsed_sec: float


@dataclass
class StreamMeta:
    match_file: str
    match_id: str
    stdin_index: int

    def as_dict(self) -> dict:
        return {
            "match_file": self.match_file,
            "match_id": self.match_id,
            "stdin_index": self.stdin_index,
        }


def decode_streams(replay_dir: Path, max_matches: int) -> Tuple[List[bytes], List[StreamMeta]]:
    files = sorted(glob.glob(str(replay_dir / "match_*.json")))
    if max_matches > 0:
        files = files[:max_matches]

    streams: List[bytes] = []
    metas: List[StreamMeta] = []
    for fp in files:
        with open(fp, "r", encoding="utf-8") as f:
            outer = json.load(f)
        if "message" not in outer:
            continue
        try:
            inner = json.loads(outer["message"])
        except Exception:
            continue
        match_file = Path(fp).name
        match_id = ""
        if match_file.startswith("match_") and match_file.endswith(".json"):
            match_id = match_file[len("match_") : -len(".json")]
        for stdin_index, s in enumerate(inner.get("stdinRecords", [])):
            try:
                streams.append(base64.b64decode(s, validate=False))
                metas.append(StreamMeta(match_file=match_file, match_id=match_id, stdin_index=stdin_index))
            except Exception:
                continue
    return streams, metas


def run_one_stream(binary: Path, stream: bytes, timeout_sec: int) -> StreamResult:
    proc = subprocess.Popen(
        [str(binary)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    out, _ = proc.communicate(stream, timeout=timeout_sec)

    non_end = 0
    frames = 0
    idx = 0
    n_out = len(out)
    while idx + 4 <= n_out:
        n = int.from_bytes(out[idx : idx + 4], byteorder="big", signed=False)
        idx += 4
        if idx + n > n_out:
            break
        payload = out[idx : idx + n]
        idx += n
        frames += 1
        for line in payload.decode("utf-8", errors="ignore").splitlines():
            line = line.strip()
            if not line:
                continue
            if line.split()[0] != "8":
                non_end += 1

    out_hash = hashlib.sha256(out).hexdigest()[:16]
    return StreamResult(out_hash=out_hash, non_end_actions=non_end, frame_count=frames)


def run_full(binary: Path, streams: List[bytes], timeout_sec: int) -> RunSummary:
    t0 = time.perf_counter()
    results = [run_one_stream(binary, s, timeout_sec) for s in streams]
    return RunSummary(stream_results=results, elapsed_sec=time.perf_counter() - t0)


def summarize_repeats(summaries: List[RunSummary]) -> dict:
    if not summaries:
        return {}

    repeats = len(summaries)
    streams = len(summaries[0].stream_results)

    unstable_streams = 0
    per_stream_hash_var = []
    for i in range(streams):
        hs = {summaries[r].stream_results[i].out_hash for r in range(repeats)}
        if len(hs) > 1:
            unstable_streams += 1
        per_stream_hash_var.append(len(hs))

    non_end_totals = []
    frame_totals = []
    for s in summaries:
        non_end_totals.append(sum(x.non_end_actions for x in s.stream_results))
        frame_totals.append(sum(x.frame_count for x in s.stream_results))

    elapsed = [s.elapsed_sec for s in summaries]

    return {
        "repeats": repeats,
        "streams": streams,
        "unstable_streams": unstable_streams,
        "unstable_rate": (unstable_streams / streams) if streams else 0.0,
        "non_end_totals": non_end_totals,
        "frame_totals": frame_totals,
        "non_end_min": min(non_end_totals),
        "non_end_max": max(non_end_totals),
        "non_end_mean": statistics.mean(non_end_totals),
        "elapsed_sec": elapsed,
        "elapsed_min": min(elapsed),
        "elapsed_max": max(elapsed),
        "elapsed_mean": statistics.mean(elapsed),
        "hash_cardinality_sample": per_stream_hash_var[:20],
    }


def compare_once(base: RunSummary, cand: RunSummary, metas: List[StreamMeta]) -> dict:
    n = min(len(base.stream_results), len(cand.stream_results))
    hash_diff_streams = 0
    non_end_delta = 0
    frame_delta = 0
    hash_diff_indices = []
    hash_diff_details = []
    non_end_by_stream = []
    frame_by_stream = []
    for i in range(n):
        b = base.stream_results[i]
        c = cand.stream_results[i]
        if b.out_hash != c.out_hash:
            hash_diff_streams += 1
            if len(hash_diff_indices) < 20:
                hash_diff_indices.append(i)
            if len(hash_diff_details) < 20:
                row = {
                    "stream": i,
                    "base_hash": b.out_hash,
                    "cand_hash": c.out_hash,
                }
                if i < len(metas):
                    row.update(metas[i].as_dict())
                hash_diff_details.append(row)
        d_non_end = c.non_end_actions - b.non_end_actions
        d_frame = c.frame_count - b.frame_count
        non_end_delta += c.non_end_actions - b.non_end_actions
        frame_delta += c.frame_count - b.frame_count
        if d_non_end != 0:
            row = {
                "stream": i,
                "base_non_end": b.non_end_actions,
                "cand_non_end": c.non_end_actions,
                "delta": d_non_end,
            }
            if i < len(metas):
                row.update(metas[i].as_dict())
            non_end_by_stream.append(row)
        if d_frame != 0:
            row = {
                "stream": i,
                "base_frames": b.frame_count,
                "cand_frames": c.frame_count,
                "delta": d_frame,
            }
            if i < len(metas):
                row.update(metas[i].as_dict())
            frame_by_stream.append(row)

    non_end_by_stream.sort(key=lambda x: abs(x["delta"]), reverse=True)
    frame_by_stream.sort(key=lambda x: abs(x["delta"]), reverse=True)
    return {
        "compare_streams": n,
        "hash_diff_streams": hash_diff_streams,
        "hash_diff_rate": (hash_diff_streams / n) if n else 0.0,
        "hash_diff_indices": hash_diff_indices,
        "hash_diff_details": hash_diff_details,
        "non_end_delta": non_end_delta,
        "frame_delta": frame_delta,
        "non_end_delta_streams": non_end_by_stream[:20],
        "frame_delta_streams": frame_by_stream[:20],
        "elapsed_base": base.elapsed_sec,
        "elapsed_cand": cand.elapsed_sec,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Saiblo replay stability checker")
    ap.add_argument("--replay-dir", required=True, help="directory containing match_*.json")
    ap.add_argument("--binary", required=True, help="primary binary to run")
    ap.add_argument("--compare-binary", default="", help="optional candidate binary for 1x compare")
    ap.add_argument("--max-matches", type=int, default=5, help="max match_*.json files to load")
    ap.add_argument("--repeats", type=int, default=3, help="how many times to rerun --binary")
    ap.add_argument("--timeout-sec", type=int, default=120, help="timeout per stream process")
    ap.add_argument("--json-out", default="", help="optional path to save json summary")
    args = ap.parse_args()

    replay_dir = Path(args.replay_dir)
    binary = Path(args.binary)
    if not replay_dir.is_dir():
        print(f"[error] replay dir not found: {replay_dir}", file=sys.stderr)
        return 2
    if not binary.exists():
        print(f"[error] binary not found: {binary}", file=sys.stderr)
        return 2

    streams, metas = decode_streams(replay_dir, args.max_matches)
    if not streams:
        print("[error] no stdin streams decoded", file=sys.stderr)
        return 3

    repeats = max(1, args.repeats)
    summaries = [run_full(binary, streams, args.timeout_sec) for _ in range(repeats)]
    payload = {
        "meta": {
            "replay_dir": str(replay_dir),
            "binary": str(binary),
            "max_matches": args.max_matches,
            "repeats": repeats,
            "streams": len(streams),
            "stream_meta_sample": [m.as_dict() for m in metas[:20]],
        },
        "stability": summarize_repeats(summaries),
    }

    if args.compare_binary:
        cmp_bin = Path(args.compare_binary)
        if not cmp_bin.exists():
            print(f"[error] compare binary not found: {cmp_bin}", file=sys.stderr)
            return 2
        # 1x run compare to control cost.
        base = summaries[0]
        cand = run_full(cmp_bin, streams, args.timeout_sec)
        payload["compare"] = compare_once(base, cand, metas)
        payload["meta"]["compare_binary"] = str(cmp_bin)

    print(json.dumps(payload, ensure_ascii=True, indent=2))

    if args.json_out:
        out_path = Path(args.json_out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
