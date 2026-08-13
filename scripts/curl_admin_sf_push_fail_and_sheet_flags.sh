#!/usr/bin/env bash
# 联调：顺丰创单失败列表 + 配送大表缺坐标/推单失败标记
# Usage:
#   export ADMIN_TOKEN='...'
#   ./scripts/curl_admin_sf_push_fail_and_sheet_flags.sh

set -euo pipefail
BASE="${API_BASE:-http://127.0.0.1:8000}"
TOKEN="${ADMIN_TOKEN:?请设置 ADMIN_TOKEN（管理端登录后的 Bearer）}"
STORE_ID="${STORE_ID:-1}"
DAY="${DELIVERY_DATE:-$(date +%Y-%m-%d)}"

echo "=== GET /api/admin/delivery-sf/pushes 创单失败 ==="
curl -sS \
  "${BASE}/api/admin/delivery-sf/pushes?store_id=${STORE_ID}&delivery_date=${DAY}&sf_create_status=fail&page=1&page_size=50" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Accept: application/json" | python -m json.tool
echo ""

echo "=== GET /api/admin/delivery-sheet 缺坐标或顺丰失败停靠点 ==="
curl -sS \
  "${BASE}/api/admin/delivery-sheet?store_id=${STORE_ID}&delivery_date=${DAY}" \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Accept: application/json" | python -c "
import json, sys
raw = json.load(sys.stdin)
data = raw.get('data') or raw
groups = data.get('groups') or []
hits = []
for g in groups:
    for st in g.get('stops') or []:
        members = st.get('members') or []
        if st.get('sf_push_failed') or any(m.get('missing_coords') for m in members):
            hits.append({
                'area': g.get('area'),
                'address': st.get('address_line'),
                'sf_push_failed': st.get('sf_push_failed'),
                'sf_push_error_msg': st.get('sf_push_error_msg'),
                'members': [
                    {'name': m.get('name'), 'phone': m.get('phone'), 'missing_coords': m.get('missing_coords')}
                    for m in members
                ],
            })
print(json.dumps({'code': raw.get('code'), 'hits': hits, 'hit_count': len(hits)}, ensure_ascii=False, indent=2))
"
echo ""
