#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT_DIR/scripts/automation_pause.sh"
PAUSE_FILE="$(automation_pause_file)"

touch "$PAUSE_FILE"
pkill -f '/root/autodl-tmp/saiblo_iter/autolab_eval.py' || true
pkill -f 'codex exec --cd /root/autodl-tmp/saiblo_iter' || true
rm -f "$ROOT_DIR"/autolab/runtime/pids/*.pid 2>/dev/null || true

echo "automation paused: $PAUSE_FILE"
