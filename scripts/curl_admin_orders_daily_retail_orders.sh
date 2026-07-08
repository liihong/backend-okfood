#!/usr/bin/env bash
# 联调示例：订单管理 · 商城订单（仅按配送阶段 Tab 过滤，不按下单日）
# Usage:
#   export ADMIN_TOKEN='...'
#   export API_BASE_URL='http://127.0.0.1:8001/api'
#   export FULFILLMENT_PHASE='pending_ship'  # 可选：awaiting_accept / pending_ship / in_delivery / delivered / after_sale
#   ./scripts/curl_admin_orders_daily_retail_orders.sh

set -euo pipefail
API_BASE="${API_BASE_URL:-http://127.0.0.1:8000/api}"
STORE_ID="${STORE_ID:-1}"
PHASE="${FULFILLMENT_PHASE:-pending_ship}"

if [[ -z "${ADMIN_TOKEN:-}" ]]; then
  echo "请先 export ADMIN_TOKEN=管理端 JWT" >&2
  exit 1
fi

QS="store_id=${STORE_ID}&page=1&page_size=20&fulfillment_phase=${PHASE}"

echo "=== GET /admin/orders/daily/retail-orders（待发货：跨日期汇总）==="
curl -sS "${API_BASE}/admin/orders/daily/retail-orders?${QS}" \
  -H "Authorization: Bearer ${ADMIN_TOKEN}"
echo ""
