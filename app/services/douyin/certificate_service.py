"""抖音验券兑换：prepare → verify → 落库 → 本地发奖（失败则撤销核销）。"""

from __future__ import annotations

import logging
from datetime import date
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.integrations.douyin_life import (
    DouyinLifeError,
    certificate_cancel,
    certificate_prepare,
    certificate_verify,
)
from app.models.douyin.certificate_redemption import DouyinCertificateRedemption
from app.models.douyin.product_mapping import DouyinProductMapping
from app.models.enums import DouyinGrantType, DouyinRedemptionStatus
from app.models.marketing_coupon_template import MarketingCouponTemplate
from app.models.member import Member
from app.models.membership_card_template import MembershipCardTemplate
from app.models.store_retail_product import StoreRetailProduct
from app.core.timeutil import beijing_now_naive
from app.schemas.douyin import AdminDouyinCertificateRedeemIn, DouyinCertificateRedeemIn, DouyinCertificateRedeemOut
from app.services.admin.store_retail_order_admin_service import _resolve_member_for_admin_retail_order
from app.services.douyin.config_service import get_douyin_access_token, get_douyin_store_config
from app.services.douyin.product_mapping_service import find_active_mapping_for_certificate, grant_type_label
from app.services.marketing.member_coupon_service import _grant_member_coupon_to_member
from app.services.member.member_card_order_service import create_paid_card_order_for_douyin_redeem
from app.services.client.store_retail_order_service import create_paid_store_retail_order_for_douyin_redeem

logger = logging.getLogger(__name__)

# 可断点续发奖 / 可重试发奖的状态
_GRANT_RETRY_STATUSES = frozenset(
    {
        DouyinRedemptionStatus.VERIFIED.value,
        DouyinRedemptionStatus.GRANT_FAILED.value,
    }
)


def _mask_code(code: str) -> str:
    c = (code or "").strip()
    if len(c) <= 4:
        return "****"
    return f"{'*' * (len(c) - 4)}{c[-4:]}"


def _amount_from_cert_fen(fen: int | None) -> Decimal | None:
    if fen is None:
        return None
    return (Decimal(fen) / Decimal("100")).quantize(Decimal("0.01"))


def _extract_verify_id(verify_data: dict) -> str | None:
    results = verify_data.get("verify_results")
    if not isinstance(results, list):
        return None
    for row in results:
        if not isinstance(row, dict):
            continue
        vid = str(row.get("verify_id") or "").strip()
        if vid:
            return vid
    return None


def _grant_error_message(exc: BaseException) -> str:
    """统一提取发奖失败文案，便于落库与返回。"""
    if isinstance(exc, HTTPException):
        detail = exc.detail
        if isinstance(detail, str):
            return detail
        return str(detail)
    return str(exc) or exc.__class__.__name__


def _try_cancel_douyin_verify(
    *,
    access_token: str,
    verify_id: str | None,
    certificate_id: str,
) -> tuple[bool, str | None]:
    """发奖失败后尝试撤销抖音核销，返回 (是否成功, 失败原因)。"""
    vid = (verify_id or "").strip()
    cid = (certificate_id or "").strip()
    if not vid or not cid:
        return False, "缺少 verify_id 或 certificate_id，无法撤销核销"
    try:
        certificate_cancel(
            access_token=access_token,
            verify_id=vid,
            certificate_id=cid,
        )
        return True, None
    except DouyinLifeError as exc:
        logger.warning(
            "抖音撤销核销失败 cert=%s verify=%s err=%s",
            cid,
            vid,
            exc,
        )
        return False, str(exc)


def _find_verified_row_for_code_retry(
    db: Session,
    *,
    member_id: int,
    code: str,
) -> DouyinCertificateRedemption | None:
    """prepare 失败时：若本地存在 verified/grant_failed 流水且券码后缀一致，允许续发奖。"""
    masked = _mask_code(code)
    return db.scalar(
        select(DouyinCertificateRedemption)
        .where(
            DouyinCertificateRedemption.member_id == int(member_id),
            DouyinCertificateRedemption.status.in_(_GRANT_RETRY_STATUSES),
            DouyinCertificateRedemption.code_masked == masked,
        )
        .order_by(DouyinCertificateRedemption.id.desc())
        .limit(1)
        .with_for_update()
    )


