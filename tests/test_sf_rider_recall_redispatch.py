"""骑士撤单后重派取货：误标「顺丰取消」的订单应恢复为「配送中」。"""

from __future__ import annotations

from datetime import date, time
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models.member import Member
from app.models.menu_dish import MenuDish
from app.models.sf_same_city_push import SfSameCityPush
from app.models.single_meal_order import SingleMealOrder
from app.models.store import Store
from app.models.tenant import Tenant
from app.services.order.single_meal_order_service import (
    _apply_sf_monitor_status_to_retail_order_no_commit,
    mark_single_meals_in_delivery_on_sf_pickup_no_commit,
    sync_single_meal_pickup_status_from_sf_push_no_commit,
)

_DELIVERY_DAY = date(2026, 7, 10)
_ORDER_ID = 777


@pytest.fixture()
def recall_db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    tables = [
        Tenant.__table__,
        Store.__table__,
        Member.__table__,
        MenuDish.__table__,
        SingleMealOrder.__table__,
        SfSameCityPush.__table__,
    ]
    Base.metadata.create_all(engine, tables=tables)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = SessionLocal()
    session.add(Tenant(id=1, name="t", is_active=True))
    session.add(
        Store(id=1, tenant_id=1, name="s", is_active=True, leave_deadline_time=time(21, 0))
    )
    session.add(Member(id=1, tenant_id=1, store_id=1, name="Sandy", phone="18603736915", balance=0))
    session.add(MenuDish(id=1, store_id=1, name="dish", is_enabled=True))
    session.add(
        SingleMealOrder(
            id=_ORDER_ID,
            tenant_id=1,
            store_id=1,
            out_trade_no="SM00000777",
            member_id=1,
            dish_id=1,
            quantity=1,
            delivery_date=_DELIVERY_DAY,
            routing_area="A",
            amount_yuan=Decimal("36.00"),
            pay_status="已支付",
            fulfillment_status="sf_cancelled",
            sf_same_city_push_id=1,
            sf_order_id="JS8248425813290",
        )
    )
    session.add(
        SfSameCityPush(
            id=1,
            store_id=1,
            delivery_date=_DELIVERY_DAY,
            stop_id=f"retail-smo-{_ORDER_ID}",
            push_kind="single_meal_retail",
            shop_order_id="OKFSMO77768208eb2bc",
            sf_order_id="JS8248425813290",
            error_code=0,
            sf_callback_order_status=15,
            last_callback_kind="delivery_status",
        )
    )
    session.commit()
    yield session
    session.close()
    engine.dispose()


def test_mark_in_delivery_recovers_sf_cancelled(recall_db: Session) -> None:
    n = mark_single_meals_in_delivery_on_sf_pickup_no_commit(recall_db, [_ORDER_ID])
    assert n == 1
    row = recall_db.get(SingleMealOrder, _ORDER_ID)
    assert row is not None
    assert row.fulfillment_status == "accepted"


def test_sync_pickup_recovers_sf_cancelled_after_rider_recall(recall_db: Session) -> None:
    pus = recall_db.get(SfSameCityPush, 1)
    assert pus is not None
    n = sync_single_meal_pickup_status_from_sf_push_no_commit(recall_db, pus)
    assert n == 1
    row = recall_db.get(SingleMealOrder, _ORDER_ID)
    assert row is not None
    assert row.fulfillment_status == "accepted"


def test_sync_pickup_skips_when_sf_still_terminal_cancel(recall_db: Session) -> None:
    pus = recall_db.get(SfSameCityPush, 1)
    assert pus is not None
    pus.sf_callback_order_status = 22
    pus.last_callback_kind = "rider_cancel"
    recall_db.flush()

    n = sync_single_meal_pickup_status_from_sf_push_no_commit(recall_db, pus)
    assert n == 0
    row = recall_db.get(SingleMealOrder, _ORDER_ID)
    assert row is not None
    assert row.fulfillment_status == "sf_cancelled"


def test_apply_monitor_status_recovers_sf_cancelled(recall_db: Session) -> None:
    order = recall_db.get(SingleMealOrder, _ORDER_ID)
    pus = recall_db.get(SfSameCityPush, 1)
    assert order is not None and pus is not None

    outcome = _apply_sf_monitor_status_to_retail_order_no_commit(recall_db, order, pus)
    assert outcome == "updated_in_delivery"
    assert order.fulfillment_status == "accepted"
