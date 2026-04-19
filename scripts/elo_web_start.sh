#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT_DIR/scripts/automation_pause.sh"
RUNTIME_DIR="$ROOT_DIR/autolab/runtime"
PID_FILE="$RUNTIME_DIR/elo_web.pid"
LOG_FILE="$RUNTIME_DIR/elo_web.log"
HOST="${ELO_WEB_HOST:-0.0.0.0}"
PORT="${ELO_WEB_PORT:-8000}"

mkdir -p "$RUNTIME_DIR"

if automation_is_paused; then
  echo "elo-web start paused by $(automation_pause_file)"
  exit 0
fi

if [[ -s "$PID_FILE" ]]; then
  pid="$(cat "$PID_FILE" || true)"
  if [[ -n "${pid}" ]] && kill -0 "$pid" 2>/dev/null; then
    echo "elo-web already running: pid=$pid"
    exit 0
  fi
fi

if ss -ltn "sport = :$PORT" | tail -n +2 | grep -q .; then
  echo "port $PORT already in use"
  exit 1
fi

nohup python3 "$ROOT_DIR/elo_web/server.py" --host "$HOST" --port "$PORT" >>"$LOG_FILE" 2>&1 &
pid=$!
echo "$pid" > "$PID_FILE"
echo "elo-web started: pid=$pid host=$HOST port=$PORT"