def _persist_redemption_row(
    db: Session,
    *,
    existing: DouyinCertificateRedemption | None,
    member: Member,
    code: str,
    certificate_id: str,
    mapping: DouyinProductMapping | None,
    cert_product_id: str | None,
    cert_sku_id: str | None,
    cert_title: str | None,
    douyin_order_id: str | None,
    verify_token: str,
    status: str,
    error_msg: str | None = None,
    grant_result_kind: str | None = None,
    grant_result_id: int | None = None,
    douyin_verify_id: str | None = None,
    amount_yuan: Decimal | None = None,
    clear_grant_result: bool = False,
) -> DouyinCertificateRedemption:
    """创建或更新核销流水（同一 certificate_id 复用行，避免 unique 冲突）。"""
    if existing is not None:
        row = existing
    else:
        row = DouyinCertificateRedemption(certificate_id=certificate_id)
        db.add(row)

    row.tenant_id = int(member.tenant_id)
    row.store_id = int(member.store_id)
    row.member_id = int(member.id)
    row.code_masked = _mask_code(code)
    row.douyin_order_id = douyin_order_id
    row.douyin_product_id = cert_product_id
    row.douyin_sku_id = cert_sku_id
    row.douyin_product_title = cert_title
    row.mapping_id = int(mapping.id) if mapping is not None else None
    row.grant_type = str(mapping.grant_type) if mapping is not None else None
    row.grant_target_id = int(mapping.target_id) if mapping and mapping.target_id is not None else None
    row.status = status
    row.error_msg = (error_msg or "")[:512] or None
    row.verify_token = verify_token
    row.douyin_verify_id = douyin_verify_id
    row.amount_yuan = amount_yuan

    if clear_grant_result:
        row.grant_result_kind = None
        row.grant_result_id = None
    if grant_result_kind is not None:
        row.grant_result_kind = grant_result_kind
    if grant_result_id is not None:
        row.grant_result_id = grant_result_id

    db.flush()
    return row


def _load_mapping_for_redemption(db: Session, row: DouyinCertificateRedemption) -> DouyinProductMapping:
    """从流水记录的 mapping_id 加载映射，用于断点续发奖。"""
    if row.mapping_id is None:
        raise HTTPException(status_code=400, detail="兑换记录缺少商品映射，请联系客服")
    mapping = db.get(DouyinProductMapping, int(row.mapping_id))
    if not mapping or int(mapping.store_id) != int(row.store_id):
        raise HTTPException(status_code=400, detail="商品映射已失效，请联系客服")
    if not bool(mapping.is_active):
        raise HTTPException(status_code=400, detail="商品映射已停用，请联系客服")
    return mapping


