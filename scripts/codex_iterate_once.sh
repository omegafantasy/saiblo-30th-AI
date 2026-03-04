#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="/www"
PROMPT_FILE="$ROOT_DIR/docs/codex_iteration_prompt.md"
OBJECTIVE_FILE="$ROOT_DIR/docs/codex_objective_fixed.md"
LOG_DIR="$ROOT_DIR/autolab/runtime"
LOG_FILE="$LOG_DIR/codex_iterate.log"
LAST_FILE="$LOG_DIR/codex_last_message.txt"
SESSION_FILE="$LOG_DIR/codex_session_id.txt"
EVENTS_FILE="$LOG_DIR/codex_events.jsonl"
PAUSE_FILE="${CODEX_ITER_PAUSE_FILE:-$LOG_DIR/codex_iterate.paused}"
CODEX_BIN="${CODEX_BIN:-/usr/local/bin/codex}"
TIMEOUT_SEC="${CODEX_ITER_TIMEOUT_SEC:-540}"
TIMEOUT_BIN="${TIMEOUT_BIN:-/usr/bin/timeout}"

mkdir -p "$LOG_DIR"

if [[ -f "$PAUSE_FILE" ]]; then
  echo "$(date -u +'%Y-%m-%dT%H:%M:%SZ') | PAUSED by $PAUSE_FILE" >> "$LOG_FILE"
  exit 0
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
cleanup() {
  rm -f "$TMP_JSON"
}
trap cleanup EXIT

echo "$(date -u +'%Y-%m-%dT%H:%M:%SZ') | START codex iteration mode=${MODE} timeout=${TIMEOUT_SEC}s sid=${SID:-none}" >> "$LOG_FILE"

# --full-auto: non-interactive automatic execution in workspace-write sandbox.
# Read prompt from stdin via '-'. For resumed turns we still provide a prompt to
# anchor behavior to the fixed objective doc.
set +e
if [[ "$MODE" == "resume" ]]; then
  if [[ -x "$TIMEOUT_BIN" ]]; then
    cat "$PROMPT_FILE" | "$TIMEOUT_BIN" --foreground "${TIMEOUT_SEC}s" \
      "$CODEX_BIN" exec resume "$SID" \
      --full-auto \
      --skip-git-repo-check \
      --json \
      --output-last-message "$LAST_FILE" \
      - > "$TMP_JSON" 2>> "$LOG_FILE"
  else
    cat "$PROMPT_FILE" | "$CODEX_BIN" exec resume "$SID" \
      --full-auto \
      --skip-git-repo-check \
      --json \
      --output-last-message "$LAST_FILE" \
      - > "$TMP_JSON" 2>> "$LOG_FILE"
  fi
else
  if [[ -x "$TIMEOUT_BIN" ]]; then
    cat "$PROMPT_FILE" | "$TIMEOUT_BIN" --foreground "${TIMEOUT_SEC}s" \
      "$CODEX_BIN" exec \
      --cd "$ROOT_DIR" \
      --full-auto \
      --skip-git-repo-check \
      --json \
      --output-last-message "$LAST_FILE" \
      - > "$TMP_JSON" 2>> "$LOG_FILE"
  else
    cat "$PROMPT_FILE" | "$CODEX_BIN" exec \
      --cd "$ROOT_DIR" \
      --full-auto \
      --skip-git-repo-check \
      --json \
      --output-last-message "$LAST_FILE" \
      - > "$TMP_JSON" 2>> "$LOG_FILE"
  fi
fi
rc=$?
set -e

if [[ "$MODE" == "resume" && $rc -ne 0 && $rc -ne 124 ]]; then
  echo "$(date -u +'%Y-%m-%dT%H:%M:%SZ') | resume failed rc=$rc, fallback to new session" >> "$LOG_FILE"
  set +e
  if [[ -x "$TIMEOUT_BIN" ]]; then
    cat "$PROMPT_FILE" | "$TIMEOUT_BIN" --foreground "${TIMEOUT_SEC}s" \
      "$CODEX_BIN" exec \
      --cd "$ROOT_DIR" \
      --full-auto \
      --skip-git-repo-check \
      --json \
      --output-last-message "$LAST_FILE" \
      - > "$TMP_JSON" 2>> "$LOG_FILE"
  else
    cat "$PROMPT_FILE" | "$CODEX_BIN" exec \
      --cd "$ROOT_DIR" \
      --full-auto \
      --skip-git-repo-check \
      --json \
      --output-last-message "$LAST_FILE" \
      - > "$TMP_JSON" 2>> "$LOG_FILE"
  fi
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
