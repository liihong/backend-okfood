"""回填商城门店自提订单行金额：去掉误按 SKU 扣减的基础配送费。"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.store_retail_order import StoreRetailOrder
from app.models.store_retail_order_item import StoreRetailOrderItem
from app.services.marketing.coupon_checkout_service import compute_coupon_payable

logger = logging.getLogger(__name__)

_TWO = Decimal("0.01")


@dataclass(frozen=True)
class StoreRetailPickupLineBackfillReport:
    """回填摘要。"""

    orders_scanned: int
    orders_updated: int
    items_updated: int
    dry_run: bool


def _line_should_be(unit_price: Decimal, quantity: int) -> Decimal:
    unit = Decimal(unit_price).quantize(_TWO)
    qty = max(1, int(quantity))
    return (unit * Decimal(qty)).quantize(_TWO)


def _item_needs_fixup(row: StoreRetailOrderItem) -> Decimal | None:
    """行金额低于单价×数量时视为旧算法误扣配送费，返回正确小计。"""
    expected = _line_should_be(Decimal(row.unit_price_yuan), int(row.quantity))
    actual = Decimal(row.line_amount_yuan).quantize(_TWO)
    if actual >= expected:
        return None
    return expected


def backfill_store_retail_pickup_line_amounts(
    db: Session,
    *,
    dry_run: bool = False,
) -> StoreRetailPickupLineBackfillReport:
    """
    仅处理 store_pickup=true 的商城订单：
    - 明细行 line_amount_yuan 纠正为 unit_price_yuan × quantity
    - 订单头 goods_amount_yuan、amount_yuan 等按新商品小计同步（自提配送费恒为 0）
    """
    order_rows = db.scalars(
        select(StoreRetailOrder)
        .where(StoreRetailOrder.store_pickup.is_(True))
        .order_by(StoreRetailOrder.id.asc())
    ).all()
    order_ids = [int(o.id) for o in order_rows]
    if not order_ids:
        return StoreRetailPickupLineBackfillReport(
            orders_scanned=0,
            orders_updated=0,
            items_updated=0,
            dry_run=bool(dry_run),
        )

    items_by_order: dict[int, list[StoreRetailOrderItem]] = {}
    item_rows = db.scalars(
        select(StoreRetailOrderItem)
        .where(StoreRetailOrderItem.order_id.in_(order_ids))
        .order_by(StoreRetailOrderItem.order_id.asc(), StoreRetailOrderItem.id.asc())
    ).all()
    for it in item_rows:
        items_by_order.setdefault(int(it.order_id), []).append(it)

    orders_updated = 0
    items_updated = 0

    for order in order_rows:
        oid = int(order.id)
        lines = items_by_order.get(oid) or []
        if not lines:
            continue

        order_item_changes = 0
        for it in lines:
            fixed = _item_needs_fixup(it)
            if fixed is None:
                continue
            if not dry_run:
                it.line_amount_yuan = fixed
            items_updated += 1
            order_item_changes += 1

        if order_item_changes == 0:
            continue

        new_goods = sum(
            (
                _item_needs_fixup(it)
                if _item_needs_fixup(it) is not None
                else Decimal(it.line_amount_yuan).quantize(_TWO)
            )
            for it in lines
        , Decimal("0")).quantize(_TWO)

        if not dry_run:
            order.goods_amount_yuan = new_goods
            order.delivery_fee_yuan = Decimal("0.00")
            pay_status = str(order.pay_status or "").strip()
            already_paid = pay_status in ("已支付", "已缴")
            if already_paid:
                # 已收款订单：实付不变，仅纠正商品标价与小计（财务按实付在行上比例分摊）
                if order.member_coupon_id is not None:
                    order.original_amount_yuan = new_goods
            elif order.member_coupon_id is not None:
                raw_disc = Decimal(order.coupon_discount_yuan or 0).quantize(_TWO)
                payable, actual_disc = compute_coupon_payable(new_goods, raw_disc)
                order.original_amount_yuan = new_goods
                order.coupon_discount_yuan = actual_disc
                order.amount_yuan = payable
            else:
                order.original_amount_yuan = None
                order.coupon_discount_yuan = None
                order.amount_yuan = new_goods
            db.add(order)

        orders_updated += 1
        logger.info(
            "商城自提行金额回填 order_id=%s items=%s goods=%s dry_run=%s",
            oid,
            order_item_changes,
            new_goods,
            dry_run,
        )

    if not dry_run and (orders_updated or items_updated):
        db.commit()

    return StoreRetailPickupLineBackfillReport(
        orders_scanned=len(order_rows),
        orders_updated=orders_updated,
        items_updated=items_updated,
        dry_run=bool(dry_run),
    )