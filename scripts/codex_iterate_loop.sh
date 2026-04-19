#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$ROOT_DIR/autolab/runtime"
LOG_FILE="$LOG_DIR/codex_iterate_loop.log"
LOCK_FILE="${CODEX_ITER_LOCK_FILE:-/tmp/codex-iterate.lock}"
INTERVAL_SEC="${CODEX_ITER_LOOP_INTERVAL_SEC:-1800}"

mkdir -p "$LOG_DIR"

log() {
  printf '%s | %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "$*" >> "$LOG_FILE"
}

log "START interval=${INTERVAL_SEC}s"

while true; do
  /usr/bin/flock -n "$LOCK_FILE" "$ROOT_DIR/scripts/codex_iterate_once.sh" >> "$LOG_FILE" 2>&1 || true
  sleep "$INTERVAL_SEC"
done
