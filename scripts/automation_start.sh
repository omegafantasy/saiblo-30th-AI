#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT_DIR/scripts/automation_pause.sh"

crontab "$ROOT_DIR/scripts/cron_root_current.cron"
rm -f "$(automation_pause_file)"
rm -f "$ROOT_DIR"/autolab/runtime/pids/*.pid 2>/dev/null || true

echo "automation resumed via cron schedule"
