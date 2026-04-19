#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT_DIR/scripts/automation_pause.sh"

if automation_is_paused; then
  exit 0
fi

GUARD_BIN="${CODEX_QUOTA_GUARD_BIN:-/root/.openclaw/workspace/scripts/codex-quota-guard.sh}"

if [[ -x "$GUARD_BIN" ]]; then
  exec "$GUARD_BIN" "$@"
fi

exec "$ROOT_DIR/scripts/codex_iterate_once.sh" "$@"
