"""芯烨云标签打印客户端。"""

from __future__ import annotations

import hashlib
import logging
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)

XPRINTER_API_BASE = "https://open.xpyun.net/api/openapi/xprinter"


class XprinterPrintError(Exception):
    def __init__(self, message: str, *, code: int | None = None, data: Any = None):
        super().__init__(message)
        self.code = code
        self.data = data


def _sign(user: str, user_key: str, timestamp: str) -> str:
    raw = f"{user}{user_key}{timestamp}"
    return hashlib.sha1(raw.encode()).hexdigest().upper()


def _post(path: str, user: str, user_key: str, body: dict[str, Any]) -> dict[str, Any]:
    ts = str(int(time.time()))
    payload = {
        "user": user,
        "timestamp": ts,
        "sign": _sign(user, user_key, ts),
        **body,
    }
    url = f"{XPRINTER_API_BASE}/{path}"
    with httpx.Client(timeout=30.0) as client:
        r = client.post(url, json=payload, headers={"Content-Type": "application/json;charset=UTF-8"})
        r.raise_for_status()
        data = r.json()
    code = int(data.get("code", -1))
    if code != 0:
        msg = str(data.get("msg") or "芯烨云打印失败")
        raise XprinterPrintError(msg, code=code, data=data)
    return data


def add_printer(user: str, user_key: str, sn: str, name: str) -> None:
    _post(
        "addPrinters",
        user,
        user_key,
        {"items": [{"sn": sn.strip(), "name": name.strip() or "OK饭"}]},
    )


def print_label(user: str, user_key: str, sn: str, content: str, *, copies: int = 1) -> str:
    data = _post(
        "printLabel",
        user,
        user_key,
        {
            "sn": sn.strip(),
            "content": content,
            "copies": max(1, copies),
            "voice": 2,
            "mode": 0,
        },
    )
    inner = data.get("data")
    if isinstance(inner, dict):
        return str(inner.get("orderId") or inner.get("id") or "")
    return str(inner or "")


def query_printer_status(user: str, user_key: str, sn: str) -> str:
    data = _post("queryPrinterStatus", user, user_key, {"sn": sn.strip()})
    return str(data.get("data") or "")
