#!/usr/bin/env bash
# 联调示例：公开菜品库列表（无需登录）
# Usage:
#   export API_BASE_URL='http://127.0.0.1:8000/api'
#   export STORE_ID='1'
#   ./scripts/curl_menu_dishes.sh

set -euo pipefail
API_BASE="${API_BASE_URL:-http://127.0.0.1:8000/api}"
STORE_ID="${STORE_ID:-1}"

echo "=== GET /menu/dishes (X-Store-Id=${STORE_ID}) ==="
curl -sS -w "\n\nHTTP %{http_code} time_total=%{time_total}s\n" \
  "${API_BASE}/menu/dishes" \
  -H "X-Store-Id: ${STORE_ID}"
echo ""

echo "=== 管理端公开展示页 ==="
echo "开发: http://127.0.0.1:5173/dish-catalog?store_id=${STORE_ID}"
echo "生产: https://ok.sourcefire.cn/dish-catalog?store_id=${STORE_ID}"
