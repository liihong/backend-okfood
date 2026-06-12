"""顺丰取消后：不占用 already_pushed、可重推、大表仍可见取消单会员。"""

from datetime import date, datetime, time

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models.sf_same_city_push import SfSameCityPush
from app.models.store import Store
from app.models.tenant import Tenant
from app.services.delivery_day_lock_service import sf_cancelled_sheet_member_ids_for_delivery_date
from app.services.sf_same_city_service import (
    _active_success_push_stop_ids_set,
    _cancelled_success_push_id_by_stop,
    _sf_push_row_is_cancelled,
    _successful_push_stop_ids_set,
)


@pytest.fixture()
def sf_cancel_db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    tables = [
        Tenant.__table__,
        Store.__table__,
        SfSameCityPush.__table__,
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


def test_active_success_stop_ids_exclude_cancelled(sf_cancel_db: Session):
    d = date(2026, 6, 12)
    sf_cancel_db.add_all(
        [
            SfSameCityPush(
                store_id=1,
                delivery_date=d,
                stop_id="stop-active",
                push_kind="delivery_sheet",
                shop_order_id="shop-1",
                error_code=0,
            ),
            SfSameCityPush(
                store_id=1,
                delivery_date=d,
                stop_id="stop-cancelled",
                push_kind="delivery_sheet",
                shop_order_id="shop-2",
                error_code=0,
                merchant_cancel_requested_at=datetime(2026, 6, 12, 9, 0, 0),
            ),
        ]
    )
    sf_cancel_db.commit()

    all_ok = _successful_push_stop_ids_set(sf_cancel_db, store_id=1, d=d)
    active = _active_success_push_stop_ids_set(sf_cancel_db, store_id=1, d=d)
    assert all_ok == {"stop-active", "stop-cancelled"}
    assert active == {"stop-active"}


def test_cancelled_success_push_id_by_stop(sf_cancel_db: Session):
    d = date(2026, 6, 12)
    row = SfSameCityPush(
        store_id=1,
        delivery_date=d,
        stop_id="stop-x",
        push_kind="delivery_sheet",
        shop_order_id="shop-x",
        error_code=0,
        merchant_cancel_requested_at=datetime(2026, 6, 12, 10, 0, 0),
        request_snapshot={"fulfillment_member_ids": [977]},
    )
    sf_cancel_db.add(row)
    sf_cancel_db.commit()

    mapping = _cancelled_success_push_id_by_stop(sf_cancel_db, store_id=1, d=d, stop_ids={"stop-x"})
    assert mapping == {"stop-x": int(row.id)}
    assert _sf_push_row_is_cancelled(row)


def test_cancelled_sheet_member_ids_union(sf_cancel_db: Session):
    d = date(2026, 6, 12)
    sf_cancel_db.add(
        SfSameCityPush(
            store_id=1,
            delivery_date=d,
            stop_id="stop-late",
            push_kind="delivery_sheet",
            shop_order_id="shop-late",
            error_code=0,
            merchant_cancel_requested_at=datetime(2026, 6, 12, 11, 0, 0),
            request_snapshot={"fulfillment_member_ids": [977, 978]},
        )
    )
    sf_cancel_db.commit()

    mids = sf_cancelled_sheet_member_ids_for_delivery_date(sf_cancel_db, store_id=1, delivery_date=d)
    assert mids == frozenset({977, 978})


def test_merged_home_member_ids_include_cancelled_not_in_frozen(sf_cancel_db: Session):
    d = date(2026, 6, 12)
    sf_cancel_db.add(
        SfSameCityPush(
            store_id=1,
            delivery_date=d,
            stop_id="stop-late",
            push_kind="delivery_sheet",
            shop_order_id="shop-late",
            error_code=0,
            merchant_cancel_requested_at=datetime(2026, 6, 12, 11, 0, 0),
            request_snapshot={"fulfillment_member_ids": [977]},
        )
    )
    sf_cancel_db.commit()

    cancelled_mids = sf_cancelled_sheet_member_ids_for_delivery_date(
        sf_cancel_db, store_id=1, delivery_date=d
    )
    assert 977 in cancelled_mids

    frozen_base = frozenset({1, 2})
    merged = set(frozen_base) | set(cancelled_mids)
    assert merged >= {1, 2, 977}
