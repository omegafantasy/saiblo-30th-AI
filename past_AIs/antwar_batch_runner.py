"""
ANTWar-AI Self-Play Batch Runner

Runs ANTWar-AI self-play matches via the ANTWar-Logic judger protocol.
Captures stderr (AI debug output) and replays for statistical analysis.

Protocol:
  Logic → Runner: 4-byte len(n) + 4-byte object_id + n bytes payload
  AI → Runner:    4-byte len(n) + n bytes payload (no object prefix)
  Runner → AI:    raw text (OJ format), no binary prefix
  Runner → Logic:  4-byte len(n) + n bytes JSON

Usage:
    python antwar_batch_runner.py [--matches N] [--jobs J] [--output-dir DIR]
"""

import argparse
import json
import os
import struct
import subprocess
import sys
import threading
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()
LOGIC_BIN = SCRIPT_DIR / "ANTWar-Logic" / "output" / "main.exe"
AI_BIN = SCRIPT_DIR / "ANTWar-AI" / "main"
DEFAULT_OUTPUT = SCRIPT_DIR / "antwar_matches"


def send_to_logic(stdin, msg_str: str):
    """Send length-prefixed message to logic."""
    encoded = msg_str.encode("UTF-8")
    stdin.write(struct.pack(">I", len(encoded)) + encoded)
    stdin.flush()


def recv_from_logic(stdout):
    """
    Read from logic: 4-byte len(n) + 4-byte object_id + n bytes payload.
    Returns (object_id, payload_bytes).
    """
    raw_len = stdout.read(4)
    if len(raw_len) < 4:
        raise EOFError("EOF reading length from logic")
    n = struct.unpack(">I", raw_len)[0]
    data = stdout.read(4 + n)
    if len(data) < 4 + n:
        raise EOFError(f"Short read from logic (expected {4+n}, got {len(data)})")
    obj_id = struct.unpack(">i", data[:4])[0]
    return obj_id, data[4:]


def recv_from_ai(stdout):
    """
    Read from AI: 4-byte len(n) + n bytes payload.
    Returns payload as string.
    """
    raw_len = stdout.read(4)
    if len(raw_len) < 4:
        raise EOFError("EOF reading length from AI")
    n = struct.unpack(">I", raw_len)[0]
    data = stdout.read(n)
    if len(data) < n:
        raise EOFError(f"Short read from AI (expected {n}, got {len(data)})")
    return data.decode("UTF-8")


def drain_stderr(stream, lines: list):
    """Capture stderr into list."""
    try:
        for line in stream:
            if isinstance(line, bytes):
                line = line.decode("utf-8", errors="replace")
            lines.append(line.rstrip("\n"))
    except Exception:
        pass


