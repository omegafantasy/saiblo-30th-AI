#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNTIME_DIR="$ROOT_DIR/Game2/runtime/skeptic_watch"
PID_FILE="$RUNTIME_DIR/watcher.pid"
LOG_FILE="$RUNTIME_DIR/daemon.log"
STATUS_JSON="$RUNTIME_DIR/status.json"

mkdir -p "$RUNTIME_DIR"

if [[ -s "$PID_FILE" ]]; then
  pid="$(cat "$PID_FILE" || true)"
  if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
    echo "skeptic-watch already running: pid=$pid status=$STATUS_JSON"
    exit 0
  fi
fi

INTERVAL="${SKEPTIC_WATCH_INTERVAL:-300}"
SESSION_MAX_AGE_HOURS="${SKEPTIC_WATCH_SESSION_MAX_AGE_HOURS:-72}"
RUN_TOOLS="${SKEPTIC_WATCH_RUN_TOOLS:-on_change}"
BOOTSTRAP_MODE="${SKEPTIC_WATCH_BOOTSTRAP_MODE:-tail}"
ACTION_CMD="${SKEPTIC_WATCH_ACTION_CMD:-}"
ACTION_TRIGGER="${SKEPTIC_WATCH_ACTION_TRIGGER:-on_change}"
ACTION_COOLDOWN="${SKEPTIC_WATCH_ACTION_COOLDOWN:-1800}"

cmd=(
  python3 "$ROOT_DIR/Game2/tools/skeptic_watch_codex_progress.py"
  --interval "$INTERVAL"
  --session-max-age-hours "$SESSION_MAX_AGE_HOURS"
  --run-tools "$RUN_TOOLS"
  --bootstrap-mode "$BOOTSTRAP_MODE"
  --state-json "$RUNTIME_DIR/state.json"
  --status-json "$RUNTIME_DIR/status.json"
  --history-jsonl "$RUNTIME_DIR/history.jsonl"
  --log-file "$RUNTIME_DIR/watch.log"
  --action-trigger "$ACTION_TRIGGER"
  --action-cooldown "$ACTION_COOLDOWN"
)

if [[ -n "$ACTION_CMD" ]]; then
  cmd+=(--action-cmd "$ACTION_CMD")
fi

setsid "${cmd[@]}" >>"$LOG_FILE" 2>&1 < /dev/null &
pid=$!
echo "$pid" > "$PID_FILE"
sleep 1
if ! kill -0 "$pid" 2>/dev/null; then
  rm -f "$PID_FILE"
  echo "skeptic-watch failed to stay running; see $LOG_FILE" >&2
  exit 1
fi
echo "skeptic-watch started: pid=$pid status=$STATUS_JSON log=$RUNTIME_DIR/watch.log"
