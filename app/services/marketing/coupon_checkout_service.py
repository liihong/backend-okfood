"""优惠券结算：scope 校验、金额计算、锁券/释放/核销（购卡/单次零售/商城零售预留）。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.timeutil import beijing_now_naive
from app.models.enums import (
    CardOrderKind,
    CouponBizType,
    CouponLockedOrderBiz,
    CouponScopeLevel,
    MemberCouponStatus,
)
from app.models.member_coupon import MemberCoupon
from app.models.menu_dish import MenuDish
from app.models.membership_card_template import MembershipCardTemplate
from app.models.store_retail_product import StoreRetailProduct

_TWO = Decimal("0.01")
_MIN_PAY = Decimal("0.01")


@dataclass(frozen=True)
class CouponCheckoutContext:
    """下单前校验上下文。"""

    checkout_biz: CouponLockedOrderBiz
    original_amount_yuan: Decimal
    card_kind: str | None = None
    membership_template_id: int | None = None
    dish_id: int | None = None
    retail_product_id: int | None = None
    retail_category_id: int | None = None


def format_amount_yuan(v: Decimal) -> str:
    return f"{v.quantize(_TWO):.2f}"


def compute_coupon_payable(original: Decimal, discount: Decimal) -> tuple[Decimal, Decimal]:
    """返回 (实付, 实际抵扣)。"""
    orig = Decimal(original).quantize(_TWO)
    disc = min(Decimal(discount).quantize(_TWO), orig - _MIN_PAY)
    if disc < Decimal("0"):
        disc = Decimal("0")
    payable = (orig - disc).quantize(_TWO)
    if payable < _MIN_PAY:
        payable = _MIN_PAY
        disc = (orig - payable).quantize(_TWO)
    return payable, disc


def _coupon_biz_matches(coupon_biz: str, checkout_biz: CouponLockedOrderBiz) -> bool:
    cb = (coupon_biz or "").strip()
    if cb == CouponBizType.ALL.value:
        return True
    return cb == checkout_biz.value


def _scope_matches(db: Session, coupon: MemberCoupon, ctx: CouponCheckoutContext, *, store_id: int) -> bool:
    if not _coupon_biz_matches(coupon.biz_type, ctx.checkout_biz):
        return False
    level = (coupon.scope_level or CouponScopeLevel.ALL.value).strip()
    target = coupon.scope_target_id
    if level == CouponScopeLevel.ALL.value or (coupon.biz_type or "").strip() == CouponBizType.ALL.value:
        return True

    if ctx.checkout_biz == CouponLockedOrderBiz.MEMBER_CARD:
        if level == CouponScopeLevel.WEEK_MONTH.value:
            ck = (ctx.card_kind or "").strip()
            return ck in (CardOrderKind.WEEK.value, CardOrderKind.MONTH.value)
        if level == CouponScopeLevel.MEMBERSHIP_TEMPLATE.value:
            return target is not None and ctx.membership_template_id is not None and int(target) == int(
                ctx.membership_template_id
            )
        return False

    if ctx.checkout_biz == CouponLockedOrderBiz.SINGLE_MEAL:
        if level == CouponScopeLevel.MENU_DISH.value:
            return target is not None and ctx.dish_id is not None and int(target) == int(ctx.dish_id)
        return False

    if ctx.checkout_biz == CouponLockedOrderBiz.STORE_RETAIL:
        if level == CouponScopeLevel.RETAIL_PRODUCT.value:
            return target is not None and ctx.retail_product_id is not None and int(target) == int(
                ctx.retail_product_id
            )
        if level == CouponScopeLevel.RETAIL_CATEGORY.value:
            if target is None or ctx.retail_product_id is None:
                return False
            prod = db.get(StoreRetailProduct, int(ctx.retail_product_id))
            if not prod or int(prod.store_id) != int(store_id):
                return False
            cat_id = prod.category_id
            return cat_id is not None and int(target) == int(cat_id)
        return False

    return False


def coupon_is_expired(coupon: MemberCoupon, *, now: datetime | None = None) -> bool:
    ts = now or beijing_now_naive()
    exp = coupon.expires_at
    return exp is not None and ts >= exp


def assert_coupon_usable_for_checkout(
    db: Session,
    coupon: MemberCoupon,
    ctx: CouponCheckoutContext,
    *,
    member_id: int,
    store_id: int,
) -> None:
    if int(coupon.member_id) != int(member_id):
        raise HTTPException(status_code=403, detail="无权使用该优惠券")
    if int(coupon.store_id) != int(store_id):
        raise HTTPException(status_code=400, detail="优惠券不属于当前门店")
    st = (coupon.status or "").strip()
    if st == MemberCouponStatus.USED.value:
        raise HTTPException(status_code=400, detail="优惠券已使用")
    if st == MemberCouponStatus.REVOKED.value:
        raise HTTPException(status_code=400, detail="优惠券已作废")
    if st == MemberCouponStatus.EXPIRED.value or coupon_is_expired(coupon):
        raise HTTPException(status_code=400, detail="优惠券已过期")
    if st == MemberCouponStatus.LOCKED.value:
        raise HTTPException(status_code=400, detail="优惠券已绑定其他未支付订单")
    if st != MemberCouponStatus.AVAILABLE.value:
        raise HTTPException(status_code=400, detail="优惠券不可用")

    orig = Decimal(ctx.original_amount_yuan).quantize(_TWO)
    min_need = Decimal(coupon.min_order_yuan or 0).quantize(_TWO)
    if orig < min_need:
        raise HTTPException(status_code=400, detail=f"订单未满 {format_amount_yuan(min_need)} 元，不可使用该券")

    if not _scope_matches(db, coupon, ctx, store_id=int(store_id)):
        raise HTTPException(status_code=400, detail="优惠券不适用于当前商品")


def lock_member_coupon_for_order(
    db: Session,
    *,
    member_coupon_id: int,
    member_id: int,
    store_id: int,
    ctx: CouponCheckoutContext,
    order_id: int,
) -> tuple[Decimal, Decimal, Decimal]:
    """行锁券并绑定订单，返回 (original, discount, payable)。"""
    coupon = db.scalar(
        select(MemberCoupon)
        .where(MemberCoupon.id == int(member_coupon_id))
        .with_for_update()
    )
    if not coupon:
        raise HTTPException(status_code=404, detail="优惠券不存在")
    assert_coupon_usable_for_checkout(db, coupon, ctx, member_id=member_id, store_id=store_id)

    orig = Decimal(ctx.original_amount_yuan).quantize(_TWO)
    payable, disc = compute_coupon_payable(orig, Decimal(coupon.discount_yuan))

    coupon.status = MemberCouponStatus.LOCKED.value
    coupon.locked_order_biz = ctx.checkout_biz.value
    coupon.locked_order_id = int(order_id)
    db.flush()
    return orig, disc, payable


def release_member_coupon_for_order(
    db: Session,
    *,
    order_biz: CouponLockedOrderBiz | str,
    order_id: int,
) -> None:
    """删单/取消/超时：释放 locked 券。"""
    biz = order_biz.value if isinstance(order_biz, CouponLockedOrderBiz) else str(order_biz).strip()
    coupon = db.scalar(
        select(MemberCoupon)
        .where(
            MemberCoupon.locked_order_biz == biz,
            MemberCoupon.locked_order_id == int(order_id),
            MemberCoupon.status == MemberCouponStatus.LOCKED.value,
        )
        .with_for_update()
    )
    if not coupon:
        return
    coupon.status = MemberCouponStatus.AVAILABLE.value
    coupon.locked_order_biz = None
    coupon.locked_order_id = None


def mark_member_coupon_used_for_order(
    db: Session,
    *,
    order_biz: CouponLockedOrderBiz | str,
    order_id: int,
) -> None:
    """支付成功核销。"""
    biz = order_biz.value if isinstance(order_biz, CouponLockedOrderBiz) else str(order_biz).strip()
    coupon = db.scalar(
        select(MemberCoupon)
        .where(
            MemberCoupon.locked_order_biz == biz,
            MemberCoupon.locked_order_id == int(order_id),
        )
        .with_for_update()
    )
    if not coupon:
        return
    if (coupon.status or "").strip() == MemberCouponStatus.USED.value:
        return
    coupon.status = MemberCouponStatus.USED.value
    coupon.used_at = beijing_now_naive()
    coupon.locked_order_biz = None
    coupon.locked_order_id = None


def expire_member_coupon_if_needed(coupon: MemberCoupon, *, now: datetime | None = None) -> bool:
    """若已过期则标记 expired，返回是否刚过期。"""
    if (coupon.status or "").strip() != MemberCouponStatus.AVAILABLE.value:
        return False
    if not coupon_is_expired(coupon, now=now):
        return False
    coupon.status = MemberCouponStatus.EXPIRED.value
    return True


def compute_grant_expires_at(
    *,
    validity_mode: str,
    valid_from: datetime | None,
    valid_until: datetime | None,
    valid_days_after_grant: int | None,
    granted_at: datetime | None = None,
) -> datetime | None:
    """发放时计算用户券过期时间。"""
    mode = (validity_mode or "").strip()
    now = granted_at or beijing_now_naive()
    if mode == "fixed_range":
        return valid_until
    if mode == "days_after_grant":
        days = int(valid_days_after_grant or 0)
        if days < 1:
            return None
        return now + timedelta(days=days)
    return None


def validate_scope_target_belongs_store(
    db: Session,
    *,
    store_id: int,
    biz_type: str,
    scope_level: str,
    scope_target_id: int | None,
) -> None:
    """Admin 创建券种时校验 scope 目标归属。"""
    if scope_target_id is None:
        return
    bt = (biz_type or "").strip()
    lv = (scope_level or "").strip()
    tid = int(scope_target_id)
    if bt == CouponBizType.MEMBER_CARD.value and lv == CouponScopeLevel.MEMBERSHIP_TEMPLATE.value:
        tpl = db.get(MembershipCardTemplate, tid)
        if not tpl or int(tpl.store_id) != int(store_id):
            raise HTTPException(status_code=400, detail="卡包模板不存在或不属于当前门店")
        return
    if bt == CouponBizType.SINGLE_MEAL.value and lv == CouponScopeLevel.MENU_DISH.value:
        dish = db.get(MenuDish, tid)
        if not dish:
            raise HTTPException(status_code=400, detail="菜品不存在")
        return
    if bt == CouponBizType.STORE_RETAIL.value:
        if lv == CouponScopeLevel.RETAIL_PRODUCT.value:
            prod = db.get(StoreRetailProduct, tid)
            if not prod or int(prod.store_id) != int(store_id):
                raise HTTPException(status_code=400, detail="零售商品不存在或不属于当前门店")
            return
        if lv == CouponScopeLevel.RETAIL_CATEGORY.value:
            from app.models.store_retail_category import StoreRetailCategory

            cat = db.get(StoreRetailCategory, tid)
            if not cat or int(cat.store_id) != int(store_id):
                raise HTTPException(status_code=400, detail="零售类目不存在或不属于当前门店")
