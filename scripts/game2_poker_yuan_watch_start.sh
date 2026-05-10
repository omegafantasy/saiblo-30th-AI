#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNTIME_DIR="$ROOT_DIR/Game2/runtime/game2_poker_yuan_watch"
PID_FILE="$RUNTIME_DIR/watcher.pid"
LOG_FILE="$RUNTIME_DIR/daemon.log"
STATUS_JSON="$RUNTIME_DIR/status.json"

mkdir -p "$RUNTIME_DIR"

if [[ -s "$PID_FILE" ]]; then
  pid="$(cat "$PID_FILE" || true)"
  if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
    echo "game2-poker-yuan-watch already running: pid=$pid status=$STATUS_JSON"
    exit 0
  fi
fi

INTERVAL="${GAME2_CEILING_WATCH_INTERVAL:-300}"
SESSION_MAX_AGE_HOURS="${GAME2_CEILING_WATCH_SESSION_MAX_AGE_HOURS:-72}"
ACTION_TRIGGER="${GAME2_CEILING_WATCH_ACTION_TRIGGER:-always}"
ACTION_COOLDOWN="${GAME2_CEILING_WATCH_ACTION_COOLDOWN:-1800}"
ACTION_CMD="${GAME2_CEILING_WATCH_ACTION_CMD:-GAME2_CEILING_HEALTH_TIMEOUT=20 SAIBLO_API_TIMEOUT=20 scripts/game2_poker_yuan_ceiling_queue.sh}"

cmd=(
  python3 "$ROOT_DIR/Game2/tools/skeptic_watch_codex_progress.py"
  --interval "$INTERVAL"
  --session-max-age-hours "$SESSION_MAX_AGE_HOURS"
  --run-tools never
  --bootstrap-mode tail
  --state-json "$RUNTIME_DIR/state.json"
  --status-json "$STATUS_JSON"
  --history-jsonl "$RUNTIME_DIR/history.jsonl"
  --log-file "$RUNTIME_DIR/watch.log"
  --action-cmd "$ACTION_CMD"
  --action-trigger "$ACTION_TRIGGER"
  --action-cooldown "$ACTION_COOLDOWN"
)

setsid "${cmd[@]}" >>"$LOG_FILE" 2>&1 < /dev/null &
pid=$!
echo "$pid" > "$PID_FILE"
sleep 1
if ! kill -0 "$pid" 2>/dev/null; then
  rm -f "$PID_FILE"
  echo "game2-poker-yuan-watch failed to stay running; see $LOG_FILE" >&2
  exit 1
fi
echo "game2-poker-yuan-watch started: pid=$pid status=$STATUS_JSON log=$RUNTIME_DIR/watch.log"
