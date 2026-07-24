#!/usr/bin/env bash
# 平台管理员：为租户生成微信第三方平台传统模式授权链接
# 用法：TOKEN=... TENANT_ID=3 bash scripts/curl_wx_pre_auth_link.sh

set -euo pipefail
BASE="${BASE:-http://127.0.0.1:8001}"
TOKEN="${TOKEN:?请先 export TOKEN=平台管理员 JWT}"
TENANT_ID="${TENANT_ID:-3}"

echo "== POST /api/admin/system/tenants/${TENANT_ID}/wx-authorizer/pre-auth-link =="
curl -sS -X POST "${BASE}/api/admin/system/tenants/${TENANT_ID}/wx-authorizer/pre-auth-link" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{}' | python -m json.tool
