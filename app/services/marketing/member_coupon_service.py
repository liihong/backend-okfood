"""用户持券：发放、作废、可用券查询。"""

from __future__ import annotations

import re
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.timeutil import beijing_now_naive
from app.models.enums import (
    MEMBER_COUPON_REMINDER_BIZ_TYPES,
    CouponLockedOrderBiz,
    MemberCouponStatus,
)
from app.models.marketing_coupon_template import MarketingCouponTemplate
from app.models.member import Member
from app.models.member_coupon import MemberCoupon
from app.schemas.marketing.coupon import (
    MemberCouponBatchGrantFailedItem,
    MemberCouponBatchGrantIn,
    MemberCouponBatchGrantOut,
    MemberCouponGrantIn,
    MemberCouponOut,
    UserMemberCouponAvailableOut,
    UserMemberCouponReminderOut,
)
from app.services.marketing.coupon_checkout_service import (
    CouponCheckoutContext,
    _scope_matches,
    compute_grant_expires_at,
    expire_member_coupon_if_needed,
    format_amount_yuan,
)


def _member_coupon_to_out(db: Session, row: MemberCoupon) -> MemberCouponOut:
    tpl_name: str | None = None
    tpl = db.get(MarketingCouponTemplate, int(row.template_id))
    if tpl:
        tpl_name = str(tpl.name)
    mem = db.get(Member, int(row.member_id))
    phone = (mem.phone or "").strip() if mem else None
    name = (mem.name or "").strip() if mem else None
    return MemberCouponOut(
        id=int(row.id),
        template_id=int(row.template_id),
        template_name=tpl_name,
        member_id=int(row.member_id),
        member_phone=phone,
        member_name=name,
        discount_yuan=format_amount_yuan(Decimal(row.discount_yuan)),
        min_order_yuan=format_amount_yuan(Decimal(row.min_order_yuan or 0)),
        biz_type=str(row.biz_type),
        scope_level=str(row.scope_level),
        scope_target_id=int(row.scope_target_id) if row.scope_target_id is not None else None,
        status=str(row.status),
        expires_at=row.expires_at.isoformat() if row.expires_at else None,
        locked_order_biz=(row.locked_order_biz or "").strip() or None,
        locked_order_id=int(row.locked_order_id) if row.locked_order_id is not None else None,
        issued_by=str(row.issued_by),
        issued_at=row.issued_at.isoformat() if row.issued_at else None,
        used_at=row.used_at.isoformat() if row.used_at else None,
        revoked_at=row.revoked_at.isoformat() if row.revoked_at else None,
        remark=(row.remark or "").strip() or None,
    )


def _normalize_member_phone(phone: str) -> str:
    """规范化手机号：去首尾空白并移除常见分隔符。"""
    return (phone or "").strip().replace(" ", "").replace("-", "")


def _parse_batch_member_phones(raw: list[str]) -> list[str]:
    """解析批量手机号：支持换行、逗号、分号分隔，去重并保持顺序。"""
    seen: set[str] = set()
    out: list[str] = []
    for item in raw:
        for part in re.split(r"[\n,;，；\s]+", item or ""):
            ph = _normalize_member_phone(part)
            if not ph or ph in seen:
                continue
            seen.add(ph)
            out.append(ph)
    return out


def _resolve_member_by_phone(
    db: Session,
    *,
    phone: str,
    tenant_id: int,
    store_id: int,
) -> Member:
    ph = _normalize_member_phone(phone)
    if not ph:
        raise HTTPException(status_code=400, detail="手机号不能为空")
    mem = db.scalar(
        select(Member).where(
            Member.phone == ph,
            Member.store_id == int(store_id),
            Member.deleted_at.is_(None),
        )
    )
    if not mem:
        raise HTTPException(status_code=404, detail=f"未找到手机号 {ph} 对应的会员")
    if int(mem.tenant_id) != int(tenant_id):
        raise HTTPException(status_code=400, detail="会员不属于当前租户")
    return mem


