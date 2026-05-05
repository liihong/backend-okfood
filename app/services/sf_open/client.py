"""HTTP 调用顺丰同城开放平台接口：POST JSON 与 URL 中 sign 参数（createorder / cancelorder 等）。"""

from __future__ import annotations

import json
import logging
from typing import Any
from urllib.parse import quote

import httpx

from app.core.config import get_settings
from app.services.sf_open.sign import generate_open_sign

logger = logging.getLogger(__name__)


class SfOpenApiError(Exception):
    """顺丰返回 `error_code != 0` 或 HTTP 非 2xx。"""

    def __init__(self, message: str, *, error_code: int | None = None, error_data: Any = None):
        super().__init__(message)
        self.error_code = error_code
        self.error_data = error_data


class SfOpenClient:
    """
    顺丰同城开放平台客户端。

    配置来自 ``Settings``：``SF_API_BASE``、``SF_OPEN_DEV_ID``、``SF_OPEN_SECRET``。
    """

    CREATE_ORDER_PATH = "/open/api/external/createorder"
    CANCEL_ORDER_PATH = "/open/api/external/cancelorder"

    def __init__(self, base_url: str | None = None, timeout_sec: float = 45.0) -> None:
        s = get_settings()
        self._base = (base_url or s.SF_API_BASE).rstrip("/")
        self._timeout = timeout_sec

    def create_order(
        self,
        post_body: dict[str, Any],
        *,
        dev_id: int,
        app_key: str,
    ) -> dict[str, Any]:
        """
        发送 createorder 请求。``post_body`` 须为最终 JSON 对象（**须含 dev_id 且与入参 dev_id 一致**）。

        与签名使用完全相同的 json 串：使用 ``app.services.sf_open.sign`` 的规范序列化。
        """
        from app.services.sf_open import sign as sign_mod

        json_str = sign_mod._canonical_json(post_body)
        sig = generate_open_sign(json_str, int(dev_id), app_key)
        soid = post_body.get("shop_order_id")
        logger.info(
            "SF createorder POST body (canonical JSON, equals sign source): shop_order_id=%s %s",
            soid,
            json_str,
        )
        url = f"{self._base}{self.CREATE_ORDER_PATH}?sign={quote(sig, safe='')}"
        headers = {"Content-Type": "application/json; charset=utf-8"}
        with httpx.Client(timeout=self._timeout) as client:
            resp = client.post(url, content=json_str.encode("utf-8"), headers=headers)
        text = resp.text
        if resp.status_code != 200:
            raise SfOpenApiError(f"顺丰 HTTP {resp.status_code}", error_code=resp.status_code)
        try:
            data: dict[str, Any] = json.loads(text)
        except json.JSONDecodeError as e:
            raise SfOpenApiError(f"顺丰响应非 JSON: {e}") from e
        err = data.get("error_code")
        try:
            ec = int(err) if err is not None and err != "" else 0
        except (TypeError, ValueError):
            ec = -1
        if ec != 0:
            msg = str(data.get("error_msg") or "未知错误")
            ed = data.get("error_data")
            raise SfOpenApiError(msg, error_code=ec, error_data=ed)
        return data

    def cancel_order(
        self,
        post_body: dict[str, Any],
        *,
        dev_id: int,
        app_key: str,
    ) -> dict[str, Any]:
        """
        商家取消配送订单 ``cancelorder``。

        ``post_body`` 须含 ``dev_id``（与入参一致）、``push_time``，以及
        ``order_id`` + ``order_type``（1=顺丰单号，2=商家订单号）等字段；签名同源 canonical JSON。
        """
        from app.services.sf_open import sign as sign_mod

        json_str = sign_mod._canonical_json(post_body)
        sig = generate_open_sign(json_str, int(dev_id), app_key)
        oid = post_body.get("order_id")
        logger.info(
            "SF cancelorder POST body (canonical JSON): order_id=%s order_type=%s %s",
            oid,
            post_body.get("order_type"),
            json_str,
        )
        url = f"{self._base}{self.CANCEL_ORDER_PATH}?sign={quote(sig, safe='')}"
        headers = {"Content-Type": "application/json; charset=utf-8"}
        with httpx.Client(timeout=self._timeout) as client:
            resp = client.post(url, content=json_str.encode("utf-8"), headers=headers)
        text = resp.text
        if resp.status_code != 200:
            raise SfOpenApiError(f"顺丰 HTTP {resp.status_code}", error_code=resp.status_code)
        try:
            data: dict[str, Any] = json.loads(text)
        except json.JSONDecodeError as e:
            raise SfOpenApiError(f"顺丰响应非 JSON: {e}") from e
        err = data.get("error_code")
        try:
            ec = int(err) if err is not None and err != "" else 0
        except (TypeError, ValueError):
            ec = -1
        if ec != 0:
            msg = str(data.get("error_msg") or "未知错误")
            ed = data.get("error_data")
            raise SfOpenApiError(msg, error_code=ec, error_data=ed)
        return data
