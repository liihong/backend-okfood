"""后台：门店普通商品分类 CRUD。"""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.store import Store
from app.models.store_retail_category import StoreRetailCategory
from app.models.store_retail_spu import StoreRetailSpu
from app.schemas.catalog_admin import StoreRetailCategoryCreateIn, StoreRetailCategoryPatchIn


def _is_mysql_dup(e: Exception) -> bool:
    s = str(e).lower()
    return "duplicate" in s or "1062" in s


def assert_retail_category_belongs_store(db: Session, *, category_id: int, store_id: int) -> StoreRetailCategory:
    c = db.get(StoreRetailCategory, category_id)
    if not c or int(c.store_id) != store_id:
        raise HTTPException(status_code=404, detail="零售分类不存在或所属门店不匹配")
    return c


def list_retail_categories(db: Session, *, store_id: int, active_only: bool = False) -> list[StoreRetailCategory]:
    q = select(StoreRetailCategory).where(StoreRetailCategory.store_id == int(store_id)).order_by(
        StoreRetailCategory.sort_order.asc(), StoreRetailCategory.id.asc()
    )
    if active_only:
        q = q.where(StoreRetailCategory.is_active.is_(True))
    return list(db.scalars(q).all())


def create_retail_category(
    db: Session, *, store_id: int, body: StoreRetailCategoryCreateIn
) -> StoreRetailCategory:
    st = db.get(Store, store_id)
    if not st or not st.is_active:
        raise HTTPException(status_code=404, detail="门店不存在或已停用")
    row = StoreRetailCategory(
        store_id=int(store_id),
        name=body.name.strip(),
        sort_order=int(body.sort_order),
        is_active=bool(body.is_active),
    )
    db.add(row)
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        if _is_mysql_dup(e):
            raise HTTPException(status_code=400, detail="该门店下已有同名分类")
        raise
    db.refresh(row)
    return row


def patch_retail_category(
    db: Session, *, category_id: int, store_id: int, body: StoreRetailCategoryPatchIn
) -> StoreRetailCategory:
    row = assert_retail_category_belongs_store(db, category_id=category_id, store_id=store_id)
    if body.name is not None:
        row.name = body.name.strip()
    if body.sort_order is not None:
        row.sort_order = int(body.sort_order)
    if body.is_active is not None:
        row.is_active = bool(body.is_active)
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        if _is_mysql_dup(e):
            raise HTTPException(status_code=400, detail="该门店下已有同名分类")
        raise
    db.refresh(row)
    return row


def delete_retail_category(db: Session, *, category_id: int, store_id: int) -> None:
    row = assert_retail_category_belongs_store(db, category_id=category_id, store_id=store_id)
    cnt = db.scalar(
        select(func.count()).select_from(StoreRetailSpu).where(StoreRetailSpu.category_id == int(category_id))
    )
    if int(cnt or 0) > 0:
        raise HTTPException(status_code=400, detail="该分类下仍有商品，无法删除")
    db.delete(row)
    db.commit()
