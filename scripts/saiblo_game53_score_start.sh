#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT_DIR/scripts/automation_pause.sh"

RUNTIME_DIR="$ROOT_DIR/autolab/runtime/saiblo_game53_score"
PID_FILE="$RUNTIME_DIR/crawler.pid"
LOG_FILE="$RUNTIME_DIR/crawler.log"

mkdir -p "$RUNTIME_DIR"

if automation_is_paused; then
  echo "saiblo-game53-score start paused by $(automation_pause_file)"
  exit 0
fi

if [[ -s "$PID_FILE" ]]; then
  pid="$(cat "$PID_FILE" || true)"
  if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
    echo "saiblo-game53-score already running: pid=$pid"
    exit 0
  fi
fi

INTERVAL="${SAIBLO_GAME53_SCORE_INTERVAL:-60}"
MAX_LIST_PAGES="${SAIBLO_GAME53_SCORE_MAX_LIST_PAGES:-50}"
MAX_DETAIL="${SAIBLO_GAME53_SCORE_MAX_DETAIL_PER_CYCLE:-60}"
REQUEST_DELAY="${SAIBLO_GAME53_SCORE_REQUEST_DELAY:-0.25}"

setsid python3 "$ROOT_DIR/saiblo_game53_score.py" crawl \
  --loop \
  --interval "$INTERVAL" \
  --max-list-pages "$MAX_LIST_PAGES" \
  --max-detail-per-cycle "$MAX_DETAIL" \
  --request-delay "$REQUEST_DELAY" \
  >>"$LOG_FILE" 2>&1 < /dev/null &
pid=$!
echo "$pid" > "$PID_FILE"
sleep 1
if ! kill -0 "$pid" 2>/dev/null; then
  rm -f "$PID_FILE"
  echo "saiblo-game53-score failed to stay running; see $LOG_FILE" >&2
  exit 1
fi
echo "saiblo-game53-score started: pid=$pid latest=$RUNTIME_DIR/latest.json"
