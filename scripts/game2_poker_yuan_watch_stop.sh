#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PID_FILE="$ROOT_DIR/Game2/runtime/game2_poker_yuan_watch/watcher.pid"

if [[ ! -s "$PID_FILE" ]]; then
  echo "game2-poker-yuan-watch not running (no pid file)"
  exit 0
fi

pid="$(cat "$PID_FILE" || true)"
if [[ -z "$pid" ]]; then
  rm -f "$PID_FILE"
  echo "game2-poker-yuan-watch pid file empty, cleaned"
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
echo "game2-poker-yuan-watch stopped: pid=$pid"
