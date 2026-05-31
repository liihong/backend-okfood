#!/usr/bin/env bash
# 管理端：从微信拉单并将开卡工单记为已缴（补救已扣款仍显示未缴）
# 用法：ADMIN_TOKEN=xxx ORDER_ID=775 ./scripts/curl_admin_sync_card_order_wechat_pay.sh

set -euo pipefail
BASE="${API_BASE:-https://ok.sourcefire.cn}"
TOKEN="${ADMIN_TOKEN:?请设置 ADMIN_TOKEN（管理端登录后的 Bearer）}"
ORDER_ID="${ORDER_ID:?请设置 ORDER_ID，如 775}"
STORE_ID="${STORE_ID:-1}"

curl -sS -X POST \
  "${BASE}/api/admin/card-orders/${ORDER_ID}/sync-wechat-pay?store_id=${STORE_ID}" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" | python3 -m json.tool
