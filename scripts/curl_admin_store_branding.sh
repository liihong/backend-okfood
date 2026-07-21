#!/usr/bin/env bash
# 管理端侧栏门店品牌：登录后 GET /api/admin/store-branding
set -euo pipefail
BASE="${BASE:-http://127.0.0.1:8001}"
USERNAME="${ADMIN_USERNAME:-admin}"
PASSWORD="${ADMIN_PASSWORD:-changeme}"
STORE_ID="${STORE_ID:-1}"

echo "== 登录 =="
LOGIN=$(curl -sS -X POST "${BASE}/api/admin/login" \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"${USERNAME}\",\"password\":\"${PASSWORD}\"}")
echo "$LOGIN" | python3 -m json.tool
TOKEN=$(echo "$LOGIN" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('data',{}).get('access_token',''))")
if [[ -z "$TOKEN" ]]; then
  echo "登录失败：未拿到 access_token" >&2
  exit 1
fi

echo "== 门店侧栏品牌 store_id=${STORE_ID} =="
curl -sS "${BASE}/api/admin/store-branding?store_id=${STORE_ID}" \
  -H "Authorization: Bearer ${TOKEN}" | python3 -m json.tool
