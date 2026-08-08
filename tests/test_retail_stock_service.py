"""商城零售库存：支付前排除本单占用。"""

from __future__ import annotations

from datetime import date, time
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models.member import Member
from app.models.store import Store
from app.models.store_retail_order import StoreRetailOrder
from app.models.store_retail_order_item import StoreRetailOrderItem
from app.models.store_retail_product import StoreRetailProduct
from app.models.store_retail_spu import StoreRetailSpu
from app.models.tenant import Tenant
from app.services.retail.retail_stock_service import assert_retail_stock_available, get_retail_stock_snapshots


@pytest.fixture()
def retail_db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    tables = [
        Tenant.__table__,
        Store.__table__,
        Member.__table__,
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
        session.add(
            Member(
                id=1,
                tenant_id=1,
                store_id=1,
                phone="13800000000",
                name="u",
                balance=0,
                meal_quota_total=0,
                is_active=True,
            )
        )
        session.add(
            StoreRetailSpu(
                id=1,
                store_id=1,
                category_id=None,
                title="测试商品",
                sort_order=0,
                is_on_shelf=True,
            )
        )
        session.add(
            StoreRetailProduct(
                id=10,
                store_id=1,
                spu_id=1,
                unit_price_yuan=Decimal("10.00"),
                stock_quantity=2,
                is_on_shelf=True,
            )
        )
        session.flush()
        order = StoreRetailOrder(
            id=100,
            tenant_id=1,
            store_id=1,
            member_id=1,
            retail_product_id=10,
            product_title="测试商品",
            quantity=2,
            amount_yuan=Decimal("20.00"),
            pay_status="未支付",
            fulfillment_status="pending",
            fulfillment_date=date.today(),
            routing_area="测试",
            out_trade_no="TMP100",
        )
        session.add(order)
        session.flush()
        session.add(
            StoreRetailOrderItem(
                id=1,
                order_id=100,
                retail_product_id=10,
                spu_id=1,
                product_title="测试商品",
                spu_title="测试商品",
                unit_price_yuan=Decimal("10.00"),
                quantity=2,
                line_amount_yuan=Decimal("20.00"),
            )
        )
        session.commit()
        yield session
    finally:
        session.close()


def test_stock_snapshot_counts_unpaid(retail_db: Session):
    snap = get_retail_stock_snapshots(retail_db, [10]).get(10)
    assert snap is not None
    assert snap.reserved_count == 2
    assert snap.available == 0


def test_assert_stock_excludes_own_unpaid_order(retail_db: Session):
    assert_retail_stock_available(retail_db, product_id=10, need_qty=2, exclude_order_id=100)


def test_assert_stock_fails_when_insufficient(retail_db: Session):
    with pytest.raises(HTTPException):
        assert_retail_stock_available(retail_db, product_id=10, need_qty=3)


def test_delete_retail_sku_blocked_when_has_orders(retail_db: Session):
    from app.services.admin.retail_sku_admin_service import delete_retail_sku

    with pytest.raises(HTTPException) as exc:
        delete_retail_sku(retail_db, sku_id=10, store_id=1)
    assert exc.value.status_code == 400
    assert "订单" in str(exc.value.detail)

