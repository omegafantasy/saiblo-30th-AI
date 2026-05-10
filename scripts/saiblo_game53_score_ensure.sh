#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT_DIR/scripts/automation_pause.sh"
PID_FILE="$ROOT_DIR/autolab/runtime/saiblo_game53_score/crawler.pid"

if automation_is_paused; then
  exit 0
fi

if [[ -s "$PID_FILE" ]]; then
  pid="$(cat "$PID_FILE" || true)"
  if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
    exit 0
  fi
fi

/usr/bin/flock -n /tmp/saiblo-game53-score-start.lock "$ROOT_DIR/scripts/saiblo_game53_score_start.sh" >/dev/null 2>&1 || true
