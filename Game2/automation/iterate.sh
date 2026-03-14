#!/usr/bin/env bash
# iterate.sh - Drive one full iteration cycle for Game2 DeepClue AI.
# Intended to be invoked by Claude Code, cron, or a loop.
#
# Usage:
#   bash Game2/automation/iterate.sh
#   # or from anywhere:
#   bash /d/others/saiblo_iter/Game2/automation/iterate.sh

set -euo pipefail

# ── Paths ────────────────────────────────────────────────────────────────────
REPO_ROOT="D:/others/saiblo_iter"
AUTOMATION_DIR="${REPO_ROOT}/Game2/automation"
STATE_FILE="${AUTOMATION_DIR}/state.json"
LOG_DIR="${AUTOMATION_DIR}/logs"
LOG_FILE="${LOG_DIR}/iterate.log"
AI_DIR="${REPO_ROOT}/Game2/deepclue_ai"

# ── Helpers ──────────────────────────────────────────────────────────────────
timestamp() {
    date '+%Y-%m-%d %H:%M:%S'
}

log() {
    local msg="[$(timestamp)] $*"
    echo "$msg" | tee -a "$LOG_FILE"
}

die() {
    log "FATAL: $*"
    exit 1
}

# ── Setup ────────────────────────────────────────────────────────────────────
cd "$REPO_ROOT" || die "Cannot cd to repo root: ${REPO_ROOT}"

mkdir -p "$LOG_DIR"

log "========== iterate.sh started =========="

# Check python availability
PYTHON=""
for candidate in python3 python; do
    if command -v "$candidate" &>/dev/null; then
        PYTHON="$candidate"
        break
    fi
done
[ -n "$PYTHON" ] || die "No python3 or python found in PATH"
log "Using python: $PYTHON ($(${PYTHON} --version 2>&1))"

# ── Read state ───────────────────────────────────────────────────────────────
if [ ! -f "$STATE_FILE" ]; then
    die "State file not found: ${STATE_FILE}"
fi

# Parse current_state from the JSON (works with basic tools, no jq needed)
current_state=$($PYTHON -c "
import json, sys
with open(r'${STATE_FILE}') as f:
    d = json.load(f)
print(d.get('current_state', 'unknown'))
") || die "Failed to parse state.json"

log "Current state: ${current_state}"

# ── Find latest AI version ───────────────────────────────────────────────────
find_latest_ai() {
    # List vN directories, sort numerically, pick the highest
    local latest_v
    latest_v=$(ls -d "${AI_DIR}"/v[0-9]* 2>/dev/null \
        | sed 's|.*/v||' \
        | sort -n \
        | tail -1) || true

    if [ -z "$latest_v" ]; then
        die "No vN directories found in ${AI_DIR}"
    fi

    local ai_path="${AI_DIR}/v${latest_v}/ai_v${latest_v}.py"
    if [ ! -f "$ai_path" ]; then
        # Try alternate naming patterns
        ai_path="${AI_DIR}/v${latest_v}/ai.py"
        if [ ! -f "$ai_path" ]; then
            die "AI source not found in ${AI_DIR}/v${latest_v}/"
        fi
    fi

    echo "$ai_path"
}

# ── State machine ────────────────────────────────────────────────────────────
case "$current_state" in

    idle|completed)
        log "State is '${current_state}' -- starting new iteration cycle."

        latest_ai=$(find_latest_ai)
        log "Latest AI source: ${latest_ai}"

        log "Running: run_cycle.py --source ${latest_ai} --entity-name g2auto --top-k 1 --timeout 600"
        $PYTHON Game2/automation/run_cycle.py \
            --source "$latest_ai" \
            --entity-name g2auto \
            --top-k 1 \
            --timeout 600 \
            2>&1 | tee -a "$LOG_FILE"
        rc=${PIPESTATUS[0]}

        if [ "$rc" -ne 0 ]; then
            log "run_cycle.py exited with code ${rc}"
        fi
        ;;

    batch_created|batch_polling|submitted)
        log "State is '${current_state}' -- resuming pending cycle."

        log "Running: run_cycle.py --resume --timeout 600"
        $PYTHON Game2/automation/run_cycle.py \
            --resume \
            --timeout 600 \
            2>&1 | tee -a "$LOG_FILE"
        rc=${PIPESTATUS[0]}

        if [ "$rc" -ne 0 ]; then
            log "run_cycle.py (resume) exited with code ${rc}"
        fi
        ;;

    failed)
        log "State is 'failed'. Not auto-retrying -- manual intervention or Claude review needed."
        log "Check state.json and logs for error details."
        # Re-read and display any error info from state.json
        $PYTHON -c "
import json
with open(r'${STATE_FILE}') as f:
    d = json.load(f)
err = d.get('error') or d.get('last_error') or 'no error detail in state.json'
print(f'Error detail: {err}')
" 2>&1 | tee -a "$LOG_FILE"
        log "========== iterate.sh finished (failed state, no action) =========="
        exit 1
        ;;

    *)
        die "Unknown state: '${current_state}'. Cannot proceed."
        ;;
esac

# ── Post-cycle: check if completed and print analysis ────────────────────────
# Re-read state after the cycle run
post_state=$($PYTHON -c "
import json
with open(r'${STATE_FILE}') as f:
    d = json.load(f)
print(d.get('current_state', 'unknown'))
") || true

log "Post-cycle state: ${post_state}"

if [ "$post_state" = "completed" ]; then
    log "Cycle completed. Running analysis..."
    if [ -f "Game2/automation/analyze_results.py" ]; then
        $PYTHON Game2/automation/analyze_results.py --print \
            2>&1 | tee -a "$LOG_FILE"
        analysis_rc=${PIPESTATUS[0]}
        if [ "$analysis_rc" -ne 0 ]; then
            log "analyze_results.py exited with code ${analysis_rc}"
        fi
    else
        log "WARNING: analyze_results.py not found, skipping analysis."
    fi
elif [ "$post_state" = "failed" ]; then
    log "Cycle ended in 'failed' state. Review logs and state.json."
else
    log "Cycle not yet complete (state: ${post_state}). Re-run iterate.sh to continue."
fi

log "========== iterate.sh finished =========="
