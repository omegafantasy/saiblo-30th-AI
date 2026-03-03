#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json

from autolab.evaluator import run_from_args


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Autolab batch evaluator with Elo")
    p.add_argument("--mode", choices=["gauntlet", "round_robin"], default="gauntlet")
    p.add_argument("--versions", default="", help="comma-separated version ids")
    p.add_argument("--challengers", default="", help="comma-separated challenger ids (gauntlet)")
    p.add_argument("--opponents", default="", help="comma-separated opponent ids (gauntlet)")
    p.add_argument("--games-per-pair", type=int, default=20, help="seeds per pair; each seed runs both seats")
    p.add_argument("--max-rounds", type=int, default=160)
    p.add_argument("--jobs", type=int, default=14)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--k-factor", type=float, default=20.0)
    p.add_argument("--base-rating", type=float, default=1500.0)
    p.add_argument("--auto-promote", action=argparse.BooleanOptionalAction, default=True)
    p.add_argument("--promote-min-delta", type=float, default=35.0)
    p.add_argument("--cpu-policy", choices=["all", "idle_only"], default="all")
    p.add_argument("--idle-threshold", type=float, default=0.02, help="busy ratio threshold for idle_only policy")
    p.add_argument("--idle-sample-sec", type=float, default=0.8, help="sampling window for idle core detection")
    p.add_argument("--pin-cpu", action=argparse.BooleanOptionalAction, default=True, help="pin worker processes to selected cores")
    p.add_argument("--runtime-scope", default="", help="optional runtime sub-scope, outputs under autolab/runtime/scopes/<scope>")
    p.add_argument("--write-latest", action=argparse.BooleanOptionalAction, default=True, help="whether to write latest.json in selected runtime scope")
    p.add_argument("--doc-out", default="", help="optional markdown output path")
    return p


def main() -> int:
    args = build_parser().parse_args()
    result = run_from_args(args)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
