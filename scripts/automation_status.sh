#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT_DIR/scripts/automation_pause.sh"
ITER_PAUSE_FILE="${CODEX_ITER_PAUSE_FILE:-$ROOT_DIR/autolab/runtime/codex_iterate.paused}"
ANCHOR_PAUSE_FILE="${CODEX_ANCHOR_ITER_PAUSE_FILE:-$ROOT_DIR/autolab/runtime/codex_anchor_iterate.paused}"
SAIBLO_PAUSE_FILE="${CODEX_SAIBLO_ITER_PAUSE_FILE:-$ROOT_DIR/autolab/runtime/codex_saiblo_iterate.paused}"

show_schedule() {
  local name="$1"
  local pattern="$2"
  if crontab -l 2>/dev/null | grep -Fq "$pattern"; then
    printf '%s: scheduled\n' "$name"
  else
    printf '%s: missing\n' "$name"
  fi
}

show_active() {
  local name="$1"
  local pattern="$2"
  local matches
  matches="$(ps -eo pid=,args= | grep -F "$pattern" | grep -v grep || true)"
  if [[ -n "$matches" ]]; then
    printf '%s: active\n' "$name"
    printf '%s\n' "$matches"
  else
    printf '%s: idle\n' "$name"
  fi
}

show_pause() {
  local name="$1"
  local path="$2"
  if [[ -f "$path" ]]; then
    printf '%s: paused (%s)\n' "$name" "$path"
  else
    printf '%s: clear\n' "$name"
  fi
}

if pgrep -x cron >/dev/null 2>&1 || pgrep -f '/usr/sbin/cron -P' >/dev/null 2>&1; then
  echo "cron: running"
else
  echo "cron: stopped"
fi

if automation_is_paused; then
  echo "automation: paused ($(automation_pause_file))"
else
  echo "automation: active"
fi

show_pause "codex_iterate_pause" "$ITER_PAUSE_FILE"
show_pause "codex_anchor_pause" "$ANCHOR_PAUSE_FILE"
show_pause "codex_saiblo_pause" "$SAIBLO_PAUSE_FILE"

show_schedule "autolab_idle_eval" "AUTOLAB_IDLE_RUN_ONCE=1"
show_schedule "codex_iterate" "scripts/codex_iterate_once.sh"
show_schedule "codex_anchor_iterate" "scripts/codex_anchor_iterate_once.sh"
show_schedule "codex_saiblo_iterate" "scripts/codex_saiblo_iterate_once.sh"
show_schedule "autolab_runtime_gc" "scripts/autolab_runtime_gc.sh"
show_schedule "codex_auth_rotate" "codex-auth-rotate"

show_active "autolab_eval" "/root/autodl-tmp/saiblo_iter/autolab_eval.py"
show_active "codex_iterate" "codex_last_message.txt"
show_active "codex_anchor_iterate" "codex_anchor_last_message.txt"
show_active "codex_saiblo_iterate" "codex_saiblo_last_message.txt"
