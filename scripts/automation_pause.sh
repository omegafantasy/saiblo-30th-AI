#!/usr/bin/env bash

automation_pause_file() {
  printf '%s\n' "${AUTOMATION_GLOBAL_PAUSE_FILE:-/www/autolab/runtime/automation.paused}"
}

automation_is_paused() {
  local pause_file
  pause_file="$(automation_pause_file)"
  [[ -f "$pause_file" ]]
}
