# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Dual-game competitive AI development workspace for the Saiblo platform:
- **Game1 (蚁洋陷役2 / AntGame2)**: Turn-based ant colony strategy game — C++ AI implementations
- **Game2 (DeepClue)**: LLM-based mystery solving game — Python AI implementations

## Key Directories

- `Game1/Ant-Game/` — **Authoritative game code and rules** (upstream repo, single source of truth)
- `Game1/antgame_ai_cpp/` — C++ AI versions (v1–v4, sim, saiblo_v1)
- `Game2/deepclue_ai/` — Python AI versions (v1–v12, probe_fast)
- `Game2/DeepClueSDK-python/` — Game2 SDK
- `autolab/` — Batch evaluation framework (evaluator, match runner, registry, Elo ranking)
- `docs/` — Game analysis docs and parsed rule pages
- `past_AIs/` — Legacy AI implementations (ANTWar-AI, ANTWar-Logic) — reference only
- `saiblo_tools.py` — Saiblo platform HTTP API client

## Build Commands

### Game1 C++ AI

```bash
# Build a specific version (each version has its own Makefile)
cd Game1/antgame_ai_cpp/v1 && make

# Compiler: g++ -O2 -std=c++17 -Wall -Wextra -Wshadow -Wconversion
# Headers from: Game1/Ant-Game/game/include
```

### Package and run Game1 locally

```bash
cd Game1/Ant-Game
bash AI/package_ai.sh cpp_v1 /tmp/game1_cpp_v1_pkg
python3 tools/run_local_match.py --ai0 cpp_v1 --ai1 example --seed 7 --keep-dir /tmp/match_output
```

### Game1 local evaluation

```bash
python3 eval_cpp_local.py --games 10 --opponent greedy --swap-seats
```

### Autolab batch evaluation

```bash
python3 autolab_eval.py --mode round_robin --versions cpp_v1_current,greedy,random --games-per-pair 2 --jobs 4
python3 autolab_replay_analyze.py --latest
```

### Game2 batch evaluation

```bash
python3 Game2/tools/run_batch_eval.py
```

## Architecture

### Game1 execution patterns
- **C++ bridge** (v1): Python wrapper sends JSON state snapshots → C++ binary makes decisions
- **Pure C++** (v3): Direct stdin/stdout protocol implementation for Saiblo upload
- **Rollout-based** (v4): Experimental Monte Carlo variant

### Game2 execution pattern
- SDK communicates via binary length-prefixed JSON over stdin/stdout
- `call_llm()` SDK method for LLM-based planning and summarization

### Autolab system
- Version registry in `autolab/registry.json` (kind, executable, source path, enabled flag)
- Elo ratings stored in `autolab/runtime/latest.json`
- Automation controlled by `autolab/runtime/automation.paused` flag
- CPU limit: 8 cores for evaluation

### Configuration
- `config.example.json` — template (Saiblo API base, C++ AI path, Ant-Game dir)
- `config.local.json` — local overrides
- `config_runtime.py` — hierarchical JSON config loader
- `SAIBLO_BEARER` env var or `past_AIs/zdata.py` for platform auth tokens

## Important Caveats

- `Game1/Ant-Game` is the **sole authoritative source** for game rules and implementation — rule docs are reference only
- Legacy `autolab/`, `eval_cpp_local.py`, `ai_cpp_policy.py` paths may still point to old directories; verify before using for Game1
- Old Elo data and version iteration docs from `past_AIs/` do not reflect current Game1 state
