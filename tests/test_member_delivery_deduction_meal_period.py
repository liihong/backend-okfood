"""消费记录按餐段拆开：同日午餐、晚餐各一条，标明 meal_period。"""

from __future__ import annotations

from datetime import date, datetime, time

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models.balance_log import BalanceLog
from app.models.delivery_log import DeliveryLog
from app.models.enums import BalanceReason, DeliveryStatus, MealPeriod, PlanType
from app.models.member import Member
from app.models.store import Store
from app.models.tenant import Tenant
from app.services.admin.member_delivery_deduction_service import (
    _merged_consumption_items,
    delivery_meal_units_by_date,
)

DAY = date(2026, 8, 28)


@pytest.fixture()
def deduct_db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    tables = [
        Tenant.__table__,
        Store.__table__,
        Member.__table__,
        DeliveryLog.__table__,
        BalanceLog.__table__,
    ]
    Base.metadata.create_all(engine, tables=tables)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = SessionLocal()
    try:
        session.add_all(
            [
                Tenant(id=1, name="测试租户", is_active=True),
                Store(id=1, tenant_id=1, name="测试门店", leave_deadline_time=time(21, 0), is_active=True),
            ]
        )
        session.flush()
        yield session
    finally:
        session.close()
        engine.dispose()


def _member(db: Session) -> Member:
    m = Member(
        tenant_id=1,
        store_id=1,
        phone="13993175678",
        name="郑先生",
        balance=10,
        daily_meal_units=1,
        meal_quota_total=10,
        plan_type=PlanType.MONTH.value,
        is_active=True,
        delivery_start_date=DAY,
        delivery_deferred=False,
        store_pickup=False,
    )
    db.add(m)
    db.flush()
    return m


def _delivered(
    db: Session,
    member: Member,
    *,
    meal_period: str,
    when: datetime,
    change: int = -1,
) -> None:
    db.add(
        DeliveryLog(
            member_id=int(member.id),
            delivery_date=DAY,
            meal_period=meal_period,
            status=DeliveryStatus.DELIVERED.value,
            courier_id=None,
            created_at=when,
            updated_at=when,
        )
    )
    db.add(
        BalanceLog(
            member_id=int(member.id),
            meal_period=meal_period,
            change=change,
            reason=BalanceReason.DELIVERY.value,
            operator="test",
            created_at=when,
        )
    )
    db.flush()


def test_same_day_lunch_and_dinner_are_two_records(deduct_db: Session) -> None:
    m = _member(deduct_db)
    _delivered(deduct_db, m, meal_period=MealPeriod.LUNCH.value, when=datetime(2026, 8, 28, 11, 0, 0))
    _delivered(deduct_db, m, meal_period=MealPeriod.DINNER.value, when=datetime(2026, 8, 28, 11, 1, 0))
    items = _merged_consumption_items(deduct_db, int(m.id))
    sub = [x for x in items if x.deduction_kind == "subscription"]
    assert len(sub) == 2
    assert sub[0].meal_period == MealPeriod.DINNER.value
    assert sub[0].meal_units == 1
    assert sub[1].meal_period == MealPeriod.LUNCH.value
    assert sub[1].meal_units == 1
    assert sub[0].delivery_date == DAY
    assert sub[1].delivery_date == DAY


def test_same_day_units_sum_for_refund_map(deduct_db: Session) -> None:
    m = _member(deduct_db)
    _delivered(deduct_db, m, meal_period=MealPeriod.LUNCH.value, when=datetime(2026, 8, 28, 11, 0, 0))
    _delivered(deduct_db, m, meal_period=MealPeriod.DINNER.value, when=datetime(2026, 8, 28, 11, 1, 0))
    by_date = delivery_meal_units_by_date(deduct_db, int(m.id))
    assert by_date[DAY] == 2
