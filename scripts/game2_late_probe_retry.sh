#!/usr/bin/env bash
set -u

ROOT="/root/autodl-tmp/saiblo_iter"
LOG="$ROOT/Game2/runtime/game2_late_probe_retry.log"
INTERVAL="${GAME2_LATE_PROBE_RETRY_INTERVAL:-300}"

mkdir -p "$(dirname "$LOG")"
cd "$ROOT" || exit 1

check_profile() {
  python3 - <<'PY'
from saiblo_tools import get_profile, require_token

token = require_token('', 'game2 late probe retry')
profile = get_profile(token)
user = profile.get('user', {}) if isinstance(profile.get('user'), dict) else {}
username = str(user.get('username', '')).strip()
if username != 'thebeginning':
    raise SystemExit(f'wrong username: {username!r}')
print(username)
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
    --labels n576a n576b n576c \
    --count 3 \
    --timeout 900 \
    --eval-poll-interval 75 \
    --upload-poll-interval 120 \
    --upload-poll-max 80 \
    --request-timeout 180 \
    --allow-partial-eval \
    --continue-on-error \
    --expected-username thebeginning

  python3 Game2/tools/run_recovery_eval_queue.py \
    --labels n574c \
    --count 2 \
    --timeout 900 \
    --eval-poll-interval 75 \
    --upload-poll-interval 120 \
    --upload-poll-max 80 \
    --request-timeout 180 \
    --allow-partial-eval \
    --continue-on-error \
    --expected-username thebeginning

  echo "[$(date -u +'%Y-%m-%dT%H:%M:%SZ')] retry watcher finished"
} >>"$LOG" 2>&1
