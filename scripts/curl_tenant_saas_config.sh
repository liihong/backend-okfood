#!/usr/bin/env bash
# SaaS 租户公开配置联调（OK饭 兼容：仅 X-Store-Id 亦可）
# 用法：BASE=http://127.0.0.1:8001 ./scripts/curl_tenant_saas_config.sh

set -euo pipefail
BASE="${BASE:-http://127.0.0.1:8001}"

echo "== GET /api/tenant/config (OK饭路径：仅 X-Store-Id) =="
curl -sS "${BASE}/api/tenant/config" -H "X-Store-Id: 1" | head -c 800
echo ""

echo "== GET /api/home/layout =="
curl -sS "${BASE}/api/home/layout" -H "X-Store-Id: 1" | head -c 800
echo ""

echo "== GET /api/tenant/config (SaaS：X-Tenant-Id + X-Store-Id) =="
curl -sS "${BASE}/api/tenant/config" \
  -H "X-Tenant-Id: 1" \
  -H "X-Store-Id: 1" | head -c 800
echo ""
