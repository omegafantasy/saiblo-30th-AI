#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT_DIR/scripts/automation_pause.sh"

RUNTIME_DIR="$ROOT_DIR/autolab/runtime/saiblo_game1_elo"
PID_FILE="$RUNTIME_DIR/crawler.pid"
LOG_FILE="$RUNTIME_DIR/crawler.log"

mkdir -p "$RUNTIME_DIR"

if automation_is_paused; then
  echo "saiblo-game1-elo start paused by $(automation_pause_file)"
  exit 0
fi

if [[ -s "$PID_FILE" ]]; then
  pid="$(cat "$PID_FILE" || true)"
  if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
    echo "saiblo-game1-elo already running: pid=$pid"
    exit 0
  fi
fi

INTERVAL="${SAIBLO_GAME1_ELO_INTERVAL:-60}"
MAX_LIST_PAGES="${SAIBLO_GAME1_ELO_MAX_LIST_PAGES:-50}"
MAX_DETAIL="${SAIBLO_GAME1_ELO_MAX_DETAIL_PER_CYCLE:-30}"
REQUEST_DELAY="${SAIBLO_GAME1_ELO_REQUEST_DELAY:-0.35}"
REPLAY_CONCURRENCY="${SAIBLO_GAME1_ELO_REPLAY_CONCURRENCY:-3}"
SUPPLEMENT_INTERVAL_MIN="${SAIBLO_GAME1_ELO_SUPPLEMENT_INTERVAL_MIN:-600}"
SUPPLEMENT_INTERVAL_MAX="${SAIBLO_GAME1_ELO_SUPPLEMENT_INTERVAL_MAX:-1200}"
SUPPLEMENT_MIN_PER_CYCLE="${SAIBLO_GAME1_ELO_SUPPLEMENT_MIN_PER_CYCLE:-10}"
SUPPLEMENT_MAX_PER_CYCLE="${SAIBLO_GAME1_ELO_SUPPLEMENT_MAX_PER_CYCLE:-30}"
SUPPLEMENT_MAX_OUTSTANDING="${SAIBLO_GAME1_ELO_SUPPLEMENT_MAX_OUTSTANDING:-80}"

setsid python3 "$ROOT_DIR/saiblo_game1_elo.py" crawl \
  --loop \
  --interval "$INTERVAL" \
  --max-list-pages "$MAX_LIST_PAGES" \
  --max-detail-per-cycle "$MAX_DETAIL" \
  --request-delay "$REQUEST_DELAY" \
  --replay-concurrency "$REPLAY_CONCURRENCY" \
  --supplement-interval-min-sec "$SUPPLEMENT_INTERVAL_MIN" \
  --supplement-interval-max-sec "$SUPPLEMENT_INTERVAL_MAX" \
  --supplement-min-per-cycle "$SUPPLEMENT_MIN_PER_CYCLE" \
  --supplement-max-per-cycle "$SUPPLEMENT_MAX_PER_CYCLE" \
  --supplement-max-outstanding "$SUPPLEMENT_MAX_OUTSTANDING" \
  >>"$LOG_FILE" 2>&1 < /dev/null &
pid=$!
echo "$pid" > "$PID_FILE"
sleep 1
if ! kill -0 "$pid" 2>/dev/null; then
  rm -f "$PID_FILE"
  echo "saiblo-game1-elo failed to stay running; see $LOG_FILE" >&2
  exit 1
fi
echo "saiblo-game1-elo started: pid=$pid latest=$RUNTIME_DIR/latest.json"
