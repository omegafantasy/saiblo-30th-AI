#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
EVAL_SCRIPT = ROOT_DIR / "autolab_eval.py"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Periodic scheduler for autolab evaluations")
    p.add_argument("--interval-min", type=float, default=30.0, help="minutes between cycles")
    p.add_argument("--cycles", type=int, default=0, help="0 means infinite loop")
    p.add_argument("--stop-on-error", action="store_true")
    p.add_argument("--eval-args", default="", help="args forwarded to autolab_eval.py")
    return p


def main() -> int:
    args = build_parser().parse_args()
    interval_sec = max(1.0, args.interval_min * 60.0)
    cycle = 0
    while True:
        cycle += 1
        cmd = [sys.executable, str(EVAL_SCRIPT)]
        if args.eval_args.strip():
            cmd.extend(args.eval_args.strip().split())
        print(f"[autolab-schedule] cycle={cycle} cmd={' '.join(cmd)}", flush=True)
        ret = subprocess.run(cmd).returncode
        if ret != 0 and args.stop_on_error:
            return ret
        if args.cycles > 0 and cycle >= args.cycles:
            return 0
        time.sleep(interval_sec)


if __name__ == "__main__":
    raise SystemExit(main())

