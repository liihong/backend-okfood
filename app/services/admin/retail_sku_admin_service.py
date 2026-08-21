"""后台：普通商品 SKU CRUD。"""

from __future__ import annotations

from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.douyin.product_mapping import DouyinProductMapping
from app.models.enums import DouyinGrantType
from app.models.store import Store
from app.models.store_retail_order import StoreRetailOrder
from app.models.store_retail_order_item import StoreRetailOrderItem
from app.models.store_retail_product import StoreRetailProduct
from app.models.store_retail_spu import StoreRetailSpu
from app.schemas.catalog_admin import StoreRetailSkuCreateIn, StoreRetailSkuPatchIn, StoreRetailSkuUpsertIn
from app.services.admin.retail_catalog_serialize import sku_admin_dump
from app.services.retail.retail_display import retail_sku_display_title
from app.services.retail.retail_stock_service import get_retail_stock_snapshots


def _assert_spu_belongs_store(db: Session, *, spu_id: int, store_id: int) -> StoreRetailSpu:
    spu = db.get(StoreRetailSpu, int(spu_id))
    if not spu or int(spu.store_id) != int(store_id):
        raise HTTPException(status_code=404, detail="所属商品不存在")
    return spu


def _spec_label_key(spec_label: str | None) -> str:
    return (spec_label or "").strip() or "__default__"


def _assert_spec_label_unique(
    db: Session, *, spu_id: int, spec_label: str | None, exclude_sku_id: int | None = None
) -> None:
    """同 SPU 下规格名不可重复（空规格视为「默认」）。"""
    key = _spec_label_key(spec_label)
    rows = db.scalars(select(StoreRetailProduct).where(StoreRetailProduct.spu_id == int(spu_id))).all()
    for r in rows:
        if exclude_sku_id is not None and int(r.id) == int(exclude_sku_id):
            continue
        if _spec_label_key(r.spec_label) == key:
            raise HTTPException(status_code=400, detail="该商品下已有相同规格名")


def _upsert_sku_row(
    db: Session,
    *,
    store_id: int,
    spu_id: int,
    body: StoreRetailSkuUpsertIn,
    sort_fallback: int = 0,
) -> StoreRetailProduct:
    """创建或更新 SKU 行（不含 commit）。"""
    spec = (body.spec_label.strip() if body.spec_label else None)
    if body.id is not None:
        row = get_retail_sku_row(db, sku_id=int(body.id), store_id=store_id)
        if int(row.spu_id) != int(spu_id):
            raise HTTPException(status_code=400, detail="SKU 不属于当前商品")
        _assert_spec_label_unique(db, spu_id=int(spu_id), spec_label=spec, exclude_sku_id=int(row.id))
        row.sku_code = (body.sku_code.strip() or None) if body.sku_code else None
        row.spec_label = spec
        row.unit_price_yuan = Decimal(body.unit_price_yuan)
        row.list_price_yuan = Decimal(body.list_price_yuan) if body.list_price_yuan is not None else None
        row.sort_order = int(body.sort_order) if body.sort_order is not None else sort_fallback
        row.is_on_shelf = bool(body.is_on_shelf)
        if body.stock_quantity is not None:
            snap = get_retail_stock_snapshots(db, [int(row.id)]).get(int(row.id))
            if snap and snap.stock_quantity is not None:
                min_stock = int(snap.sold_count) + int(snap.reserved_count)
                if int(body.stock_quantity) < min_stock:
                    raise HTTPException(
                        status_code=400,
                        detail=f"库存不能低于已售与未支付占用合计（至少 {min_stock} 件）",
                    )
        row.stock_quantity = int(body.stock_quantity) if body.stock_quantity is not None else None
        # 同请求里后续新建 SKU 做规格唯一校验时，需看到本次改名后的值
        db.flush()
        return row

    _assert_spec_label_unique(db, spu_id=int(spu_id), spec_label=spec)
    row = StoreRetailProduct(
        store_id=int(store_id),
        spu_id=int(spu_id),
        sku_code=(body.sku_code.strip() or None) if body.sku_code else None,
        spec_label=spec,
        unit_price_yuan=Decimal(body.unit_price_yuan),
        list_price_yuan=Decimal(body.list_price_yuan) if body.list_price_yuan is not None else None,
        sort_order=int(body.sort_order) if body.sort_order is not None else sort_fallback,
        is_on_shelf=bool(body.is_on_shelf),
        stock_quantity=int(body.stock_quantity) if body.stock_quantity is not None else None,
    )
    db.add(row)
    db.flush()
    return row


