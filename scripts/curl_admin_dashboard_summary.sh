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
    today_menu_day_total_stock: .data.today_menu_day_total_stock,
    tomorrow_menu_day_total_stock: .data.tomorrow_menu_day_total_stock,
    today_meals_week_over_week_caption: .data.today_meals_week_over_week_caption,
    tomorrow_meals_week_over_week_caption: .data.tomorrow_meals_week_over_week_caption,
    paused_delivery_count: .data.paused_delivery_count
  }'