def _grant_member_coupon_to_member(
    db: Session,
    *,
    tpl: MarketingCouponTemplate,
    mem: Member,
    tenant_id: int,
    store_id: int,
    operator: str,
    remark: str | None,
    now,
) -> MemberCoupon:
    """向指定会员发放一张券（调用方须已锁定券种模板行）。"""
    if tpl.max_grants is not None and int(tpl.grants_issued or 0) >= int(tpl.max_grants):
        raise HTTPException(status_code=400, detail="该券种发放已达上限")

    if tpl.validity_mode == "fixed_range":
        if tpl.valid_from and now < tpl.valid_from:
            raise HTTPException(status_code=400, detail="券种固定有效期尚未开始，暂不可发放")
        if tpl.valid_until and now > tpl.valid_until:
            raise HTTPException(status_code=400, detail="券种固定有效期已结束，无法发放")
    expires = compute_grant_expires_at(
        validity_mode=str(tpl.validity_mode),
        valid_from=tpl.valid_from,
        valid_until=tpl.valid_until,
        valid_days_after_grant=tpl.valid_days_after_grant,
        granted_at=now,
    )
    if expires is not None and expires <= now:
        raise HTTPException(status_code=400, detail="券种有效期计算异常，无法发放")

    row = MemberCoupon(
        template_id=int(tpl.id),
        member_id=int(mem.id),
        tenant_id=int(tenant_id),
        store_id=int(store_id),
        discount_yuan=Decimal(tpl.discount_yuan),
        min_order_yuan=Decimal(tpl.min_order_yuan or 0),
        biz_type=str(tpl.biz_type),
        scope_level=str(tpl.scope_level),
        scope_target_id=int(tpl.scope_target_id) if tpl.scope_target_id is not None else None,
        status=MemberCouponStatus.AVAILABLE.value,
        expires_at=expires,
        issued_by=(operator or "").strip()[:64] or "admin",
        issued_at=now,
        remark=(remark or "").strip()[:500] or None,
    )
    db.add(row)
    tpl.grants_issued = int(tpl.grants_issued or 0) + 1
    return row


def grant_member_coupon(
    db: Session,
    *,
    tenant_id: int,
    store_id: int,
    body: MemberCouponGrantIn,
    operator: str,
) -> MemberCouponOut:
    tpl = db.scalar(
        select(MarketingCouponTemplate)
        .where(
            MarketingCouponTemplate.id == int(body.template_id),
            MarketingCouponTemplate.store_id == int(store_id),
        )
        .with_for_update()
    )
    if not tpl:
        raise HTTPException(status_code=404, detail="券种不存在")
    if not bool(tpl.is_active):
        raise HTTPException(status_code=400, detail="券种已下架，无法发放")

    mem = _resolve_member_by_phone(
        db,
        phone=body.member_phone,
        tenant_id=int(tenant_id),
        store_id=int(store_id),
    )
    now = beijing_now_naive()
    row = _grant_member_coupon_to_member(
        db,
        tpl=tpl,
        mem=mem,
        tenant_id=int(tenant_id),
        store_id=int(store_id),
        operator=operator,
        remark=body.remark,
        now=now,
    )
    db.commit()
    db.refresh(row)
    return _member_coupon_to_out(db, row)


