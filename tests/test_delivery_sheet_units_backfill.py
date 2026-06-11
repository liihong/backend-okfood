"""历史顺丰推单回填份数快照。"""

from datetime import date, time

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models.member import Member
from app.models.sf_same_city_push import SfSameCityPush
from app.models.store import Store
from app.models.tenant import Tenant
from app.services.delivery_sheet_units_backfill_service import (
    build_member_meal_units_from_sf_pushes,
    upsert_delivery_sheet_units_snapshot,
)
from app.models.delivery_sheet_push_units_snapshot import DeliverySheetPushUnitsSnapshot


@pytest.fixture()
def backfill_db() -> Session:
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
        session.add(
            Member(
                id=7,
                tenant_id=1,
                store_id=1,
                phone="13000000007",
                name="会员7",
                balance=5,
                daily_meal_units=2,
                is_active=True,
                store_pickup=False,
            )
        )
        session.add(
            SfSameCityPush(
                store_id=1,
                delivery_date=date(2026, 6, 11),
                stop_id="stop-7",
                push_kind="delivery_sheet",
                shop_order_id="shop-7",
                error_code=0,
                request_snapshot={
                    "fulfillment_member_ids": [7],
                    "preview_row": {"subscription_pending_units": 1},
                },
            )
        )
        session.commit()
        yield session
    finally:
        session.close()
        engine.dispose()


def test_build_units_from_single_member_push(backfill_db: Session):
    units, stats = build_member_meal_units_from_sf_pushes(
        backfill_db, store_id=1, delivery_date=date(2026, 6, 11)
    )
    assert units.get(7) == 1
    assert stats["from_sf_pushes"] == 1


def test_upsert_overwrites(backfill_db: Session):
    upsert_delivery_sheet_units_snapshot(
        backfill_db,
        store_id=1,
        delivery_date=date(2026, 6, 11),
        member_units={7: 1},
        overwrite=True,
    )
    upsert_delivery_sheet_units_snapshot(
        backfill_db,
        store_id=1,
        delivery_date=date(2026, 6, 11),
        member_units={7: 2},
        overwrite=True,
    )
    backfill_db.commit()
    row = backfill_db.get(
        DeliverySheetPushUnitsSnapshot,
        {"store_id": 1, "delivery_date": date(2026, 6, 11)},
    )
    assert row is not None
    assert row.member_meal_units.get("7") == 2
