"""后台：普通商品 SPU 与 SKU 联动保存、校验。"""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.store import Store
from app.models.store_retail_product import StoreRetailProduct
from app.models.store_retail_spu import StoreRetailSpu
from app.schemas.catalog_admin import (
    StoreRetailSkuUpsertIn,
    StoreRetailSpuBundleSaveIn,
    StoreRetailSpuCreateIn,
    StoreRetailSpuPatchIn,
)
from app.services.admin.retail_category_admin_service import assert_retail_category_belongs_store
from app.services.admin.retail_catalog_serialize import spu_admin_dump, spu_list_item_dump
from app.services.admin.retail_sku_admin_service import (
    _upsert_sku_row,
    get_retail_sku_row,
)
from app.services.retail.retail_catalog_repo import load_skus_by_spu_ids
from app.services.retail.retail_html_sanitize import normalize_retail_gallery_urls, sanitize_retail_detail_html
from app.services.retail.retail_stock_service import get_retail_stock_snapshots


def _apply_spu_fields(
    row: StoreRetailSpu,
    *,
    category_id: int | None,
    title: str,
    subtitle: str | None,
    detail_html: str | None,
    gallery_urls: list[str] | None,
    purchase_notice: str | None,
    sort_order: int,
    is_on_shelf: bool,
    store_id: int,
    db: Session,
) -> None:
    if category_id is not None:
        assert_retail_category_belongs_store(db, category_id=int(category_id), store_id=store_id)
    row.category_id = int(category_id) if category_id is not None else None
    row.title = title.strip()
    row.subtitle = (subtitle.strip() if subtitle else None)
    row.detail_html = sanitize_retail_detail_html(detail_html)
    row.gallery_urls = normalize_retail_gallery_urls(gallery_urls)
    row.purchase_notice = (purchase_notice.strip() if purchase_notice else None)
    row.sort_order = int(sort_order)
    row.is_on_shelf = bool(is_on_shelf)


def _validate_bundle_skus(skus: list[StoreRetailSkuUpsertIn]) -> None:
    if not skus:
        raise HTTPException(status_code=400, detail="至少添加一个规格 SKU")
    labels: set[str] = set()
    for s in skus:
        label = (s.spec_label or "").strip()
        key = label or "__default__"
        if key in labels:
            raise HTTPException(status_code=400, detail=f"规格名重复：{label or '默认'}")
        labels.add(key)


def save_retail_spu_bundle(db: Session, *, store_id: int, body: StoreRetailSpuBundleSaveIn, spu_id: int | None = None) -> dict:
    """同事务保存 SPU + 全部 SKU。"""
    st = db.get(Store, store_id)
    if not st or not st.is_active:
        raise HTTPException(status_code=404, detail="门店不存在或已停用")
    _validate_bundle_skus(body.skus)

    if body.is_on_shelf and not any(bool(s.is_on_shelf) for s in body.skus):
        raise HTTPException(status_code=400, detail="商品上架时至少一个规格须上架")

    try:
        if spu_id is None:
            row = StoreRetailSpu(store_id=int(store_id))
            db.add(row)
            db.flush()
        else:
            row = db.get(StoreRetailSpu, int(spu_id))
            if not row or int(row.store_id) != int(store_id):
                raise HTTPException(status_code=404, detail="商品不存在")

        _apply_spu_fields(
            row,
            category_id=body.category_id,
            title=body.title,
            subtitle=body.subtitle,
            detail_html=body.detail_html,
            gallery_urls=body.gallery_urls,
            purchase_notice=body.purchase_notice,
            sort_order=body.sort_order,
            is_on_shelf=body.is_on_shelf,
            store_id=int(store_id),
            db=db,
        )
        db.flush()

        seen_ids: set[int] = set()
        for idx, sku_in in enumerate(body.skus):
            saved = _upsert_sku_row(
                db,
                store_id=int(store_id),
                spu_id=int(row.id),
                body=sku_in,
                sort_fallback=idx,
            )
            seen_ids.add(int(saved.id))

        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise

    return get_retail_spu_detail(db, spu_id=int(row.id), store_id=store_id)


def list_retail_spus(
    db: Session, *, store_id: int, category_id: int | None = None, shelf_only: bool = False
) -> list[dict]:
    q = (
        select(StoreRetailSpu)
        .where(StoreRetailSpu.store_id == int(store_id))
        .order_by(StoreRetailSpu.sort_order.asc(), StoreRetailSpu.id.asc())
    )
    if category_id is not None:
        q = q.where(StoreRetailSpu.category_id == int(category_id))
    if shelf_only:
        q = q.where(StoreRetailSpu.is_on_shelf.is_(True))
    spus = list(db.scalars(q).all())
    if not spus:
        return []
    spu_ids = [int(s.id) for s in spus]
    sku_map = load_skus_by_spu_ids(db, store_id=store_id, spu_ids=spu_ids, shelf_only=False)
    all_sku_ids = [int(s.id) for skus in sku_map.values() for s in skus]
    stock_map = get_retail_stock_snapshots(db, all_sku_ids)
    return [
        spu_list_item_dump(s, skus=sku_map.get(int(s.id), []), stock_map=stock_map) for s in spus
    ]


