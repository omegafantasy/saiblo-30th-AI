#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import struct
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from autolab.game1_match_runner import (
    _close_stdin,
    _launch_ai,
    _packet,
    _read_exact,
    _terminate,
    _write_all,
    ensure_game_bin,
    stage_version,
)


ANT_GAME_DIR = ROOT / "Game1" / "Ant-Game"
REGISTRY_PATH = ROOT / "autolab" / "registry.json"
TIMEOUT_SECONDS = 20.0


def _read_game_packet(game: subprocess.Popen[bytes]) -> tuple[int, bytes]:
    deadline = time.monotonic() + TIMEOUT_SECONDS
    size = struct.unpack(">I", _read_exact(game.stdout, 4, game, "game packet length", deadline=deadline))[0]
    obj = struct.unpack(">i", _read_exact(game.stdout, 4, game, "game packet object", deadline=deadline))[0]
    payload = _read_exact(game.stdout, size, game, "game packet payload", deadline=deadline)
    return obj, payload


def _read_ai_packet(ai: subprocess.Popen[bytes], label: str) -> tuple[bytes, int]:
    start = time.monotonic()
    deadline = start + TIMEOUT_SECONDS
    size = struct.unpack(">I", _read_exact(ai.stdout, 4, ai, f"{label} packet length", deadline=deadline))[0]
    payload = _read_exact(ai.stdout, size, ai, f"{label} packet payload", deadline=deadline)
    elapsed_ms = max(0, int(math.ceil((time.monotonic() - start) * 1000.0)))
    return struct.pack(">I", size) + payload, elapsed_ms


def _summarize(samples: list[int]) -> dict[str, int | float]:
    if not samples:
        return {}
    ordered = sorted(samples)

    def percentile(p: float) -> int:
        index = min(len(ordered) - 1, max(0, int(math.ceil(len(ordered) * p)) - 1))
        return ordered[index]

    return {
        "n": len(ordered),
        "avg_ms": round(sum(ordered) / len(ordered), 2),
        "p95_ms": percentile(0.95),
        "p99_ms": percentile(0.99),
        "max_ms": ordered[-1],
        "gt100": sum(1 for item in ordered if item > 100),
        "gt200": sum(1 for item in ordered if item > 200),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe Game1 AI per-turn decision latency")
    parser.add_argument("--a", required=True, help="registry version id for seat 0")
    parser.add_argument("--b", required=True, help="registry version id for seat 1")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--max-listens", type=int, default=120, help="stop after this many AI replies")
    args = parser.parse_args()

    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    versions = {str(item["id"]): item for item in registry.get("versions", [])}
    if args.a not in versions or args.b not in versions:
        raise SystemExit(f"unknown versions: {args.a}, {args.b}")

    game_bin = ensure_game_bin(ANT_GAME_DIR)
    with tempfile.TemporaryDirectory(prefix="game1_ai_time_probe_") as temp_root:
        temp_dir = Path(temp_root)
        a_dir = temp_dir / "a"
        b_dir = temp_dir / "b"
        stage_version(ANT_GAME_DIR, versions[args.a], a_dir)
        stage_version(ANT_GAME_DIR, versions[args.b], b_dir)

        ai0 = _launch_ai(a_dir, temp_dir / "ai0.stderr.log")
        ai1 = _launch_ai(b_dir, temp_dir / "ai1.stderr.log")
        game_stderr = (temp_dir / "game.stderr.log").open("wb")
        game = subprocess.Popen(
            [str(game_bin)],
            cwd=game_bin.parent.parent,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=game_stderr,
        )

        timings = {0: [], 1: []}
        listen_count = 0
        status = "ended"
        try:
            init = {
                "player_list": [1, 1],
                "player_num": 2,
                "config": {"random_seed": args.seed, "max_rounds": 180},
                "replay": str(temp_dir / "replay.json"),
            }
            _write_all(game.stdin, _packet(init))

            while True:
                obj, payload = _read_game_packet(game)
                if obj in (0, 1):
                    _write_all((ai0 if obj == 0 else ai1).stdin, payload)
                    continue

                message = json.loads(payload.decode("utf-8"))
                if isinstance(message, dict) and "player" in message and "content" in message:
                    for player, content in zip(message["player"], message["content"]):
                        _write_all((ai0 if int(player) == 0 else ai1).stdin, content.encode("utf-8"))
                if isinstance(message, dict) and message.get("listen"):
                    for player in message["listen"]:
                        target_ai = ai0 if int(player) == 0 else ai1
                        packet, elapsed_ms = _read_ai_packet(target_ai, f"ai{player}")
                        timings[int(player)].append(elapsed_ms)
                        reply = {
                            "player": int(player),
                            "content": packet.decode("latin1"),
                            "time": min(elapsed_ms, 200),
                        }
                        _write_all(game.stdin, _packet(reply))
                        listen_count += 1
                        if listen_count >= args.max_listens:
                            status = "truncated"
                            raise StopIteration
                if isinstance(message, dict) and "end_state" in message:
                    break
        except StopIteration:
            pass
        finally:
            _close_stdin(ai0)
            _close_stdin(ai1)
            _terminate(ai0)
            _terminate(ai1)
            _terminate(game)
            game_stderr.close()

    result = {
        "pair": [args.a, args.b],
        "seed": args.seed,
        "status": status,
        "seat0": _summarize(timings[0]),
        "seat1": _summarize(timings[1]),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
