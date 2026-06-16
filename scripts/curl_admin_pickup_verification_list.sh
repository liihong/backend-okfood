#!/usr/bin/env bash
# 首页门店自提快速核销舱（轻量接口，不含完整配送大表）
set -euo pipefail
BASE="${BASE:-http://127.0.0.1:8001}"
TOKEN="${ADMIN_TOKEN:?请 export ADMIN_TOKEN=管理端JWT}"
DATE="${1:-$(date +%F)}"

echo "== GET /api/admin/pickup-verification-list delivery_date=${DATE} =="
curl -sS "${BASE}/api/admin/pickup-verification-list?delivery_date=${DATE}" \
  -H "Authorization: Bearer ${TOKEN}" | jq .
