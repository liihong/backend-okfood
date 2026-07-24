#!/usr/bin/env bash
# 启动微信第三方平台 component_verify_ticket 推送（须在服务器白名单 IP 上执行）
# 用法：bash scripts/start_wx_component_push_ticket.sh

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PY="$ROOT/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PY="python3"
else
  echo "未找到 Python：请先创建虚拟环境 python3 -m venv .venv && .venv/bin/pip install -r requirements.txt" >&2
  exit 1
fi

export PYTHONPATH="$ROOT"
exec "$PY" "$ROOT/scripts/start_wx_component_push_ticket.py"
