#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

ENTITY_NAME="${SKEPTIC_AUTO_ENTITY_NAME:-sk548e0910pyh}"
LABEL_PREFIX="${SKEPTIC_AUTO_LABEL_PREFIX:-sk548e0910pyh_auto}"
SHARDS="${SKEPTIC_AUTO_SHARDS:-1}"
COUNT_PER_SHARD="${SKEPTIC_AUTO_COUNT_PER_SHARD:-4}"
TIMEOUT="${SKEPTIC_AUTO_TIMEOUT:-420}"
POLL_INTERVAL="${SKEPTIC_AUTO_POLL_INTERVAL:-8}"
REQUEST_TIMEOUT="${SKEPTIC_AUTO_REQUEST_TIMEOUT:-90}"
LOG_DIR="$ROOT_DIR/Game2/runtime/skeptic_watch/auto_probe_logs"

mkdir -p "$LOG_DIR"

for shard in $(seq 1 "$SHARDS"); do
  label="${LABEL_PREFIX}${shard}"
  log_file="$LOG_DIR/${label}.log"
  echo "[skeptic-auto] start label=$label log=$log_file"
  python3 Game2/tools/run_room_eval.py \
    --entity-name "$ENTITY_NAME" \
    --label "$label" \
    --count "$COUNT_PER_SHARD" \
    --timeout "$TIMEOUT" \
    --poll-interval "$POLL_INTERVAL" \
    --request-timeout "$REQUEST_TIMEOUT" \
    >"$log_file" 2>&1 &
done

wait
