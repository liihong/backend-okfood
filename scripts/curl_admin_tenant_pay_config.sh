#!/usr/bin/env bash
# 店主「门店配置」本租户微信支付商户号联调
set -euo pipefail
BASE="${BASE_URL:-http://127.0.0.1:8000}"
TOKEN="${ADMIN_TOKEN:?请 export ADMIN_TOKEN=...}"

auth=(-H "Authorization: Bearer ${TOKEN}" -H "Content-Type: application/json")

echo "== GET /api/admin/tenant-pay-config =="
curl -sS "${auth[@]}" "${BASE}/api/admin/tenant-pay-config"
echo ""

echo "== PUT /api/admin/tenant-pay-config（示例：只改特约商户号） =="
curl -sS "${auth[@]}" -X PUT "${BASE}/api/admin/tenant-pay-config" \
  -d '{"wechat_pay_mch_id":"1116333132"}'
echo ""
