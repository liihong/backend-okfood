"""抖音验券兑换：prepare → verify → 本地发奖。"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.integrations.douyin_life import (
    DouyinLifeError,
    certificate_prepare,
    certificate_verify,
)
from app.models.douyin.certificate_redemption import DouyinCertificateRedemption
from app.models.douyin.product_mapping import DouyinProductMapping
from app.models.enums import DouyinGrantType, DouyinRedemptionStatus
from app.models.marketing_coupon_template import MarketingCouponTemplate
from app.models.member import Member
from app.models.membership_card_template import MembershipCardTemplate
from app.core.timeutil import beijing_now_naive
from app.schemas.douyin import DouyinCertificateRedeemIn, DouyinCertificateRedeemOut
from app.services.douyin.config_service import get_douyin_access_token, get_douyin_store_config
from app.services.douyin.product_mapping_service import find_active_mapping_for_certificate, grant_type_label
from app.services.marketing.member_coupon_service import _grant_member_coupon_to_member
from app.services.member_card_order_service import create_paid_card_order_for_douyin_redeem


def _mask_code(code: str) -> str:
    c = (code or "").strip()
    if len(c) <= 4:
        return "****"
    return f"{'*' * (len(c) - 4)}{c[-4:]}"


def _amount_from_cert_fen(fen: int | None) -> Decimal | None:
    if fen is None:
        return None
    return (Decimal(fen) / Decimal("100")).quantize(Decimal("0.01"))


def _save_redemption_row(
    db: Session,
    *,
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
    amount_yuan: Decimal | None = None,
) -> DouyinCertificateRedemption:
    row = DouyinCertificateRedemption(
        tenant_id=int(member.tenant_id),
        store_id=int(member.store_id),
        member_id=int(member.id),
        code_masked=_mask_code(code),
        douyin_order_id=douyin_order_id,
        certificate_id=certificate_id,
        douyin_product_id=cert_product_id,
        douyin_sku_id=cert_sku_id,
        douyin_product_title=cert_title,
        mapping_id=int(mapping.id) if mapping is not None else None,
        grant_type=str(mapping.grant_type) if mapping is not None else None,
        grant_target_id=int(mapping.target_id) if mapping and mapping.target_id is not None else None,
        grant_result_kind=grant_result_kind,
        grant_result_id=grant_result_id,
        status=status,
        error_msg=(error_msg or "")[:512] or None,
        verify_token=verify_token,
        amount_yuan=amount_yuan,
    )
    db.add(row)
    return row


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
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    cert = prepared.certificates[0]
    cert_id = str(cert.certificate_id)

    existing = db.scalar(
        select(DouyinCertificateRedemption).where(DouyinCertificateRedemption.certificate_id == cert_id)
    )
    if existing:
        if existing.status == DouyinRedemptionStatus.SUCCESS.value:
            raise HTTPException(status_code=400, detail="该券已兑换，请勿重复提交")
        raise HTTPException(status_code=400, detail="该券存在历史兑换记录，请联系客服")

    mapping = find_active_mapping_for_certificate(db, store_id=int(member.store_id), cert=cert)
    amount_yuan = _amount_from_cert_fen(cert.pay_amount_fen)

    try:
        certificate_verify(
            access_token=access_token,
            verify_token=prepared.verify_token,
            poi_id=store_cfg.poi_id,
            encrypted_codes=[cert.encrypted_code],
            order_id=prepared.order_id,
        )
    except DouyinLifeError as exc:
        _save_redemption_row(
            db,
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
        )
        db.commit()
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    try:
        grant_kind, grant_id, grant_label = _apply_local_grant(
            db,
            member=member,
            mapping=mapping,
            delivery_start_date=body.delivery_start_date,
            amount_yuan=amount_yuan,
            douyin_order_id=prepared.order_id,
        )
    except HTTPException as exc:
        _save_redemption_row(
            db,
            member=member,
            code=code,
            certificate_id=cert_id,
            mapping=mapping,
            cert_product_id=cert.product_id,
            cert_sku_id=cert.sku_id,
            cert_title=cert.title,
            douyin_order_id=prepared.order_id,
            verify_token=prepared.verify_token,
            status=DouyinRedemptionStatus.GRANT_FAILED.value,
            error_msg=str(exc.detail),
            amount_yuan=amount_yuan,
        )
        db.commit()
        raise

    _save_redemption_row(
        db,
        member=member,
        code=code,
        certificate_id=cert_id,
        mapping=mapping,
        cert_product_id=cert.product_id,
        cert_sku_id=cert.sku_id,
        cert_title=cert.title,
        douyin_order_id=prepared.order_id,
        verify_token=prepared.verify_token,
        status=DouyinRedemptionStatus.SUCCESS.value,
        grant_result_kind=grant_kind,
        grant_result_id=grant_id,
        amount_yuan=amount_yuan,
    )
    db.commit()

    msg = f"兑换成功，已获得{grant_label}"
    if grant_kind == "member_card_order" and body.delivery_start_date is None:
        msg += "；请完善配送信息后开始履约"
    return DouyinCertificateRedeemOut(
        grant_type=str(mapping.grant_type),
        grant_label=grant_label,
        grant_result_kind=grant_kind,
        grant_result_id=grant_id,
        message=msg,
    )