def list_retail_skus(
    db: Session,
    *,
    store_id: int,
    spu_id: int | None = None,
    shelf_only: bool = False,
) -> list[dict]:
    q = (
        select(StoreRetailProduct)
        .where(StoreRetailProduct.store_id == int(store_id))
        .order_by(StoreRetailProduct.sort_order.asc(), StoreRetailProduct.id.asc())
    )
    if spu_id is not None:
        q = q.where(StoreRetailProduct.spu_id == int(spu_id))
    if shelf_only:
        q = q.where(StoreRetailProduct.is_on_shelf.is_(True))
    rows = list(db.scalars(q).all())
    stock_map = get_retail_stock_snapshots(db, [int(r.id) for r in rows])
    spu_map = {
        int(s.id): s
        for s in db.scalars(
            select(StoreRetailSpu).where(
                StoreRetailSpu.id.in_({int(r.spu_id) for r in rows}) if rows else [0]
            )
        ).all()
    }
    out = []
    for r in rows:
        dump = sku_admin_dump(r, stock=stock_map.get(int(r.id)))
        spu = spu_map.get(int(r.spu_id))
        if spu:
            dump["spu_title"] = spu.title
            dump["display_title"] = retail_sku_display_title(
                spu_title=spu.title, spec_label=r.spec_label
            )
        out.append(dump)
    return out


