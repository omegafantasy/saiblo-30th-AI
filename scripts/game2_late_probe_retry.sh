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
    --labels n576a n576b n576c n577a n577b n577c n577d n580a n580b n580c n580d n582a n582b n582c n582d n583a n583b n583c n586a n586b n587a n587b \
    --count 3 \
    --timeout 900 \
    --eval-poll-interval 75 \
    --upload-poll-interval 120 \
    --upload-poll-max 80 \
    --request-timeout 180 \
    --allow-partial-eval \
    --continue-on-error \
    --expected-username thebeginning &
  pid_yuan_core=$!

  python3 Game2/tools/run_recovery_eval_queue.py \
    --labels n586c n587c n590a n590b n590c n591a n591b n591c n591d n593c n594c n595c n595d n596e n596f n596g n597b n597c \
    --count 3 \
    --timeout 900 \
    --eval-poll-interval 75 \
    --upload-poll-interval 120 \
    --upload-poll-max 80 \
    --request-timeout 180 \
    --allow-partial-eval \
    --continue-on-error \
    --expected-username thebeginning &
  pid_yuan_stage=$!

  python3 Game2/tools/run_recovery_eval_queue.py \
    --labels n578a n578b n578c n578d n579a n579d n581a n581b n584a n584b n584c n585a n585b n585c n574c \
    --count 3 \
    --timeout 900 \
    --eval-poll-interval 75 \
    --upload-poll-interval 120 \
    --upload-poll-max 80 \
    --request-timeout 180 \
    --allow-partial-eval \
    --continue-on-error \
    --expected-username thebeginning &
  pid_poker_core=$!

  python3 Game2/tools/run_recovery_eval_queue.py \
    --labels n588a n588b n588c n589a n589b n589c n592a n592b n592c n593a n594a n595a n595b n596a n596c n597a \
    --count 3 \
    --timeout 900 \
    --eval-poll-interval 75 \
    --upload-poll-interval 120 \
    --upload-poll-max 80 \
    --request-timeout 180 \
    --allow-partial-eval \
    --continue-on-error \
    --expected-username thebeginning &
  pid_poker_stage=$!

  python3 Game2/tools/run_recovery_eval_queue.py \
    --labels n577e n578e n578f n579b n579c n581c n581d n583d n584d n585d n586d n587d n588d n589d n590d n592d n593b n593d n594b n594d n596b n596d n596h n597d n597e \
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
  for pid in "$pid_yuan_core" "$pid_yuan_stage" "$pid_poker_core" "$pid_poker_stage" "$pid_full"; do
    if ! wait "$pid"; then
      status=1
    fi
  done

  python3 Game2/tools/summarize_late_probe_results.py || true

  echo "[$(date -u +'%Y-%m-%dT%H:%M:%SZ')] retry watcher finished status=${status}"
  exit "$status"
} >>"$LOG" 2>&1
