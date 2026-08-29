#!/usr/bin/env bash
# 礼品券管理端联调（需管理员 Token）
# 用法: TOKEN=... STORE_ID=1 bash scripts/curl_admin_gift_coupons.sh

set -euo pipefail
BASE="${BASE:-http://127.0.0.1:8000}"
TOKEN="${TOKEN:?请设置 TOKEN}"
STORE_ID="${STORE_ID:-1}"
AUTH=(-H "Authorization: Bearer ${TOKEN}" -H "Content-Type: application/json")

echo "== 活动列表 =="
curl -sS "${BASE}/api/admin/gift-coupons/campaigns?store_id=${STORE_ID}" "${AUTH[@]}" | head -c 800
echo

echo "== 圈人预览（8月月卡示例，按需改日期） =="
curl -sS -X POST "${BASE}/api/admin/gift-coupons/campaigns/preview-audience?store_id=${STORE_ID}" \
  "${AUTH[@]}" \
  -d '{"plan_kinds":["month"],"credited_from":"2026-08-01","credited_to":"2026-08-31","exclude_membership_refunded":true}' | head -c 800
echo