def _apply_local_grant(
    db: Session,
    *,
    member: Member,
    mapping: DouyinProductMapping,
    delivery_start_date: date | None,
    amount_yuan: Decimal | None,
    douyin_order_id: str | None,
) -> tuple[str, int, str]:
    """验券成功后发放本地权益，返回 (grant_result_kind, grant_result_id, grant_label)。"""
    gt = DouyinGrantType(str(mapping.grant_type))
    remark = f"抖音验券兑换 order={douyin_order_id or '-'}"

    if gt == DouyinGrantType.COUPON_TEMPLATE:
        if mapping.target_id is None:
            raise HTTPException(status_code=400, detail="优惠券映射缺少券种 ID")
        tpl = db.scalar(
            select(MarketingCouponTemplate)
            .where(
                MarketingCouponTemplate.id == int(mapping.target_id),
                MarketingCouponTemplate.store_id == int(member.store_id),
            )
            .with_for_update()
        )
        if not tpl:
            raise HTTPException(status_code=404, detail="优惠券券种不存在")
        if not bool(tpl.is_active):
            raise HTTPException(status_code=400, detail="券种已下架，无法发放")
        now = beijing_now_naive()
        coupon_row = _grant_member_coupon_to_member(
            db,
            tpl=tpl,
            mem=member,
            tenant_id=int(member.tenant_id),
            store_id=int(member.store_id),
            operator="douyin_redeem",
            remark=remark,
            now=now,
        )
        db.flush()
        return "member_coupon", int(coupon_row.id), grant_type_label(gt.value, display_name=tpl.name)

    if gt == DouyinGrantType.RETAIL_PRODUCT:
        if mapping.target_id is None:
            raise HTTPException(status_code=400, detail="商城商品映射缺少商品 ID")
        prod = db.get(StoreRetailProduct, int(mapping.target_id))
        if not prod or int(prod.store_id) != int(member.store_id):
            raise HTTPException(status_code=404, detail="商城商品不存在")
        if not bool(prod.is_on_shelf):
            raise HTTPException(status_code=400, detail="商城商品已下架，无法核销")
        grant_label = grant_type_label(gt.value, display_name=prod.title)
        order = create_paid_store_retail_order_for_douyin_redeem(
            db,
            member=member,
            retail_product_id=int(prod.id),
            amount_yuan=amount_yuan,
            remark=remark,
        )
        return "store_retail_order", int(order.id), grant_label

    card_kind: str | None = None
    membership_template_id: int | None = None
    grant_label = mapping.display_name
    if gt == DouyinGrantType.WEEK_CARD:
        card_kind = "周卡"
        grant_label = grant_type_label(gt.value)
    elif gt == DouyinGrantType.MONTH_CARD:
        card_kind = "月卡"
        grant_label = grant_type_label(gt.value)
    elif gt == DouyinGrantType.MEMBERSHIP_TEMPLATE:
        membership_template_id = int(mapping.target_id) if mapping.target_id is not None else None
        if membership_template_id is None:
            raise HTTPException(status_code=400, detail="卡包映射缺少模板 ID")
        tpl_card = db.get(MembershipCardTemplate, membership_template_id)
        grant_label = grant_type_label(gt.value, display_name=tpl_card.name if tpl_card else mapping.display_name)
    else:
        raise HTTPException(status_code=400, detail="未知映射类型")

    order = create_paid_card_order_for_douyin_redeem(
        db,
        member=member,
        card_kind=card_kind,
        membership_template_id=membership_template_id,
        delivery_start_date=delivery_start_date,
        amount_yuan=amount_yuan,
        remark=remark,
    )
    return "member_card_order", int(order.id), grant_label


def _build_redeem_out(
    *,
    mapping: DouyinProductMapping,
    grant_kind: str,
    grant_id: int,
    grant_label: str,
    delivery_start_date: date | None,
) -> DouyinCertificateRedeemOut:
    msg = f"兑换成功，已获得{grant_label}"
    if grant_kind == "member_card_order" and delivery_start_date is None:
        msg += "；请完善配送信息后开始履约"
    elif grant_kind == "store_retail_order":
        msg += "；已生成商城订单，请到店自提或联系门店安排配送"
    return DouyinCertificateRedeemOut(
        grant_type=str(mapping.grant_type),
        grant_label=grant_label,
        grant_result_kind=grant_kind,
        grant_result_id=grant_id,
        message=msg,
    )


