#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY_BIN="${PY_BIN:-$(command -v python3 || command -v python || true)}"
LOG_DIR="$ROOT_DIR/autolab/runtime"
LOG_FILE="$LOG_DIR/game1_strategy_probe.log"
LOCK_FILE="${GAME1_STRATEGY_PROBE_LOCK:-/tmp/game1-strategy-probe.lock}"
PAUSE_FILE="${GAME1_STRATEGY_PROBE_PAUSE_FILE:-$ROOT_DIR/autolab/runtime/game1_strategy_probe.paused}"
JOBS="${GAME1_STRATEGY_PROBE_JOBS:-4}"
SEEDS="${GAME1_STRATEGY_PROBE_SEEDS:-0}"
INCLUDE_ROUND_ROBIN="${GAME1_STRATEGY_PROBE_INCLUDE_ROUND_ROBIN:-0}"
SEAT_SWAPS="${GAME1_STRATEGY_PROBE_SEAT_SWAPS:-0}"

mkdir -p "$LOG_DIR"

log() {
  printf '%s | %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "$*" | tee -a "$LOG_FILE"
}

if [[ -z "$PY_BIN" || ! -x "$PY_BIN" ]]; then
  log "FATAL missing python interpreter"
  exit 1
fi

if [[ -f "$PAUSE_FILE" ]]; then
  log "PAUSED by $PAUSE_FILE"
  exit 0
fi

exec {lock_fd}> "$LOCK_FILE"
if ! flock -n "$lock_fd"; then
  log "SKIP lock busy"
  exit 0
fi

args=(
  "$ROOT_DIR/scripts/game1_strategy_probe.py"
  --jobs "$JOBS"
  --seeds "$SEEDS"
  --keep-artifacts
)
if [[ "$INCLUDE_ROUND_ROBIN" == "1" ]]; then
  args+=(--include-round-robin)
fi
if [[ "$SEAT_SWAPS" == "1" ]]; then
  args+=(--seat-swaps)
else
  args+=(--no-seat-swaps)
fi

log "START strategy probe jobs=$JOBS seeds=$SEEDS round_robin=$INCLUDE_ROUND_ROBIN seat_swaps=$SEAT_SWAPS"
set +e
"$PY_BIN" "${args[@]}" >> "$LOG_FILE" 2>&1
rc=$?
set -e
log "END strategy probe rc=$rc"
exit $rc
