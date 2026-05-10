#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNTIME_DIR="$ROOT_DIR/Game2/runtime/skeptic_watch"
PID_FILE="$RUNTIME_DIR/watcher.pid"
STATUS_JSON="$RUNTIME_DIR/status.json"

if [[ -s "$PID_FILE" ]]; then
  pid="$(cat "$PID_FILE" || true)"
  if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
    echo "skeptic-watch: running pid=$pid"
  else
    echo "skeptic-watch: stale pid=$pid"
  fi
else
  echo "skeptic-watch: stopped"
fi

if [[ -s "$STATUS_JSON" ]]; then
  jq '{time,cycle,has_change,new_labels_count:(.new_labels|length),new_labels_sample:(.new_labels[:12]),new_match_count:.rooms.new_match_count,low_score_count:.rooms.low_score_count,action:.action.status}' "$STATUS_JSON"
else
  echo "status: missing ($STATUS_JSON)"
fi
