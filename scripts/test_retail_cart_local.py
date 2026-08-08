#!/usr/bin/env python3
"""商城购物车改造：本地自测脚本（不依赖 pytest）。"""

from __future__ import annotations

from decimal import Decimal

from app.services.marketing.coupon_checkout_service import CouponCheckoutContext, RetailCheckoutLine
from app.services.retail.retail_order_item_repo import build_order_items_summary
from app.models.enums import CouponLockedOrderBiz


def test_build_summary():
    s = build_order_items_summary([("苹果汁", 2), ("蛋白棒", 1)])
    assert "等3件" in s
    print("build_order_items_summary ok:", s)


def test_coupon_context_lines():
    ctx = CouponCheckoutContext(
        checkout_biz=CouponLockedOrderBiz.STORE_RETAIL,
        original_amount_yuan=Decimal("100.00"),
        retail_lines=(
            RetailCheckoutLine(1, 10, Decimal("60.00")),
            RetailCheckoutLine(2, 10, Decimal("40.00")),
        ),
    )
    assert ctx.retail_lines and len(ctx.retail_lines) == 2
    print("coupon context lines ok")


if __name__ == "__main__":
    test_build_summary()
    test_coupon_context_lines()
    print("ALL OK")
