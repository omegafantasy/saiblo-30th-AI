#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT_DIR/scripts/automation_pause.sh"
PROMPT_FILE="$ROOT_DIR/docs/codex_saiblo_iteration_prompt.md"
OBJECTIVE_FILE="$ROOT_DIR/docs/codex_saiblo_objective_fixed.md"
RUNBOOK_FILE="$ROOT_DIR/docs/codex_automation_runbook.md"
LOG_DIR="$ROOT_DIR/autolab/runtime"
LOG_FILE="$LOG_DIR/codex_saiblo_iterate.log"
LAST_FILE="$LOG_DIR/codex_saiblo_last_message.txt"
SESSION_FILE="$LOG_DIR/codex_saiblo_session_id.txt"
EVENTS_FILE="$LOG_DIR/codex_saiblo_events.jsonl"
PAUSE_FILE="${CODEX_SAIBLO_ITER_PAUSE_FILE:-$LOG_DIR/codex_saiblo_iterate.paused}"
GLOBAL_LOCK_PATH="${CODEX_GLOBAL_LOCK_PATH:-/tmp/codex-automation-global.lock}"
GLOBAL_LOCK_WAIT_SEC="${CODEX_GLOBAL_LOCK_WAIT_SEC:-120}"
CODEX_BIN="${CODEX_BIN:-/usr/local/bin/codex}"
TIMEOUT_SEC="${CODEX_SAIBLO_ITER_TIMEOUT_SEC:-1500}"
TIMEOUT_BIN="${TIMEOUT_BIN:-/usr/bin/timeout}"
LOAD_GUARD_ENABLED="${CODEX_SAIBLO_LOAD_GUARD_ENABLED:-1}"
LOAD_GUARD_PATTERN="${CODEX_SAIBLO_LOAD_GUARD_PATTERN:-autolab_eval.py}"
LOAD_GUARD_THRESHOLD="${CODEX_SAIBLO_LOAD_GUARD_THRESHOLD:-}"

mkdir -p "$LOG_DIR"

if automation_is_paused; then
  echo "$(date -u +'%Y-%m-%dT%H:%M:%SZ') | PAUSED by $(automation_pause_file)" >> "$LOG_FILE"
  exit 0
fi

if [[ -f "$PAUSE_FILE" ]]; then
  echo "$(date -u +'%Y-%m-%dT%H:%M:%SZ') | PAUSED by $PAUSE_FILE" >> "$LOG_FILE"
  exit 0
fi

exec 9>"$GLOBAL_LOCK_PATH"
if [[ "$GLOBAL_LOCK_WAIT_SEC" =~ ^[0-9]+$ ]] && [[ "$GLOBAL_LOCK_WAIT_SEC" -gt 0 ]]; then
  if ! flock -w "$GLOBAL_LOCK_WAIT_SEC" 9; then
    echo "$(date -u +'%Y-%m-%dT%H:%M:%SZ') | SKIP global-lock timeout=${GLOBAL_LOCK_WAIT_SEC}s: $GLOBAL_LOCK_PATH" >> "$LOG_FILE"
    exit 0
  fi
else
  if ! flock -n 9; then
    echo "$(date -u +'%Y-%m-%dT%H:%M:%SZ') | SKIP global-lock busy: $GLOBAL_LOCK_PATH" >> "$LOG_FILE"
    exit 0
  fi
fi

if [[ ! -f "$PROMPT_FILE" ]]; then
  echo "$(date -u +'%Y-%m-%dT%H:%M:%SZ') | missing prompt: $PROMPT_FILE" >> "$LOG_FILE"
  exit 1
fi
if [[ ! -x "$CODEX_BIN" ]]; then
  echo "$(date -u +'%Y-%m-%dT%H:%M:%SZ') | missing codex binary: $CODEX_BIN" >> "$LOG_FILE"
  exit 1
fi
if [[ ! -f "$OBJECTIVE_FILE" ]]; then
  echo "$(date -u +'%Y-%m-%dT%H:%M:%SZ') | missing objective doc: $OBJECTIVE_FILE" >> "$LOG_FILE"
  exit 1
fi
if [[ ! -f "$RUNBOOK_FILE" ]]; then
  echo "$(date -u +'%Y-%m-%dT%H:%M:%SZ') | missing runbook doc: $RUNBOOK_FILE" >> "$LOG_FILE"
  exit 1
fi

if [[ "$LOAD_GUARD_ENABLED" != "0" ]]; then
  LOAD1="$(awk '{print $1}' /proc/loadavg 2>/dev/null || echo "")"
  if [[ -z "$LOAD_GUARD_THRESHOLD" ]]; then
    LOAD_GUARD_THRESHOLD="$(nproc 2>/dev/null || echo 0)"
  fi
  AUTOLAB_ACTIVE=0
  if pgrep -f "$LOAD_GUARD_PATTERN" >/dev/null 2>&1; then
    AUTOLAB_ACTIVE=1
  fi
  SHOULD_SKIP="$(
    python3 - "$LOAD1" "$LOAD_GUARD_THRESHOLD" "$AUTOLAB_ACTIVE" <<'PY'
