#!/usr/bin/env bash
# 联调示例：订单管理 · 当日单次点餐分页 + data.summary 桶统计
# Usage:
#   export ADMIN_TOKEN='...'
#   export API_BASE_URL='http://127.0.0.1:8001/api'
#   ./scripts/curl_admin_orders_daily_single_meals.sh

set -euo pipefail
API_BASE="${API_BASE_URL:-http://127.0.0.1:8000/api}"
STORE_ID="${STORE_ID:-1}"
DAY="${DELIVERY_DATE:-}" # 留空则后端默认上海当日

if [[ -z "${ADMIN_TOKEN:-}" ]]; then
  echo "请先 export ADMIN_TOKEN=管理端 JWT" >&2
  exit 1
fi

QS="store_id=${STORE_ID}&page=1&page_size=20"
if [[ -n "${DAY}" ]]; then
  QS+="&delivery_date=${DAY}"
fi

echo "=== GET /admin/orders/daily/single-meals（检查 data.summary: paid / pending_ship / unpaid / cancelled）==="
curl -sS "${API_BASE}/admin/orders/daily/single-meals?${QS}" \
  -H "Authorization: Bearer ${ADMIN_TOKEN}"
echo ""
