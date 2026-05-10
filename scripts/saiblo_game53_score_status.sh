#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PID_FILE="$ROOT_DIR/autolab/runtime/saiblo_game53_score/crawler.pid"

if [[ -s "$PID_FILE" ]]; then
  pid="$(cat "$PID_FILE" || true)"
  if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
    echo "crawler: running pid=$pid"
  else
    echo "crawler: stale pid=$pid"
  fi
else
  echo "crawler: stopped"
fi

python3 "$ROOT_DIR/saiblo_game53_score.py" status
