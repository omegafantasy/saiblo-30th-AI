#!/usr/bin/env python3
"""
Locate first divergent output frame/line between two binaries on Saiblo stdinRecords.
"""

from __future__ import annotations

import argparse
import base64
import glob
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

OPCODE_NAMES = {
    1: "MOVE_ARMY",
    2: "MOVE_GENERAL",
    3: "UPGRADE_GENERAL",
    4: "USE_GENERAL_SKILL",
    5: "UPGRADE_TECH",
    6: "USE_SUPERWEAPON",
    7: "CALL_GENERAL",
    8: "END",
}


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
        msg = outer.get("message")
        if not isinstance(msg, str):
            continue
        try:
            inner = json.loads(msg)
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


def run_binary(binary: Path, stream: bytes, timeout_sec: int) -> bytes:
    proc = subprocess.Popen(
        [str(binary)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    out, _ = proc.communicate(stream, timeout=timeout_sec)
    return out


def parse_output_frames(blob: bytes) -> List[List[str]]:
    frames: List[List[str]] = []
    idx = 0
    n = len(blob)
    while idx + 4 <= n:
        payload_len = int.from_bytes(blob[idx : idx + 4], byteorder="big", signed=False)
        idx += 4
        if payload_len < 0 or idx + payload_len > n:
            break
        payload = blob[idx : idx + payload_len]
        idx += payload_len
        lines = []
        for line in payload.decode("utf-8", errors="ignore").splitlines():
            s = line.strip()
            if s:
                lines.append(s)
        frames.append(lines)
    return frames


def frames_signature(frames: List[List[str]]) -> Tuple[Tuple[str, ...], ...]:
    return tuple(tuple(lines) for lines in frames)


def run_frames_with_stability(
    binary: Path, stream: bytes, timeout_sec: int, runs: int
) -> Tuple[List[List[str]], bool]:
    runs = max(1, runs)
    first_frames: List[List[str]] = []
    first_sig: Tuple[Tuple[str, ...], ...] = ()
    stable = True
    for i in range(runs):
        out = run_binary(binary, stream, timeout_sec)
        frames = parse_output_frames(out)
        sig = frames_signature(frames)
        if i == 0:
            first_frames = frames
            first_sig = sig
        elif sig != first_sig:
            stable = False
    return first_frames, stable


def find_line_in_future_frames(frames: List[List[str]], frame_index: int, line: str, lookahead: int) -> int:
    if not line or lookahead <= 0:
        return -1
    n = len(frames)
    for off in range(1, lookahead + 1):
        j = frame_index + off
        if j < 0 or j >= n:
            break
        if line in frames[j]:
            return off
    return -1


def parse_opcode(line: str) -> Tuple[int, str]:
    if not line:
        return -1, "UNKNOWN"
    parts = line.split()
    if not parts:
        return -1, "UNKNOWN"
    try:
        op = int(parts[0])
    except Exception:
        return -1, "UNKNOWN"
    return op, OPCODE_NAMES.get(op, "UNKNOWN")


def first_frame_diff(base_frames: List[List[str]], cand_frames: List[List[str]]) -> dict:
    nf = min(len(base_frames), len(cand_frames))
    for fi in range(nf):
        a = base_frames[fi]
        b = cand_frames[fi]
        if a == b:
            continue
        nl = min(len(a), len(b))
        line_idx = -1
        for li in range(nl):
            if a[li] != b[li]:
                line_idx = li
                break
        if line_idx < 0:
            line_idx = nl

        def pick(lines: List[str], idx: int) -> str:
            if idx < 0 or idx >= len(lines):
                return ""
            return lines[idx]

        base_line = pick(a, line_idx)
        cand_line = pick(b, line_idx)
        shared = len(set(a) & set(b))
        union = len(set(a) | set(b))
        jaccard = (shared / union) if union > 0 else 1.0

        return {
            "frame_index": fi,
            "line_index": line_idx,
            "base_frame_lines": len(a),
            "cand_frame_lines": len(b),
            "diff_kind": "replace_or_shift",
            "base_line": base_line,
            "cand_line": cand_line,
            "base_line_present_in_cand_frame": bool(base_line and base_line in b),
            "cand_line_present_in_base_frame": bool(cand_line and cand_line in a),
            "shared_line_count": shared,
            "union_line_count": union,
            "frame_jaccard": jaccard,
            "base_frame_preview": a[:12],
            "cand_frame_preview": b[:12],
        }

    if len(base_frames) != len(cand_frames):
        return {
            "frame_index": nf,
            "line_index": 0,
            "base_frame_lines": len(base_frames[nf]) if nf < len(base_frames) else 0,
            "cand_frame_lines": len(cand_frames[nf]) if nf < len(cand_frames) else 0,
            "diff_kind": "frame_count_diff",
            "base_line": "",
            "cand_line": "",
            "base_frame_preview": base_frames[nf][:12] if nf < len(base_frames) else [],
            "cand_frame_preview": cand_frames[nf][:12] if nf < len(cand_frames) else [],
            "frame_count_diff": len(cand_frames) - len(base_frames),
        }
    return {}


def parse_stream_filter(raw: str) -> List[int]:
    if not raw:
        return []
    out: List[int] = []
    for tok in raw.split(","):
        tok = tok.strip()
        if not tok:
            continue
        out.append(int(tok))
    return sorted(set(i for i in out if i >= 0))


def main() -> int:
    ap = argparse.ArgumentParser(description="Locate first output diff per replay stream")
    ap.add_argument("--replay-dir", required=True, help="directory containing match_*.json")
    ap.add_argument("--binary", required=True, help="base binary")
    ap.add_argument("--compare-binary", required=True, help="candidate binary")
    ap.add_argument("--max-matches", type=int, default=5, help="max match_*.json files to load")
    ap.add_argument("--timeout-sec", type=int, default=120, help="timeout per stream process")
    ap.add_argument("--stability-runs", type=int, default=1, help="reruns per binary per stream for stability check")
    ap.add_argument("--lookahead-frames", type=int, default=2, help="future-frame window for delayed-line detection")
    ap.add_argument("--stream-filter", default="", help="optional comma-separated stream indices")
    ap.add_argument("--json-out", default="", help="optional path to save json")
    args = ap.parse_args()

    replay_dir = Path(args.replay_dir)
    base_bin = Path(args.binary)
    cand_bin = Path(args.compare_binary)

    if not replay_dir.is_dir():
        print(f"[error] replay dir not found: {replay_dir}", file=sys.stderr)
        return 2
    if not base_bin.exists():
        print(f"[error] binary not found: {base_bin}", file=sys.stderr)
        return 2
    if not cand_bin.exists():
        print(f"[error] compare binary not found: {cand_bin}", file=sys.stderr)
        return 2

    streams, metas = decode_streams(replay_dir, args.max_matches)
    if not streams:
        print("[error] no stdin streams decoded", file=sys.stderr)
        return 3

    filter_indices = parse_stream_filter(args.stream_filter)
    target_indices = filter_indices if filter_indices else list(range(len(streams)))

    diffs = []
    unstable = []
    for i in target_indices:
        if i < 0 or i >= len(streams):
            continue
        s = streams[i]
        base_frames, base_stable = run_frames_with_stability(base_bin, s, args.timeout_sec, args.stability_runs)
        cand_frames, cand_stable = run_frames_with_stability(cand_bin, s, args.timeout_sec, args.stability_runs)
        if not base_stable or not cand_stable:
            row = {
                "stream": i,
                "base_stable": base_stable,
                "cand_stable": cand_stable,
                "stability_runs": max(1, args.stability_runs),
            }
            if i < len(metas):
                row.update(metas[i].as_dict())
            unstable.append(row)
            continue
        d = first_frame_diff(base_frames, cand_frames)
        if d:
            row = {
                "stream": i,
                "base_frames": len(base_frames),
                "cand_frames": len(cand_frames),
            }
            if i < len(metas):
                row.update(metas[i].as_dict())
            row.update(d)
            base_op, base_op_name = parse_opcode(row.get("base_line", ""))
            cand_op, cand_op_name = parse_opcode(row.get("cand_line", ""))
            row["base_opcode"] = base_op
            row["cand_opcode"] = cand_op
            row["base_opcode_name"] = base_op_name
            row["cand_opcode_name"] = cand_op_name
            row["semantic_diff_kind"] = "unknown"
            frame_index = int(row.get("frame_index", -1))
            lookahead = max(0, int(args.lookahead_frames))
            base_line = row.get("base_line", "")
            cand_line = row.get("cand_line", "")
            base_ahead = find_line_in_future_frames(cand_frames, frame_index, base_line, lookahead)
            cand_ahead = find_line_in_future_frames(base_frames, frame_index, cand_line, lookahead)
            row["base_line_ahead_in_cand_frames"] = base_ahead
            row["cand_line_ahead_in_base_frames"] = cand_ahead

            base_in_cand = bool(row.get("base_line_present_in_cand_frame"))
            cand_in_base = bool(row.get("cand_line_present_in_base_frame"))
            if row["base_line"] and not row["cand_line"]:
                row["diff_kind"] = "extra_line_in_base"
                row["semantic_diff_kind"] = "line_deleted_in_cand"
            elif row["cand_line"] and not row["base_line"]:
                row["diff_kind"] = "extra_line_in_cand"
                row["semantic_diff_kind"] = "line_inserted_in_cand"
            else:
                if base_op != cand_op:
                    row["semantic_diff_kind"] = "opcode_change"
                elif base_in_cand and cand_in_base:
                    if base_op == 1:
                        row["semantic_diff_kind"] = "intra_frame_reorder_move_army"
                    else:
                        row["semantic_diff_kind"] = "intra_frame_reorder_same_opcode"
                elif base_in_cand or cand_in_base:
                    row["semantic_diff_kind"] = "partial_intra_frame_shift"
                else:
                    row["semantic_diff_kind"] = "line_replace_same_opcode"
                if base_op == 7:
                    if base_ahead > 0:
                        row["semantic_diff_kind"] = "call_general_delayed_in_cand"
                    elif not base_in_cand:
                        row["semantic_diff_kind"] = "call_general_missing_in_cand"
                elif cand_op == 7:
                    if cand_ahead > 0:
                        row["semantic_diff_kind"] = "call_general_delayed_in_base"
                    elif not cand_in_base:
                        row["semantic_diff_kind"] = "call_general_missing_in_base"
            diffs.append(row)

    compared_streams = len(target_indices) - len(unstable)
    payload = {
        "meta": {
            "replay_dir": str(replay_dir),
            "binary": str(base_bin),
            "compare_binary": str(cand_bin),
            "max_matches": args.max_matches,
            "stability_runs": max(1, args.stability_runs),
            "lookahead_frames": max(0, int(args.lookahead_frames)),
            "streams_total": len(streams),
            "stream_filter": target_indices,
        },
        "summary": {
            "checked_streams": len(target_indices),
            "unstable_streams": len(unstable),
            "compared_streams": compared_streams,
            "diff_streams": len(diffs),
            "same_streams": compared_streams - len(diffs),
        },
        "diffs": diffs,
        "unstable": unstable,
    }

    print(json.dumps(payload, ensure_ascii=True, indent=2))
    if args.json_out:
        out_path = Path(args.json_out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
