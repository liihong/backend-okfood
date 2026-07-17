#!/usr/bin/env bash
# 开卡工单列表：按创建时间（上海自然日）筛选
# 用法：ADMIN_TOKEN=xxx ./scripts/curl_admin_card_orders_date_filter.sh
set -euo pipefail

BASE="${BASE_URL:-http://127.0.0.1:8000}"
TOKEN="${ADMIN_TOKEN:?请设置 ADMIN_TOKEN}"

DATE_FROM="${DATE_FROM:-$(date +%Y-%m-%d)}"
DATE_TO="${DATE_TO:-$(date +%Y-%m-%d)}"

curl -sS "${BASE}/api/admin/card-orders?include_history=true&page=1&page_size=15&date_from=${DATE_FROM}&date_to=${DATE_TO}" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Accept: application/json" | python -m json.tool
