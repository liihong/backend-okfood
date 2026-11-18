"""08:50 自动推接驳单仅圈定午餐零售单，晚餐须手动推。"""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models.single_meal_order import SingleMealOrder
from app.services.order.single_meal_order_service import list_morning_auto_retail_order_ids


@pytest.fixture()
def smo_db() -> Session:
    engine = create_engine("sqlite://")

    @event.listens_for(engine, "connect")
    def _pragma(dbapi_connection, _record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=OFF")
        cursor.close()

    Base.metadata.create_all(engine, tables=[SingleMealOrder.__table__])
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


def _insert(
    db: Session,
    *,
    oid: int,
    meal_period: str,
    created_at: datetime,
) -> None:
    db.add(
        SingleMealOrder(
            id=oid,
            tenant_id=1,
            store_id=1,
            out_trade_no=f"smo{oid:06d}",
            member_id=100,
            routing_area="测试",
            amount_yuan="18.00",
            delivery_date=date(2026, 3, 18),
            meal_period=meal_period,
            pay_status="已支付",
            store_pickup=False,
            fulfillment_status="pending",
            created_at=created_at,
        )
    )
    db.commit()


def test_morning_auto_retail_ids_exclude_dinner(smo_db: Session) -> None:
    cutoff = datetime(2026, 3, 18, 8, 50, 0)
    before = cutoff - timedelta(minutes=5)
    _insert(smo_db, oid=1, meal_period="lunch", created_at=before)
    _insert(smo_db, oid=2, meal_period="dinner", created_at=before)

    ids = list_morning_auto_retail_order_ids(
        smo_db,
        store_id=1,
        delivery_date=date(2026, 3, 18),
        created_before=cutoff,
    )
    assert ids == [1]