def get_retail_spu_detail(db: Session, *, spu_id: int, store_id: int) -> dict:
    spu = db.get(StoreRetailSpu, int(spu_id))
    if not spu or int(spu.store_id) != int(store_id):
        raise HTTPException(status_code=404, detail="商品不存在")
    skus = load_skus_by_spu_ids(db, store_id=store_id, spu_ids=[int(spu_id)], shelf_only=False).get(
        int(spu_id), []
    )
    stock_map = get_retail_stock_snapshots(db, [int(s.id) for s in skus])
    return spu_admin_dump(spu, skus=skus, stock_map=stock_map)


def create_retail_spu(db: Session, *, store_id: int, body: StoreRetailSpuCreateIn) -> dict:
    st = db.get(Store, store_id)
    if not st or not st.is_active:
        raise HTTPException(status_code=404, detail="门店不存在或已停用")
    if body.category_id is not None:
        assert_retail_category_belongs_store(db, category_id=int(body.category_id), store_id=store_id)
    if bool(body.is_on_shelf):
        raise HTTPException(status_code=400, detail="新建商品请先添加规格 SKU，或使用 bundle 接口一并保存")

    row = StoreRetailSpu(
        store_id=int(store_id),
        category_id=int(body.category_id) if body.category_id is not None else None,
        title=body.title.strip(),
        subtitle=(body.subtitle.strip() if body.subtitle else None),
        detail_html=sanitize_retail_detail_html(body.detail_html),
        gallery_urls=normalize_retail_gallery_urls(body.gallery_urls),
        purchase_notice=(body.purchase_notice.strip() if body.purchase_notice else None),
        sort_order=int(body.sort_order),
        is_on_shelf=bool(body.is_on_shelf),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return spu_admin_dump(row, skus=[], stock_map={})


def patch_retail_spu(
    db: Session, *, spu_id: int, store_id: int, body: StoreRetailSpuPatchIn
) -> dict:
    row = db.get(StoreRetailSpu, int(spu_id))
    if not row or int(row.store_id) != int(store_id):
        raise HTTPException(status_code=404, detail="商品不存在")

    if body.is_on_shelf is True:
        cnt = db.scalar(
            select(func.count())
            .select_from(StoreRetailProduct)
            .where(
                StoreRetailProduct.spu_id == int(spu_id),
                StoreRetailProduct.is_on_shelf.is_(True),
            )
        )
        if int(cnt or 0) < 1:
            raise HTTPException(status_code=400, detail="商品上架前至少一个规格 SKU 须上架")

    if "category_id" in body.model_fields_set:
        cid = body.category_id
        if cid is None:
            row.category_id = None
        else:
            assert_retail_category_belongs_store(db, category_id=int(cid), store_id=store_id)
            row.category_id = int(cid)
    if body.title is not None:
        row.title = body.title.strip()
    if body.subtitle is not None:
        row.subtitle = body.subtitle.strip() or None
    if "detail_html" in body.model_fields_set:
        row.detail_html = sanitize_retail_detail_html(body.detail_html)
    if "gallery_urls" in body.model_fields_set:
        row.gallery_urls = normalize_retail_gallery_urls(body.gallery_urls)
    if "purchase_notice" in body.model_fields_set:
        row.purchase_notice = (body.purchase_notice.strip() if body.purchase_notice else None)
    if body.sort_order is not None:
        row.sort_order = int(body.sort_order)
    if body.is_on_shelf is not None:
        row.is_on_shelf = bool(body.is_on_shelf)

    db.commit()
    db.refresh(row)
    return get_retail_spu_detail(db, spu_id=int(row.id), store_id=store_id)


def delete_retail_spu(db: Session, *, spu_id: int, store_id: int) -> None:
    row = db.get(StoreRetailSpu, int(spu_id))
    if not row or int(row.store_id) != int(store_id):
        raise HTTPException(status_code=404, detail="商品不存在")
    cnt = db.scalar(
        select(func.count())
        .select_from(StoreRetailProduct)
        .where(StoreRetailProduct.spu_id == int(spu_id))
    )
    if int(cnt or 0) > 0:
        raise HTTPException(status_code=400, detail="该商品下仍有规格 SKU，请先删除 SKU")
    db.delete(row)
    db.commit()
