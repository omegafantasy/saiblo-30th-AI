#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PID_FILE="$ROOT_DIR/autolab/runtime/saiblo_game53_score/crawler.pid"

if [[ ! -s "$PID_FILE" ]]; then
  echo "saiblo-game53-score not running (no pid file)"
  exit 0
fi

pid="$(cat "$PID_FILE" || true)"
if [[ -z "$pid" ]]; then
  rm -f "$PID_FILE"
  echo "saiblo-game53-score pid file empty, cleaned"
  exit 0
fi

if kill -0 "$pid" 2>/dev/null; then
  kill "$pid" || true
  sleep 1
  if kill -0 "$pid" 2>/dev/null; then
    kill -9 "$pid" || true
  fi
fi

rm -f "$PID_FILE"
echo "saiblo-game53-score stopped: pid=$pid"
