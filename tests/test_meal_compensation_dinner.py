"""补餐赔付：晚餐池入账与 balance_logs.meal_period 隔离。"""

from __future__ import annotations

from datetime import date, time

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models.balance_log import BalanceLog
from app.models.enums import MealPeriod
from app.models.member import Member
from app.models.member_meal_period_state import MemberMealPeriodState
from app.models.member_operation_log import MemberOperationLog
from app.models.store import Store
from app.models.tenant import Tenant
from app.schemas.admin import MemberMealCompensationIn
from app.services.admin.member_meal_compensation_service import admin_member_meal_compensation


@pytest.fixture()
def comp_dinner_db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    tables = [
        Tenant.__table__,
        Store.__table__,
        Member.__table__,
        MemberMealPeriodState.__table__,
        BalanceLog.__table__,
        MemberOperationLog.__table__,
    ]
    Base.metadata.create_all(engine, tables=tables)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = SessionLocal()
    try:
        session.add(Tenant(id=1, name="t", is_active=True))
        session.add(
            Store(
                id=1,
                tenant_id=1,
                name="s",
                leave_deadline_time=time(21, 0),
                is_active=True,
            )
        )
        yield session
    finally:
        session.close()
        engine.dispose()


def test_dinner_meal_compensation_credits_dinner_pool(comp_dinner_db: Session) -> None:
    db = comp_dinner_db
    m = Member(
        tenant_id=1,
        store_id=1,
        phone="13800000999",
        name="晚餐补餐",
        balance=0,
        is_active=True,
        delivery_start_date=date(2026, 1, 1),
    )
    db.add(m)
    db.flush()
    db.add(
        MemberMealPeriodState(
            member_id=int(m.id),
            meal_period=MealPeriod.DINNER.value,
            daily_meal_units=1,
            balance=2,
            meal_quota_total=5,
        )
    )
    db.commit()

    out = admin_member_meal_compensation(
        db,
        member_id=int(m.id),
        store_id=1,
        body=MemberMealCompensationIn(meal_units=2, meal_period="dinner", remark="测试"),
        operator="admin:test",
    )
    assert out.meal_period == "dinner"
    assert out.balance_before == 2
    assert out.balance_after == 4
    assert int(m.balance or 0) == 0

    row = db.scalar(
        select(BalanceLog).where(
            BalanceLog.member_id == int(m.id),
            BalanceLog.meal_period == MealPeriod.DINNER.value,
        )
    )
    assert row is not None
    assert int(row.change) == 2
