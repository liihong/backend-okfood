#!/usr/bin/env bash
# 营业概览：核对明日预测底栏「暂停配送」= data.paused_delivery_count
set -euo pipefail
BASE="${BASE:-http://127.0.0.1:8001}"
TOKEN="${ADMIN_TOKEN:?请 export ADMIN_TOKEN=管理端JWT}"
STORE_ID="${STORE_ID:-1}"

echo "== GET /api/admin/dashboard-summary store_id=${STORE_ID} =="
curl -sS "${BASE}/api/admin/dashboard-summary?store_id=${STORE_ID}" \
  -H "Authorization: Bearer ${TOKEN}" | jq '{
    code,
    msg,
    paused_delivery_count: .data.paused_delivery_count,
    tomorrow_leave_members: .data.tomorrow_leave_members,
    tomorrow_first_meal_new_members: .data.tomorrow_first_meal_new_members,
    tomorrow_single_retail_total_quantity: .data.tomorrow_single_retail_total_quantity
  }'
