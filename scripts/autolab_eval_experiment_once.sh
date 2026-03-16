#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="/www"
source "$ROOT_DIR/scripts/automation_pause.sh"
PY_BIN="${PY_BIN:-$(command -v python3 || command -v python || true)}"
EVAL_SCRIPT="$ROOT_DIR/autolab_eval.py"
REPLAY_ANALYZE_SCRIPT="$ROOT_DIR/autolab_replay_analyze.py"
DOC_OUT="${EXPERIMENT_DOC_OUT:-$ROOT_DIR/docs/generated/iter_eval_latest.md}"
RUNTIME_SCOPE="${EXPERIMENT_RUNTIME_SCOPE:-iter}"
JOBS="${EXPERIMENT_JOBS:-8}"
JOBS_CAP="${AUTOMATION_MAX_JOBS_CAP:-8}"
CPU_POLICY="${EXPERIMENT_CPU_POLICY:-all}"
ALLOW_ARG_OVERRIDE="${EXPERIMENT_ALLOW_ARG_OVERRIDE:-0}"
REPLAY_ANALYZE="${EXPERIMENT_REPLAY_ANALYZE:-1}"

if automation_is_paused; then
  echo "experiment eval paused by $(automation_pause_file)" >&2
  exit 0
fi

if [[ "$JOBS" =~ ^[0-9]+$ ]] && [[ "$JOBS_CAP" =~ ^[0-9]+$ ]] && [[ "$JOBS" -gt "$JOBS_CAP" ]]; then
  JOBS="$JOBS_CAP"
fi

if [[ -z "$PY_BIN" || ! -x "$PY_BIN" ]]; then
  echo "missing python interpreter" >&2
  exit 1
fi
if [[ ! -f "$EVAL_SCRIPT" ]]; then
  echo "missing eval script: $EVAL_SCRIPT" >&2
  exit 1
fi
if [[ "$REPLAY_ANALYZE" == "1" && ! -f "$REPLAY_ANALYZE_SCRIPT" ]]; then
  echo "missing replay analyzer script: $REPLAY_ANALYZE_SCRIPT" >&2
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

if [[ "$REPLAY_ANALYZE" == "1" ]]; then
  SCOPE_LABEL="${RUNTIME_SCOPE:-production}"
  RUNTIME_DIR="$ROOT_DIR/autolab/runtime"
  if [[ -n "$RUNTIME_SCOPE" ]]; then
    RUNTIME_DIR="$RUNTIME_DIR/scopes/$RUNTIME_SCOPE"
  fi
  REPORT_DIR="$RUNTIME_DIR/replay_analysis"
  DOC_REPLAY_DIR="$ROOT_DIR/docs/generated/replay_analysis"
  mkdir -p "$REPORT_DIR" "$DOC_REPLAY_DIR"
  "$PY_BIN" "$REPLAY_ANALYZE_SCRIPT" \
    --scope "$RUNTIME_SCOPE" \
    --latest \
    --top-matches "${EXPERIMENT_REPLAY_TOP_MATCHES:-12}" \
    --max-matches "${EXPERIMENT_REPLAY_MAX_MATCHES:-0}" \
    >/dev/null
  if [[ -f "$REPORT_DIR/latest.md" ]]; then
    cp "$REPORT_DIR/latest.md" "$DOC_REPLAY_DIR/${SCOPE_LABEL}_latest.md"
  fi
  if [[ -f "$REPORT_DIR/latest.json" ]]; then
    cp "$REPORT_DIR/latest.json" "$DOC_REPLAY_DIR/${SCOPE_LABEL}_latest.json"
  fi
fi
