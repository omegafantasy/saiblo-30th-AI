#!/usr/bin/env bash
set -u

cd /root/autodl-tmp/saiblo_iter || exit 1

attempt=0
max_attempts="${N548_RETRY_MAX_ATTEMPTS:-0}"

valid_count() {
  python3 - "$@" <<'PY'
import glob
import json
import sys

total = 0
for label in sys.argv[1:]:
    for path in glob.glob(f'Game2/runtime/room_matches/*_{label}_room/summary.json'):
        try:
            data = json.load(open(path, encoding='utf-8'))
        except Exception:
            continue
        for row in data.get('rows', []):
            score = row.get('score')
            if row.get('end_state') == 'OK' and isinstance(score, int) and score > 0:
                total += 1
print(total)
PY
}

pending_labels() {
  python3 <<'PY'
import glob
import json

def valid_count(label: str) -> int:
    total = 0
    for path in glob.glob(f'Game2/runtime/room_matches/*_{label}_room/summary.json'):
        try:
            data = json.load(open(path, encoding='utf-8'))
        except Exception:
            continue
        for row in data.get('rows', []):
            score = row.get('score')
            if row.get('end_state') == 'OK' and isinstance(score, int) and score > 0:
                total += 1
    return total

labels = [f'n548{x}' for x in 'efghij']
print(' '.join(label for label in labels if valid_count(label) < 5))
PY
}

is_complete() {
  python3 <<'PY'
import glob
import json
import sys

def valid_count(label: str) -> int:
    total = 0
    for path in glob.glob(f'Game2/runtime/room_matches/*_{label}_room/summary.json'):
        try:
            data = json.load(open(path, encoding='utf-8'))
        except Exception:
            continue
        for row in data.get('rows', []):
            score = row.get('score')
            if row.get('end_state') == 'OK' and isinstance(score, int) and score > 0:
                total += 1
    return total

ok = sum(valid_count(label) for label in ['n548d', 'n548d_more', 'n548d_more2']) >= 5
ok = ok and valid_count('n547c_more') >= 5
for label in [f'n548{x}' for x in 'efghij']:
    ok = ok and valid_count(label) >= 5
sys.exit(0 if ok else 1)
PY
}

while [ "$max_attempts" -eq 0 ] || [ "$attempt" -lt "$max_attempts" ]; do
  attempt=$((attempt + 1))
  if [ "$max_attempts" -eq 0 ]; then
    echo "[n548-retry] attempt ${attempt}/unlimited"
  else
    echo "[n548-retry] attempt ${attempt}/${max_attempts}"
  fi

  d_count=$(valid_count n548d n548d_more n548d_more2)
  d_remaining=$((5 - d_count))
  if [ "$d_remaining" -gt 0 ]; then
    python3 Game2/tools/run_room_eval.py \
      --code-id f8b88bdb0eef4b338dbf1ecd0eae6d03 \
      --label n548d_more2 \
      --count "$d_remaining" \
      --timeout 1200 \
      --poll-interval 30 \
      --request-timeout 180 || true
  else
    echo "[n548-retry] n548d already has ${d_count} valid samples"
  fi

  direct_count=$(valid_count n547c_more)
  direct_remaining=$((5 - direct_count))
  if [ "$direct_remaining" -gt 0 ]; then
    python3 Game2/tools/run_room_eval.py \
      --code-id b8560b15c1594ba2b208d5267fccc03a \
      --label n547c_more \
      --count "$direct_remaining" \
      --timeout 1200 \
      --poll-interval 30 \
      --request-timeout 180 || true
  else
    echo "[n548-retry] n547c_more already has ${direct_count} valid samples"
  fi

  labels="$(pending_labels)"
  if [ -n "$labels" ]; then
    python3 Game2/tools/run_recovery_eval_queue.py \
      --labels $labels \
      --count 5 \
      --expected-username thebeginning \
      --continue-on-error \
      --timeout 1200 \
      --request-timeout 180 \
      --eval-poll-interval 30 \
      --upload-poll-interval 30 \
      --upload-poll-max 120 || true
  else
    echo "[n548-retry] n548e-j already have at least 5 valid samples each"
  fi

  python3 Game2/tools/summarize_room_evals.py || true
  python3 Game2/tools/analyze_room_score_factors.py || true

  if is_complete; then
    echo "[n548-retry] completed"
    exit 0
  fi

  echo "[n548-retry] incomplete; sleeping 900s"
  sleep 900
done

echo "[n548-retry] incomplete after ${max_attempts} attempts" >&2
exit 1
