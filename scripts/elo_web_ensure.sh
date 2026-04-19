#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT_DIR/scripts/automation_pause.sh"
RUNTIME_DIR="$ROOT_DIR/autolab/runtime"
PID_FILE="$RUNTIME_DIR/elo_web.pid"
PORT="${ELO_WEB_PORT:-8000}"

mkdir -p "$RUNTIME_DIR"

if automation_is_paused; then
  exit 0
fi

if ss -ltn "sport = :$PORT" | tail -n +2 | grep -q .; then
  exit 0
fi

if [[ -s "$PID_FILE" ]]; then
  pid="$(cat "$PID_FILE" || true)"
  if [[ -n "${pid}" ]] && kill -0 "$pid" 2>/dev/null; then
    exit 0
  fi
fi

/usr/bin/flock -n /tmp/elo-web-start.lock "$ROOT_DIR/scripts/elo_web_start.sh" >/dev/null 2>&1 || true