def _complete_local_grant(
    db: Session,
    *,
    redemption_id: int,
    member: Member,
    mapping: DouyinProductMapping,
    code: str,
    certificate_id: str,
    cert_product_id: str | None,
    cert_sku_id: str | None,
    cert_title: str | None,
    douyin_order_id: str | None,
    verify_token: str,
    douyin_verify_id: str | None,
    amount_yuan: Decimal | None,
    delivery_start_date: date | None,
) -> DouyinCertificateRedeemOut:
    """执行本地发奖并将流水更新为 success。"""
    grant_kind, grant_id, grant_label = _apply_local_grant(
        db,
        member=member,
        mapping=mapping,
        delivery_start_date=delivery_start_date,
        amount_yuan=amount_yuan,
        douyin_order_id=douyin_order_id,
    )
    row = db.get(DouyinCertificateRedemption, int(redemption_id))
    if row is None:
        raise HTTPException(status_code=500, detail="兑换流水异常，请联系客服")

    _persist_redemption_row(
        db,
        existing=row,
        member=member,
        code=code,
        certificate_id=certificate_id,
        mapping=mapping,
        cert_product_id=cert_product_id,
        cert_sku_id=cert_sku_id,
        cert_title=cert_title,
        douyin_order_id=douyin_order_id,
        verify_token=verify_token,
        status=DouyinRedemptionStatus.SUCCESS.value,
        error_msg=None,
        grant_result_kind=grant_kind,
        grant_result_id=grant_id,
        douyin_verify_id=douyin_verify_id,
        amount_yuan=amount_yuan,
    )
    db.commit()
    return _build_redeem_out(
        mapping=mapping,
        grant_kind=grant_kind,
        grant_id=grant_id,
        grant_label=grant_label,
        delivery_start_date=delivery_start_date,
    )


def _handle_grant_failure(
    db: Session,
    *,
    access_token: str,
    redemption_id: int,
    certificate_id: str,
    douyin_verify_id: str | None,
    grant_error: str,
) -> None:
    """
    发奖失败：回滚本地未提交变更 → 尝试撤销抖音核销 → 更新流水。
    撤销成功记 cancelled（用户可重新兑换）；撤销失败记 grant_failed（可断点续发奖）。
    """
    db.rollback()
    logger.error(
        "抖音验券本地发奖失败 redemption_id=%s cert=%s verify=%s err=%s",
        redemption_id,
        certificate_id,
        douyin_verify_id,
        grant_error,
    )

    # 行锁：避免与用户重试并发时，撤销核销把已成功/已续发奖的抖音券误改回未核销
    row = db.scalar(
        select(DouyinCertificateRedemption)
        .where(DouyinCertificateRedemption.id == int(redemption_id))
        .with_for_update()
    )
    if row is None:
        logger.error(
            "发奖失败但找不到流水 redemption_id=%s cert=%s grant_error=%s",
            redemption_id,
            certificate_id,
            grant_error,
        )
        raise HTTPException(status_code=500, detail="兑换异常，请联系客服")

    if row.status == DouyinRedemptionStatus.SUCCESS.value:
        logger.warning(
            "发奖失败处理时流水已为 success，跳过撤销核销 redemption_id=%s cert=%s",
            redemption_id,
            certificate_id,
        )
        return

    cancel_ok, cancel_err = _try_cancel_douyin_verify(
        access_token=access_token,
        verify_id=douyin_verify_id,
        certificate_id=certificate_id,
    )

    if cancel_ok:
        row.status = DouyinRedemptionStatus.CANCELLED.value
        row.error_msg = f"发奖失败已撤销核销：{grant_error}"[:512]
        user_detail = "发奖失败，已撤销团购核销，请重新兑换"
        http_status = 400
    else:
        row.status = DouyinRedemptionStatus.GRANT_FAILED.value
        parts = [f"发奖失败：{grant_error}"]
        if cancel_err:
            parts.append(f"撤销核销失败：{cancel_err}")
        row.error_msg = "；".join(parts)[:512]
        user_detail = "兑换失败，请稍后重试；若仍失败请联系客服"
        http_status = 500

    row.grant_result_kind = None
    row.grant_result_id = None
    db.add(row)
    db.commit()
    raise HTTPException(status_code=http_status, detail=user_detail)


