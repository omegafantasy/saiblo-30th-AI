#!/usr/bin/env bash

AUTOMATION_ROOT_DIR="${AUTOMATION_ROOT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"

automation_pause_file() {
  printf '%s\n' "${AUTOMATION_GLOBAL_PAUSE_FILE:-$AUTOMATION_ROOT_DIR/autolab/runtime/automation.paused}"
}

automation_is_paused() {
  local pause_file
  pause_file="$(automation_pause_file)"
  [[ -f "$pause_file" ]]
}
