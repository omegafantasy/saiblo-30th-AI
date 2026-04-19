#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$ROOT_DIR/scripts/automation_pause.sh"
RUNTIME_DIR="${RUNTIME_DIR:-$ROOT_DIR/autolab/runtime}"
REPLAYS_DIR="${REPLAYS_DIR:-$RUNTIME_DIR/replays}"
THRESHOLD_GB="${THRESHOLD_GB:-50}"
THRESHOLD_BYTES=$((THRESHOLD_GB * 1024 * 1024 * 1024))
LOG_FILE="${LOG_FILE:-$RUNTIME_DIR/runtime_gc.log}"
LOCK_FILE="${LOCK_FILE:-/tmp/autolab-runtime-gc.lock}"
TRANSIENT_TTL_MIN="${TRANSIENT_TTL_MIN:-180}"

timestamp() {
  date -u +"%Y-%m-%dT%H:%M:%SZ"
}

log() {
  printf "%s [runtime-gc] %s\n" "$(timestamp)" "$*" >> "$LOG_FILE"
}

runtime_size_bytes() {
  if du -sb "$RUNTIME_DIR" >/dev/null 2>&1; then
    du -sb "$RUNTIME_DIR" | awk '{print $1}'
  else
    du -sB1 "$RUNTIME_DIR" | awk '{print $1}'
  fi
}

cleanup_transient_dir() {
  local target="$1"
  local label="$2"
  if [ ! -d "$target" ]; then
    return 0
  fi
  while IFS= read -r path; do
    [ -n "$path" ] || continue
    case "$path" in
      "$target"/*) ;;
      *)
        log "unsafe transient delete blocked: $path"
        continue
        ;;
    esac
    rm -rf -- "$path"
    log "deleted transient $label: $path"
  done < <(find "$target" -mindepth 1 -maxdepth 1 -mmin +"$TRANSIENT_TTL_MIN" -print 2>/dev/null | sort)
}

cleanup_scope_transients() {
  local scopes_root="$1"
  if [ ! -d "$scopes_root" ]; then
    return 0
  fi
  while IFS= read -r path; do
    [ -n "$path" ] || continue
    case "$path" in
      "$scopes_root"/*/tmp_replays/*|"$scopes_root"/*/match_work/*|"$scopes_root"/*/packages/*|"$scopes_root"/*/replays/*) ;;
      *)
        log "unsafe scope transient delete blocked: $path"
        continue
        ;;
    esac
    rm -rf -- "$path"
    log "deleted scope transient: $path"
  done < <(find "$scopes_root" -mindepth 2 -maxdepth 3 \( -path "$scopes_root/*/tmp_replays/*" -o -path "$scopes_root/*/match_work/*" -o -path "$scopes_root/*/packages/*" -o -path "$scopes_root/*/replays/*" \) -mmin +"$TRANSIENT_TTL_MIN" -print 2>/dev/null | sort)
}

if command -v flock >/dev/null 2>&1; then
  exec 9>"$LOCK_FILE"
  if ! flock -n 9; then
    exit 0
  fi
fi

if [ ! -d "$RUNTIME_DIR" ]; then
  exit 0
fi

mkdir -p "$RUNTIME_DIR"
touch "$LOG_FILE"

if automation_is_paused; then
  log "paused by $(automation_pause_file)"
  exit 0
fi

cleanup_transient_dir "$RUNTIME_DIR/tmp_replays" "tmp_replays"
cleanup_transient_dir "$RUNTIME_DIR/match_work" "match_work"
cleanup_transient_dir "$RUNTIME_DIR/packages" "packages"
cleanup_transient_dir "$RUNTIME_DIR/tmp_smoke" "tmp_smoke"
cleanup_scope_transients "$RUNTIME_DIR/scopes"

if [ ! -d "$REPLAYS_DIR" ]; then
  log "replays dir missing: $REPLAYS_DIR"
  exit 0
fi

current_size="$(runtime_size_bytes)"
if [ "$current_size" -le "$THRESHOLD_BYTES" ]; then
  exit 0
fi

log "start cleanup runtime_size=${current_size}B threshold=${THRESHOLD_BYTES}B"
deleted_count=0

while [ "$current_size" -ge "$THRESHOLD_BYTES" ]; do
  oldest_dir="$(find "$REPLAYS_DIR" -mindepth 1 -maxdepth 1 -type d -printf '%T@ %p\n' | sort -n | head -n 1 | cut -d' ' -f2-)"
  if [ -z "$oldest_dir" ]; then
    log "no replay directory to delete, stop at ${current_size}B"
    break
  fi

  case "$oldest_dir" in
    "$REPLAYS_DIR"/*) ;;
    *)
      log "unsafe delete target blocked: $oldest_dir"
      break
      ;;
  esac

  before_size="$current_size"
  rm -rf -- "$oldest_dir"
  deleted_count=$((deleted_count + 1))
  current_size="$(runtime_size_bytes)"
  log "deleted=$oldest_dir size_before=${before_size}B size_after=${current_size}B"
done

if [ "$current_size" -lt "$THRESHOLD_BYTES" ]; then
  log "cleanup complete deleted_dirs=${deleted_count} final_size=${current_size}B"
else
  log "cleanup incomplete deleted_dirs=${deleted_count} final_size=${current_size}B"
fi
