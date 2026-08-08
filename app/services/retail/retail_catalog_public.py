"""商城零售：C 端目录（分类 → SPU 列表 / SPU 详情）。"""

from __future__ import annotations

from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.store_retail_category import StoreRetailCategory
from app.models.store_retail_product import StoreRetailProduct
from app.models.store_retail_spu import StoreRetailSpu
from app.services.admin.retail_category_admin_service import list_retail_categories
from app.services.retail.retail_catalog_repo import load_skus_by_spu_ids, load_spus_by_ids
from app.services.retail.retail_display import decimal_to_str_money, retail_gallery_cover, retail_price_range_yuan
from app.services.retail.retail_stock_service import RetailProductStockSnapshot, get_retail_stock_snapshots
from app.services.shared.image_url_service import image_list_thumb_url
from sqlalchemy import select


def _sku_is_sellable(*, sku: StoreRetailProduct, snap: RetailProductStockSnapshot | None) -> bool:
    """SKU 是否可售（上架且未售罄）。"""
    if not bool(sku.is_on_shelf):
        return False
    if snap and snap.available is not None and int(snap.available) <= 0:
        return False
    return True


def _spu_card_from_skus(
    spu: StoreRetailSpu,
    skus: list[StoreRetailProduct],
    stock_map: dict[int, RetailProductStockSnapshot],
) -> dict | None:
    """聚合 SPU 卡片：起售价、库存、封面等。"""
    sellable: list[StoreRetailProduct] = []
    for sku in skus:
        snap = stock_map.get(int(sku.id))
        if _sku_is_sellable(sku=sku, snap=snap):
            sellable.append(sku)
    if not sellable:
        return None

    prices = [Decimal(s.unit_price_yuan) for s in sellable]
    price_min, price_max = retail_price_range_yuan(prices)
    cover = retail_gallery_cover(spu.gallery_urls)
    # 列表库存取可售 SKU 的最小剩余量，避免多规格加总误导用户
    stock_limited = any(s.stock_quantity is not None for s in sellable)
    stock_remaining: int | None = None
    if stock_limited:
        avail_vals: list[int] = []
        for s in sellable:
            if s.stock_quantity is None:
                continue
            snap = stock_map.get(int(s.id))
            if snap and snap.available is not None:
                avail_vals.append(int(snap.available))
        stock_remaining = min(avail_vals) if avail_vals else 0

    return {
        "id": int(spu.id),
        "title": spu.title,
        "subtitle": spu.subtitle,
        "cover_image_url": cover,
        "cover_image_thumb_url": image_list_thumb_url(cover) if cover else None,
        "price_min_yuan": price_min,
        "price_max_yuan": price_max,
        "has_multi_sku": len(sellable) > 1,
        "stock_limited": stock_limited,
        "stock_remaining": stock_remaining,
        "sort_order": int(spu.sort_order),
    }


def list_retail_menu_public(db: Session, *, store_id: int) -> list[dict]:
    """小程序菜单：按分类返回上架 SPU 卡片。"""
    categories = list_retail_categories(db, store_id=store_id, active_only=True)
    spu_rows = list(
        db.scalars(
            select(StoreRetailSpu)
            .where(
                StoreRetailSpu.store_id == int(store_id),
                StoreRetailSpu.is_on_shelf.is_(True),
                StoreRetailSpu.category_id.is_not(None),
            )
            .order_by(StoreRetailSpu.sort_order.asc(), StoreRetailSpu.id.asc())
        ).all()
    )
    if not spu_rows:
        return []

    spu_ids = [int(s.id) for s in spu_rows]
    sku_map = load_skus_by_spu_ids(db, store_id=store_id, spu_ids=spu_ids, shelf_only=True)
    all_sku_ids = [int(s.id) for skus in sku_map.values() for s in skus]
    stock_map = get_retail_stock_snapshots(db, all_sku_ids)

    by_cat: dict[int, list[dict]] = {}
    for spu in spu_rows:
        cid = int(spu.category_id) if spu.category_id is not None else None
        if cid is None:
            continue
        card = _spu_card_from_skus(spu, sku_map.get(int(spu.id), []), stock_map)
        if card:
            by_cat.setdefault(cid, []).append(card)

    out: list[dict] = []
    for cat in categories:
        items = by_cat.get(int(cat.id), [])
        if not items:
            continue
        out.append(
            {
                "id": int(cat.id),
                "name": cat.name,
                "sort_order": int(cat.sort_order),
                "products": items,
            }
        )
    return out


def _sku_public_dump(
    sku: StoreRetailProduct, *, snap: RetailProductStockSnapshot | None
) -> dict:
    sold = int(snap.sold_count) if snap else 0
    remaining = snap.available if snap else None
    return {
        "id": int(sku.id),
        "spec_label": sku.spec_label,
        "sku_code": sku.sku_code,
        "unit_price_yuan": decimal_to_str_money(sku.unit_price_yuan),
        "list_price_yuan": decimal_to_str_money(sku.list_price_yuan),
        "sort_order": int(sku.sort_order),
        "is_on_shelf": bool(sku.is_on_shelf),
        "sold_count": sold,
        "stock_remaining": remaining,
        "stock_limited": sku.stock_quantity is not None,
    }


