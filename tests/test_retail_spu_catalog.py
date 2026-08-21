"""商城零售 SPU/SKU 模型与目录聚合测试。"""

from __future__ import annotations

from decimal import Decimal
from datetime import time

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models.store import Store
from app.models.store_retail_category import StoreRetailCategory
from app.models.store_retail_order import StoreRetailOrder
from app.models.store_retail_order_item import StoreRetailOrderItem
from app.models.store_retail_product import StoreRetailProduct
from app.models.store_retail_spu import StoreRetailSpu
from app.models.tenant import Tenant
from app.services.retail.retail_catalog_public import get_retail_spu_detail_public, list_retail_menu_public
from app.services.retail.retail_display import retail_sku_display_title


@pytest.fixture()
def catalog_db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    tables = [
        Tenant.__table__,
        Store.__table__,
        StoreRetailCategory.__table__,
        StoreRetailSpu.__table__,
        StoreRetailProduct.__table__,
        StoreRetailOrder.__table__,
        StoreRetailOrderItem.__table__,
    ]
    Base.metadata.create_all(engine, tables=tables)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = SessionLocal()
    try:
        session.add(Tenant(id=1, name="t", is_active=True))
        session.add(Store(id=1, tenant_id=1, name="s", leave_deadline_time=time(21, 0), is_active=True))
        session.add(StoreRetailCategory(id=1, store_id=1, name="果蔬汁", sort_order=0, is_active=True))
        session.add(
            StoreRetailSpu(
                id=1,
                store_id=1,
                category_id=1,
                title="轻断食果蔬汁",
                subtitle="新鲜榨取",
                detail_html="<p>详情</p>",
                gallery_urls=["https://example.com/a.jpg"],
                sort_order=0,
                is_on_shelf=True,
            )
        )
        session.add(
            StoreRetailProduct(
                id=10,
                store_id=1,
                spu_id=1,
                spec_label="1日体验",
                unit_price_yuan=Decimal("99.00"),
                list_price_yuan=Decimal("129.00"),
                sort_order=0,
                is_on_shelf=True,
                stock_quantity=10,
            )
        )
        session.add(
            StoreRetailProduct(
                id=11,
                store_id=1,
                spu_id=1,
                spec_label="3日体验",
                unit_price_yuan=Decimal("199.00"),
                sort_order=1,
                is_on_shelf=True,
                stock_quantity=None,
            )
        )
        session.commit()
        yield session
    finally:
        session.close()


def test_retail_sku_display_title():
    assert retail_sku_display_title(spu_title="果蔬汁", spec_label="1日") == "果蔬汁 · 1日"
    assert retail_sku_display_title(spu_title="果蔬汁", spec_label=None) == "果蔬汁"


def test_list_retail_menu_public_groups_spu(catalog_db: Session):
    menu = list_retail_menu_public(catalog_db, store_id=1)
    assert len(menu) == 1
    assert menu[0]["name"] == "果蔬汁"
    products = menu[0]["products"]
    assert len(products) == 1
    assert products[0]["title"] == "轻断食果蔬汁"
    assert products[0]["has_multi_sku"] is True
    assert products[0]["price_min_yuan"] == "99.00"


def test_get_retail_spu_detail_public(catalog_db: Session):
    detail = get_retail_spu_detail_public(catalog_db, store_id=1, spu_id=1)
    assert detail is not None
    assert detail["title"] == "轻断食果蔬汁"
    assert len(detail["skus"]) == 2
    assert detail["skus"][0]["spec_label"] == "1日体验"


def test_list_retail_menu_stock_uses_min_not_sum(catalog_db: Session):
    """多规格库存展示取最小剩余量，避免加总误导。"""
    menu = list_retail_menu_public(catalog_db, store_id=1)
    card = menu[0]["products"][0]
    assert card["stock_limited"] is True
    # id=10 限 10 件，id=11 不限；应展示有限 SKU 的剩余
    assert card["stock_remaining"] is not None
    assert int(card["stock_remaining"]) <= 10


def test_get_retail_sku_public(catalog_db: Session):
    from app.services.retail.retail_catalog_public import get_retail_sku_public

    sku = get_retail_sku_public(catalog_db, store_id=1, sku_id=10)
    assert sku is not None
    assert sku["retail_product_id"] == 10
    assert "1日体验" in sku["title"]


def test_save_retail_spu_bundle_create_does_not_flush_empty_title():
    """新建时不得在 title 仍为空时 flush；MySQL 下会 1048 Column 'title' cannot be null。"""
    import inspect

    from app.services.admin.retail_spu_admin_service import save_retail_spu_bundle

    src = inspect.getsource(save_retail_spu_bundle)
    create_block = src.split("if spu_id is None:", 1)[1].split("else:", 1)[0]
    assert "db.flush()" not in create_block
    assert "_apply_spu_fields" in src
    apply_at = src.index("_apply_spu_fields")
    first_flush_at = src.index("db.flush()")
    assert apply_at < first_flush_at
