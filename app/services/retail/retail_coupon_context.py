"""商城零售：多商品优惠券结算上下文。"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.enums import CouponLockedOrderBiz, CouponScopeLevel
from app.models.member_coupon import MemberCoupon
from app.services.marketing.coupon_checkout_service import CouponCheckoutContext
from app.services.retail.retail_order_lines import ResolvedRetailLine


@dataclass(frozen=True)
class RetailCheckoutLine:
    retail_product_id: int
    retail_category_id: int | None
    line_amount_yuan: Decimal


def retail_lines_from_resolved(lines: list[ResolvedRetailLine]) -> tuple[RetailCheckoutLine, ...]:
    return tuple(
        RetailCheckoutLine(
            retail_product_id=int(ln.product.id),
            retail_category_id=int(ln.spu.category_id) if ln.spu.category_id is not None else None,
            line_amount_yuan=Decimal(ln.line_amount_yuan).quantize(Decimal("0.01")),
        )
        for ln in lines
    )


def build_store_retail_coupon_context(
    *,
    goods_subtotal: Decimal,
    lines: list[ResolvedRetailLine],
) -> CouponCheckoutContext:
    """构建商城多商品券校验上下文。"""
    retail_lines = retail_lines_from_resolved(lines)
    first = lines[0] if lines else None
    return CouponCheckoutContext(
        checkout_biz=CouponLockedOrderBiz.STORE_RETAIL,
        original_amount_yuan=Decimal(goods_subtotal).quantize(Decimal("0.01")),
        retail_product_id=int(first.product.id) if first else None,
        retail_category_id=int(first.spu.category_id)
        if first and first.spu.category_id is not None
        else None,
        retail_lines=retail_lines,
    )


def retail_coupon_eligible_subtotal(
    db: Session,
    coupon: MemberCoupon,
    ctx: CouponCheckoutContext,
    *,
    store_id: int,
) -> Decimal | None:
    """
    计算券可抵扣的商品小计基数。
    返回 None 表示不适用；返回 Decimal 表示可用（可为 0）。
    """
    from app.services.marketing.coupon_checkout_service import _coupon_biz_matches

    if not _coupon_biz_matches(coupon.biz_type, ctx.checkout_biz):
        return None
    level = (coupon.scope_level or CouponScopeLevel.ALL.value).strip()
    lines = ctx.retail_lines or ()
    if not lines and ctx.retail_product_id is not None:
        lines = (
            RetailCheckoutLine(
                retail_product_id=int(ctx.retail_product_id),
                retail_category_id=ctx.retail_category_id,
                line_amount_yuan=Decimal(ctx.original_amount_yuan).quantize(Decimal("0.01")),
            ),
        )

    if level == CouponScopeLevel.ALL.value or (coupon.biz_type or "").strip() == "all":
        return Decimal(ctx.original_amount_yuan).quantize(Decimal("0.01"))

    target = coupon.scope_target_id
    if level == CouponScopeLevel.RETAIL_PRODUCT.value:
        if target is None:
            return None
        eligible = Decimal("0")
        matched = False
        for ln in lines:
            if int(ln.retail_product_id) == int(target):
                matched = True
                eligible += Decimal(ln.line_amount_yuan)
        return eligible.quantize(Decimal("0.01")) if matched else None

    if level == CouponScopeLevel.RETAIL_CATEGORY.value:
        if target is None:
            return None
        eligible = Decimal("0")
        matched = False
        for ln in lines:
            if ln.retail_category_id is not None and int(ln.retail_category_id) == int(target):
                matched = True
                eligible += Decimal(ln.line_amount_yuan)
        return eligible.quantize(Decimal("0.01")) if matched else None

    _ = db
    _ = store_id
    return None
