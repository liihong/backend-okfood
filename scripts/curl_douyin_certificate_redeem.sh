#!/usr/bin/env bash
# 抖音验券联调脚本（需替换 TOKEN、券码、门店配置）
set -euo pipefail

BASE="${API_BASE:-http://127.0.0.1:8001}"
MEMBER_TOKEN="${MEMBER_TOKEN:-}"
ADMIN_TOKEN="${ADMIN_TOKEN:-}"
STORE_ID="${STORE_ID:-1}"
DOUYIN_CODE="${DOUYIN_CODE:-}"

if [[ -z "$MEMBER_TOKEN" ]]; then
  echo "请设置 MEMBER_TOKEN（会员 JWT）"
  exit 1
fi

echo "== 我的优惠券列表 =="
curl -sS "${BASE}/api/user/member-coupons/wallet" \
  -H "Authorization: Bearer ${MEMBER_TOKEN}" | jq .

if [[ -n "$DOUYIN_CODE" ]]; then
  echo "== 抖音验券兑换 =="
  curl -sS "${BASE}/api/user/douyin-certificates/redeem" \
    -H "Authorization: Bearer ${MEMBER_TOKEN}" \
    -H "Content-Type: application/json" \
    -d "{\"code\":\"${DOUYIN_CODE}\"}" | jq .
fi

if [[ -n "$ADMIN_TOKEN" ]]; then
  echo "== 管理端：商品映射 =="
  curl -sS "${BASE}/api/admin/marketing/douyin/product-mappings?store_id=${STORE_ID}&page=1&page_size=20" \
    -H "Authorization: Bearer ${ADMIN_TOKEN}" | jq .

  echo "== 管理端：核销记录 =="
  curl -sS "${BASE}/api/admin/marketing/douyin/redemptions?store_id=${STORE_ID}&page=1&page_size=20" \
    -H "Authorization: Bearer ${ADMIN_TOKEN}" | jq .
fi
