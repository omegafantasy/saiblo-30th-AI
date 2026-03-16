#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="/www"
PID_FILE="$ROOT_DIR/autolab/runtime/elo_web.pid"

if [[ ! -s "$PID_FILE" ]]; then
  echo "elo-web not running (no pid file)"
  exit 0
fi

pid="$(cat "$PID_FILE" || true)"
if [[ -z "$pid" ]]; then
  rm -f "$PID_FILE"
  echo "elo-web pid file empty, cleaned"
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
echo "elo-web stopped: pid=$pid"
