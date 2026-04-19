#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT_DIR/scripts/automation_pause.sh"
PROMPT_FILE="$ROOT_DIR/docs/codex_iteration_prompt.md"
OBJECTIVE_FILE="$ROOT_DIR/docs/codex_objective_fixed.md"
RUNBOOK_FILE="$ROOT_DIR/docs/codex_automation_runbook.md"
LOG_DIR="$ROOT_DIR/autolab/runtime"
LOG_FILE="$LOG_DIR/codex_iterate.log"
LAST_FILE="$LOG_DIR/codex_last_message.txt"
SESSION_FILE="$LOG_DIR/codex_session_id.txt"
EVENTS_FILE="$LOG_DIR/codex_events.jsonl"
PAUSE_FILE="${CODEX_ITER_PAUSE_FILE:-$LOG_DIR/codex_iterate.paused}"
GLOBAL_LOCK_PATH="${CODEX_GLOBAL_LOCK_PATH:-/tmp/codex-automation-global.lock}"
GLOBAL_LOCK_WAIT_SEC="${CODEX_GLOBAL_LOCK_WAIT_SEC:-0}"
CODEX_BIN="${CODEX_BIN:-/usr/local/bin/codex}"
TIMEOUT_SEC="${CODEX_ITER_TIMEOUT_SEC:-1500}"
TIMEOUT_BIN="${TIMEOUT_BIN:-/usr/bin/timeout}"

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
cd "$ROOT_DIR"

SID=""
if [[ -s "$SESSION_FILE" ]]; then
  SID="$(tr -d '[:space:]' < "$SESSION_FILE")"
fi
MODE="new"
if [[ -n "$SID" ]]; then
  MODE="resume"
fi

TMP_JSON="$(mktemp "$LOG_DIR/codex_exec_XXXXXX.jsonl")"
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

echo "$(date -u +'%Y-%m-%dT%H:%M:%SZ') | START codex iteration mode=${MODE} timeout=${TIMEOUT_LABEL} sid=${SID:-none}" >> "$LOG_FILE"

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

# Always prepend the fixed objective and runbook so resumed turns keep the same
# operating context instead of relying on the prompt file alone.
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
  echo "$(date -u +'%Y-%m-%dT%H:%M:%SZ') | END codex iteration rc=$rc (timeout)" >> "$LOG_FILE"
else
  echo "$(date -u +'%Y-%m-%dT%H:%M:%SZ') | END codex iteration rc=$rc" >> "$LOG_FILE"
fi
exit $rc
