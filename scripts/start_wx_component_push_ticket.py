#!/usr/bin/env python3
"""启动微信第三方平台 component_verify_ticket 推送（控制台显示「关闭推送Ticket」时执行）。

生产环境请用项目虚拟环境执行，勿直接用系统 python3：

  bash scripts/start_wx_component_push_ticket.sh

或：

  /var/www/okfood/backend/.venv/bin/python scripts/start_wx_component_push_ticket.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# 允许 ``python scripts/xxx.py`` 直接运行（自动把项目根目录加入 sys.path）
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

try:
    import httpx
except ModuleNotFoundError:
    print(
        "缺少依赖 httpx：请使用项目虚拟环境运行，例如：\n"
        "  bash scripts/start_wx_component_push_ticket.sh\n"
        "或：.venv/bin/pip install -r requirements.txt",
        file=sys.stderr,
    )
    raise SystemExit(1) from None

from app.core.config import get_settings

START_PUSH_URL = "https://api.weixin.qq.com/cgi-bin/component/api_start_push_ticket"


def main() -> int:
    s = get_settings()
    appid = (s.WX_OPEN_COMPONENT_APPID or "").strip()
    secret = (s.WX_OPEN_COMPONENT_SECRET or "").strip()
    if not appid or not secret:
        print("请在 .env 配置 WX_OPEN_COMPONENT_APPID / WX_OPEN_COMPONENT_SECRET", file=sys.stderr)
        return 1

    payload = {"component_appid": appid, "component_secret": secret}
    print(f"POST {START_PUSH_URL}")
    print(json.dumps(payload, ensure_ascii=False))

    with httpx.Client(timeout=20.0) as client:
        r = client.post(START_PUSH_URL, json=payload)
        r.raise_for_status()
        data = r.json()

    print(json.dumps(data, ensure_ascii=False, indent=2))
    errcode = data.get("errcode")
    if errcode not in (0, None):
        print(f"启动失败: {data.get('errmsg')}", file=sys.stderr)
        return 2
    print("已请求启动 ticket 推送；约 10 分钟内 POST 到授权事件接收 URL。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
