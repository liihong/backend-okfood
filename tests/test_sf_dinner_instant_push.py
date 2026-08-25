"""晚餐配送大表及时单：立即推单、餐段隔离、不占用午餐停靠点。"""

from __future__ import annotations

from datetime import date, datetime, time

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models.enums import MealPeriod
from app.models.sf_same_city_push import SfSameCityPush
from app.models.store import Store
from app.models.tenant import Tenant
from app.schemas.admin import SfSameCityPreviewRow, SfSameCityPushIn, SfSameCityPushOut
from app.services.delivery.sf_order_fulfillment_service import (
    SF_PUSH_KIND_DELIVERY_SHEET,
    SF_PUSH_KIND_DINNER_DELIVERY_SHEET,
)
from app.services.delivery.sf_same_city_service import (
    _active_success_push_stop_ids_set,
    push_sf_dinner_same_city_instant,
)


@pytest.fixture()
def persist_db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    tables = [Tenant.__table__, Store.__table__, SfSameCityPush.__table__]
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
                sf_retail_push_shop_id="6282826746497",
                sf_retail_push_shop_type=1,
            )
        )
        session.flush()
        yield session
    finally:
        session.close()
        engine.dispose()


def _preview_row(*, push_immediately: bool = False) -> SfSameCityPreviewRow:
    return SfSameCityPreviewRow(
        stop_id="stop-dinner-001",
        group_area="城南",
        address_line="测试路 1 号",
        pickup_phone="13800000000",
        map_location_text="测试路 1 号",
        door_detail="",
        recv_address="测试路 1 号",
        recv_building="",
        recv_lng=113.8,
        recv_lat=35.2,
        recv_name="张三",
        recv_phone="13800001111",
        product_category="餐品",
        weight_kg=0.5,
        push_immediately=push_immediately,
        expect_delivery_at=datetime(2026, 8, 25, 18, 0, 0),
        remark=None,
        is_direct=False,
        vehicle_type="小轿车",
        is_insured=False,
        goods_value_yuan=None,
        subscription_pending_units=1,
        single_meal_count=0,
        selected=True,
        already_pushed=False,
    )


def test_lunch_success_does_not_block_dinner_same_stop(persist_db: Session) -> None:
    d = date(2026, 8, 25)
    persist_db.add(
        SfSameCityPush(
            store_id=1,
            delivery_date=d,
            stop_id="same-addr-stop",
            shop_order_id="OKF-LUNCH-001",
            sf_order_id="SF000001",
            error_code=0,
            push_kind=SF_PUSH_KIND_DELIVERY_SHEET,
        )
    )
    persist_db.commit()
    lunch = _active_success_push_stop_ids_set(
        persist_db, store_id=1, d=d, push_kind=SF_PUSH_KIND_DELIVERY_SHEET
    )
    dinner = _active_success_push_stop_ids_set(
        persist_db, store_id=1, d=d, push_kind=SF_PUSH_KIND_DINNER_DELIVERY_SHEET
    )
    assert "same-addr-stop" in lunch
    assert "same-addr-stop" not in dinner


def test_push_sf_dinner_same_city_instant_forces_immediate_and_instant_shop(
    persist_db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    import app.services.delivery.sf_same_city_service as svc

    captured: dict = {}

    def _fake_push(db, body, **kwargs):
        captured["body"] = body
        captured["kwargs"] = kwargs
        return SfSameCityPushOut(results=[], hint=None)

    monkeypatch.setattr(svc, "push_sf_same_city", _fake_push)

    item = _preview_row(push_immediately=False)
    push_sf_dinner_same_city_instant(
        persist_db,
        SfSameCityPushIn(delivery_date=date(2026, 8, 25), rows=[item]),
        store_id=1,
    )
    assert captured["kwargs"]["use_instant_shop"] is True
    assert captured["kwargs"]["push_kind"] == SF_PUSH_KIND_DINNER_DELIVERY_SHEET
    assert captured["kwargs"]["meal_period"] == MealPeriod.DINNER.value
    assert captured["kwargs"]["store_id"] == 1
    forced = captured["body"].rows[0]
    assert forced.push_immediately is True
    assert forced.expect_delivery_at is None
