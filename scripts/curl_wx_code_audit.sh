#!/usr/bin/env bash
# 租户小程序 · 提审 / 查状态 / 发布正式版（须先 commit 体验版）
set -euo pipefail

BASE_URL="${BASE_URL:-https://ok.sourcefire.cn}"
TENANT_ID="${TENANT_ID:-3}"
ADMIN_TOKEN="${ADMIN_TOKEN:?请 export ADMIN_TOKEN=平台管理员JWT}"

auth=(-H "Authorization: Bearer ${ADMIN_TOKEN}")

echo "== categories =="
curl -sS "${auth[@]}" "${BASE_URL}/api/admin/system/tenants/${TENANT_ID}/wx-code/categories" | head -c 800
echo ""

echo "== audit-status =="
curl -sS "${auth[@]}" "${BASE_URL}/api/admin/system/tenants/${TENANT_ID}/wx-code/audit-status" | head -c 800
echo ""

echo "== submit-audit (示例，默认不执行；设 RUN_SUBMIT=1 启用) =="
if [[ "${RUN_SUBMIT:-0}" == "1" ]]; then
  curl -sS "${auth[@]}" -X POST "${BASE_URL}/api/admin/system/tenants/${TENANT_ID}/wx-code/submit-audit" \
    -H "Content-Type: application/json" \
    -d '{"item_list":[{"address":"pages/home/index","tag":"餐饮 点餐","first_class":"餐饮","second_class":"点餐","first_id":1,"second_id":2,"title":"首页"}],"version_desc":"SaaS 正式版"}' \
    | head -c 800
  echo ""
fi

echo "== release (示例，默认不执行；设 RUN_RELEASE=1 且审核已通过) =="
if [[ "${RUN_RELEASE:-0}" == "1" ]]; then
  curl -sS "${auth[@]}" -X POST "${BASE_URL}/api/admin/system/tenants/${TENANT_ID}/wx-code/release" \
    -H "Content-Type: application/json" -d '{}' | head -c 800
  echo ""
fi
