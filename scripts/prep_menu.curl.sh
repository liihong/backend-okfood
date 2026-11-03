#!/usr/bin/env bash
# 开菜单接口烟测。先把 TOKEN 换成管理端登录拿到的 access_token。
# 份数覆盖只影响本次响应，不会写回本周菜单的日总份。

BASE="${BASE:-http://127.0.0.1:8000}"
TOKEN="${TOKEN:?请设置 TOKEN}"
STORE_ID="${STORE_ID:-1}"
AUTH="Authorization: Bearer ${TOKEN}"

curl -sS -H "$AUTH" "$BASE/api/admin/prep-menu/ingredients?store_id=$STORE_ID"

curl -sS -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"name":"花菜","unit":"g","yield_rate":"0.7000"}' \
  "$BASE/api/admin/prep-menu/ingredients?store_id=$STORE_ID"

curl -sS -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"week_start":"2026-11-02","portion_overrides":[{"meal_period":"lunch","slot":1,"portions":100}]}' \
  "$BASE/api/admin/prep-menu/estimate?store_id=$STORE_ID"
