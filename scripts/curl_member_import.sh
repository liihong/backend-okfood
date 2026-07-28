#!/usr/bin/env bash
# 会员批量导入接口联调（需先登录获取 ADMIN_TOKEN，并指定 store_id）
# 用法：
#   export ADMIN_TOKEN="your_jwt"
#   export STORE_ID=1
#   bash scripts/curl_member_import.sh

set -euo pipefail
BASE="${API_BASE:-http://127.0.0.1:8000}"
TOKEN="${ADMIN_TOKEN:?请设置 ADMIN_TOKEN}"
STORE_ID="${STORE_ID:-1}"

echo "== 1. 下载导入模板 =="
curl -sS -o /tmp/member_import_template.xlsx \
  -H "Authorization: Bearer ${TOKEN}" \
  "${BASE}/api/admin/members/import/template.xlsx?store_id=${STORE_ID}"
echo "已保存 /tmp/member_import_template.xlsx"

echo "== 2. 预览上传（请先将模板填好并替换 FILE 路径） =="
FILE="${IMPORT_FILE:-/tmp/member_import_template.xlsx}"
curl -sS -X POST \
  -H "Authorization: Bearer ${TOKEN}" \
  -F "file=@${FILE}" \
  "${BASE}/api/admin/members/import/preview?store_id=${STORE_ID}" | python -m json.tool

echo "== 3. 确认入库（将 preview 中 ready 行的 data 填入 rows 后执行） =="
curl -sS -X POST \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"rows":[{"phone":"13800138000","name":"测试","plan_type":"周卡","address":"测试地址","balance":4,"meal_quota_total":6,"daily_meal_units":1,"delivery_start_date":null,"store_pickup":false,"delivery_deferred":false,"remarks":null}]}' \
  "${BASE}/api/admin/members/import/confirm?store_id=${STORE_ID}" | python -m json.tool
