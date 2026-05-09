#!/usr/bin/env bash
set -u

ROOT="/root/autodl-tmp/saiblo_iter"
LOG="$ROOT/Game2/runtime/game2_late_probe_retry.log"
INTERVAL="${GAME2_LATE_PROBE_RETRY_INTERVAL:-300}"
PROFILE_WALL_TIMEOUT="${GAME2_PROFILE_CHECK_WALL_TIMEOUT:-180s}"

mkdir -p "$(dirname "$LOG")"
cd "$ROOT" || exit 1

check_profile() {
  timeout "$PROFILE_WALL_TIMEOUT" env SAIBLO_API_TIMEOUT="${SAIBLO_API_TIMEOUT:-120}" \
    python3 Game2/tools/check_saiblo_profile.py --expected-username thebeginning
}

{
  echo "[$(date -u +'%Y-%m-%dT%H:%M:%SZ')] retry watcher start"
  while true; do
    if check_profile; then
      echo "[$(date -u +'%Y-%m-%dT%H:%M:%SZ')] profile ok; running queued probes"
      break
    fi
    echo "[$(date -u +'%Y-%m-%dT%H:%M:%SZ')] profile unavailable; sleep ${INTERVAL}s"
    sleep "$INTERVAL"
  done

  python3 Game2/tools/run_recovery_eval_queue.py \
    --labels n576a n576b n576c n577a n577b n577c n577d n580a n580b n580c n580d n582a n582b n582c n582d n583a n583b n583c \
    --count 3 \
    --timeout 900 \
    --eval-poll-interval 75 \
    --upload-poll-interval 120 \
    --upload-poll-max 80 \
    --request-timeout 180 \
    --allow-partial-eval \
    --continue-on-error \
    --expected-username thebeginning &
  pid_yuan=$!

  python3 Game2/tools/run_recovery_eval_queue.py \
    --labels n578a n578b n578c n578d n579a n579d n581a n581b n584a n584b n584c n574c \
    --count 3 \
    --timeout 900 \
    --eval-poll-interval 75 \
    --upload-poll-interval 120 \
    --upload-poll-max 80 \
    --request-timeout 180 \
    --allow-partial-eval \
    --continue-on-error \
    --expected-username thebeginning &
  pid_poker=$!

  python3 Game2/tools/run_recovery_eval_queue.py \
    --labels n577e n578e n578f n579b n579c n581c n581d n583d n584d \
    --count 3 \
    --timeout 900 \
    --eval-poll-interval 75 \
    --upload-poll-interval 120 \
    --upload-poll-max 80 \
    --request-timeout 180 \
    --allow-partial-eval \
    --continue-on-error \
    --expected-username thebeginning &
  pid_full=$!

  status=0
  for pid in "$pid_yuan" "$pid_poker" "$pid_full"; do
    if ! wait "$pid"; then
      status=1
    fi
  done

  python3 Game2/tools/summarize_late_probe_results.py || true

  echo "[$(date -u +'%Y-%m-%dT%H:%M:%SZ')] retry watcher finished status=${status}"
  exit "$status"
} >>"$LOG" 2>&1
