#!/usr/bin/env bash
# 会员端：进小程序购卡优惠券提醒汇总
set -euo pipefail
BASE="${BASE:-http://127.0.0.1:8001}"
TOKEN="${MEMBER_TOKEN:?请 export MEMBER_TOKEN=会员JWT}"

curl -sS "${BASE}/api/user/member-coupons/reminder" \
  -H "Authorization: Bearer ${TOKEN}" \
  | python3 -m json.tool
