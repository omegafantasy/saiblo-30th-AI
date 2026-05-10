#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

ENTITY_ID="${SAIBLO_ENTITY_ID:-21493}"
ENTITY_NAME="${SAIBLO_ENTITY_NAME:-sk548e0910pyh}"
USERNAME="${SAIBLO_USERNAME:-thebeginning}"
LABELS="${GAME2_CEILING_LABELS:-sk548e0910qcb sk548e0910qcc sk548e0910qcd sk548e0910qce sk548e0910qcf}"
COUNT="${GAME2_CEILING_COUNT:-2}"
ROOM_TIMEOUT="${GAME2_CEILING_ROOM_TIMEOUT:-900}"
POLL_INTERVAL="${GAME2_CEILING_POLL_INTERVAL:-30}"
REQUEST_TIMEOUT="${SAIBLO_API_TIMEOUT:-180}"
HEALTH_TIMEOUT="${GAME2_CEILING_HEALTH_TIMEOUT:-45}"
UPLOAD_POLL_INTERVAL="${GAME2_CEILING_UPLOAD_POLL_INTERVAL:-20}"
UPLOAD_POLL_MAX="${GAME2_CEILING_UPLOAD_POLL_MAX:-30}"
SKIP_EVALUATED="${GAME2_CEILING_SKIP_EVALUATED:-1}"
LOG_DIR="$ROOT_DIR/Game2/runtime/ceiling_queue_logs/$(date -u +'%Y%m%d_%H%M%S')"

mkdir -p "$LOG_DIR"

echo "[ceiling-queue] health check entity_id=$ENTITY_ID timeout=$HEALTH_TIMEOUT"
if ! timeout "$HEALTH_TIMEOUT" env SAIBLO_API_TIMEOUT="$REQUEST_TIMEOUT" \
  python3 saiblo_tools.py codes --entity-id "$ENTITY_ID" >"$LOG_DIR/health.json" 2>"$LOG_DIR/health.err"; then
  echo "[ceiling-queue] API health check failed; logs: $LOG_DIR" >&2
  exit 75
fi

for label in $LABELS; do
  source="Game2/deepclue_ai/${label}/ai.py"
  if [[ ! -f "$source" ]]; then
    echo "[ceiling-queue] missing source for $label: $source" >&2
    exit 2
  fi

  if [[ "$SKIP_EVALUATED" != "0" ]]; then
    existing_count="$(find Game2/runtime/room_matches -maxdepth 1 -type d -name "*_${label}_room" | wc -l | tr -d ' ')"
    if [[ "${existing_count:-0}" != "0" ]]; then
      echo "[ceiling-queue] skip label=$label existing_room_dirs=$existing_count"
      continue
    fi
  fi

  upload_json="$LOG_DIR/${label}_upload.json"
  upload_err="$LOG_DIR/${label}_upload.err"
  eval_json="$LOG_DIR/${label}_eval.json"
  eval_err="$LOG_DIR/${label}_eval.err"

  echo "[ceiling-queue] upload label=$label source=$source"
  env SAIBLO_SKIP_ENTITY_LIST=1 SAIBLO_API_TIMEOUT="$REQUEST_TIMEOUT" \
    python3 saiblo_tools.py upload-ai \
      --game-id 53 \
      --entity-id "$ENTITY_ID" \
      --entity-name "$ENTITY_NAME" \
      --language python \
      --source "$source" \
      --remark "r" \
      --username "$USERNAME" \
      --skip-entity-list \
      --wait-compile \
      --poll-interval "$UPLOAD_POLL_INTERVAL" \
      --poll-max "$UPLOAD_POLL_MAX" \
      >"$upload_json" 2>"$upload_err"

  code_id="$(python3 - "$upload_json" <<'PY'
import json
import sys
with open(sys.argv[1], encoding='utf-8') as fh:
    data = json.load(fh)
print(str(data.get('uploaded_code_id') or '').replace('-', ''))
PY
)"
  if [[ -z "$code_id" ]]; then
    echo "[ceiling-queue] upload did not return code id for $label; logs: $LOG_DIR" >&2
    exit 3
  fi

  echo "[ceiling-queue] eval label=$label code_id=$code_id count=$COUNT"
  python3 Game2/tools/run_room_eval.py \
    --code-id "$code_id" \
    --label "$label" \
    --count "$COUNT" \
    --timeout "$ROOM_TIMEOUT" \
    --poll-interval "$POLL_INTERVAL" \
    --request-timeout "$REQUEST_TIMEOUT" \
    >"$eval_json" 2>"$eval_err"
done

echo "[ceiling-queue] done logs=$LOG_DIR"