def get_retail_spu_detail_public(db: Session, *, store_id: int, spu_id: int) -> dict | None:
    """小程序商品详情：SPU 信息 + 可售 SKU 列表。"""
    spu = load_spus_by_ids(db, [int(spu_id)]).get(int(spu_id))
    if not spu or int(spu.store_id) != int(store_id):
        return None
    if not bool(spu.is_on_shelf):
        return None
    if spu.category_id is not None:
        cat = db.get(StoreRetailCategory, int(spu.category_id))
        if not cat or not bool(cat.is_active) or int(cat.store_id) != int(store_id):
            return None

    skus = load_skus_by_spu_ids(db, store_id=store_id, spu_ids=[int(spu_id)], shelf_only=True).get(
        int(spu_id), []
    )
    stock_map = get_retail_stock_snapshots(db, [int(s.id) for s in skus])
    sellable = [s for s in skus if _sku_is_sellable(sku=s, snap=stock_map.get(int(s.id)))]
    if not sellable:
        return None

    cover = retail_gallery_cover(spu.gallery_urls)
    gallery = [u for u in (spu.gallery_urls or []) if isinstance(u, str) and u.strip()]
    prices = [Decimal(s.unit_price_yuan) for s in sellable]
    price_min, price_max = retail_price_range_yuan(prices)

    return {
        "id": int(spu.id),
        "category_id": int(spu.category_id) if spu.category_id is not None else None,
        "title": spu.title,
        "subtitle": spu.subtitle,
        "detail_html": spu.detail_html,
        "gallery_urls": gallery,
        "purchase_notice": spu.purchase_notice,
        "cover_image_url": cover,
        "cover_image_thumb_url": image_list_thumb_url(cover) if cover else None,
        "price_min_yuan": price_min,
        "price_max_yuan": price_max,
        "skus": [_sku_public_dump(s, snap=stock_map.get(int(s.id))) for s in sellable],
    }


def get_retail_sku_public(db: Session, *, store_id: int, sku_id: int) -> dict | None:
    """按 SKU id 返回可售商品信息（结算页等单规格场景）。"""
    from app.services.retail.retail_display import retail_sku_display_title

    sku = db.get(StoreRetailProduct, int(sku_id))
    if not sku or int(sku.store_id) != int(store_id):
        return None
    spu = load_spus_by_ids(db, [int(sku.spu_id)]).get(int(sku.spu_id))
    if not spu:
        return None
    try:
        assert_retail_sku_orderable(db, sku=sku, spu=spu, store_id=int(store_id))
    except HTTPException:
        return None
    snap = get_retail_stock_snapshots(db, [int(sku.id)]).get(int(sku.id))
    if not _sku_is_sellable(sku=sku, snap=snap):
        return None
    cover = retail_gallery_cover(spu.gallery_urls)
    return {
        "retail_product_id": int(sku.id),
        "spu_id": int(spu.id),
        "title": retail_sku_display_title(spu_title=spu.title, spec_label=sku.spec_label),
        "spu_title": spu.title,
        "subtitle": spu.subtitle,
        "spec_label": sku.spec_label,
        "unit_price_yuan": decimal_to_str_money(sku.unit_price_yuan),
        "list_price_yuan": decimal_to_str_money(sku.list_price_yuan),
        "cover_image_url": cover,
        "stock_remaining": snap.available if snap else None,
        "stock_limited": sku.stock_quantity is not None,
        "sold_count": int(snap.sold_count) if snap else 0,
    }


def assert_retail_sku_orderable(
    db: Session, *, sku: StoreRetailProduct, spu: StoreRetailSpu, store_id: int
) -> StoreRetailSpu:
    """C 端 SKU 可售校验（与下单链路一致）。"""
    from app.services.retail.retail_order_amount import assert_retail_product_orderable

    return assert_retail_product_orderable(db, product=sku, store_id=int(store_id), spu=spu)


def build_sku_lookup_from_menu(db: Session, *, store_id: int) -> dict[int, dict]:
    """从目录构建 SKU id → 公开信息映射（购物车同步用）。"""
    detail_map: dict[int, dict] = {}
    menu = list_retail_menu_public(db, store_id=store_id)
    spu_ids = []
    for cat in menu:
        for p in cat.get("products") or []:
            if p.get("id"):
                spu_ids.append(int(p["id"]))
    if not spu_ids:
        return detail_map

    spu_map = load_spus_by_ids(db, spu_ids)
    sku_map = load_skus_by_spu_ids(db, store_id=store_id, spu_ids=spu_ids, shelf_only=True)
    stock_map = get_retail_stock_snapshots(
        db, [int(s.id) for skus in sku_map.values() for s in skus]
    )
    from app.services.retail.retail_display import retail_sku_display_title

    for spu_id, skus in sku_map.items():
        spu = spu_map.get(int(spu_id))
        if not spu:
            continue
        cover = retail_gallery_cover(spu.gallery_urls)
        for sku in skus:
            snap = stock_map.get(int(sku.id))
            if not _sku_is_sellable(sku=sku, snap=snap):
                continue
            detail_map[int(sku.id)] = {
                "retail_product_id": int(sku.id),
                "spu_id": int(spu.id),
                "title": retail_sku_display_title(spu_title=spu.title, spec_label=sku.spec_label),
                "spu_title": spu.title,
                "spec_label": sku.spec_label,
                "unit_price_yuan": decimal_to_str_money(sku.unit_price_yuan),
                "list_price_yuan": decimal_to_str_money(sku.list_price_yuan),
                "cover_image_url": cover,
                "stock_remaining": snap.available if snap else None,
                "stock_limited": sku.stock_quantity is not None,
                "sold_count": int(snap.sold_count) if snap else 0,
            }
    return detail_map
