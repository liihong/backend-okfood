#!/usr/bin/env bash
# 联调示例：客服配送资质校验（租户配送片区；需管理端 Bearer）
# Usage:
#   export ADMIN_TOKEN='...'
#   export API_BASE_URL='http://127.0.0.1:8000/api'
#   ./scripts/curl_delivery_region_consult.sh

set -euo pipefail
API_BASE="${API_BASE_URL:-http://127.0.0.1:8000/api}"
STORE_ID="${STORE_ID:-1}"

if [[ -z "${ADMIN_TOKEN:-}" ]]; then
  echo "请先 export ADMIN_TOKEN=管理端 JWT" >&2
  exit 1
fi

echo "=== 关键字地理编码 + 片区判断 ==="
curl -sS "${API_BASE}/admin/delivery-region/consult?store_id=${STORE_ID}" \
  -H "Authorization: Bearer ${ADMIN_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"address_keyword":"河南省新乡市中心医院"}'
echo ""

echo ""
echo "=== GCJ-02 坐标直接判断 ==="
curl -sS "${API_BASE}/admin/delivery-region/consult?store_id=${STORE_ID}" \
  -H "Authorization: Bearer ${ADMIN_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"location":{"lng":113.93,"lat":35.30}}'
echo ""
