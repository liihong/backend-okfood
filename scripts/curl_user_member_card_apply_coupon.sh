#!/usr/bin/env bash
# 会员端：未支付购卡单绑定优惠券（409 续付或支付前换券）
set -euo pipefail
BASE="${BASE:-http://127.0.0.1:8001}"
TOKEN="${MEMBER_TOKEN:?请 export MEMBER_TOKEN=会员JWT}"
ORDER_ID="${ORDER_ID:?请 export ORDER_ID=未支付购卡单id}"
COUPON_ID="${MEMBER_COUPON_ID:?请 export MEMBER_COUPON_ID=用户券id}"

curl -sS -X POST "${BASE}/api/user/member-card-orders/${ORDER_ID}/apply-coupon" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d "{\"member_coupon_id\": ${COUPON_ID}}" \
  | python3 -m json.tool
