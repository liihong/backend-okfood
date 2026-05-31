#!/usr/bin/env bash
# 恢复 2026-06-01 供餐日「已支付但履约 cancelled」的单次零售订单
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PYTHON="${PYTHON:-python3}"
[[ -d .venv/bin ]] && PYTHON=".venv/bin/python"
exec "$PYTHON" scripts/restore_paid_single_meal_fulfillment.py \
  --delivery-date "${DELIVERY_DATE:-2026-06-01}" \
  --store-id "${STORE_ID:-1}" \
  "$@"
