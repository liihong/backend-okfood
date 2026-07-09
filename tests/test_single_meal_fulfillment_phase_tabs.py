"""零售订单（单次点餐）：管理端按发货状态 Tab 过滤。"""

from __future__ import annotations

from datetime import date, time
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models.member import Member
from app.models.member_address import MemberAddress
from app.models.delivery_region import DeliveryRegion
from app.models.menu_dish import MenuDish
from app.models.single_meal_order import SingleMealOrder
from app.models.store import Store
from app.models.tenant import Tenant
from app.services.order.single_meal_order_service import list_admin_store_single_meal_orders_by_delivery_day

_DELIVERY_DAY = date(2026, 7, 9)


@pytest.fixture()
def single_db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    tables = [
        Tenant.__table__,
        Store.__table__,
        Member.__table__,
        DeliveryRegion.__table__,
        MemberAddress.__table__,
        MenuDish.__table__,
        SingleMealOrder.__table__,
    ]
    Base.metadata.create_all(engine, tables=tables)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = SessionLocal()
    session.add(Tenant(id=1, name="t", is_active=True))
    session.add(
        Store(id=1, tenant_id=1, name="s", is_active=True, leave_deadline_time=time(21, 0))
    )
    session.add(Member(id=1, tenant_id=1, store_id=1, name="m", phone="13800000000", balance=0))
    session.add(MenuDish(id=1, store_id=1, name="dish", is_enabled=True))
    session.flush()
    yield session
    session.close()
    engine.dispose()


def _add_order(
    db: Session,
    *,
    oid: int,
    pay_status: str = "未支付",
    fulfillment_status: str = "pending",
) -> None:
    db.add(
        SingleMealOrder(
            id=oid,
            tenant_id=1,
            store_id=1,
            out_trade_no=f"SM{oid:08d}",
            member_id=1,
            dish_id=1,
            quantity=1,
            delivery_date=_DELIVERY_DAY,
            routing_area="A",
            amount_yuan=Decimal("30.00"),
            pay_status=pay_status,
            fulfillment_status=fulfillment_status,
        )
    )


def test_pending_ship_tab_only_paid_pending(single_db: Session) -> None:
    _add_order(single_db, oid=1, pay_status="已支付", fulfillment_status="pending")
    _add_order(single_db, oid=2, pay_status="未支付", fulfillment_status="pending")
    _add_order(single_db, oid=3, pay_status="已支付", fulfillment_status="accepted")
    _add_order(single_db, oid=4, pay_status="已支付", fulfillment_status="sf_cancelled")
    single_db.commit()

    items, total = list_admin_store_single_meal_orders_by_delivery_day(
        single_db,
        store_id=1,
        delivery_day=_DELIVERY_DAY,
        fulfillment_phase="pending_ship",
    )
    assert total == 2
    assert {i.id for i in items} == {1, 4}


def test_after_sale_tab_includes_unpaid_cancelled_refunded(single_db: Session) -> None:
    _add_order(single_db, oid=1, pay_status="未支付", fulfillment_status="pending")
    _add_order(single_db, oid=2, pay_status="已支付", fulfillment_status="cancelled")
    _add_order(single_db, oid=3, pay_status="已退款", fulfillment_status="cancelled")
    _add_order(single_db, oid=4, pay_status="已支付", fulfillment_status="pending")
    single_db.commit()

    items, total = list_admin_store_single_meal_orders_by_delivery_day(
        single_db,
        store_id=1,
        delivery_day=_DELIVERY_DAY,
        fulfillment_phase="after_sale",
    )
    assert total == 3
    assert {i.id for i in items} == {1, 2, 3}


def test_in_delivery_tab(single_db: Session) -> None:
    _add_order(single_db, oid=1, pay_status="已支付", fulfillment_status="accepted")
    _add_order(single_db, oid=2, pay_status="已支付", fulfillment_status="sf_awaiting_pickup")
    _add_order(single_db, oid=3, pay_status="已支付", fulfillment_status="pending")
    single_db.commit()

    _, total = list_admin_store_single_meal_orders_by_delivery_day(
        single_db,
        store_id=1,
        delivery_day=_DELIVERY_DAY,
        fulfillment_phase="in_delivery",
    )
    assert total == 2