def _retry_local_grant(
    db: Session,
    *,
    existing: DouyinCertificateRedemption,
    member: Member,
    body: DouyinCertificateRedeemIn,
    access_token: str,
) -> DouyinCertificateRedeemOut:
    """抖音已核销、本地未成功发奖：仅重试本地发奖，不再调用 verify。"""
    if int(existing.member_id) != int(member.id):
        raise HTTPException(status_code=403, detail="该券兑换记录不属于当前用户")
    if not existing.douyin_verify_id:
        raise HTTPException(status_code=400, detail="兑换记录异常，请联系客服")

    mapping = _load_mapping_for_redemption(db, existing)
    code = (body.code or "").strip()
    cert_id = str(existing.certificate_id)
    amount_yuan = existing.amount_yuan

    try:
        return _complete_local_grant(
            db,
            redemption_id=int(existing.id),
            member=member,
            mapping=mapping,
            code=code,
            certificate_id=cert_id,
            cert_product_id=existing.douyin_product_id,
            cert_sku_id=existing.douyin_sku_id,
            cert_title=existing.douyin_product_title,
            douyin_order_id=existing.douyin_order_id,
            verify_token=str(existing.verify_token or ""),
            douyin_verify_id=existing.douyin_verify_id,
            amount_yuan=amount_yuan,
            delivery_start_date=body.delivery_start_date,
        )
    except HTTPException as exc:
        _handle_grant_failure(
            db,
            access_token=access_token,
            redemption_id=int(existing.id),
            certificate_id=cert_id,
            douyin_verify_id=existing.douyin_verify_id,
            grant_error=_grant_error_message(exc),
        )
        raise  # pragma: no cover — _handle_grant_failure 必 raise
    except Exception as exc:
        _handle_grant_failure(
            db,
            access_token=access_token,
            redemption_id=int(existing.id),
            certificate_id=cert_id,
            douyin_verify_id=existing.douyin_verify_id,
            grant_error=_grant_error_message(exc),
        )
        raise  # pragma: no cover


