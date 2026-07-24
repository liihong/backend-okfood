#!/usr/bin/env bash
# 平台：模板列表 / 发布状态 / commit / 体验码（需管理员 JWT）
# 用法：
#   export ADMIN_TOKEN=...
#   export BASE_URL=https://ok.sourcefire.cn
#   export TENANT_ID=3
#   bash scripts/curl_wx_code_commit.sh

set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8001}"
ADMIN_TOKEN="${ADMIN_TOKEN:?请设置 ADMIN_TOKEN}"
TENANT_ID="${TENANT_ID:-3}"
TEMPLATE_ID="${TEMPLATE_ID:-1}"
USER_VERSION="${USER_VERSION:-1.0.0}"
USER_DESC="${USER_DESC:-SaaS 体验版}"

AUTH_H=(-H "Authorization: Bearer ${ADMIN_TOKEN}" -H "Content-Type: application/json")

echo "== 模板列表 =="
curl -sS "${BASE_URL}/api/admin/system/wx-open/templates" "${AUTH_H[@]}" | python -m json.tool

echo "== 发布状态 tenant=${TENANT_ID} =="
curl -sS "${BASE_URL}/api/admin/system/tenants/${TENANT_ID}/wx-code/publish-state" "${AUTH_H[@]}" \
  | python -m json.tool

echo "== commit template_id=${TEMPLATE_ID} =="
curl -sS -X POST "${BASE_URL}/api/admin/system/tenants/${TENANT_ID}/wx-code/commit" \
  "${AUTH_H[@]}" \
  -d "{\"template_id\": ${TEMPLATE_ID}, \"user_version\": \"${USER_VERSION}\", \"user_desc\": \"${USER_DESC}\"}" \
  | python -m json.tool

echo "== 体验码（仅打印字段，不落盘） =="
curl -sS "${BASE_URL}/api/admin/system/tenants/${TENANT_ID}/wx-code/trial-qrcode" "${AUTH_H[@]}" \
  | python -c "import sys,json; d=json.load(sys.stdin); data=d.get('data') or {}; print({k: (str(v)[:48]+'...') if k=='image_base64' else v for k,v in data.items()}); print('code', d.get('code'), d.get('msg'))"