import sys

load1 = float(sys.argv[1] or 0.0)
threshold = float(sys.argv[2] or 0.0)
autolab_active = int(sys.argv[3] or 0)
print("1" if autolab_active and threshold > 0 and load1 > threshold else "0")
PY
  )"
  if [[ "$SHOULD_SKIP" == "1" ]]; then
    echo "$(date -u +'%Y-%m-%dT%H:%M:%SZ') | SKIP high-load load1=${LOAD1} threshold=${LOAD_GUARD_THRESHOLD} autolab_active=${AUTOLAB_ACTIVE} pattern=${LOAD_GUARD_PATTERN}" >> "$LOG_FILE"
    exit 0
  fi
fi

cd "$ROOT_DIR"

SID=""
if [[ -s "$SESSION_FILE" ]]; then
  SID="$(tr -d '[:space:]' < "$SESSION_FILE")"
fi
MODE="new"
if [[ -n "$SID" ]]; then
  MODE="resume"
fi

TMP_JSON="$(mktemp "$LOG_DIR/codex_saiblo_exec_XXXXXX.jsonl")"
TIMEOUT_LABEL="none"
if [[ "$TIMEOUT_SEC" =~ ^[0-9]+$ ]] && [[ "$TIMEOUT_SEC" -gt 0 ]]; then
  TIMEOUT_LABEL="${TIMEOUT_SEC}s"
fi
cleanup() {
  rm -f "$TMP_JSON"
}
trap cleanup EXIT

compose_prompt() {
  cat "$OBJECTIVE_FILE"
  printf '\n\n'
  cat "$RUNBOOK_FILE"
  printf '\n\n'
  cat "$PROMPT_FILE"
}

echo "$(date -u +'%Y-%m-%dT%H:%M:%SZ') | START codex saiblo mode=${MODE} timeout=${TIMEOUT_LABEL} sid=${SID:-none}" >> "$LOG_FILE"

run_codex() {
  local mode="$1"
  local sid="$2"
  local -a cmd
  if [[ "$mode" == "resume" ]]; then
    cmd=(
      "$CODEX_BIN" exec resume "$sid"
      -c 'transport="responses_http"'
      --dangerously-bypass-approvals-and-sandbox
      --skip-git-repo-check
      --json
      --output-last-message "$LAST_FILE"
      -
    )
  else
    cmd=(
      "$CODEX_BIN" exec
      -c 'transport="responses_http"'
      --cd "$ROOT_DIR"
      --dangerously-bypass-approvals-and-sandbox
      --skip-git-repo-check
      --json
      --output-last-message "$LAST_FILE"
      -
    )
  fi

  if [[ "$TIMEOUT_SEC" =~ ^[0-9]+$ ]] && [[ "$TIMEOUT_SEC" -gt 0 ]] && [[ -x "$TIMEOUT_BIN" ]]; then
    compose_prompt | "$TIMEOUT_BIN" --foreground "${TIMEOUT_SEC}s" "${cmd[@]}" > "$TMP_JSON" 2>> "$LOG_FILE"
  else
    compose_prompt | "${cmd[@]}" > "$TMP_JSON" 2>> "$LOG_FILE"
  fi
}

set +e
run_codex "$MODE" "$SID"
rc=$?
set -e

if [[ "$MODE" == "resume" && $rc -ne 0 ]]; then
  echo "$(date -u +'%Y-%m-%dT%H:%M:%SZ') | resume failed rc=$rc, fallback to new session" >> "$LOG_FILE"
  set +e
  run_codex "new" ""
  rc=$?
  set -e
fi

if [[ -s "$TMP_JSON" ]]; then
  cat "$TMP_JSON" >> "$EVENTS_FILE"
  NEW_SID="$(python3 - "$TMP_JSON" <<'PY'
import json
import sys
from pathlib import Path

p = Path(sys.argv[1])
sid = ""
for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
    try:
        obj = json.loads(line)
    except Exception:
        continue
    if obj.get("type") == "thread.started" and obj.get("thread_id"):
        sid = str(obj["thread_id"])
        break
if sid:
    print(sid)
PY
)"
  if [[ -n "${NEW_SID:-}" ]]; then
    echo "$NEW_SID" > "$SESSION_FILE"
  fi
fi

if [[ $rc -eq 124 ]]; then
  echo "$(date -u +'%Y-%m-%dT%H:%M:%SZ') | END codex saiblo rc=$rc (timeout)" >> "$LOG_FILE"
else
  echo "$(date -u +'%Y-%m-%dT%H:%M:%SZ') | END codex saiblo rc=$rc" >> "$LOG_FILE"
fi
exit $rc