def run_single_match(match_id: int, seed: int, output_dir: Path, timeout_s: int = 300):
    """Run a single self-play match."""
    match_dir = output_dir / f"match_{match_id:04d}"
    match_dir.mkdir(parents=True, exist_ok=True)

    result = {
        "match_id": match_id, "seed": seed, "status": "unknown",
        "rounds": 0, "winner": -1, "end_info": None, "error": None,
    }

    replay_path = str(match_dir / "replay.json").replace("\\", "/")
    init_msg = json.dumps({
        "player_list": [1, 1], "player_num": 2,
        "config": {"random_seed": seed}, "replay": replay_path,
    })

    stderr_lines = [[], []]
    logic_proc = None
    ai_procs = [None, None]
    stderr_threads = []

    try:
        logic_proc = subprocess.Popen(
            [str(LOGIC_BIN)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        for i in range(2):
            ai_procs[i] = subprocess.Popen(
                [str(AI_BIN)],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            t = threading.Thread(target=drain_stderr, args=(ai_procs[i].stderr, stderr_lines[i]))
            t.daemon = True
            t.start()
            stderr_threads.append(t)

        logic_out = logic_proc.stdout
        logic_in = logic_proc.stdin

        # 1. Send init to logic
        send_to_logic(logic_in, init_msg)

        # 2. Read init response from logic
        _, payload = recv_from_logic(logic_out)
        init_output = json.loads(payload)
        if "end_info" in init_output:
            result["status"] = "init_end"
            return result

        # 3. Send init strings to AIs (raw text, no binary prefix)
        for i, msg in zip(init_output["player"], init_output["content"]):
            ai_procs[i].stdin.write(msg.encode("UTF-8"))
            ai_procs[i].stdin.flush()

        # Game loop
        round_count = 0
        start_time = time.time()

        while True:
            if time.time() - start_time > timeout_s:
                result["status"] = "timeout"
                result["error"] = f"Timeout after {timeout_s}s at round {round_count}"
                break

            for current_player in [0, 1]:
                other_player = 1 - current_player

                # A. Read config message from logic (config_to_judger)
                _, cfg_payload = recv_from_logic(logic_out)
                cfg = json.loads(cfg_payload)
                if "end_info" in cfg:
                    result["status"] = "completed"
                    result["end_info"] = cfg.get("end_info")
                    raise StopIteration

                # B. Read AI's response (operations)
                ai_response = recv_from_ai(ai_procs[current_player].stdout)

                # C. Send AI's response to logic
                to_logic = json.dumps({
                    "player": current_player,
                    "content": ai_response,
                    "time": 2785,
                })
                send_to_logic(logic_in, to_logic)

                # D. Read listen state from logic (2nd msg from listen_player)
                obj_id, payload = recv_from_logic(logic_out)
                if obj_id == -1:
                    try:
                        msg = json.loads(payload)
                        if "end_info" in msg:
                            result["status"] = "completed"
                            result["end_info"] = msg.get("end_info")
                            raise StopIteration
                    except json.JSONDecodeError:
                        pass

                # E. Read operation forward to other player
                obj_id, payload = recv_from_logic(logic_out)
                if obj_id == -1:
                    try:
                        msg = json.loads(payload)
                        if "end_info" in msg:
                            result["status"] = "completed"
                            result["end_info"] = msg.get("end_info")
                            raise StopIteration
                    except json.JSONDecodeError:
                        pass
                else:
                    # Forward raw OJ text to other AI (no binary prefix)
                    ai_procs[other_player].stdin.write(payload)
                    ai_procs[other_player].stdin.flush()

            # F. Read round state from logic (dump_round_state)
            _, payload = recv_from_logic(logic_out)
            round_output = json.loads(payload)
            if "end_info" in round_output:
                result["status"] = "completed"
                result["end_info"] = round_output.get("end_info")
                break

            # Send round state to AIs (raw text)
            for i, msg in zip(round_output["player"], round_output["content"]):
                ai_procs[i].stdin.write(msg.encode("UTF-8"))
                ai_procs[i].stdin.flush()

            round_count += 1

    except StopIteration:
        pass
    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)
    finally:
        result["rounds"] = round_count
        for proc in [logic_proc] + ai_procs:
            if proc:
                try:
                    proc.kill()
                    proc.wait(timeout=5)
                except Exception:
                    pass
        for t in stderr_threads:
            t.join(timeout=5)
        for i in range(2):
            with open(match_dir / f"ai{i}_stderr.txt", "w", encoding="utf-8") as f:
                f.write("\n".join(stderr_lines[i]))
        with open(match_dir / "result.json", "w") as f:
            json.dump(result, f, indent=2, default=str)

    return result


def run_match_wrapper(args):
    return run_single_match(args[0], args[1], Path(args[2]), args[3])


def main():
    parser = argparse.ArgumentParser(description="ANTWar-AI Self-Play Batch Runner")
    parser.add_argument("--matches", type=int, default=200, help="Number of matches")
    parser.add_argument("--jobs", type=int, default=8, help="Parallel jobs")
    parser.add_argument("--output-dir", type=str, default=str(DEFAULT_OUTPUT))
    parser.add_argument("--seed-start", type=int, default=1000, help="Starting seed")
    parser.add_argument("--timeout", type=int, default=300, help="Per-match timeout (s)")
    parser.add_argument("--test", action="store_true", help="Run 2 test matches")
    args = parser.parse_args()

    if args.test:
        args.matches = 2
        args.jobs = 1

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    ai_bin = AI_BIN
    if not ai_bin.exists():
        alt = ai_bin.with_suffix(".exe")
        if alt.exists():
            ai_bin = alt
        else:
            print(f"ERROR: AI binary not found at {ai_bin}")
            sys.exit(1)
    if not LOGIC_BIN.exists():
        print(f"ERROR: Logic binary not found at {LOGIC_BIN}")
        sys.exit(1)

    # Update global AI_BIN if needed
    if ai_bin != AI_BIN:
        import antwar_batch_runner
        antwar_batch_runner.AI_BIN = ai_bin

    print(f"ANTWar-AI Self-Play Batch Runner")
    print(f"  Logic: {LOGIC_BIN}")
    print(f"  AI:    {ai_bin}")
    print(f"  Matches: {args.matches}, Jobs: {args.jobs}")
    print(f"  Output:  {output_dir}")
    print()

    match_params = [
        (i, args.seed_start + i * 7, str(output_dir), args.timeout)
        for i in range(args.matches)
    ]

    results = []
    completed = 0
    errors = 0
    start_time = time.time()

    if args.jobs == 1:
        for params in match_params:
            result = run_match_wrapper(params)
            results.append(result)
            completed += 1
            if result["status"] == "error":
                errors += 1
                print(f"  Match {result['match_id']}: ERROR - {result['error']}")
            else:
                print(f"  Match {result['match_id']}: {result['status']} ({result['rounds']} rounds)")
    else:
        with ProcessPoolExecutor(max_workers=args.jobs) as executor:
            futures = {executor.submit(run_match_wrapper, p): p[0] for p in match_params}
            for future in as_completed(futures):
                result = future.result()
                results.append(result)
                completed += 1
                if result["status"] == "error":
                    errors += 1
                if completed % 10 == 0 or completed == args.matches:
                    elapsed = time.time() - start_time
                    rate = completed / elapsed if elapsed > 0 else 0
                    print(f"  Progress: {completed}/{args.matches} ({rate:.1f} matches/s, {errors} errors)")

    elapsed = time.time() - start_time
    print(f"\nDone: {completed} matches in {elapsed:.1f}s ({errors} errors)")

    summary_path = output_dir / "batch_summary.json"
    with open(summary_path, "w") as f:
        json.dump({
            "total_matches": args.matches, "completed": completed,
            "errors": errors, "elapsed_seconds": elapsed,
            "seed_start": args.seed_start, "results": results,
        }, f, indent=2, default=str)
    print(f"Summary saved to {summary_path}")


if __name__ == "__main__":
    main()