def create_retail_sku(db: Session, *, store_id: int, body: StoreRetailSkuCreateIn) -> dict:
    st = db.get(Store, store_id)
    if not st or not st.is_active:
        raise HTTPException(status_code=404, detail="门店不存在或已停用")
    _assert_spu_belongs_store(db, spu_id=int(body.spu_id), store_id=store_id)
    _assert_spec_label_unique(db, spu_id=int(body.spu_id), spec_label=body.spec_label)

    row = StoreRetailProduct(
        store_id=int(store_id),
        spu_id=int(body.spu_id),
        sku_code=(body.sku_code.strip() or None) if body.sku_code else None,
        spec_label=(body.spec_label.strip() if body.spec_label else None),
        unit_price_yuan=Decimal(body.unit_price_yuan),
        list_price_yuan=Decimal(body.list_price_yuan) if body.list_price_yuan is not None else None,
        sort_order=int(body.sort_order),
        is_on_shelf=bool(body.is_on_shelf),
        stock_quantity=int(body.stock_quantity) if body.stock_quantity is not None else None,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    stock_map = get_retail_stock_snapshots(db, [int(row.id)])
    dump = sku_admin_dump(row, stock=stock_map.get(int(row.id)))
    spu = db.get(StoreRetailSpu, int(row.spu_id))
    if spu:
        dump["spu_title"] = spu.title
        dump["display_title"] = retail_sku_display_title(spu_title=spu.title, spec_label=row.spec_label)
    return dump


def get_retail_sku_row(db: Session, *, sku_id: int, store_id: int) -> StoreRetailProduct:
    row = db.get(StoreRetailProduct, int(sku_id))
    if not row or int(row.store_id) != int(store_id):
        raise HTTPException(status_code=404, detail="SKU 不存在")
    return row


def patch_retail_sku(db: Session, *, sku_id: int, store_id: int, body: StoreRetailSkuPatchIn) -> dict:
    row = get_retail_sku_row(db, sku_id=sku_id, store_id=store_id)
    target_spu_id = int(body.spu_id) if body.spu_id is not None else int(row.spu_id)
    if body.spu_id is not None:
        _assert_spu_belongs_store(db, spu_id=int(body.spu_id), store_id=store_id)
        row.spu_id = int(body.spu_id)
    if body.spec_label is not None:
        spec = body.spec_label.strip() or None
        _assert_spec_label_unique(
            db, spu_id=target_spu_id, spec_label=spec, exclude_sku_id=int(row.id)
        )
        row.spec_label = spec
    if body.sku_code is not None:
        row.sku_code = body.sku_code.strip() or None
    if body.unit_price_yuan is not None:
        row.unit_price_yuan = Decimal(body.unit_price_yuan)
    if body.list_price_yuan is not None:
        row.list_price_yuan = Decimal(body.list_price_yuan) if body.list_price_yuan else None
    if body.sort_order is not None:
        row.sort_order = int(body.sort_order)
    if body.is_on_shelf is not None:
        row.is_on_shelf = bool(body.is_on_shelf)
    if "stock_quantity" in body.model_fields_set:
        new_stock = int(body.stock_quantity) if body.stock_quantity is not None else None
        if new_stock is not None:
            snap = get_retail_stock_snapshots(db, [int(row.id)]).get(int(row.id))
            if snap is not None and snap.stock_quantity is not None:
                min_stock = int(snap.sold_count) + int(snap.reserved_count)
                if new_stock < min_stock:
                    raise HTTPException(
                        status_code=400,
                        detail=f"库存不能低于已售与未支付占用合计（至少 {min_stock} 件）",
                    )
        row.stock_quantity = new_stock
    db.commit()
    db.refresh(row)
    stock_map = get_retail_stock_snapshots(db, [int(row.id)])
    dump = sku_admin_dump(row, stock=stock_map.get(int(row.id)))
    spu = db.get(StoreRetailSpu, int(row.spu_id))
    if spu:
        dump["spu_title"] = spu.title
        dump["display_title"] = retail_sku_display_title(spu_title=spu.title, spec_label=row.spec_label)
    return dump


def _assert_sku_deletable(db: Session, *, sku_id: int) -> None:
    """有订单或抖音映射引用的 SKU 不可物理删除。"""
    order_cnt = db.scalar(
        select(func.count())
        .select_from(StoreRetailOrder)
        .where(StoreRetailOrder.retail_product_id == int(sku_id))
    )
    if int(order_cnt or 0) > 0:
        raise HTTPException(
            status_code=400,
            detail="该规格已有订单记录，无法删除。请改为下架处理",
        )

    item_cnt = db.scalar(
        select(func.count())
        .select_from(StoreRetailOrderItem)
        .where(StoreRetailOrderItem.retail_product_id == int(sku_id))
    )
    if int(item_cnt or 0) > 0:
        raise HTTPException(
            status_code=400,
            detail="该规格已有订单明细，无法删除。请改为下架处理",
        )

    mapping_cnt = db.scalar(
        select(func.count())
        .select_from(DouyinProductMapping)
        .where(
            DouyinProductMapping.grant_type == DouyinGrantType.RETAIL_PRODUCT.value,
            DouyinProductMapping.target_id == int(sku_id),
        )
    )
    if int(mapping_cnt or 0) > 0:
        raise HTTPException(
            status_code=400,
            detail="该规格仍被抖音商品映射引用，请先解除映射后再删除",
        )


def delete_retail_sku(db: Session, *, sku_id: int, store_id: int) -> None:
    row = get_retail_sku_row(db, sku_id=sku_id, store_id=store_id)
    _assert_sku_deletable(db, sku_id=int(row.id))
    try:
        db.delete(row)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail="该规格仍被业务数据引用，无法删除。请改为下架处理",
        ) from None
