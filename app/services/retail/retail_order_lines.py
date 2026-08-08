"""商城零售：购物车下单行校验与合并。"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.store_retail_product import StoreRetailProduct
from app.models.store_retail_spu import StoreRetailSpu
from app.schemas.store_retail_order import StoreRetailOrderItemIn
from app.services.retail.retail_catalog_repo import load_spus_by_ids
from app.services.retail.retail_display import retail_sku_display_title
from app.services.retail.retail_order_amount import assert_retail_product_orderable, compute_retail_line_amount
from app.services.retail.retail_stock_service import assert_retail_stock_available

MAX_CART_SKUS = 20
MAX_LINE_QTY = 50


@dataclass(frozen=True)
class ResolvedRetailLine:
    """校验通过后的下单行。"""

    product: StoreRetailProduct
    spu: StoreRetailSpu
    display_title: str
    quantity: int
    unit_price_yuan: Decimal
    line_amount_yuan: Decimal


def merge_retail_order_items(raw_items: list[StoreRetailOrderItemIn]) -> list[StoreRetailOrderItemIn]:
    """同 SKU 合并数量。"""
    merged: dict[int, int] = {}
    for it in raw_items:
        pid = int(it.retail_product_id)
        merged[pid] = merged.get(pid, 0) + int(it.quantity)
    return [
        StoreRetailOrderItemIn(retail_product_id=pid, quantity=qty)
        for pid, qty in sorted(merged.items(), key=lambda x: x[0])
    ]


def _lock_retail_products(db: Session, product_ids: list[int]) -> dict[int, StoreRetailProduct]:
    """按 id 顺序加行锁，防止并发下单超卖。"""
    ids = sorted({int(x) for x in product_ids if int(x) > 0})
    if not ids:
        return {}
    rows = db.scalars(
        select(StoreRetailProduct)
        .where(StoreRetailProduct.id.in_(ids))
        .order_by(StoreRetailProduct.id)
        .with_for_update()
    ).all()
    return {int(r.id): r for r in rows}


def resolve_retail_order_lines(
    db: Session,
    *,
    items: list[StoreRetailOrderItemIn],
    store_id: int,
    store_pickup: bool,
) -> list[ResolvedRetailLine]:
    """校验商品、库存、金额，返回可落库明细。"""
    if not items:
        raise HTTPException(status_code=400, detail="购物车为空")
    merged = merge_retail_order_items(items)
    if len(merged) > MAX_CART_SKUS:
        raise HTTPException(status_code=400, detail=f"单次最多购买 {MAX_CART_SKUS} 种商品")

    locked_products = _lock_retail_products(db, [int(it.retail_product_id) for it in merged])
    spu_map = load_spus_by_ids(db, [int(p.spu_id) for p in locked_products.values()])

    resolved: list[ResolvedRetailLine] = []
    for it in merged:
        qty = int(it.quantity)
        if qty < 1 or qty > MAX_LINE_QTY:
            raise HTTPException(status_code=400, detail=f"每种商品数量须在 1～{MAX_LINE_QTY} 之间")
        prod = locked_products.get(int(it.retail_product_id))
        if not prod:
            raise HTTPException(status_code=404, detail="商品不存在或已下架")
        spu = spu_map.get(int(prod.spu_id))
        spu = assert_retail_product_orderable(db, product=prod, store_id=int(store_id), spu=spu)
        assert_retail_stock_available(db, product_id=int(prod.id), need_qty=qty)
        unit = Decimal(prod.unit_price_yuan).quantize(Decimal("0.01"))
        line_amt = compute_retail_line_amount(
            db,
            unit_price=unit,
            quantity=qty,
            store_pickup=bool(store_pickup),
            store_id=int(store_id),
        )
        display = retail_sku_display_title(spu_title=spu.title, spec_label=prod.spec_label)
        resolved.append(
            ResolvedRetailLine(
                product=prod,
                spu=spu,
                display_title=display,
                quantity=qty,
                unit_price_yuan=unit,
                line_amount_yuan=line_amt,
            )
        )
    return resolved


def goods_subtotal_yuan(lines: list[ResolvedRetailLine]) -> Decimal:
    total = Decimal("0")
    for ln in lines:
        total += Decimal(ln.line_amount_yuan)
    return total.quantize(Decimal("0.01"))
