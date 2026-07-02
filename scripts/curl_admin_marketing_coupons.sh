#!/usr/bin/env bash
# 管理端营销优惠券联调脚本（需先 admin 登录拿到 TOKEN）
set -euo pipefail
BASE="${BASE:-http://127.0.0.1:8001}"
TOKEN="${ADMIN_TOKEN:?请 export ADMIN_TOKEN=...}"
STORE_ID="${STORE_ID:-1}"

echo "== 创建券种 =="
CREATE=$(curl -sS -X POST "${BASE}/api/admin/marketing/coupon-templates?store_id=${STORE_ID}" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "购卡测试券50元",
    "discount_yuan": "50.00",
    "min_order_yuan": "0.00",
    "biz_type": "member_card",
    "scope_level": "all",
    "validity_mode": "days_after_grant",
    "valid_days_after_grant": 30,
    "usage_instructions": "仅小程序购卡可用",
    "sort_order": 10,
    "is_active": true
  }')
echo "$CREATE" | python3 -m json.tool
TPL_ID=$(echo "$CREATE" | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['id'])")

echo "== 券种列表 =="
curl -sS "${BASE}/api/admin/marketing/coupon-templates?store_id=${STORE_ID}&page=1" \
  -H "Authorization: Bearer ${TOKEN}" | python3 -m json.tool

MEMBER_PHONE="${MEMBER_PHONE:?请 export MEMBER_PHONE=会员手机号}"
echo "== 发放给用户 phone=${MEMBER_PHONE} =="
curl -sS -X POST "${BASE}/api/admin/marketing/member-coupons/grant?store_id=${STORE_ID}" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d "{\"template_id\": ${TPL_ID}, \"member_phone\": \"${MEMBER_PHONE}\", \"remark\": \"curl测试\"}" \
  | python3 -m json.tool

echo "== 批量发放（示例） =="
curl -sS -X POST "${BASE}/api/admin/marketing/member-coupons/grant-batch?store_id=${STORE_ID}" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d "{\"template_id\": ${TPL_ID}, \"member_phones\": [\"${MEMBER_PHONE}\"], \"remark\": \"curl批量测试\"}" \
  | python3 -m json.tool

echo "== 发放记录（含 summary 统计） =="
curl -sS "${BASE}/api/admin/marketing/member-coupons?store_id=${STORE_ID}&page=1" \
  -H "Authorization: Bearer ${TOKEN}" | python3 -m json.tool

echo "== 按手机号搜索发放记录 phone=${MEMBER_PHONE} =="
curl -sS "${BASE}/api/admin/marketing/member-coupons?store_id=${STORE_ID}&page=1&member_phone=${MEMBER_PHONE}" \
  -H "Authorization: Bearer ${TOKEN}" | python3 -m json.tool
