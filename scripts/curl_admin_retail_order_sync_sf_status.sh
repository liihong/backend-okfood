#!/usr/bin/env bash
# 联调示例：商城订单 · 批量同步顺丰配送状态
# Usage:
#   export ADMIN_TOKEN='...'
#   export API_BASE_URL='http://127.0.0.1:8001/api'
#   ./scripts/curl_admin_retail_order_sync_sf_status.sh
#
# 单笔同步（可选）：
#   export ORDER_ID='123'
#   ./scripts/curl_admin_retail_order_sync_sf_status.sh single

set -euo pipefail
API_BASE="${API_BASE_URL:-http://127.0.0.1:8000/api}"
STORE_ID="${STORE_ID:-1}"
ORDER_ID="${ORDER_ID:-}"
MODE="${1:-bulk}"

if [[ -z "${ADMIN_TOKEN:-}" ]]; then
  echo "请先 export ADMIN_TOKEN=管理端 JWT" >&2
  exit 1
fi

if [[ "${MODE}" == "single" ]]; then
  if [[ -z "${ORDER_ID}" ]]; then
    echo "单笔同步请先 export ORDER_ID=商城订单 id" >&2
    exit 1
  fi
  echo "=== POST /admin/orders/retail-orders/${ORDER_ID}/sync-delivered-from-sf-monitor ==="
  curl -sS -X POST \
    "${API_BASE}/admin/orders/retail-orders/${ORDER_ID}/sync-delivered-from-sf-monitor?store_id=${STORE_ID}" \
    -H "Authorization: Bearer ${ADMIN_TOKEN}" \
    -H "Content-Type: application/json"
  echo ""
  exit 0
fi

echo "=== POST /admin/orders/retail-orders/sync-delivery-status ==="
curl -sS -X POST \
  "${API_BASE}/admin/orders/retail-orders/sync-delivery-status?store_id=${STORE_ID}&max_orders=500" \
  -H "Authorization: Bearer ${ADMIN_TOKEN}" \
  -H "Content-Type: application/json"
echo ""
