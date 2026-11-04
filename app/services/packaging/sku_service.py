"""包装品类档案。

负责建档、停用、指定唯一打包袋和导入常用品。
不改结存。有流水的品只停用，避免把历史流水挂空。
"""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.packaging_dish_line import PackagingDishLine
from app.models.packaging_sku import PackagingSku
from app.models.packaging_slot_line import PackagingSlotLine
from app.models.packaging_standard_line import PackagingStandardLine
from app.models.packaging_stock import PackagingStock
from app.models.packaging_stock_txn import PackagingStockTxn
from app.services.packaging.catalog_seed import DEFAULT_PACKAGING_SKUS
from app.services.packaging.constants import BAG_FLAG


def list_skus(db: Session, *, store_id: int) -> list[PackagingSku]:
    rows = db.scalars(
        select(PackagingSku)
        .where(PackagingSku.store_id == int(store_id))
        .order_by(PackagingSku.id.asc())
    ).all()
    return list(rows)


def create_sku(
    db: Session,
    *,
    store_id: int,
    name: str,
    usage_note: str | None,
    supplier_name: str | None,
    unit: str,
    safety_stock: int | None,
    is_meal_bag: bool,
) -> PackagingSku:
    cleaned = _clean_name(name)
    _ensure_name_free(db, store_id=store_id, name=cleaned, exclude_id=None)
    row = PackagingSku(
        store_id=int(store_id),
        name=cleaned,
        usage_note=_blank_to_none(usage_note),
        supplier_name=_blank_to_none(supplier_name),
        unit=_clean_unit(unit),
        safety_stock=safety_stock,
        bag_flag=None,
        is_active=True,
    )
    db.add(row)
    db.flush()
    if is_meal_bag:
        _mark_only_bag(db, store_id=store_id, sku=row)
    db.commit()
    db.refresh(row)
    return row


def patch_sku(
    db: Session,
    sku_id: int,
    *,
    store_id: int,
    name: str | None = None,
    usage_note: str | None = None,
    supplier_name: str | None = None,
    unit: str | None = None,
    safety_stock: int | None = None,
    safety_stock_set: bool = False,
    is_active: bool | None = None,
    is_meal_bag: bool | None = None,
) -> PackagingSku:
    row = _require_sku(db, sku_id, store_id=store_id)
    if name is not None:
        cleaned = _clean_name(name)
        _ensure_name_free(db, store_id=store_id, name=cleaned, exclude_id=row.id)
        row.name = cleaned
    if usage_note is not None:
        row.usage_note = _blank_to_none(usage_note)
    if supplier_name is not None:
        row.supplier_name = _blank_to_none(supplier_name)
    if unit is not None:
        row.unit = _clean_unit(unit)
    if safety_stock_set:
        row.safety_stock = safety_stock
    if is_active is not None:
        row.is_active = bool(is_active)
    if is_meal_bag is True:
        _mark_only_bag(db, store_id=store_id, sku=row)
    elif is_meal_bag is False and row.bag_flag == BAG_FLAG:
        row.bag_flag = None
    db.commit()
    db.refresh(row)
    return row


def delete_sku(db: Session, sku_id: int, *, store_id: int) -> None:
    """没有流水、也没被配方引用时才物理删除。否则只能停用。"""
    row = _require_sku(db, sku_id, store_id=store_id)
    txn_count = db.scalar(
        select(func.count()).select_from(PackagingStockTxn).where(PackagingStockTxn.sku_id == row.id)
    )
    if int(txn_count or 0) > 0:
        raise HTTPException(status_code=400, detail="已有库存流水，请停用而不是删除")
    used = _sku_is_referenced(db, row.id)
    if used:
        raise HTTPException(status_code=400, detail="仍被用盒或标配引用，请先去掉引用或停用")
    stock = db.get(PackagingStock, row.id)
    if stock is not None:
        db.delete(stock)
    db.delete(row)
    db.commit()


def import_default_skus(db: Session, *, store_id: int) -> int:
    """按名称补齐常用品。已存在的不覆盖供应商和最低库存。"""
    existing = {
        row.name: row
        for row in db.scalars(select(PackagingSku).where(PackagingSku.store_id == int(store_id))).all()
    }
    created = 0
    bag_row: PackagingSku | None = None
    for item in DEFAULT_PACKAGING_SKUS:
        row = existing.get(item.name)
        if row is None:
            row = PackagingSku(
                store_id=int(store_id),
                name=item.name,
                usage_note=item.usage_note or None,
                supplier_name=item.supplier_name or None,
                unit=item.unit,
                safety_stock=None,
                bag_flag=None,
                is_active=True,
            )
            db.add(row)
            db.flush()
            existing[item.name] = row
            created += 1
        if item.is_meal_bag:
            bag_row = row
    if bag_row is not None and bag_row.bag_flag != BAG_FLAG:
        _mark_only_bag(db, store_id=store_id, sku=bag_row)
    db.commit()
    return created


def sku_to_dict(row: PackagingSku, *, qty: int | None, initialized: bool) -> dict:
    return {
        "id": int(row.id),
        "name": row.name,
        "usage_note": row.usage_note or "",
        "supplier_name": row.supplier_name or "",
        "unit": row.unit,
        "safety_stock": row.safety_stock,
        "is_meal_bag": row.bag_flag == BAG_FLAG,
        "is_active": bool(row.is_active),
        "qty": qty,
        "initialized": initialized,
    }


def _mark_only_bag(db: Session, *, store_id: int, sku: PackagingSku) -> None:
    """先清掉原打包袋标记再写入，保证唯一约束不会在同一门店撞上两行 1。"""
    others = db.scalars(
        select(PackagingSku).where(
            PackagingSku.store_id == int(store_id),
            PackagingSku.bag_flag == BAG_FLAG,
            PackagingSku.id != sku.id,
        )
    ).all()
    for other in others:
        other.bag_flag = None
    db.flush()
    sku.bag_flag = BAG_FLAG


def _require_sku(db: Session, sku_id: int, *, store_id: int) -> PackagingSku:
    row = db.get(PackagingSku, int(sku_id))
    if row is None or int(row.store_id) != int(store_id):
        raise HTTPException(status_code=404, detail="耗材不存在")
    return row


def _ensure_name_free(db: Session, *, store_id: int, name: str, exclude_id: int | None) -> None:
    query = select(PackagingSku.id).where(
        PackagingSku.store_id == int(store_id),
        PackagingSku.name == name,
    )
    if exclude_id is not None:
        query = query.where(PackagingSku.id != int(exclude_id))
    if db.scalar(query) is not None:
        raise HTTPException(status_code=409, detail="同名耗材已存在")


def _sku_is_referenced(db: Session, sku_id: int) -> bool:
    for model in (PackagingDishLine, PackagingSlotLine, PackagingStandardLine):
        found = db.scalar(select(model.id).where(model.sku_id == int(sku_id)).limit(1))
        if found is not None:
            return True
    return False


def _clean_name(name: str) -> str:
    cleaned = (name or "").strip()
    if not cleaned:
        raise HTTPException(status_code=400, detail="请填写耗材名称")
    if len(cleaned) > 64:
        raise HTTPException(status_code=400, detail="耗材名称过长")
    return cleaned


def _clean_unit(unit: str) -> str:
    cleaned = (unit or "").strip() or "个"
    if len(cleaned) > 16:
        raise HTTPException(status_code=400, detail="单位过长")
    return cleaned


def _blank_to_none(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None
