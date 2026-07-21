#!/usr/bin/env bash
# 平台租户管理员：创建/编辑展示名称（需先 platform admin 登录拿到 TOKEN）
set -euo pipefail
BASE="${BASE:-http://127.0.0.1:8001}"
TOKEN="${ADMIN_TOKEN:?请 export ADMIN_TOKEN=...}"
TENANT_ID="${TENANT_ID:-1}"
ADMIN_USERNAME="${ADMIN_USERNAME:?请 export ADMIN_USERNAME=登录账号}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:?请 export ADMIN_PASSWORD=至少8位密码}"
ADMIN_DISPLAY_NAME="${ADMIN_DISPLAY_NAME:-测试店长}"

echo "== 创建租户管理员（含展示名称） tenant_id=${TENANT_ID} =="
CREATE=$(curl -sS -X POST "${BASE}/api/admin/system/tenants/${TENANT_ID}/admins" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d "{
    \"username\": \"${ADMIN_USERNAME}\",
    \"display_name\": \"${ADMIN_DISPLAY_NAME}\",
    \"password\": \"${ADMIN_PASSWORD}\",
    \"role\": \"full\"
  }")
echo "$CREATE" | python3 -m json.tool

echo "== 管理员列表 =="
curl -sS "${BASE}/api/admin/system/tenants/${TENANT_ID}/admins" \
  -H "Authorization: Bearer ${TOKEN}" | python3 -m json.tool

echo "== 登录验证 display_name 字段 =="
curl -sS -X POST "${BASE}/api/admin/login" \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"${ADMIN_USERNAME}\",\"password\":\"${ADMIN_PASSWORD}\"}" \
  | python3 -m json.tool
