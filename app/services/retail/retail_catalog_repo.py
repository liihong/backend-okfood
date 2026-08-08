"""商城零售：SPU/SKU 仓储查询（不含业务 CRUD）。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.store_retail_product import StoreRetailProduct
from app.models.store_retail_spu import StoreRetailSpu


def load_spus_by_ids(db: Session, spu_ids: list[int]) -> dict[int, StoreRetailSpu]:
    """批量加载 SPU。"""
    ids = sorted({int(x) for x in spu_ids if int(x) > 0})
    if not ids:
        return {}
    rows = db.scalars(select(StoreRetailSpu).where(StoreRetailSpu.id.in_(ids))).all()
    return {int(r.id): r for r in rows}


def load_skus_by_spu_ids(
    db: Session, *, store_id: int, spu_ids: list[int], shelf_only: bool = False
) -> dict[int, list[StoreRetailProduct]]:
    """按 SPU 分组 SKU。"""
    ids = sorted({int(x) for x in spu_ids if int(x) > 0})
    if not ids:
        return {}
    q = (
        select(StoreRetailProduct)
        .where(
            StoreRetailProduct.store_id == int(store_id),
            StoreRetailProduct.spu_id.in_(ids),
        )
        .order_by(StoreRetailProduct.sort_order.asc(), StoreRetailProduct.id.asc())
    )
    if shelf_only:
        q = q.where(StoreRetailProduct.is_on_shelf.is_(True))
    rows = db.scalars(q).all()
    out: dict[int, list[StoreRetailProduct]] = {}
    for r in rows:
        out.setdefault(int(r.spu_id), []).append(r)
    return out


def load_skus_by_ids(db: Session, sku_ids: list[int]) -> dict[int, StoreRetailProduct]:
    """批量加载 SKU。"""
    ids = sorted({int(x) for x in sku_ids if int(x) > 0})
    if not ids:
        return {}
    rows = db.scalars(select(StoreRetailProduct).where(StoreRetailProduct.id.in_(ids))).all()
    return {int(r.id): r for r in rows}


def get_spu_row(db: Session, *, spu_id: int, store_id: int) -> StoreRetailSpu | None:
    row = db.get(StoreRetailSpu, int(spu_id))
    if not row or int(row.store_id) != int(store_id):
        return None
    return row


def get_sku_row(db: Session, *, sku_id: int, store_id: int) -> StoreRetailProduct | None:
    row = db.get(StoreRetailProduct, int(sku_id))
    if not row or int(row.store_id) != int(store_id):
        return None
    return row
