#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="/www"
source "$ROOT_DIR/scripts/automation_pause.sh"

if automation_is_paused; then
  exit 0
fi

exec /root/.openclaw/workspace/scripts/codex-quota-guard.sh "$@"
