#!/usr/bin/env bash
# 会员取消未支付开卡工单
# 用法: TOKEN=xxx ORDER_ID=814 ./scripts/curl_user_member_card_order_cancel.sh

set -euo pipefail
BASE="${BASE:-http://127.0.0.1:8001}"
TOKEN="${TOKEN:?需要会员 JWT}"
ORDER_ID="${ORDER_ID:?需要 ORDER_ID}"

curl -sS -X POST "${BASE}/api/user/member-card-orders/${ORDER_ID}/cancel" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{}' | python3 -m json.tool
