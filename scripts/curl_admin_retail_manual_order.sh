#!/usr/bin/env bash
# 管理端：商城订单手动建单 & 协助抖音验券
# 用法：export ADMIN_TOKEN=... && bash scripts/curl_admin_retail_manual_order.sh

set -euo pipefail

BASE="${BASE_URL:-http://127.0.0.1:8000}"
TOKEN="${ADMIN_TOKEN:?请设置 ADMIN_TOKEN}"
STORE_ID="${STORE_ID:-1}"
PHONE="${PHONE:-13800138000}"

echo "== POST 手动建单（门店自提，已支付） =="
curl -sS -X POST "${BASE}/api/admin/orders/retail-orders?store_id=${STORE_ID}" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d "{
    \"phone\": \"${PHONE}\",
    \"name\": \"测试会员\",
    \"retail_product_id\": 1,
    \"quantity\": 1,
    \"store_pickup\": true,
    \"pay_channel\": \"线下\",
    \"pay_status\": \"已支付\",
    \"remark\": \"curl 测试手动建单\"
  }" | python -m json.tool

echo ""
echo "== POST 协助抖音验券（需有效券码） =="
DOUYIN_CODE="${DOUYIN_CODE:-}"
if [[ -z "${DOUYIN_CODE}" ]]; then
  echo "跳过：请设置 DOUYIN_CODE 环境变量后再测验券"
  exit 0
fi

curl -sS -X POST "${BASE}/api/admin/marketing/douyin/certificates/redeem?store_id=${STORE_ID}" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d "{
    \"phone\": \"${PHONE}\",
    \"code\": \"${DOUYIN_CODE}\"
  }" | python -m json.tool
