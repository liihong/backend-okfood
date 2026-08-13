#!/usr/bin/env bash
# 管理端：为会员新增配送地址（无地址时首条自动设为默认）
# 用法：
#   ADMIN_TOKEN=xxx MEMBER_ID=1 \
#   MAP_TEXT='河南省新乡市红旗区 新乡市人民政府' \
#   LNG=113.92682648 LAT=35.30371475 \
#   ./scripts/curl_admin_create_member_address.sh

set -euo pipefail
BASE="${API_BASE:-http://127.0.0.1:8000}"
TOKEN="${ADMIN_TOKEN:?请设置 ADMIN_TOKEN（管理端登录后的 Bearer）}"
MEMBER_ID="${MEMBER_ID:?请设置 MEMBER_ID}"
STORE_ID="${STORE_ID:-1}"
NAME="${NAME:-测试收件人}"
PHONE="${PHONE:-13800138000}"
MAP_TEXT="${MAP_TEXT:?请设置 MAP_TEXT（地图主文案）}"
DOOR="${DOOR:-}"
LNG="${LNG:?请设置 LNG}"
LAT="${LAT:?请设置 LAT}"
DOOR_JSON="null"
if [ -n "${DOOR}" ]; then
  DOOR_JSON=$(printf '"%s"' "${DOOR}")
fi

curl -sS -X POST \
  "${BASE}/api/admin/users/${MEMBER_ID}/addresses?store_id=${STORE_ID}" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -d "{
    \"contact_name\": \"${NAME}\",
    \"contact_phone\": \"${PHONE}\",
    \"map_location_text\": \"${MAP_TEXT}\",
    \"door_detail\": ${DOOR_JSON},
    \"is_default\": false,
    \"location\": { \"lng\": ${LNG}, \"lat\": ${LAT} }
  }" | python -m json.tool
