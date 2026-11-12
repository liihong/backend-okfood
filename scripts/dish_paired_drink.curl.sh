#!/usr/bin/env bash
# 随餐饮饮品库烟测。先把 TOKEN 换成管理端登录拿到的 access_token。

BASE="${BASE:-http://127.0.0.1:8000}"
TOKEN="${TOKEN:?请设置 TOKEN}"
STORE_ID="${STORE_ID:-1}"
AUTH="Authorization: Bearer ${TOKEN}"

curl -sS -H "$AUTH" "$BASE/api/admin/drinks?store_id=$STORE_ID"
echo

curl -sS -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"name":"柠檬气泡","description":"冷放，放袋侧","is_enabled":true}' \
  "$BASE/api/admin/drink?store_id=$STORE_ID"
echo
