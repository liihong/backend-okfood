"""商城零售：创建订单（含多行明细）。"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.store_retail_order import StoreRetailOrder
from app.models.store_retail_order_item import StoreRetailOrderItem
from app.schemas.store_retail_order import StoreRetailOrderCreateIn
from app.services.marketing.coupon_checkout_service import lock_member_coupon_for_order
from app.services.retail.retail_coupon_context import build_store_retail_coupon_context
from app.services.retail.retail_order_item_repo import build_order_items_summary
from app.services.retail.retail_order_lines import goods_subtotal_yuan, resolve_retail_order_lines


def persist_retail_order_with_items(
    db: Session,
    *,
    tenant_id: int,
    store_id: int,
    member_id: int,
    body: StoreRetailOrderCreateIn,
    out_trade_no_temp: str,
    fulfillment_date,
    routing_area: str,
    member_address_id: int | None,
    pay_status: str = "未支付",
    pay_channel: str | None = None,
    fulfillment_status: str = "pending",
    remark: str | None = None,
) -> StoreRetailOrder:
    """写入订单头 + 明细行，可选锁券。"""
    lines = resolve_retail_order_lines(
        db,
        items=body.items,
        store_id=int(store_id),
        store_pickup=bool(body.store_pickup),
    )
    goods_total = goods_subtotal_yuan(lines)
    title_qty = [(ln.display_title, int(ln.quantity)) for ln in lines]
    summary_title = build_order_items_summary(title_qty)
    total_qty = sum(int(ln.quantity) for ln in lines)
    first_prod = lines[0].product

    row = StoreRetailOrder(
        tenant_id=int(tenant_id),
        store_id=int(store_id),
        out_trade_no=out_trade_no_temp,
        member_id=int(member_id),
        retail_product_id=int(first_prod.id),
        product_title=summary_title,
        member_address_id=member_address_id,
        store_pickup=bool(body.store_pickup),
        quantity=int(total_qty),
        fulfillment_date=fulfillment_date,
        routing_area=routing_area,
        amount_yuan=goods_total,
        pay_status=pay_status,
        pay_channel=pay_channel,
        fulfillment_status=fulfillment_status,
        courier_id=None,
        remark=(remark or "")[:500] if remark else None,
    )
    db.add(row)
    db.flush()

    for idx, ln in enumerate(lines):
        spu = ln.spu
        db.add(
            StoreRetailOrderItem(
                order_id=int(row.id),
                retail_product_id=int(ln.product.id),
                spu_id=int(spu.id),
                category_id=int(spu.category_id) if spu.category_id is not None else None,
                product_title=ln.display_title,
                spu_title=spu.title,
                spec_label=ln.product.spec_label,
                unit_price_yuan=ln.unit_price_yuan,
                quantity=int(ln.quantity),
                line_amount_yuan=ln.line_amount_yuan,
                sort_order=int(idx),
            )
        )

    if body.member_coupon_id is not None:
        ctx = build_store_retail_coupon_context(goods_subtotal=goods_total, lines=lines)
        orig, disc, payable = lock_member_coupon_for_order(
            db,
            member_coupon_id=int(body.member_coupon_id),
            member_id=int(member_id),
            store_id=int(store_id),
            ctx=ctx,
            order_id=int(row.id),
        )
        row.original_amount_yuan = orig
        row.coupon_discount_yuan = disc
        row.amount_yuan = payable
        row.member_coupon_id = int(body.member_coupon_id)

    return row
