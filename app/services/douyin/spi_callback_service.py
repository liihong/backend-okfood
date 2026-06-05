"""抖音 SPI：撤销核销异步回调（cert.fulfil.async_cancel_fulfil）。"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.timeutil import beijing_now_naive
from app.integrations.douyin_spi_sign import verify_spi_signature
from app.models.douyin.certificate_redemption import DouyinCertificateRedemption
from app.models.enums import CardOrderPayStatus, DouyinRedemptionStatus, MemberCouponStatus
from app.models.member_card_order import MemberCardOrder
from app.models.member_coupon import MemberCoupon
from app.services.douyin.config_service import resolve_douyin_client_secret_by_client_key
from app.services.member_card_order_service import revoke_paid_card_order_member_sync

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DouyinCancelFulfilItem:
    certificate_id: str | None
    verify_id: str | None
    order_id: str | None
    result_code: int | None
    status: str | None


def douyin_spi_json(*, error_code: int, description: str) -> dict[str, Any]:
    return {"data": {"error_code": int(error_code), "description": description}}


def _s(v: Any) -> str | None:
    if v is None:
        return None
    t = str(v).strip()
    return t or None


def _int_or_none(v: Any) -> int | None:
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _parse_cancel_item(obj: dict[str, Any]) -> DouyinCancelFulfilItem | None:
    if not isinstance(obj, dict):
        return None
    order_info = obj.get("order_info") if isinstance(obj.get("order_info"), dict) else {}
    cert_id = _s(
        obj.get("certificate_id")
        or obj.get("certificateId")
        or obj.get("item_order_id")
        or obj.get("itemOrderId")
    )
    verify_id = _s(obj.get("verify_id") or obj.get("verifyId"))
    order_id = _s(obj.get("order_id") or obj.get("orderId") or order_info.get("order_id"))
    status = _s(obj.get("status"))
    result_code = _int_or_none(
        obj.get("result_code") if obj.get("result_code") is not None else obj.get("result")
    )
    if not cert_id and not verify_id and not order_id:
        return None
    return DouyinCancelFulfilItem(
        certificate_id=cert_id,
        verify_id=verify_id,
        order_id=order_id,
        result_code=result_code,
        status=status,
    )


def _collect_dict_candidates(payload: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = [payload]
    for key in ("data", "msg", "message", "body"):
        nested = payload.get(key)
        if isinstance(nested, dict):
            out.append(nested)
        elif isinstance(nested, str) and nested.strip():
            try:
                parsed = json.loads(nested)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                out.append(parsed)
    for key in ("cancel_results", "cancel_result_list", "verify_cancel_list"):
        rows = payload.get(key)
        if isinstance(rows, list):
            for row in rows:
                if isinstance(row, dict):
                    out.append(row)
    data = payload.get("data")
    if isinstance(data, dict):
        for key in ("cancel_results", "cancel_result_list", "verify_cancel_list"):
            rows = data.get(key)
            if isinstance(rows, list):
                for row in rows:
                    if isinstance(row, dict):
                        out.append(row)
    return out


def parse_async_cancel_fulfil_items(payload: dict[str, Any]) -> list[DouyinCancelFulfilItem]:
    """兼容 SPI 直出字段、cancel_results 批量字段及 verify_cancel 通知结构。"""
    items: list[DouyinCancelFulfilItem] = []
    seen: set[tuple[str | None, str | None, str | None]] = set()
    for block in _collect_dict_candidates(payload):
        item = _parse_cancel_item(block)
        if item is None:
            continue
        key = (item.certificate_id, item.verify_id, item.order_id)
        if key in seen:
            continue
        seen.add(key)
        items.append(item)
    return items


def _cancel_item_failed(item: DouyinCancelFulfilItem) -> bool:
    st = (item.status or "").strip().upper()
    if st == "FAIL":
        return True
    if item.result_code is not None and item.result_code != 0:
        return True
    return False


def _find_redemption(db: Session, item: DouyinCancelFulfilItem) -> DouyinCertificateRedemption | None:
    q = select(DouyinCertificateRedemption)
    if item.certificate_id:
        row = db.scalar(q.where(DouyinCertificateRedemption.certificate_id == item.certificate_id))
        if row:
            return row
    if item.verify_id:
        row = db.scalar(q.where(DouyinCertificateRedemption.douyin_verify_id == item.verify_id))
        if row:
            return row
    if item.order_id:
        q_order = q.where(DouyinCertificateRedemption.douyin_order_id == item.order_id)
        if item.certificate_id:
            q_order = q_order.where(DouyinCertificateRedemption.certificate_id == item.certificate_id)
        row = db.scalar(q_order.order_by(DouyinCertificateRedemption.id.desc()).limit(1))
        if row:
            return row
    return None


def _revoke_local_grant(db: Session, row: DouyinCertificateRedemption) -> str | None:
    """撤销本地权益；成功返回 None，失败返回原因。"""
    kind = (row.grant_result_kind or "").strip()
    grant_id = row.grant_result_id
    if not kind or grant_id is None:
        return None

    if kind == "member_coupon":
        coupon = db.get(MemberCoupon, int(grant_id))
        if not coupon:
            return "优惠券记录不存在"
        st = (coupon.status or "").strip()
        if st == MemberCouponStatus.REVOKED.value:
            return None
        if st != MemberCouponStatus.AVAILABLE.value:
            return f"优惠券状态为 {st}，无法自动作废"
        coupon.status = MemberCouponStatus.REVOKED.value
        coupon.revoked_at = beijing_now_naive()
        db.add(coupon)
        return None

    if kind == "member_card_order":
        order = db.get(MemberCardOrder, int(grant_id))
        if not order:
            return "开卡工单不存在"
        if not order.applied_to_member:
            order.pay_status = CardOrderPayStatus.CANCELLED.value
            db.add(order)
            return None
        try:
            revoke_paid_card_order_member_sync(db, order, operator="douyin_spi_cancel")
        except ValueError as exc:
            return str(exc)
        return None

    return None


def apply_douyin_cancel_fulfil_item(db: Session, item: DouyinCancelFulfilItem) -> tuple[bool, str]:
    """处理单条撤销通知；未匹配本地流水时视为成功（幂等）。"""
    if _cancel_item_failed(item):
        logger.info(
            "抖音撤销核销回调：平台撤销失败 cert=%s verify=%s order=%s status=%s result=%s",
            item.certificate_id,
            item.verify_id,
            item.order_id,
            item.status,
            item.result_code,
        )
        return True, "platform_cancel_failed"

    row = _find_redemption(db, item)
    if row is None:
        logger.info(
            "抖音撤销核销回调：未匹配本地流水 cert=%s verify=%s order=%s",
            item.certificate_id,
            item.verify_id,
            item.order_id,
        )
        return True, "redemption_not_found"

    if row.status == DouyinRedemptionStatus.CANCELLED.value:
        return True, "already_cancelled"

    if row.status != DouyinRedemptionStatus.SUCCESS.value:
        row.status = DouyinRedemptionStatus.CANCELLED.value
        row.error_msg = "抖音撤销核销回调：原兑换状态非 success"
        db.add(row)
        return True, "marked_cancelled_non_success"

    revoke_err = _revoke_local_grant(db, row)
    row.status = DouyinRedemptionStatus.CANCELLED.value
    row.error_msg = revoke_err
    if item.verify_id and not row.douyin_verify_id:
        row.douyin_verify_id = item.verify_id
    db.add(row)
    if revoke_err:
        logger.warning(
            "抖音撤销核销回调：本地权益未能完全回滚 redemption_id=%s err=%s",
            row.id,
            revoke_err,
        )
        return True, "cancelled_with_revoke_warning"
    return True, "cancelled"


def process_douyin_async_cancel_fulfil_notify(
    db: Session,
    *,
    raw_body: bytes,
    query_params: dict[str, str],
    header_client_key: str | None,
    header_sign: str | None,
) -> tuple[int, str]:
    """验签并处理撤销核销 SPI 回调，返回 (error_code, description)。"""
    settings = get_settings()
    if not raw_body:
        return 2100005, "empty body"

    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return 2100005, "invalid json body"
    if not isinstance(payload, dict):
        return 2100005, "invalid json body"

    client_key = (query_params.get("client_key") or header_client_key or "").strip()
    if not client_key:
        return 2100005, "missing client_key"

    skip_verify = bool(getattr(settings, "DOUYIN_SPI_SKIP_SIGN_VERIFY", False))
    if not skip_verify:
        secret = resolve_douyin_client_secret_by_client_key(db, client_key)
        if not secret:
            logger.warning("抖音 SPI 回调：未找到 client_key=%s 对应凭证", client_key)
            return 2100005, "unknown client_key"
        ok = verify_spi_signature(
            client_secret=secret,
            query=query_params,
            body=raw_body,
            header_sign=header_sign,
            query_sign=query_params.get("sign"),
        )
        if not ok:
            logger.warning(
                "抖音 SPI 回调验签失败 client_key=%s sign_header=%s sign_query=%s",
                client_key,
                bool(header_sign),
                bool(query_params.get("sign")),
            )
            return 2100005, "sign verify failed"

    items = parse_async_cancel_fulfil_items(payload)
    if not items:
        logger.warning("抖音 SPI 撤销核销回调：未解析到有效字段 payload_keys=%s", list(payload.keys()))
        return 0, "success"

    for item in items:
        ok, _reason = apply_douyin_cancel_fulfil_item(db, item)
        if not ok:
            db.rollback()
            return 2100001, "process failed"

    db.commit()
    return 0, "success"
