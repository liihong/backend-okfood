"""商城零售：订单明细读写与摘要。"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.store_retail_order_item import StoreRetailOrderItem
from app.schemas.store_retail_order import StoreRetailOrderItemOut


def format_amount_yuan(v: Decimal) -> str:
    return f"{v.quantize(Decimal('0.01')):.2f}"


def build_order_items_summary(title_qty_pairs: list[tuple[str, int]]) -> str:
    """生成订单头摘要，如「冷萃果蔬汁 ×2 等3件」。"""
    if not title_qty_pairs:
        return "商品"
    first_title, first_qty = title_qty_pairs[0]
    first = (first_title or "商品").strip() or "商品"
    total_lines = len(title_qty_pairs)
    total_qty = sum(int(q) for _, q in title_qty_pairs)
    if total_lines == 1:
        return f"{first} ×{int(first_qty)}" if int(first_qty) > 1 else first
    return f"{first} ×{int(first_qty)} 等{total_qty}件"


def item_row_to_out(row: StoreRetailOrderItem) -> StoreRetailOrderItemOut:
    return StoreRetailOrderItemOut(
        id=int(row.id),
        retail_product_id=int(row.retail_product_id),
        spu_id=int(row.spu_id) if row.spu_id is not None else None,
        product_title=str(row.product_title or ""),
        spu_title=str(row.spu_title) if row.spu_title else None,
        spec_label=str(row.spec_label) if row.spec_label else None,
        unit_price_yuan=format_amount_yuan(Decimal(row.unit_price_yuan)),
        quantity=int(row.quantity or 1),
        line_amount_yuan=format_amount_yuan(Decimal(row.line_amount_yuan)),
        category_id=int(row.category_id) if row.category_id is not None else None,
    )


def load_order_items_map(db: Session, order_ids: list[int]) -> dict[int, list[StoreRetailOrderItem]]:
    ids = [int(x) for x in order_ids if int(x) > 0]
    if not ids:
        return {}
    rows = db.scalars(
        select(StoreRetailOrderItem)
        .where(StoreRetailOrderItem.order_id.in_(ids))
        .order_by(StoreRetailOrderItem.sort_order.asc(), StoreRetailOrderItem.id.asc())
    ).all()
    out: dict[int, list[StoreRetailOrderItem]] = {}
    for r in rows:
        out.setdefault(int(r.order_id), []).append(r)
    return out


def load_order_items_out(db: Session, order_id: int) -> list[StoreRetailOrderItemOut]:
    rows = load_order_items_map(db, [int(order_id)]).get(int(order_id), [])
    return [item_row_to_out(r) for r in rows]
