"""顺丰推单失败重推：覆盖原记录，不新增行。"""

from datetime import date, time

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models.sf_same_city_push import SfSameCityPush
from app.models.store import Store
from app.models.tenant import Tenant
from app.services.delivery.sf_same_city_service import _failed_push_id_by_stop


@pytest.fixture()
def sf_push_db() -> Session:
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


def test_failed_push_id_by_stop_picks_latest(sf_push_db: Session):
    d = date(2026, 6, 12)
    sf_push_db.add_all(
        [
            SfSameCityPush(
                store_id=1,
                delivery_date=d,
                stop_id="stop-a",
                push_kind="delivery_sheet",
                shop_order_id="shop-a-1",
                error_code=-1,
                error_msg="余额不足",
            ),
            SfSameCityPush(
                store_id=1,
                delivery_date=d,
                stop_id="stop-a",
                push_kind="delivery_sheet",
                shop_order_id="shop-a-2",
                error_code=-1,
                error_msg="余额不足",
            ),
            SfSameCityPush(
                store_id=1,
                delivery_date=d,
                stop_id="stop-b",
                push_kind="delivery_sheet",
                shop_order_id="shop-b-1",
                error_code=0,
                error_msg="",
            ),
        ]
    )
    sf_push_db.commit()

    mapping = _failed_push_id_by_stop(
        sf_push_db, store_id=1, d=d, stop_ids={"stop-a", "stop-b"}
    )
    latest_a = sf_push_db.scalar(
        select(func.max(SfSameCityPush.id)).where(
            SfSameCityPush.stop_id == "stop-a",
            SfSameCityPush.error_code != 0,
        )
    )
    assert mapping == {"stop-a": int(latest_a)}
    assert "stop-b" not in mapping
