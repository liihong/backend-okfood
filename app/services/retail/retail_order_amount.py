"""商城零售：商品可售校验与行金额计算。"""

from __future__ import annotations

from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.store_retail_category import StoreRetailCategory
from app.models.store_retail_product import StoreRetailProduct
from app.models.store_retail_spu import StoreRetailSpu
def assert_retail_product_orderable(
    db: Session, *, product: StoreRetailProduct, store_id: int, spu: StoreRetailSpu | None = None
) -> StoreRetailSpu:
    """校验 SKU + SPU 可售；返回 SPU 行供快照使用。"""
    if int(product.store_id) != int(store_id):
        raise HTTPException(status_code=404, detail="商品不存在或已下架")
    if not bool(product.is_on_shelf):
        raise HTTPException(status_code=400, detail="该规格已下架")

    row = spu if spu is not None else db.get(StoreRetailSpu, int(product.spu_id))
    if not row or int(row.store_id) != int(store_id):
        raise HTTPException(status_code=404, detail="商品不存在或已下架")
    if not bool(row.is_on_shelf):
        raise HTTPException(status_code=400, detail="商品已下架")
    if row.category_id is not None:
        cat = db.get(StoreRetailCategory, int(row.category_id))
        if not cat or not bool(cat.is_active) or int(cat.store_id) != int(store_id):
            raise HTTPException(status_code=400, detail="商品分类已停用")
    return row


def compute_retail_line_amount(
    db: Session, *, unit_price: Decimal, quantity: int, store_pickup: bool, store_id: int
) -> Decimal:
    """行商品金额：SKU 单价 × 数量。配送费在订单头按整单另计，与各行无关。

    store_pickup / store_id 保留入参以兼容既有调用方，不参与计算。
    """
    _ = db
    _ = store_pickup
    _ = store_id
    unit_dec = Decimal(unit_price).quantize(Decimal("0.01"))
    return (unit_dec * Decimal(int(quantity))).quantize(Decimal("0.01"))
