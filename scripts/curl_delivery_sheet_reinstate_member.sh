#!/usr/bin/env bash
# 管理端极端补送：推单冻结后补进今日配送大表
# 用法：TOKEN=... STORE_ID=1 PHONE=13800000000 ./scripts/curl_delivery_sheet_reinstate_member.sh
set -euo pipefail
BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
TOKEN="${TOKEN:?请设置 TOKEN}"
STORE_ID="${STORE_ID:-1}"
PHONE="${PHONE:?请设置 PHONE}"
MEAL_PERIOD="${MEAL_PERIOD:-lunch}"
DELIVERY_DATE="${DELIVERY_DATE:-}"

BODY=$(jq -n \
  --arg phone "$PHONE" \
  --arg meal_period "$MEAL_PERIOD" \
  --arg delivery_date "$DELIVERY_DATE" \
  '{phone:$phone, meal_period:$meal_period}
   + (if $delivery_date == "" then {} else {delivery_date:$delivery_date} end)')

curl -sS -X POST "${BASE_URL}/api/admin/delivery-sheet/reinstate-member?store_id=${STORE_ID}" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -H "X-Store-Id: ${STORE_ID}" \
  -d "$BODY"
echo
