"""易联云 K4 打印客户端。"""

from __future__ import annotations

import hashlib
import logging
import time
from typing import Any
from urllib.parse import quote

import httpx

logger = logging.getLogger(__name__)

YILIAN_API_BASE = "http://open.10ss.net:8888"


class YilianPrintError(Exception):
    def __init__(self, message: str, *, data: Any = None):
        super().__init__(message)
        self.data = data


def _sign(apikey: str, machine_code: str, partner: str, msign: str, t: str) -> str:
    raw = f"{apikey}{machine_code}{partner}{t}{msign}"
    return hashlib.md5(raw.encode()).hexdigest().upper()


def print_content(partner: str, apikey: str, machine_code: str, msign: str, content: str) -> str:
    t = str(int(time.time()))
    sign = _sign(apikey, machine_code, partner, msign, t)
    payload = {
        "partner": partner,
        "machine_code": machine_code.strip(),
        "time": t,
        "sign": sign,
        "content": quote(content, safe=""),
        "msign": msign.strip(),
    }
    with httpx.Client(timeout=30.0) as client:
        r = client.post(f"{YILIAN_API_BASE}/", data=payload)
        r.raise_for_status()
        text = r.text.strip()
        try:
            data = r.json()
        except Exception:
            if "ok" in text.lower() or text.isdigit():
                return text
            raise YilianPrintError(text or "易联云打印失败")
    state = str(data.get("state", data.get("error", "")))
    if state not in ("1", "ok", "OK"):
        msg = str(data.get("error_msg") or data.get("error") or "易联云打印失败")
        raise YilianPrintError(msg, data=data)
    return str(data.get("id") or data.get("data") or "")


def add_terminal(partner: str, apikey: str, machine_code: str, msign: str, phone: str = "") -> None:
    t = str(int(time.time()))
    sign = hashlib.md5(f"{apikey}{machine_code}{partner}{t}{msign}".encode()).hexdigest().upper()
    payload = {
        "partner": partner,
        "machine_code": machine_code.strip(),
        "mobilephone": phone or "13800000000",
        "printname": "OK饭",
        "msign": msign.strip(),
        "time": t,
        "sign": sign,
    }
    with httpx.Client(timeout=30.0) as client:
        r = client.post(f"{YILIAN_API_BASE}/api/open/addprinter", data=payload)
        r.raise_for_status()
        text = r.text.strip()
        if "ok" not in text.lower() and text not in ("1",):
            try:
                data = r.json()
                if str(data.get("state", "")) not in ("1",):
                    raise YilianPrintError(str(data.get("error") or text))
            except YilianPrintError:
                raise
            except Exception:
                if text and "exist" not in text.lower():
                    logger.warning("易联云 addprinter 响应: %s", text)
