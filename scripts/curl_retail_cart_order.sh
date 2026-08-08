#!/usr/bin/env bash
# 商城购物车下单 API 自测（需替换 TOKEN 与地址 ID）
# 用法: TOKEN=xxx ADDR_ID=1 bash scripts/curl_retail_cart_order.sh

BASE="${BASE_URL:-http://127.0.0.1:8001}"
TOKEN="${TOKEN:?需要会员 TOKEN}"
ADDR_ID="${ADDR_ID:?需要 member_address_id}"

curl -sS -X POST "$BASE/api/user/retail-orders" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"items\":[{\"retail_product_id\":1,\"quantity\":2},{\"retail_product_id\":2,\"quantity\":1}],\"member_address_id\":$ADDR_ID,\"store_pickup\":false}" | python -m json.tool
