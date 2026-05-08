#!/usr/bin/env bash
set -u

cd /root/autodl-tmp/saiblo_iter || exit 1

attempt=0
max_attempts=6

while [ "$attempt" -lt "$max_attempts" ]; do
  attempt=$((attempt + 1))
  echo "[n548-retry] attempt ${attempt}/${max_attempts}"

  python3 Game2/tools/run_room_eval.py \
    --code-id f8b88bdb0eef4b338dbf1ecd0eae6d03 \
    --label n548d_more2 \
    --count 3 \
    --timeout 1200 \
    --poll-interval 30 \
    --request-timeout 180 || true

  python3 Game2/tools/run_recovery_eval_queue.py \
    --labels n548e n548f n548g n548h n548i n548j \
    --count 5 \
    --expected-username thebeginning \
    --continue-on-error \
    --timeout 1200 \
    --request-timeout 180 \
    --eval-poll-interval 30 \
    --upload-poll-interval 30 \
    --upload-poll-max 120 || true

  python3 Game2/tools/summarize_room_evals.py || true
  python3 Game2/tools/analyze_room_score_factors.py || true

  if python3 - <<'PY'
import glob
import json
import sys

def score_count(label: str) -> int:
    total = 0
    for path in glob.glob(f'Game2/runtime/room_matches/*_{label}_room/summary.json'):
        try:
            data = json.load(open(path, encoding='utf-8'))
        except Exception:
            continue
        for row in data.get('rows', []):
            if isinstance(row.get('score'), int):
                total += 1
    return total

ok = score_count('n548d') + score_count('n548d_more') + score_count('n548d_more2') >= 5
for label in ['n548e', 'n548f', 'n548g', 'n548h', 'n548i', 'n548j']:
    ok = ok and score_count(label) >= 5
sys.exit(0 if ok else 1)
PY
  then
    echo "[n548-retry] completed"
    exit 0
  fi

  echo "[n548-retry] incomplete; sleeping 900s"
  sleep 900
done

echo "[n548-retry] incomplete after ${max_attempts} attempts" >&2
exit 1
