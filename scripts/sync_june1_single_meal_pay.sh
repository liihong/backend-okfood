#!/usr/bin/env bash
# 快捷入口：同步 2026-06-01 供餐日单次零售微信支付状态
# 在项目根目录执行（需已配置 .env 与 Python 虚拟环境）
#
#   ./scripts/sync_june1_single_meal_pay.sh              # 正式同步
#   ./scripts/sync_june1_single_meal_pay.sh --dry-run    # 仅预览
#   STORE_ID=1 ./scripts/sync_june1_single_meal_pay.sh --include-cancelled

set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

DELIVERY_DATE="${DELIVERY_DATE:-2026-06-01}"
STORE_ID="${STORE_ID:-1}"
PYTHON="${PYTHON:-python3}"

if [[ -d .venv/bin ]]; then
  PYTHON=".venv/bin/python"
fi

exec "$PYTHON" scripts/sync_single_meal_wechat_pay_by_delivery_date.py \
  --delivery-date "$DELIVERY_DATE" \
  --store-id "$STORE_ID" \
  "$@"
