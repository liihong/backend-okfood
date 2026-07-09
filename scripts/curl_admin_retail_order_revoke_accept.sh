#!/usr/bin/env bash
# 联调示例：商城订单 · 后台取消接单（待发货退回待接单）
# Usage:
#   export ADMIN_TOKEN='...'
#   export ORDER_ID='123'
#   export API_BASE_URL='http://127.0.0.1:8001/api'
#   ./scripts/curl_admin_retail_order_revoke_accept.sh

set -euo pipefail
API_BASE="${API_BASE_URL:-http://127.0.0.1:8000/api}"
STORE_ID="${STORE_ID:-1}"
ORDER_ID="${ORDER_ID:-}"

if [[ -z "${ADMIN_TOKEN:-}" ]]; then
  echo "请先 export ADMIN_TOKEN=管理端 JWT" >&2
  exit 1
fi
if [[ -z "${ORDER_ID}" ]]; then
  echo "请先 export ORDER_ID=商城订单 id" >&2
  exit 1
fi

echo "=== POST /admin/orders/retail-orders/${ORDER_ID}/revoke-accept ==="
curl -sS -X POST "${API_BASE}/admin/orders/retail-orders/${ORDER_ID}/revoke-accept?store_id=${STORE_ID}" \
  -H "Authorization: Bearer ${ADMIN_TOKEN}" \
  -H "Content-Type: application/json"
echo ""
