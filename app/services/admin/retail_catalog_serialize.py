"""后台：普通商品 SPU 序列化。"""

from __future__ import annotations

from decimal import Decimal

from app.models.store_retail_product import StoreRetailProduct
from app.models.store_retail_spu import StoreRetailSpu
from app.services.retail.retail_display import decimal_to_str_money, retail_gallery_cover, retail_price_range_yuan
from app.services.retail.retail_stock_service import RetailProductStockSnapshot


def sku_admin_dump(row: StoreRetailProduct, *, stock: RetailProductStockSnapshot | None = None) -> dict:
    """管理端 SKU 行。"""
    sold = int(stock.sold_count) if stock else 0
    remaining = stock.available if stock else None
    return {
        "id": int(row.id),
        "store_id": int(row.store_id),
        "spu_id": int(row.spu_id),
        "sku_code": row.sku_code,
        "spec_label": row.spec_label,
        "unit_price_yuan": decimal_to_str_money(row.unit_price_yuan),
        "list_price_yuan": decimal_to_str_money(row.list_price_yuan),
        "sort_order": int(row.sort_order),
        "is_on_shelf": bool(row.is_on_shelf),
        "stock_quantity": int(row.stock_quantity) if row.stock_quantity is not None else None,
        "sold_count": sold,
        "stock_remaining": remaining,
    }


def spu_admin_dump(
    spu: StoreRetailSpu,
    *,
    skus: list[StoreRetailProduct] | None = None,
    stock_map: dict[int, RetailProductStockSnapshot] | None = None,
) -> dict:
    """管理端 SPU 详情（含 SKU 列表与价格区间）。"""
    stock_map = stock_map or {}
    sku_rows = skus or []
    sku_dumps = [sku_admin_dump(s, stock=stock_map.get(int(s.id))) for s in sku_rows]
    prices = [Decimal(s.unit_price_yuan) for s in sku_rows if bool(s.is_on_shelf)]
    price_min, price_max = retail_price_range_yuan(prices)
    cover = retail_gallery_cover(spu.gallery_urls)
    gallery = [u for u in (spu.gallery_urls or []) if isinstance(u, str) and u.strip()]
    return {
        "id": int(spu.id),
        "store_id": int(spu.store_id),
        "category_id": int(spu.category_id) if spu.category_id is not None else None,
        "title": spu.title,
        "subtitle": spu.subtitle,
        "detail_html": spu.detail_html,
        "gallery_urls": gallery,
        "cover_image_url": cover,
        "purchase_notice": spu.purchase_notice,
        "sort_order": int(spu.sort_order),
        "is_on_shelf": bool(spu.is_on_shelf),
        "sku_count": len(sku_rows),
        "price_min_yuan": price_min,
        "price_max_yuan": price_max,
        "skus": sku_dumps,
    }


def spu_list_item_dump(
    spu: StoreRetailSpu,
    *,
    skus: list[StoreRetailProduct],
    stock_map: dict[int, RetailProductStockSnapshot] | None = None,
) -> dict:
    """管理端 SPU 列表行（精简）。"""
    full = spu_admin_dump(spu, skus=skus, stock_map=stock_map)
    return {
        "id": full["id"],
        "store_id": full["store_id"],
        "category_id": full["category_id"],
        "title": full["title"],
        "subtitle": full["subtitle"],
        "cover_image_url": full["cover_image_url"],
        "sort_order": full["sort_order"],
        "is_on_shelf": full["is_on_shelf"],
        "sku_count": full["sku_count"],
        "price_min_yuan": full["price_min_yuan"],
        "price_max_yuan": full["price_max_yuan"],
    }
