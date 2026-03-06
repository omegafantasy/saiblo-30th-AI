#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="/www"
EVAL_SCRIPT="$ROOT_DIR/autolab_eval.py"
LOG_DIR="$ROOT_DIR/autolab/runtime"
LOG_FILE="$LOG_DIR/idle_eval_loop.log"
PY_BIN="${PY_BIN:-$(command -v python3 || command -v python || true)}"
ITER_LOCK_FILE="${ITER_LOCK_FILE:-/tmp/codex-iterate.lock}"

EVAL_MODE="${AUTO_EVAL_MODE:-adaptive}"
MAX_JOBS="${AUTO_EVAL_MAX_JOBS:-14}"
GAMES_PER_PAIR="${AUTO_EVAL_GAMES_PER_PAIR:-6}"
ANCHOR_GAMES_PER_PAIR="${AUTO_EVAL_ANCHOR_GAMES_PER_PAIR:-1}"
ADAPTIVE_PAIR_COUNT="${AUTO_EVAL_ADAPTIVE_PAIR_COUNT:-45}"
ADAPTIVE_TOP_K="${AUTO_EVAL_ADAPTIVE_TOP_K:-6}"
ADAPTIVE_TOP_BOOST="${AUTO_EVAL_ADAPTIVE_TOP_BOOST:-1.5}"
ADAPTIVE_NEW_TARGET_GAMES="${AUTO_EVAL_ADAPTIVE_NEW_TARGET_GAMES:-600}"
ADAPTIVE_NEW_BOOST="${AUTO_EVAL_ADAPTIVE_NEW_BOOST:-2.0}"
MAX_ROUNDS="${AUTO_EVAL_MAX_ROUNDS:-180}"
IDLE_THRESHOLD="${AUTO_EVAL_IDLE_THRESHOLD:-0.03}"
IDLE_SAMPLE_SEC="${AUTO_EVAL_IDLE_SAMPLE_SEC:-0.8}"
SLEEP_OK="${AUTO_EVAL_SLEEP_OK:-20}"
SLEEP_FAIL="${AUTO_EVAL_SLEEP_FAIL:-20}"
SLEEP_ITER_ACTIVE="${AUTO_EVAL_SLEEP_ITER_ACTIVE:-30}"

mkdir -p "$LOG_DIR"

log() {
  printf '%s | %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "$*" | tee -a "$LOG_FILE"
}

if [[ ! -f "$EVAL_SCRIPT" ]]; then
  log "FATAL missing $EVAL_SCRIPT"
  exit 1
fi
if [[ -z "$PY_BIN" ]]; then
  log "FATAL cannot find python interpreter"
  exit 1
fi
if [[ ! -x "$PY_BIN" ]]; then
  log "FATAL python interpreter is not executable: $PY_BIN"
  exit 1
fi

log "START autolab idle loop python=$PY_BIN mode=$EVAL_MODE max_jobs=$MAX_JOBS games_per_pair=$GAMES_PER_PAIR anchor_games_per_pair=$ANCHOR_GAMES_PER_PAIR adaptive_pair_count=$ADAPTIVE_PAIR_COUNT max_rounds=$MAX_ROUNDS"

while true; do
  # Priority policy: when codex iterate holds its lock, pause production eval.
  exec {iter_lock_fd}> "$ITER_LOCK_FILE"
  if ! flock -n "$iter_lock_fd"; then
    log "ITER_ACTIVE skip production eval sleep=${SLEEP_ITER_ACTIVE}s"
    exec {iter_lock_fd}>&-
    sleep "$SLEEP_ITER_ACTIVE"
    continue
  fi
  flock -u "$iter_lock_fd"
  exec {iter_lock_fd}>&-

  set +e
  "$PY_BIN" "$EVAL_SCRIPT" \
    --mode "$EVAL_MODE" \
    --games-per-pair "$GAMES_PER_PAIR" \
    --anchor-games-per-pair "$ANCHOR_GAMES_PER_PAIR" \
    --adaptive-pair-count "$ADAPTIVE_PAIR_COUNT" \
    --adaptive-top-k "$ADAPTIVE_TOP_K" \
    --adaptive-top-boost "$ADAPTIVE_TOP_BOOST" \
    --adaptive-new-target-games "$ADAPTIVE_NEW_TARGET_GAMES" \
    --adaptive-new-boost "$ADAPTIVE_NEW_BOOST" \
    --max-rounds "$MAX_ROUNDS" \
    --jobs "$MAX_JOBS" \
    --cpu-policy idle_only \
    --idle-threshold "$IDLE_THRESHOLD" \
    --idle-sample-sec "$IDLE_SAMPLE_SEC" \
    --pin-cpu \
    --auto-promote \
    --doc-out "$ROOT_DIR/docs/idle_eval_latest.md" \
    >> "$LOG_FILE" 2>&1
  rc=$?
  set -e

  if [[ $rc -eq 0 ]]; then
    log "EVAL_OK sleep=${SLEEP_OK}s"
    sleep "$SLEEP_OK"
  else
    log "EVAL_SKIP_OR_FAIL rc=$rc sleep=${SLEEP_FAIL}s"
    sleep "$SLEEP_FAIL"
  fi
done
