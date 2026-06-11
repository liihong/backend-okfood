"""方案 A：推单后大表份数读首次推单快照。"""

from datetime import date, time
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models.delivery_sheet_push_units_snapshot import DeliverySheetPushUnitsSnapshot
from app.models.member import Member
from app.models.sf_same_city_push import SfSameCityPush
from app.models.store import Store
from app.models.tenant import Tenant
from app.services.delivery_sheet_meal_units_service import meal_units_for_delivery_sheet_member
from app.services.delivery_sheet_push_snapshot_service import (
    FROZEN_MEMBER_IDS_SNAPSHOT_KEY,
    capture_delivery_sheet_units_on_first_push,
    frozen_member_ids_from_units_snapshot,
    member_meal_units_snapshot_for_date,
)


@pytest.fixture()
def units_db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    tables = [
        Tenant.__table__,
        Store.__table__,
        Member.__table__,
        SfSameCityPush.__table__,
        DeliverySheetPushUnitsSnapshot.__table__,
    ]
    Base.metadata.create_all(engine, tables=tables)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = SessionLocal()
    try:
        session.add(Tenant(id=1, name="测试租户", is_active=True))
        session.add(
            Store(
                id=1,
                tenant_id=1,
                name="测试门店",
                leave_deadline_time=time(21, 0),
                is_active=True,
            )
        )
        session.commit()
        yield session
    finally:
        session.close()
        engine.dispose()


def _add_member(db: Session, *, mid: int, units: int = 1) -> Member:
    m = Member(
        id=mid,
        tenant_id=1,
        store_id=1,
        phone=f"1300000{mid:04d}",
        name=f"会员{mid}",
        balance=10,
        daily_meal_units=units,
        is_active=True,
        store_pickup=False,
        delivery_start_date=date(2026, 5, 1),
    )
    db.add(m)
    db.flush()
    return m


def test_units_snapshot_captured_once(units_db: Session):
    d = date(2026, 6, 11)
    _add_member(units_db, mid=1, units=1)
    units_db.add(
        SfSameCityPush(
            store_id=1,
            delivery_date=d,
            stop_id="stop-a",
            push_kind="delivery_sheet",
            shop_order_id="shop-a",
            error_code=0,
            request_snapshot={"fulfillment_member_ids": [1]},
        )
    )
    with patch(
        "app.services.delivery_sheet_push_snapshot_service._collect_member_meal_units_for_sf_push_sheet",
        return_value={"1": 1},
    ):
        capture_delivery_sheet_units_on_first_push(units_db, store_id=1, delivery_date=d)
        capture_delivery_sheet_units_on_first_push(units_db, store_id=1, delivery_date=d)
    units_db.commit()
    snap = member_meal_units_snapshot_for_date(units_db, store_id=1, delivery_date=d)
    assert snap == {1: 1}


def test_frozen_ids_cached_in_units_snapshot(units_db: Session):
    d = date(2026, 6, 11)
    units_db.add(
        DeliverySheetPushUnitsSnapshot(
            store_id=1,
            delivery_date=d,
            member_meal_units={
                "1": 1,
                FROZEN_MEMBER_IDS_SNAPSHOT_KEY: [1, 2, 3],
            },
        )
    )
    units_db.commit()
    cached = frozen_member_ids_from_units_snapshot(units_db, store_id=1, delivery_date=d)
    assert cached == frozenset({1, 2, 3})


def test_frozen_sheet_uses_snapshot_not_live_units(units_db: Session):
    d = date(2026, 6, 11)
    m = _add_member(units_db, mid=7, units=1)
    units_db.add(
        DeliverySheetPushUnitsSnapshot(
            store_id=1,
            delivery_date=d,
            member_meal_units={"7": 1},
        )
    )
    units_db.add(
        SfSameCityPush(
            store_id=1,
            delivery_date=d,
            stop_id="stop-b",
            push_kind="delivery_sheet",
            shop_order_id="shop-b",
            error_code=0,
            request_snapshot={"fulfillment_member_ids": [7]},
        )
    )
    units_db.commit()

    m.daily_meal_units = 2
    units_db.flush()

    shown = meal_units_for_delivery_sheet_member(units_db, m, delivery_date=d, store_id=1)
    assert shown == 1
