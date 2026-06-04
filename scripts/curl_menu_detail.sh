#!/usr/bin/env bash
# 联调示例：餐品详情（含单次卡库存，无需登录）
# Usage:
#   export API_BASE_URL='http://127.0.0.1:8000/api'
#   export STORE_ID='1'
#   ./scripts/curl_menu_detail.sh 32 2026-06-02

set -euo pipefail
API_BASE="${API_BASE_URL:-http://127.0.0.1:8000/api}"
STORE_ID="${STORE_ID:-1}"
DISH_ID="${1:-32}"
SERVICE_DATE="${2:-2026-06-02}"

echo "=== GET /menu/detail/${DISH_ID}?service_date=${SERVICE_DATE} (含 base_delivery_fee_yuan) ==="
curl -sS -w "\n\nHTTP %{http_code} time_total=%{time_total}s\n" \
  "${API_BASE}/menu/detail/${DISH_ID}?service_date=${SERVICE_DATE}" \
  -H "X-Store-Id: ${STORE_ID}"
echo ""
