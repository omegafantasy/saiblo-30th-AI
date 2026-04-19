#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from autolab.replay_analysis import analyze_single_replay


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Analyze one downloaded Saiblo replay")
    parser.add_argument("--replay", required=True, help="path to downloaded replay json")
    parser.add_argument("--output", default="", help="optional json output path")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    replay_path = Path(args.replay).resolve()
    result = analyze_single_replay(replay_path)
    if args.output:
        output_path = Path(args.output).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
