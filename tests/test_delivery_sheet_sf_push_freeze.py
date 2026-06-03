"""大表顺丰推单后冻结（不含假请假顺延）。"""

from datetime import date, time

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models.sf_same_city_push import SfSameCityPush
from app.models.store import Store
from app.models.tenant import Tenant
from app.services.delivery_day_lock_service import (
    has_delivery_sheet_sf_push_on_date,
    is_delivery_day_sheet_frozen_after_sf_push,
)


@pytest.fixture()
def freeze_db() -> Session:
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


def test_has_push_and_frozen(freeze_db: Session):
    d = date(2026, 6, 3)
    assert not has_delivery_sheet_sf_push_on_date(freeze_db, store_id=1, delivery_date=d)
    freeze_db.add(
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
    freeze_db.commit()
    assert has_delivery_sheet_sf_push_on_date(freeze_db, store_id=1, delivery_date=d)
    assert is_delivery_day_sheet_frozen_after_sf_push(
        freeze_db, store_id=1, delivery_date=d
    )
