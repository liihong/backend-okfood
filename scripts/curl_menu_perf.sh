#!/usr/bin/env bash
# 联调：优化后的菜单读接口 + 图片变体说明
# 新上传图片会生成 {uuid}.jpg + {uuid}_w480.webp + {uuid}_w1080.webp（OSS 带 Cache-Control: immutable）
# 旧 OSS 图可通过 x-oss-process 动态缩略；本地旧图仍用原 URL（小程序 @error 回退）
# Usage:
#   export API_BASE_URL='http://127.0.0.1:8000/api'
#   export STORE_ID='1'
#   ./scripts/curl_menu_perf.sh

set -euo pipefail
API_BASE="${API_BASE_URL:-http://127.0.0.1:8000/api}"
STORE_ID="${STORE_ID:-1}"
TODAY="${TODAY:-$(TZ=Asia/Shanghai date +%F)}"
TOMORROW="${TOMORROW:-$(TZ=Asia/Shanghai date -d '+1 day' +%F 2>/dev/null || date -v+1d +%F)}"

HDR=(-H "X-Store-Id: ${STORE_ID}")

echo "=== GET /menu/today (无库存，应无 single_stock_* 字段) ==="
curl -sS -w "\nHTTP %{http_code} time_total=%{time_total}s\n" \
  "${API_BASE}/menu/today?meal_period=lunch" "${HDR[@]}"
echo ""

echo "=== GET /menu/weekly include_stock=false (结构 only) ==="
curl -sS -w "\nHTTP %{http_code} time_total=%{time_total}s\n" \
  "${API_BASE}/menu/weekly?meal_period=lunch&include_stock=false" "${HDR[@]}"
echo ""

echo "=== GET /menu/weekly include_stock=true stock_dates=${TODAY},${TOMORROW} ==="
curl -sS -w "\nHTTP %{http_code} time_total=%{time_total}s\n" \
  "${API_BASE}/menu/weekly?meal_period=lunch&include_stock=true&as_of_date=${TODAY}&stock_dates=${TODAY},${TOMORROW}" "${HDR[@]}"
echo ""