def grant_member_coupons_batch(
    db: Session,
    *,
    tenant_id: int,
    store_id: int,
    body: MemberCouponBatchGrantIn,
    operator: str,
) -> MemberCouponBatchGrantOut:
    phones = _parse_batch_member_phones(body.member_phones)
    if not phones:
        raise HTTPException(status_code=400, detail="请至少填写一个有效手机号")

    tpl = db.scalar(
        select(MarketingCouponTemplate)
        .where(
            MarketingCouponTemplate.id == int(body.template_id),
            MarketingCouponTemplate.store_id == int(store_id),
        )
        .with_for_update()
    )
    if not tpl:
        raise HTTPException(status_code=404, detail="券种不存在")
    if not bool(tpl.is_active):
        raise HTTPException(status_code=400, detail="券种已下架，无法发放")

    now = beijing_now_naive()
    remark = body.remark
    items: list[MemberCouponOut] = []
    failed: list[MemberCouponBatchGrantFailedItem] = []

    for ph in phones:
        try:
            mem = _resolve_member_by_phone(
                db,
                phone=ph,
                tenant_id=int(tenant_id),
                store_id=int(store_id),
            )
            row = _grant_member_coupon_to_member(
                db,
                tpl=tpl,
                mem=mem,
                tenant_id=int(tenant_id),
                store_id=int(store_id),
                operator=operator,
                remark=remark,
                now=now,
            )
            db.flush()
            items.append(_member_coupon_to_out(db, row))
        except HTTPException as exc:
            failed.append(
                MemberCouponBatchGrantFailedItem(
                    member_phone=ph,
                    reason=str(exc.detail or "发放失败"),
                )
            )

    if items:
        db.commit()
    else:
        db.rollback()

    return MemberCouponBatchGrantOut(
        success_count=len(items),
        failed=failed,
        items=items,
    )


def revoke_member_coupon(db: Session, *, coupon_id: int, store_id: int) -> MemberCouponOut:
    row = db.get(MemberCoupon, int(coupon_id))
    if not row or int(row.store_id) != int(store_id):
        raise HTTPException(status_code=404, detail="优惠券不存在")
    st = (row.status or "").strip()
    if st != MemberCouponStatus.AVAILABLE.value:
        raise HTTPException(status_code=400, detail="仅待使用的优惠券可作废")
    row.status = MemberCouponStatus.REVOKED.value
    row.revoked_at = beijing_now_naive()
    db.commit()
    db.refresh(row)
    return _member_coupon_to_out(db, row)


def list_member_coupons_paged(
    db: Session,
    *,
    store_id: int,
    page: int = 1,
    page_size: int = 20,
    member_id: int | None = None,
    template_id: int | None = None,
    status: str | None = None,
    biz_type: str | None = None,
) -> tuple[list[MemberCouponOut], int]:
    q = select(MemberCoupon).where(MemberCoupon.store_id == int(store_id))
    if member_id is not None:
        q = q.where(MemberCoupon.member_id == int(member_id))
    if template_id is not None:
        q = q.where(MemberCoupon.template_id == int(template_id))
    if status:
        q = q.where(MemberCoupon.status == status.strip())
    if biz_type:
        q = q.where(MemberCoupon.biz_type == biz_type.strip())
    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    rows = db.scalars(
        q.order_by(MemberCoupon.id.desc())
        .offset(max(0, (page - 1) * page_size))
        .limit(page_size)
    ).all()
    return [_member_coupon_to_out(db, r) for r in rows], int(total)


def _build_checkout_context(
    *,
    checkout_biz: CouponLockedOrderBiz,
    original_amount_yuan: Decimal,
    card_kind: str | None = None,
    membership_template_id: int | None = None,
    dish_id: int | None = None,
    retail_product_id: int | None = None,
) -> CouponCheckoutContext:
    retail_category_id: int | None = None
    return CouponCheckoutContext(
        checkout_biz=checkout_biz,
        original_amount_yuan=original_amount_yuan,
        card_kind=card_kind,
        membership_template_id=membership_template_id,
        dish_id=dish_id,
        retail_product_id=retail_product_id,
        retail_category_id=retail_category_id,
    )


