"""抖音生活服务 OpenAPI：client_token、验券准备、验券核销。"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass
from typing import Any
import httpx

logger = logging.getLogger(__name__)

CLIENT_TOKEN_URL = "https://open.douyin.com/oauth/client_token/"
PREPARE_URL = "https://open.douyin.com/goodlife/v1/fulfilment/certificate/prepare/"
VERIFY_URL = "https://open.douyin.com/goodlife/v1/fulfilment/certificate/verify/"

# client_key -> (token, expires_at_unix)
_token_cache: dict[str, tuple[str, float]] = {}


class DouyinLifeError(Exception):
    """抖音 OpenAPI 调用失败。"""

    def __init__(self, message: str, *, status_code: int = 400, error_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code


@dataclass(frozen=True)
class DouyinPrepareCertificate:
    """验券准备返回的单张可用券。"""

    certificate_id: str
    encrypted_code: str
    code: str | None
    product_id: str | None
    sku_id: str | None
    product_out_id: str | None
    sku_out_id: str | None
    third_sku_id: str | None
    title: str | None
    pay_amount_fen: int | None


@dataclass(frozen=True)
class DouyinPrepareResult:
    verify_token: str
    order_id: str | None
    certificates: list[DouyinPrepareCertificate]


def new_verify_token() -> str:
    """生成一次验券幂等标识。"""
    return uuid.uuid4().hex


def _humanize_douyin_description(desc: str) -> str:
    """将开放平台原始文案转为用户/运营可理解的提示。"""
    d = (desc or "").strip()
    if not d:
        return d
    if "应用未获得该能力" in d or "未获得该能力" in d:
        return (
            "抖音应用未开通「团购验券核销」能力。"
            "请登录抖音开放平台，为当前应用申请生活服务团购核销（验券准备/核销）权限，"
            "审核通过后再试；详情见 open.douyin.com 能力中心。"
        )
    # 避免 Toast 被长链接撑满
    if "open.douyin.com" in d and len(d) > 80:
        head = d.split("https://", 1)[0].strip().rstrip("，,;；请去")
        if head:
            return f"{head}。请登录抖音开放平台能力中心申请对应权限。"
    return d


def _api_error_message(payload: dict[str, Any]) -> str:
    extra = payload.get("extra") if isinstance(payload.get("extra"), dict) else {}
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    for block in (extra, data, payload):
        desc = str(block.get("description") or block.get("sub_description") or "").strip()
        if desc:
            return _humanize_douyin_description(desc)
    code = extra.get("error_code", data.get("error_code"))
    if code not in (None, 0):
        return f"抖音接口错误(error_code={code})"
    return "抖音接口返回异常"


def _ensure_ok(payload: dict[str, Any]) -> dict[str, Any]:
    extra = payload.get("extra") if isinstance(payload.get("extra"), dict) else {}
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    err = extra.get("error_code", data.get("error_code", 0))
    try:
        err_i = int(err)
    except (TypeError, ValueError):
        err_i = -1
    if err_i != 0:
        raise DouyinLifeError(_api_error_message(payload), error_code=err_i)
    return data


def _parse_sku(sku: dict[str, Any] | None) -> tuple[str | None, str | None, str | None, str | None, str | None, str | None]:
    if not isinstance(sku, dict):
        return None, None, None, None, None, None
    return (
        _s(sku.get("product_id")),
        _s(sku.get("sku_id")),
        _s(sku.get("product_out_id")),
        _s(sku.get("sku_out_id")),
        _s(sku.get("third_sku_id")),
        _s(sku.get("title")),
    )


def _s(v: Any) -> str | None:
    if v is None:
        return None
    t = str(v).strip()
    return t or None


def _parse_prepare_certificates(data: dict[str, Any]) -> list[DouyinPrepareCertificate]:
    raw_list = data.get("certificates_v2") or data.get("certificates") or []
    if not isinstance(raw_list, list):
        return []
    out: list[DouyinPrepareCertificate] = []
    for item in raw_list:
        if not isinstance(item, dict):
            continue
        enc = _s(item.get("encrypted_code"))
        if not enc:
            continue
        cid = _s(item.get("certificate_id"))
        if not cid:
            continue
        pid, sid, pout, sout, third, title = _parse_sku(item.get("sku") if isinstance(item.get("sku"), dict) else None)
        pay_fen: int | None = None
        amount = item.get("amount")
        if isinstance(amount, dict) and amount.get("pay_amount") is not None:
            try:
                pay_fen = int(int(amount["pay_amount"]) / 100)
            except (TypeError, ValueError):
                pay_fen = None
        out.append(
            DouyinPrepareCertificate(
                certificate_id=cid,
                encrypted_code=enc,
                code=_s(item.get("code")),
                product_id=pid,
                sku_id=sid,
                product_out_id=pout,
                sku_out_id=sout,
                third_sku_id=third,
                title=title,
                pay_amount_fen=pay_fen,
            )
        )
    return out


def fetch_client_token(*, client_key: str, client_secret: str) -> str:
    """获取 client_token，带进程内缓存。"""
    key = client_key.strip()
    secret = client_secret.strip()
    if not key or not secret:
        raise DouyinLifeError("抖音开放平台凭证未配置", status_code=503)

    cached = _token_cache.get(key)
    now = time.time()
    if cached and cached[1] > now + 60:
        return cached[0]

    resp = httpx.post(
        CLIENT_TOKEN_URL,
        json={
            "client_key": key,
            "client_secret": secret,
            "grant_type": "client_credential",
        },
        headers={"Content-Type": "application/json"},
        timeout=20.0,
    )
    try:
        payload = resp.json()
    except Exception as exc:
        raise DouyinLifeError(f"抖音 token 响应解析失败: {resp.text[:200]}", status_code=502) from exc

    if resp.status_code >= 400:
        raise DouyinLifeError(_api_error_message(payload) if isinstance(payload, dict) else resp.text[:200], status_code=502)

    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, dict):
        raise DouyinLifeError("抖音 token 响应缺少 data", status_code=502)
    token = _s(data.get("access_token"))
    if not token:
        raise DouyinLifeError("抖音 token 响应缺少 access_token", status_code=502)
    expires_in = int(data.get("expires_in") or 7200)
    _token_cache[key] = (token, now + max(300, expires_in - 120))
    return token


def certificate_prepare(
    *,
    access_token: str,
    code: str,
    poi_id: str,
    account_id: str | None = None,
) -> DouyinPrepareResult:
    """验券准备：根据券码明文查询可用券列表。"""
    params: dict[str, str] = {
        "code": code.strip(),
        "poi_id": poi_id.strip(),
    }
    if account_id and account_id.strip():
        params["account_id"] = account_id.strip()

    resp = httpx.get(
        PREPARE_URL,
        params=params,
        headers={
            "access-token": access_token,
            "content-type": "application/json",
        },
        timeout=25.0,
    )
    try:
        payload = resp.json()
    except Exception as exc:
        raise DouyinLifeError(f"验券准备响应解析失败: {resp.text[:200]}", status_code=502) from exc

    data = _ensure_ok(payload if isinstance(payload, dict) else {})
    verify_token = _s(data.get("verify_token"))
    if not verify_token:
        raise DouyinLifeError("验券准备未返回 verify_token")
    certs = _parse_prepare_certificates(data)
    if not certs:
        raise DouyinLifeError("该券码当前无可用券，可能已使用或已过期")
    return DouyinPrepareResult(
        verify_token=verify_token,
        order_id=_s(data.get("order_id")),
        certificates=certs,
    )


def certificate_verify(
    *,
    access_token: str,
    verify_token: str,
    poi_id: str,
    encrypted_codes: list[str],
    order_id: str | None = None,
) -> dict[str, Any]:
    """验券核销。"""
    body: dict[str, Any] = {
        "verify_token": verify_token,
        "poi_id": poi_id.strip(),
        "encrypted_codes": encrypted_codes,
    }
    if order_id and order_id.strip():
        body["order_id"] = order_id.strip()

    resp = httpx.post(
        VERIFY_URL,
        json=body,
        headers={
            "access-token": access_token,
            "content-type": "application/json",
        },
        timeout=25.0,
    )
    try:
        payload = resp.json()
    except Exception as exc:
        raise DouyinLifeError(f"验券核销响应解析失败: {resp.text[:200]}", status_code=502) from exc

    data = _ensure_ok(payload if isinstance(payload, dict) else {})
    results = data.get("verify_results")
    if isinstance(results, list):
        for row in results:
            if not isinstance(row, dict):
                continue
            try:
                result_code = int(row.get("result", 0))
            except (TypeError, ValueError):
                result_code = -1
            if result_code != 0:
                msg = _s(row.get("msg")) or "验券失败"
                raise DouyinLifeError(msg)
    return data
