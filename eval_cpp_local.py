#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib
import json
import os
import random
import subprocess
import sys
from multiprocessing import Pool
from pathlib import Path
from typing import Callable, Tuple

from config_runtime import get_cfg

ROOT_DIR = Path(__file__).resolve().parent
ANT_GAME_DIR = ROOT_DIR / "Ant-Game"
if str(ANT_GAME_DIR) not in sys.path:
    sys.path.insert(0, str(ANT_GAME_DIR))
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from ai_cpp_policy import policy as cpp_policy
from logic.runner import run_match

AI = Callable[[int, int, object], list[list[int]]]


def load_ai(name: str) -> AI:
    mod = importlib.import_module(f"AI.ai_{name}")
    return getattr(mod, "policy")


def ensure_cpp_binary(force_build: bool = False) -> str:
    exe = os.environ.get("CPP_AI_EXE", str(get_cfg("cpp_ai.exe", str(ROOT_DIR / "ai_cpp/v1" / "ai_v1"))))
    if force_build or not os.path.isfile(exe):
        subprocess.run(["make", "-C", str(ROOT_DIR / "ai_cpp/v1")], check=True)
    if not os.path.isfile(exe):
        raise FileNotFoundError(f"cpp ai executable not found: {exe}")
    return exe


def one_game(args: Tuple[int, int, str, bool]) -> dict:
    seed, rounds, opponent_name, swap_seats = args

    opp_policy = load_ai(opponent_name)

    result = {
        "seed": seed,
        "games": 0,
        "cpp_win": 0,
        "cpp_lose": 0,
        "draw": 0,
    }

    winner0, _ = run_match(
        cpp_policy,
        opp_policy,
        seed=seed,
        max_rounds=rounds,
        p0_name="cpp_v1",
        p1_name=opponent_name,
    )
    result["games"] += 1
    if winner0 == 0:
        result["cpp_win"] += 1
    elif winner0 == 1:
        result["cpp_lose"] += 1
    else:
        result["draw"] += 1

    if swap_seats:
        winner1, _ = run_match(
            opp_policy,
            cpp_policy,
            seed=seed + 1000003,
            max_rounds=rounds,
            p0_name=opponent_name,
            p1_name="cpp_v1",
        )
        result["games"] += 1
        if winner1 == 1:
            result["cpp_win"] += 1
        elif winner1 == 0:
            result["cpp_lose"] += 1
        else:
            result["draw"] += 1

    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Root-level local batch evaluation for C++ AI")
    parser.add_argument("--games", type=int, default=10, help="number of seeds")
    parser.add_argument("--rounds", type=int, default=120, help="max rounds per match")
    parser.add_argument("--opponent", default="greedy", help="AI name in Ant-Game/AI/ai_{name}.py")
    parser.add_argument("--swap-seats", action="store_true", help="evaluate both seats")
    parser.add_argument("--jobs", type=int, default=1, help="parallel workers")
    parser.add_argument("--seed", type=int, default=0, help="base random seed")
    parser.add_argument("--build", action="store_true", help="force build C++ binary first")
    args = parser.parse_args()

    ensure_cpp_binary(force_build=args.build)

    random.seed(args.seed)
    seeds = [random.randint(1, 10**9) for _ in range(args.games)]
    tasks = [(s, args.rounds, args.opponent, args.swap_seats) for s in seeds]

    if args.jobs > 1:
        with Pool(args.jobs) as pool:
            rows = pool.map(one_game, tasks)
    else:
        rows = [one_game(t) for t in tasks]

    summary = {
        "games": sum(x["games"] for x in rows),
        "cpp_win": sum(x["cpp_win"] for x in rows),
        "cpp_lose": sum(x["cpp_lose"] for x in rows),
        "draw": sum(x["draw"] for x in rows),
    }
    summary["win_rate"] = (summary["cpp_win"] / summary["games"]) if summary["games"] else 0.0
    summary["lose_rate"] = (summary["cpp_lose"] / summary["games"]) if summary["games"] else 0.0

    print(json.dumps({"config": vars(args), "summary": summary}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
