#!/usr/bin/env bash
# 联调示例：会员端 · 待接单商城订单修改配送地址
#
# 用法：
#   export BASE_URL=http://127.0.0.1:8000
#   export MEMBER_TOKEN=your_jwt
#   export ORDER_ID=123
#   export MEMBER_ADDRESS_ID=456
#   bash scripts/curl_user_retail_order_patch_delivery.sh

set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
MEMBER_TOKEN="${MEMBER_TOKEN:-}"
ORDER_ID="${ORDER_ID:-}"
MEMBER_ADDRESS_ID="${MEMBER_ADDRESS_ID:-}"

if [[ -z "$MEMBER_TOKEN" ]]; then
  echo "请先 export MEMBER_TOKEN=会员 JWT" >&2
  exit 1
fi
if [[ -z "$ORDER_ID" ]]; then
  echo "请先 export ORDER_ID=商城订单 id" >&2
  exit 1
fi
if [[ -z "$MEMBER_ADDRESS_ID" ]]; then
  echo "请先 export MEMBER_ADDRESS_ID=会员地址 id" >&2
  exit 1
fi

curl -sS -X PATCH "${BASE_URL}/api/user/retail-orders/${ORDER_ID}/delivery" \
  -H "Authorization: Bearer ${MEMBER_TOKEN}" \
  -H "Content-Type: application/json" \
  -d "{\"member_address_id\": ${MEMBER_ADDRESS_ID}}" | jq .
