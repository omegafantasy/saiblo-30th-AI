#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json

from autolab.replay_analysis import ReplayAnalysisConfig, run_replay_analysis


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Replay analyzer for autolab matches")
    p.add_argument("--scope", default="", help="runtime scope under autolab/runtime/scopes/<scope>")
    p.add_argument("--latest", action=argparse.BooleanOptionalAction, default=True, help="analyze latest.json of selected scope")
    p.add_argument("--matches", default="", help="explicit matches jsonl path; overrides --latest")
    p.add_argument("--max-matches", type=int, default=0, help="if >0, only analyze latest N matches from file")
    p.add_argument("--top-matches", type=int, default=12, help="how many notable matches to keep in report")
    p.add_argument("--output-json", default="", help="output json path; default autolab/runtime.../replay_analysis/<tag>_replay_analysis.json")
    p.add_argument("--output-md", default="", help="output markdown path; default autolab/runtime.../replay_analysis/<tag>_replay_analysis.md")
    return p


def main() -> int:
    args = build_parser().parse_args()
    cfg = ReplayAnalysisConfig(
        runtime_scope=args.scope,
        latest=bool(args.latest),
        matches_file=args.matches,
        max_matches=args.max_matches,
        top_matches=args.top_matches,
        output_json=args.output_json,
        output_md=args.output_md,
    )
    result = run_replay_analysis(cfg)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
