#!/usr/bin/env bash
# 菜品管理列表：校验 last_used_date 字段（需先登录获取 ADMIN_TOKEN）
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
ADMIN_TOKEN="${ADMIN_TOKEN:?请先 export ADMIN_TOKEN=你的后台JWT}"

curl -sS "${BASE_URL}/api/admin/dishes?store_id=1" \
  -H "Authorization: Bearer ${ADMIN_TOKEN}" \
  | python -m json.tool \
  | head -n 40
