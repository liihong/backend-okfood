#!/usr/bin/env bash
# 联调：会员退卡预览（应退 = 剩余次数 × 菜单单价，不按开卡实收）
# Usage:
#   export ADMIN_TOKEN='...'
#   export MEMBER_ID=1
#   ./scripts/curl_admin_membership_refund_preview.sh

set -euo pipefail
BASE="${API_BASE:-http://127.0.0.1:8000}"
TOKEN="${ADMIN_TOKEN:?请设置 ADMIN_TOKEN（管理端登录后的 Bearer）}"
MEMBER_ID="${MEMBER_ID:?请设置 MEMBER_ID}"
STORE_ID="${STORE_ID:-1}"

echo "=== GET /api/admin/users/${MEMBER_ID}/membership-refund-preview ==="
curl -sS \
  "${BASE}/api/admin/users/${MEMBER_ID}/membership-refund-preview?store_id=${STORE_ID}" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Accept: application/json" | python -m json.tool
echo ""
