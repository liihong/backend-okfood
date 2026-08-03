#!/usr/bin/env bash
# 门店打印机 API 联调（需先执行 sql/migration_060_store_print.sql）
set -euo pipefail
BASE="${BASE_URL:-http://127.0.0.1:8000}"
TOKEN="${ADMIN_TOKEN:?请 export ADMIN_TOKEN=...}"
STORE="${STORE_ID:-1}"

auth=(-H "Authorization: Bearer ${TOKEN}")

echo "== GET profiles =="
curl -sS "${auth[@]}" "${BASE}/api/admin/store-print/profiles?store_id=${STORE}" | head -c 500
echo ""

echo "== GET scene-settings =="
curl -sS "${auth[@]}" "${BASE}/api/admin/store-print/resolve?store_id=${STORE}&scene=delivery_sheet" | head -c 500
echo ""

echo "== GET templates =="
curl -sS "${auth[@]}" "${BASE}/api/admin/store-print/templates" | head -c 500
echo ""
