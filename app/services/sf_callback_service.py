"""
顺丰同城开放平台：各类 HTTP 推送回调。

验签与开放接口下单一致：对请求体 JSON 字符串使用 ``generate_open_sign``；
``sign`` 在 URL query 中。
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any
from urllib.parse import unquote

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.sf_same_city_callback import SfSameCityCallback
from app.models.sf_same_city_push import SfSameCityPush
from app.services.sf_open.sign import _canonical_json, generate_open_sign

logger = logging.getLogger(__name__)


def _sign_match(raw_for_sign: str, sign_query: str, dev_id: int, app_key: str) -> bool:
    sig = generate_open_sign(raw_for_sign, dev_id, app_key)
    wanted = unquote(sign_query.strip())
    return sig == wanted


def verify_sf_callback_signature(raw_body: str, sign_query: str | None, dev_id: int, app_key: str) -> bool:
    """用原始正文与 canonical JSON 两种串尝试验签。"""
    if not sign_query or not raw_body.strip():
        return False
    candidates = [raw_body.strip()]
    try:
        obj = json.loads(raw_body)
        if isinstance(obj, dict):
            candidates.append(_canonical_json(obj))
    except json.JSONDecodeError:
        pass
    for cand in candidates:
        if _sign_match(cand, sign_query, dev_id, app_key):
            return True
    return False


def _extract_ids(payload: dict[str, Any]) -> tuple[str | None, str | None]:
    shop_order_id = (
        payload.get("shop_order_id")
        or payload.get("shopOrderId")
        or payload.get("merchant_order_id")
    )
    shop_s = None
    if shop_order_id is not None:
        shop_s = str(shop_order_id)[:128]
    sf_order_id = (
        payload.get("sf_order_id")
        or payload.get("sfOrderId")
        or payload.get("order_id")
        or payload.get("sfBillId")
    )
    sf_s = None
    if sf_order_id is not None:
        sf_s = str(sf_order_id)[:64]
    return shop_s, sf_s


def persist_sf_callback_and_sync_push(
    db: Session,
    *,
    route_kind: str,
    raw_body: str,
    sign_ok: bool,
    payload: dict[str, Any] | None,
    verify_error: str | None,
) -> SfSameCityCallback:
    """写入回调日志；验签通过且命中推单记录时刷新最近顺丰字段。"""
    shop_order_id = None
    sf_order_id = None
    if payload:
        shop_order_id, sf_order_id = _extract_ids(payload)

    truncated = raw_body[:65000] if len(raw_body) > 65000 else raw_body
    row = SfSameCityCallback(
        route_kind=route_kind,
        sign_ok=sign_ok,
        error_message=(verify_error[:512] if verify_error else None),
        shop_order_id=shop_order_id,
        sf_order_id=sf_order_id,
        payload_json=payload,
        raw_body=truncated,
    )
    db.add(row)

    if sign_ok and payload:
        pus = None
        if shop_order_id:
            pus = db.scalar(select(SfSameCityPush).where(SfSameCityPush.shop_order_id == shop_order_id))
        if pus is None and sf_order_id:
            pus = db.scalar(select(SfSameCityPush).where(SfSameCityPush.sf_order_id == sf_order_id))
        if pus is not None:
            pus.last_callback_at = datetime.utcnow()
            pus.last_callback_kind = route_kind[:64]
            ost = payload.get("order_status")
            if ost is not None:
                try:
                    pus.sf_callback_order_status = int(ost)
                except (TypeError, ValueError):
                    pass

    db.commit()
    db.refresh(row)
    return row


def process_sf_notify(
    *,
    db: Session,
    route_kind: str,
    raw_body: str,
    sign_query: str | None,
) -> tuple[bool, str | None]:
    """配送类订单回调：验签、落库。"""
    settings = get_settings()
    skip = bool(settings.SF_CALLBACK_SKIP_SIGN_VERIFY)
    dev_id = int(settings.SF_OPEN_DEV_ID or 0)
    app_key = (settings.SF_OPEN_SECRET or "").strip()

    verify_err: str | None = None
    payload: dict[str, Any] | None = None
    if raw_body.strip():
        try:
            obj = json.loads(raw_body)
            if isinstance(obj, dict):
                payload = obj
        except json.JSONDecodeError as e:
            verify_err = f"invalid json: {e}"
    else:
        verify_err = "empty body"

    if skip:
        sign_ok = verify_err is None and (payload is not None or raw_body.strip() == "{}")
    elif verify_err:
        sign_ok = False
    elif not dev_id or not app_key:
        verify_err = verify_err or "missing SF_OPEN_DEV_ID or SF_OPEN_SECRET"
        sign_ok = False
    elif not sign_query:
        verify_err = "missing sign parameter"
        sign_ok = False
    else:
        sign_ok = verify_sf_callback_signature(raw_body, sign_query, dev_id, app_key)
        if not sign_ok:
            verify_err = verify_err or "sign mismatch"

    try:
        persist_sf_callback_and_sync_push(
            db,
            route_kind=route_kind,
            raw_body=raw_body or "",
            sign_ok=sign_ok,
            payload=payload,
            verify_error=verify_err,
        )
    except Exception:
        logger.exception("顺丰回调落库失败 route_kind=%s", route_kind)
        db.rollback()
        raise

    return sign_ok, verify_err


def persist_oauth_style_callback(
    db: Session,
    *,
    route_kind: str,
    query_params: dict[str, str],
    raw_body: str,
) -> None:
    """授权类 URL 多为 GET query，无统一 sign 规则；仅落库备查。"""
    merged: dict[str, Any] = {"_query": query_params}
    rb = raw_body.strip()
    if rb:
        try:
            o = json.loads(rb)
            if isinstance(o, dict):
                merged.update(o)
        except json.JSONDecodeError:
            merged["_raw_post"] = rb[:5000]
    row = SfSameCityCallback(
        route_kind=route_kind,
        sign_ok=True,
        error_message="oauth_or_auth_callback_no_sign",
        shop_order_id=None,
        sf_order_id=None,
        payload_json=merged,
        raw_body=json.dumps(merged, ensure_ascii=False)[:65000],
    )
    db.add(row)
    db.commit()
