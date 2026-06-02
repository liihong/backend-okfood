#!/usr/bin/env bash
# 管理端：更新开卡工单起送日（允许选当日上海业务日）
# 用法：ADMIN_TOKEN=xxx ORDER_ID=1 DELIVERY_START=2026-06-02 ./scripts/curl_admin_patch_card_order_delivery_start.sh

set -euo pipefail
BASE="${API_BASE:-https://ok.sourcefire.cn}"
TOKEN="${ADMIN_TOKEN:?请设置 ADMIN_TOKEN（管理端登录后的 Bearer）}"
ORDER_ID="${ORDER_ID:?请设置 ORDER_ID}"
DELIVERY_START="${DELIVERY_START:?请设置 DELIVERY_START，格式 YYYY-MM-DD（可为当日）}"
STORE_ID="${STORE_ID:-1}"

curl -sS -X PATCH \
  "${BASE}/api/admin/card-orders/${ORDER_ID}?store_id=${STORE_ID}" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d "{\"delivery_start_date\":\"${DELIVERY_START}\"}" | python3 -m json.tool
