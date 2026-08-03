"""飞鹅云标签打印客户端。"""

from __future__ import annotations

import hashlib
import logging
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)

FEIE_API_BASE = "https://api.feieyun.cn/Api/Open/"


class FeiePrintError(Exception):
    def __init__(self, message: str, *, ret: int | None = None, data: Any = None):
        super().__init__(message)
        self.ret = ret
        self.data = data


def _sign(user: str, ukey: str, stime: str) -> str:
    return hashlib.sha1(f"{user}{ukey}{stime}".encode()).hexdigest()


def _post(apiname: str, user: str, ukey: str, extra: dict[str, str]) -> dict[str, Any]:
    stime = str(int(time.time()))
    payload = {
        "user": user,
        "stime": stime,
        "sig": _sign(user, ukey, stime),
        "apiname": apiname,
        **extra,
    }
    with httpx.Client(timeout=30.0) as client:
        r = client.post(FEIE_API_BASE, data=payload)
        r.raise_for_status()
        data = r.json()
    if int(data.get("ret", -1)) != 0:
        msg = str(data.get("msg") or "飞鹅云打印失败")
        raise FeiePrintError(msg, ret=int(data.get("ret", -1)), data=data)
    return data


def add_printer(user: str, ukey: str, sn: str, key: str, name: str) -> None:
    content = f"{sn.strip()}#{key.strip()}#{name.strip() or 'OK饭'}"
    _post("Open_printerAddlist", user, ukey, {"printerContent": content})


def print_label(user: str, ukey: str, sn: str, content: str, *, copies: int = 1) -> str:
    data = _post(
        "Open_printLabelMsg",
        user,
        ukey,
        {
            "sn": sn.strip(),
            "content": content,
            "times": str(max(1, copies)),
        },
    )
    return str(data.get("data") or "")


def query_printer_status(user: str, ukey: str, sn: str) -> str:
    data = _post("Open_queryPrinterStatus", user, ukey, {"sn": sn.strip()})
    return str(data.get("data") or "")