def list_available_member_coupons_for_user(
    db: Session,
    *,
    member_id: int,
    store_id: int,
    biz_type: str,
    original_amount_yuan: Decimal | None = None,
    card_kind: str | None = None,
    membership_template_id: int | None = None,
    dish_id: int | None = None,
    retail_product_id: int | None = None,
) -> list[UserMemberCouponAvailableOut]:
    """小程序结算页：列出可用券（不含 locked/used）。"""
    checkout_map = {
        "member_card": CouponLockedOrderBiz.MEMBER_CARD,
        "single_meal": CouponLockedOrderBiz.SINGLE_MEAL,
        "store_retail": CouponLockedOrderBiz.STORE_RETAIL,
    }
    bt = (biz_type or "").strip()
    checkout_biz = checkout_map.get(bt)
    if not checkout_biz:
        raise HTTPException(status_code=400, detail="无效 biz_type")

    orig = Decimal(original_amount_yuan).quantize(Decimal("0.01")) if original_amount_yuan is not None else None
    ctx = _build_checkout_context(
        checkout_biz=checkout_biz,
        original_amount_yuan=orig or Decimal("0"),
        card_kind=card_kind,
        membership_template_id=membership_template_id,
        dish_id=dish_id,
        retail_product_id=retail_product_id,
    )

    rows = db.scalars(
        select(MemberCoupon)
        .where(
            MemberCoupon.member_id == int(member_id),
            MemberCoupon.store_id == int(store_id),
            MemberCoupon.status == MemberCouponStatus.AVAILABLE.value,
        )
        .order_by(MemberCoupon.id.desc())
    ).all()

    out: list[UserMemberCouponAvailableOut] = []
    changed = False
    for row in rows:
        if expire_member_coupon_if_needed(row):
            changed = True
            continue
        if orig is not None:
            min_need = Decimal(row.min_order_yuan or 0).quantize(Decimal("0.01"))
            if orig < min_need:
                continue
        if not _scope_matches(db, row, ctx, store_id=int(store_id)):
            continue
        tpl = db.get(MarketingCouponTemplate, int(row.template_id))
        out.append(
            UserMemberCouponAvailableOut(
                id=int(row.id),
                template_name=str(tpl.name) if tpl else None,
                discount_yuan=format_amount_yuan(Decimal(row.discount_yuan)),
                min_order_yuan=format_amount_yuan(Decimal(row.min_order_yuan or 0)),
                biz_type=str(row.biz_type),
                scope_level=str(row.scope_level),
                usage_instructions=(tpl.usage_instructions or "").strip() if tpl else None,
                expires_at=row.expires_at.isoformat() if row.expires_at else None,
            )
        )
    if changed:
        db.commit()
    out.sort(key=lambda x: Decimal(x.discount_yuan), reverse=True)
    return out


def list_member_card_coupons_for_reminder(
    db: Session,
    *,
    member_id: int,
    store_id: int,
) -> UserMemberCouponReminderOut:
    """进小程序提醒：列出购卡线可用券（不做 scope/门槛预筛）。"""
    rows = db.scalars(
        select(MemberCoupon)
        .where(
            MemberCoupon.member_id == int(member_id),
            MemberCoupon.store_id == int(store_id),
            MemberCoupon.status == MemberCouponStatus.AVAILABLE.value,
        )
        .order_by(MemberCoupon.id.desc())
    ).all()

    coupons: list[UserMemberCouponAvailableOut] = []
    changed = False
    max_disc = Decimal("0")
    for row in rows:
        if expire_member_coupon_if_needed(row):
            changed = True
            continue
        biz = (row.biz_type or "").strip()
        if biz not in MEMBER_COUPON_REMINDER_BIZ_TYPES:
            continue
        disc = Decimal(row.discount_yuan or 0).quantize(Decimal("0.01"))
        if disc > max_disc:
            max_disc = disc
        tpl = db.get(MarketingCouponTemplate, int(row.template_id))
        coupons.append(
            UserMemberCouponAvailableOut(
                id=int(row.id),
                template_name=str(tpl.name) if tpl else None,
                discount_yuan=format_amount_yuan(disc),
                min_order_yuan=format_amount_yuan(Decimal(row.min_order_yuan or 0)),
                biz_type=biz,
                scope_level=str(row.scope_level),
                usage_instructions=(tpl.usage_instructions or "").strip() if tpl else None,
                expires_at=row.expires_at.isoformat() if row.expires_at else None,
            )
        )
    if changed:
        db.commit()
    coupons.sort(key=lambda x: Decimal(x.discount_yuan), reverse=True)
    return UserMemberCouponReminderOut(
        count=len(coupons),
        max_discount_yuan=format_amount_yuan(max_disc),
        coupons=coupons,
    )
