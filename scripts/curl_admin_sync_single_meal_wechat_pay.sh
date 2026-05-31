#!/usr/bin/env bash
# 管理端：单次零售订单微信已扣款但库内仍「未支付」时，向微信查单并同步入账。
# 用法：ADMIN_TOKEN=xxx ORDER_ID=154 STORE_ID=1 ./scripts/curl_admin_sync_single_meal_wechat_pay.sh

set -euo pipefail
BASE="${BASE_URL:-http://127.0.0.1:8001}"
TOKEN="${ADMIN_TOKEN:?请设置 ADMIN_TOKEN}"
ORDER_ID="${ORDER_ID:?请设置 ORDER_ID（如 154）}"
STORE_ID="${STORE_ID:-1}"

curl -sS -X POST \
  "${BASE}/api/admin/orders/single-meals/${ORDER_ID}/sync-wechat-pay?store_id=${STORE_ID}" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" | python3 -m json.tool
