#!/usr/bin/env bash
# 平台：同步小程序服务器域名 / 查询生效域名（需管理员 JWT）
# 用法：
#   export ADMIN_TOKEN=...
#   export BASE_URL=https://ok.sourcefire.cn
#   export TENANT_ID=3
#   bash scripts/curl_wx_code_sync_domains.sh

set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8001}"
ADMIN_TOKEN="${ADMIN_TOKEN:?请设置 ADMIN_TOKEN}"
TENANT_ID="${TENANT_ID:-3}"
ACTION="${ACTION:-add}"

AUTH_H=(-H "Authorization: Bearer ${ADMIN_TOKEN}" -H "Content-Type: application/json")

echo "== 同步域名 tenant=${TENANT_ID} action=${ACTION} =="
curl -sS -X POST "${BASE_URL}/api/admin/system/tenants/${TENANT_ID}/wx-code/sync-domains" \
  "${AUTH_H[@]}" \
  -d "{\"action\": \"${ACTION}\"}" \
  | python -m json.tool

echo "== 生效域名 tenant=${TENANT_ID} =="
curl -sS "${BASE_URL}/api/admin/system/tenants/${TENANT_ID}/wx-code/effective-domains" \
  "${AUTH_H[@]}" \
  | python -m json.tool
