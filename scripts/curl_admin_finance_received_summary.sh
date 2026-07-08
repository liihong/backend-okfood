#!/usr/bin/env bash
# 联调示例：财务统计 · 已收汇总（含商城订单 store_retail_orders 分项）
# Usage:
#   export ADMIN_TOKEN='...'
#   export API_BASE_URL='http://127.0.0.1:8001/api'
#   ./scripts/curl_admin_finance_received_summary.sh

set -euo pipefail
API_BASE="${API_BASE_URL:-http://127.0.0.1:8000/api}"
STORE_ID="${STORE_ID:-1}"

if [[ -z "${ADMIN_TOKEN:-}" ]]; then
  echo "请先 export ADMIN_TOKEN=管理端 JWT" >&2
  exit 1
fi

echo "=== GET /admin/finance/received-summary（检查 data.today.store_retail_orders）==="
curl -sS "${API_BASE}/admin/finance/received-summary?store_id=${STORE_ID}" \
  -H "Authorization: Bearer ${ADMIN_TOKEN}"
echo ""