def redeem_douyin_certificate(
    db: Session,
    *,
    member_id: int,
    body: DouyinCertificateRedeemIn,
) -> DouyinCertificateRedeemOut:
    """小程序粘贴券码兑换。"""
    code = (body.code or "").strip()
    if len(code) < 4:
        raise HTTPException(status_code=400, detail="请输入有效券码")

    member = db.get(Member, int(member_id))
    if not member or member.deleted_at is not None:
        raise HTTPException(status_code=404, detail="用户不存在")

    store_cfg = get_douyin_store_config(db, int(member.store_id))
    access_token = get_douyin_access_token(db, int(member.tenant_id))

    try:
        prepared = certificate_prepare(
            access_token=access_token,
            code=code,
            poi_id=store_cfg.poi_id,
            account_id=store_cfg.account_id,
        )
    except DouyinLifeError as exc:
        pending_row = _find_verified_row_for_code_retry(db, member_id=int(member_id), code=code)
        if pending_row is not None:
            return _retry_local_grant(
                db,
                existing=pending_row,
                member=member,
                body=body,
                access_token=access_token,
            )
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    cert = prepared.certificates[0]
    cert_id = str(cert.certificate_id)

    # 行锁：避免「发奖失败撤销核销」与「用户重试兑换」并发导致本地成功但抖音未核销
    existing = db.scalar(
        select(DouyinCertificateRedemption)
        .where(DouyinCertificateRedemption.certificate_id == cert_id)
        .with_for_update()
    )
    if existing:
        if existing.status == DouyinRedemptionStatus.SUCCESS.value:
            raise HTTPException(status_code=400, detail="该券已兑换，请勿重复提交")
        # prepare 成功说明抖音侧券仍可用，必须重新 verify，不可仅续发本地权益。
        # 仅当 prepare 失败（券已在抖音核销）时才走 _retry_local_grant。
        if existing.status in _GRANT_RETRY_STATUSES:
            logger.warning(
                "抖音验券本地流水待续发但 prepare 仍返回可用券，将重新核销 cert=%s status=%s order=%s",
                cert_id,
                existing.status,
                prepared.order_id,
            )
        # failed / cancelled / verified / grant_failed：均重新走 verify → 发奖

    mapping = find_active_mapping_for_certificate(db, store_id=int(member.store_id), cert=cert)
    amount_yuan = _amount_from_cert_fen(cert.pay_amount_fen)

    try:
        verify_data = certificate_verify(
            access_token=access_token,
            verify_token=prepared.verify_token,
            poi_id=store_cfg.poi_id,
            encrypted_codes=[cert.encrypted_code],
            order_id=prepared.order_id,
        )
    except DouyinLifeError as exc:
        db.rollback()
        _persist_redemption_row(
            db,
            existing=existing,
            member=member,
            code=code,
            certificate_id=cert_id,
            mapping=mapping,
            cert_product_id=cert.product_id,
            cert_sku_id=cert.sku_id,
            cert_title=cert.title,
            douyin_order_id=prepared.order_id,
            verify_token=prepared.verify_token,
            status=DouyinRedemptionStatus.FAILED.value,
            error_msg=str(exc),
            amount_yuan=amount_yuan,
            clear_grant_result=True,
        )
        db.commit()
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    douyin_verify_id = _extract_verify_id(verify_data)
    if not douyin_verify_id:
        db.rollback()
        _persist_redemption_row(
            db,
            existing=existing,
            member=member,
            code=code,
            certificate_id=cert_id,
            mapping=mapping,
            cert_product_id=cert.product_id,
            cert_sku_id=cert.sku_id,
            cert_title=cert.title,
            douyin_order_id=prepared.order_id,
            verify_token=prepared.verify_token,
            status=DouyinRedemptionStatus.FAILED.value,
            error_msg="验券成功但未返回 verify_id",
            amount_yuan=amount_yuan,
            clear_grant_result=True,
        )
        db.commit()
        raise HTTPException(status_code=502, detail="验券响应异常，请稍后重试或联系客服")

    # 抖音已核销：先落 verified 流水并提交，避免发奖异常时无记录
    verified_row = _persist_redemption_row(
        db,
        existing=existing,
        member=member,
        code=code,
        certificate_id=cert_id,
        mapping=mapping,
        cert_product_id=cert.product_id,
        cert_sku_id=cert.sku_id,
        cert_title=cert.title,
        douyin_order_id=prepared.order_id,
        verify_token=prepared.verify_token,
        status=DouyinRedemptionStatus.VERIFIED.value,
        error_msg=None,
        douyin_verify_id=douyin_verify_id,
        amount_yuan=amount_yuan,
        clear_grant_result=True,
    )
    db.commit()
    redemption_id = int(verified_row.id)

    try:
        return _complete_local_grant(
            db,
            redemption_id=redemption_id,
            member=member,
            mapping=mapping,
            code=code,
            certificate_id=cert_id,
            cert_product_id=cert.product_id,
            cert_sku_id=cert.sku_id,
            cert_title=cert.title,
            douyin_order_id=prepared.order_id,
            verify_token=prepared.verify_token,
            douyin_verify_id=douyin_verify_id,
            amount_yuan=amount_yuan,
            delivery_start_date=body.delivery_start_date,
        )
    except HTTPException as exc:
        _handle_grant_failure(
            db,
            access_token=access_token,
            redemption_id=redemption_id,
            certificate_id=cert_id,
            douyin_verify_id=douyin_verify_id,
            grant_error=_grant_error_message(exc),
        )
        raise  # pragma: no cover
    except Exception as exc:
        logger.exception(
            "抖音验券本地发奖未预期异常 redemption_id=%s cert=%s err=%s",
            redemption_id,
            cert_id,
            exc,
        )
        _handle_grant_failure(
            db,
            access_token=access_token,
            redemption_id=redemption_id,
            certificate_id=cert_id,
            douyin_verify_id=douyin_verify_id,
            grant_error=_grant_error_message(exc),
        )
        raise  # pragma: no cover


def admin_redeem_douyin_certificate(
    db: Session,
    *,
    tenant_id: int,
    store_id: int,
    body: AdminDouyinCertificateRedeemIn,
    operator: str,
) -> DouyinCertificateRedeemOut:
    """管理端：协助会员完成抖音验券兑换（按手机号匹配或创建会员）。"""
    _ = operator
    member = _resolve_member_for_admin_retail_order(
        db,
        phone=body.phone,
        name=body.name,
        tenant_id=int(tenant_id),
        store_id=int(store_id),
    )
    redeem_body = DouyinCertificateRedeemIn(
        code=body.code,
        delivery_start_date=body.delivery_start_date,
    )
    return redeem_douyin_certificate(db, member_id=int(member.id), body=redeem_body)
