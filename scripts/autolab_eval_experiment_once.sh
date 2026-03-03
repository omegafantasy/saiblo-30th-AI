#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="/www"
PY_BIN="${PY_BIN:-$(command -v python3 || command -v python || true)}"
EVAL_SCRIPT="$ROOT_DIR/autolab_eval.py"
DOC_OUT="${EXPERIMENT_DOC_OUT:-$ROOT_DIR/docs/iter_eval_latest.md}"
RUNTIME_SCOPE="${EXPERIMENT_RUNTIME_SCOPE:-iter}"
JOBS="${EXPERIMENT_JOBS:-14}"
CPU_POLICY="${EXPERIMENT_CPU_POLICY:-all}"
ALLOW_ARG_OVERRIDE="${EXPERIMENT_ALLOW_ARG_OVERRIDE:-0}"

if [[ -z "$PY_BIN" || ! -x "$PY_BIN" ]]; then
  echo "missing python interpreter" >&2
  exit 1
fi
if [[ ! -f "$EVAL_SCRIPT" ]]; then
  echo "missing eval script: $EVAL_SCRIPT" >&2
  exit 1
fi

# Iteration evaluation is isolated from production:
# - no champion auto-promote
# - write results only in runtime scope 'iter' by default
#
# Priority policy:
# - defaults to high parallelism (`JOBS=14`, `CPU_POLICY=all`)
# - by default, command-line `--jobs/--cpu-policy` are ignored to prevent
#   accidental low-parallel runs from agent prompts
ARGS=()
if [[ "$ALLOW_ARG_OVERRIDE" == "1" ]]; then
  ARGS=("$@")
else
  skip_next=0
  for arg in "$@"; do
    if [[ "$skip_next" == "1" ]]; then
      skip_next=0
      continue
    fi
    case "$arg" in
      --jobs|--cpu-policy)
        skip_next=1
        ;;
      --jobs=*|--cpu-policy=*)
        ;;
      *)
        ARGS+=("$arg")
        ;;
    esac
  done
fi

"$PY_BIN" "$EVAL_SCRIPT" \
  --mode gauntlet \
  --games-per-pair "${EXPERIMENT_GAMES_PER_PAIR:-6}" \
  --max-rounds "${EXPERIMENT_MAX_ROUNDS:-180}" \
  --jobs "$JOBS" \
  --cpu-policy "$CPU_POLICY" \
  --idle-threshold "${EXPERIMENT_IDLE_THRESHOLD:-0.03}" \
  --idle-sample-sec "${EXPERIMENT_IDLE_SAMPLE_SEC:-0.8}" \
  --pin-cpu \
  --no-auto-promote \
  --runtime-scope "$RUNTIME_SCOPE" \
  --write-latest \
  --doc-out "$DOC_OUT" \
  "${ARGS[@]}"
