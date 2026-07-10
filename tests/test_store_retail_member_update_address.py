"""商城订单：会员端待接单修改配送地址。"""

from __future__ import annotations

from datetime import date, time
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models.member import Member
from app.models.member_address import MemberAddress
from app.models.store import Store
from app.models.store_retail_order import StoreRetailOrder
from app.models.store_retail_product import StoreRetailProduct
from app.models.tenant import Tenant
from app.services.client.store_retail_order_service import (
    _FULFILLMENT_AWAITING_ACCEPT,
    member_update_store_retail_order_address,
)


@pytest.fixture()
def retail_db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    tables = [
        Tenant.__table__,
        Store.__table__,
        Member.__table__,
        MemberAddress.__table__,
        StoreRetailProduct.__table__,
        StoreRetailOrder.__table__,
    ]
    Base.metadata.create_all(engine, tables=tables)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = SessionLocal()
    session.add(Tenant(id=1, name="t", is_active=True))
    session.add(
        Store(id=1, tenant_id=1, name="s", is_active=True, leave_deadline_time=time(21, 0))
    )
    session.add(Member(id=1, tenant_id=1, store_id=1, name="m", phone="13800000000", balance=0))
    session.add(
        StoreRetailProduct(
            id=1,
            store_id=1,
            title="juice",
            unit_price_yuan=Decimal("98.00"),
            is_on_shelf=True,
        )
    )
    session.add(
        MemberAddress(
            id=10,
            member_id=1,
            contact_name="张三",
            contact_phone="13800000000",
            map_location_text="某小区",
            door_detail="1号楼",
            lng=121.0,
            lat=31.0,
            is_default=True,
        )
    )
    session.add(
        MemberAddress(
            id=11,
            member_id=1,
            contact_name="李四",
            contact_phone="13800000001",
            map_location_text="另一小区",
            door_detail="2号楼",
            lng=121.1,
            lat=31.1,
            is_default=False,
        )
    )
    session.flush()
    yield session
    session.close()
    engine.dispose()


def _add_order(
    db: Session,
    *,
    oid: int,
    pay_status: str = "已支付",
    fulfillment_status: str = _FULFILLMENT_AWAITING_ACCEPT,
    store_pickup: bool = False,
    member_address_id: int | None = 10,
) -> None:
    db.add(
        StoreRetailOrder(
            id=oid,
            tenant_id=1,
            store_id=1,
            out_trade_no=f"RO{oid:08d}",
            member_id=1,
            retail_product_id=1,
            product_title="juice",
            member_address_id=member_address_id,
            store_pickup=store_pickup,
            quantity=1,
            fulfillment_date=date(2026, 7, 8),
            routing_area="A区",
            amount_yuan=Decimal("98.00"),
            pay_status=pay_status,
            fulfillment_status=fulfillment_status,
        )
    )


def test_member_update_address_awaiting_accept(retail_db: Session) -> None:
    _add_order(retail_db, oid=1)
    retail_db.commit()

    out = member_update_store_retail_order_address(
        retail_db, member_id=1, order_id=1, member_address_id=11
    )
    assert out.member_address_id == 11
    assert "另一小区" in out.address_summary


def test_member_update_address_rejects_after_accept(retail_db: Session) -> None:
    _add_order(retail_db, oid=1, fulfillment_status="pending")
    retail_db.commit()

    with pytest.raises(HTTPException) as exc:
        member_update_store_retail_order_address(
            retail_db, member_id=1, order_id=1, member_address_id=11
        )
    assert exc.value.status_code == 400
    assert "接单" in str(exc.value.detail)


def test_member_update_address_rejects_store_pickup(retail_db: Session) -> None:
    _add_order(retail_db, oid=1, store_pickup=True, member_address_id=None)
    retail_db.commit()

    with pytest.raises(HTTPException) as exc:
        member_update_store_retail_order_address(
            retail_db, member_id=1, order_id=1, member_address_id=11
        )
    assert exc.value.status_code == 400
    assert "自提" in str(exc.value.detail)
