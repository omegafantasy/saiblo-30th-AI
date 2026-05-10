#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNTIME_DIR="$ROOT_DIR/Game2/runtime/game2_poker_yuan_watch"
PID_FILE="$RUNTIME_DIR/watcher.pid"
STATUS_JSON="$RUNTIME_DIR/status.json"

if [[ -s "$PID_FILE" ]]; then
  pid="$(cat "$PID_FILE" || true)"
  if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
    echo "game2-poker-yuan-watch: running pid=$pid"
  else
    echo "game2-poker-yuan-watch: stale pid=$pid"
  fi
else
  echo "game2-poker-yuan-watch: stopped"
fi

if [[ -s "$STATUS_JSON" ]]; then
  jq '{time,cycle,has_change,new_labels_count:(.new_labels|length),new_labels_sample:(.new_labels[:12]),new_candidate_count:(.candidates.new_candidate_dir_count // 0),new_candidate_sample:(.candidates.new_candidate_dirs[:12] // []),new_match_count:.rooms.new_match_count,low_score_count:.rooms.low_score_count,action:.action}' "$STATUS_JSON"
else
  echo "status: missing ($STATUS_JSON)"
fi
