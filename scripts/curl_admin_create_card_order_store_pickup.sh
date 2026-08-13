#!/usr/bin/env bash
# 管理端：新建开卡工单并标记门店自提（无需 delivery_address）
# 用法：
#   ADMIN_TOKEN=xxx PHONE=13800138000 NAME=测试 TEMPLATE_ID=1 \
#   ./scripts/curl_admin_create_card_order_store_pickup.sh
#
# 成功响应应为 {code, data, msg}；会员档案 store_pickup=true。

set -euo pipefail
BASE="${API_BASE:-http://127.0.0.1:8000}"
TOKEN="${ADMIN_TOKEN:?请设置 ADMIN_TOKEN（管理端登录后的 Bearer）}"
PHONE="${PHONE:?请设置 PHONE}"
NAME="${NAME:-自提开卡}"
WECHAT_NAME="${WECHAT_NAME:-自提开卡}"
TEMPLATE_ID="${TEMPLATE_ID:?请设置 TEMPLATE_ID（已开启的卡包模版 id）}"
STORE_ID="${STORE_ID:-1}"
START_DATE="${START_DATE:-$(TZ=Asia/Shanghai date +%Y-%m-%d)}"

curl -sS -X POST \
  "${BASE}/api/admin/card-orders?store_id=${STORE_ID}" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -d "{
    \"phone\": \"${PHONE}\",
    \"open_mode\": \"new_member\",
    \"name\": \"${NAME}\",
    \"wechat_name\": \"${WECHAT_NAME}\",
    \"delivery_start_date\": \"${START_DATE}\",
    \"defer_delivery_activation\": false,
    \"membership_template_id\": ${TEMPLATE_ID},
    \"pay_channel\": \"微信\",
    \"pay_status\": \"已缴\",
    \"store_pickup\": true
  }" | python -m json.tool
