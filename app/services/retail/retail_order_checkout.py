"""商城零售：结算试算（商品小计 + 配送费 + 券），与落库共用逻辑。"""

from __future__ import annotations

from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.member_coupon import MemberCoupon
from app.schemas.store_retail_order import StoreRetailOrderCreateIn
from app.services.marketing.coupon_checkout_service import (
    _MIN_PAY,
    assert_coupon_usable_for_checkout,
    compute_coupon_payable,
    _retail_coupon_threshold_yuan,
)
from app.services.retail.retail_coupon_context import build_store_retail_coupon_context
from app.services.retail.retail_delivery_fee import (
    compute_retail_delivery_fee,
    strikethrough_delivery_fee_yuan,
)
from app.services.retail.retail_order_lines import goods_subtotal_yuan, resolve_retail_order_lines

_TWO = Decimal("0.01")


def _format_money(v: Decimal) -> str:
    return f"{v.quantize(_TWO):.2f}"


def resolve_retail_checkout_amounts(
    db: Session,
    *,
    store_id: int,
    member_id: int | None,
    body: StoreRetailOrderCreateIn,
) -> dict:
    """解析商品行、配送费、券抵扣与应付（不锁券、不写库）。"""
    lines = resolve_retail_order_lines(
        db,
        items=body.items,
        store_id=int(store_id),
        store_pickup=bool(body.store_pickup),
    )
    goods = goods_subtotal_yuan(lines)
    delivery_fee, breakdown = compute_retail_delivery_fee(
        db, lines=lines, store_pickup=bool(body.store_pickup), store_id=int(store_id)
    )
    coupon_discount = Decimal("0.00")
    goods_after_coupon = goods

    if body.member_coupon_id is not None:
        if member_id is None:
            raise HTTPException(status_code=401, detail="须登录后使用优惠券")
        coupon = db.get(MemberCoupon, int(body.member_coupon_id))
        if not coupon:
            raise HTTPException(status_code=404, detail="优惠券不存在")
        ctx = build_store_retail_coupon_context(goods_subtotal=goods, lines=lines)
        assert_coupon_usable_for_checkout(
            db, coupon, ctx, member_id=int(member_id), store_id=int(store_id)
        )
        orig = Decimal(ctx.original_amount_yuan).quantize(_TWO)
        threshold = _retail_coupon_threshold_yuan(db, coupon, ctx, store_id=int(store_id))
        discount_base = threshold if threshold >= Decimal("0") else orig
        _, disc = compute_coupon_payable(discount_base, Decimal(coupon.discount_yuan))
        goods_after_coupon = (orig - disc).quantize(_TWO)
        if goods_after_coupon < _MIN_PAY:
            goods_after_coupon = _MIN_PAY
            disc = (orig - goods_after_coupon).quantize(_TWO)
        coupon_discount = disc

    payable = (goods_after_coupon + delivery_fee).quantize(_TWO)
    strike = strikethrough_delivery_fee_yuan(breakdown)
    return {
        "goods_amount_yuan": _format_money(goods),
        "delivery_fee_yuan": _format_money(delivery_fee),
        "delivery_fee_strikethrough_yuan": _format_money(strike) if strike > 0 else None,
        "coupon_discount_yuan": _format_money(coupon_discount) if coupon_discount > 0 else None,
        "payable_yuan": _format_money(payable),
        "delivery_breakdown": [b.to_dict() for b in breakdown],
        "_lines": lines,
        "_goods_dec": goods,
        "_delivery_dec": delivery_fee,
        "_payable_dec": payable,
    }