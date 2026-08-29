#!/usr/bin/env bash
# 会员档案库搜索：完整手机号 / 后四位模糊（需管理员 Token）
# 用法: TOKEN=... STORE_ID=1 Q=8000 bash scripts/curl_admin_member_archive_search.sh

set -euo pipefail
BASE="${BASE:-http://127.0.0.1:8000}"
TOKEN="${TOKEN:?请设置 TOKEN}"
STORE_ID="${STORE_ID:-1}"
Q="${Q:-}"
AUTH=(-H "Authorization: Bearer ${TOKEN}" -H "Content-Type: application/json")

echo "== GET /api/admin/users q=${Q:-<(空)}（手机后四位或完整号码）=="
curl -sS -G "${BASE}/api/admin/users" \
  "${AUTH[@]}" \
  --data-urlencode "store_id=${STORE_ID}" \
  --data-urlencode "page=1" \
  --data-urlencode "page_size=20" \
  ${Q:+--data-urlencode "q=${Q}"} | head -c 1200
echo
