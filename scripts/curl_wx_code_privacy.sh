#!/usr/bin/env bash
# 租户小程序 · 查询 / 同步用户隐私保护指引
set -euo pipefail

BASE_URL="${BASE_URL:-https://ok.sourcefire.cn}"
TENANT_ID="${TENANT_ID:-3}"
ADMIN_TOKEN="${ADMIN_TOKEN:?请 export ADMIN_TOKEN=平台管理员JWT}"

auth=(-H "Authorization: Bearer ${ADMIN_TOKEN}")

echo "== get privacy-setting (开发版 privacy_ver=2) =="
curl -sS "${auth[@]}" \
  "${BASE_URL}/api/admin/system/tenants/${TENANT_ID}/wx-code/privacy-setting?privacy_ver=2" \
  | head -c 1200
echo ""

echo "== sync-privacy-setting (示例，默认不执行；设 RUN_SYNC=1 启用) =="
if [[ "${RUN_SYNC:-0}" == "1" ]]; then
  curl -sS "${auth[@]}" -X POST \
    "${BASE_URL}/api/admin/system/tenants/${TENANT_ID}/wx-code/sync-privacy-setting" \
    -H "Content-Type: application/json" \
    -d '{"privacy_ver":2,"contact_phone":"13800138000","notice_method":"弹窗提示"}' \
    | head -c 1200
  echo ""
fi

echo "提示：提审接口 submit-audit 会在提审前自动调用 sync-privacy-setting（privacy_ver=2）"
