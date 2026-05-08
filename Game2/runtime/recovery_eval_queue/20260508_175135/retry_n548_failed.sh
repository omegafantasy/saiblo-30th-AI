#!/usr/bin/env bash
set -u

cd /root/autodl-tmp/saiblo_iter || exit 1

python3 Game2/tools/run_room_eval.py \
  --code-id f8b88bdb0eef4b338dbf1ecd0eae6d03 \
  --label n548d_more2 \
  --count 3 \
  --timeout 1200 \
  --poll-interval 30 \
  --request-timeout 180

python3 Game2/tools/run_recovery_eval_queue.py \
  --labels n548e n548f n548g n548h n548i n548j \
  --count 5 \
  --expected-username thebeginning \
  --continue-on-error \
  --timeout 1200 \
  --request-timeout 180 \
  --eval-poll-interval 30 \
  --upload-poll-interval 30 \
  --upload-poll-max 120

python3 Game2/tools/summarize_room_evals.py
python3 Game2/tools/analyze_room_score_factors.py
