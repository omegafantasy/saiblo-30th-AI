#!/usr/bin/env bash
set -u

ROOT="/root/autodl-tmp/saiblo_iter"
LOG="$ROOT/Game2/runtime/game2_late_probe_retry.log"
INTERVAL="${GAME2_LATE_PROBE_RETRY_INTERVAL:-300}"

mkdir -p "$(dirname "$LOG")"
cd "$ROOT" || exit 1

check_profile() {
  SAIBLO_API_TIMEOUT="${SAIBLO_API_TIMEOUT:-20}" python3 - <<'PY'
from saiblo_tools import get_profile, require_token

try:
    token = require_token('', 'game2 late probe retry')
    profile = get_profile(token)
    user = profile.get('user', {}) if isinstance(profile.get('user'), dict) else {}
    username = str(user.get('username', '')).strip()
    if username != 'thebeginning':
        raise SystemExit(f'wrong username: {username!r}')
    print(username)
except SystemExit:
    raise
except Exception as exc:
    raise SystemExit(f'{type(exc).__name__}: {exc}')
PY
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
    --labels n576a n576b n576c n577a n577b n577c n577d n580a n580b n580c n580d \
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
    --labels n578a n578b n578c n578d n579a n579d n581a n581b n574c \
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
    --labels n577e n578e n578f n579b n579c n581c n581d \
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
