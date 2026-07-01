"""备餐锁窗：按目标餐段阻断，不影响无关餐段自助请假。"""

from __future__ import annotations

from datetime import date, datetime, time

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models.enums import CardOrderPayStatus, MealPeriod
from app.models.member import Member
from app.models.member_card_order import MemberCardOrder
from app.models.member_meal_period_state import MemberMealPeriodState
from app.models.store import Store
from app.models.tenant import Tenant
from app.services.member.leave import guard_miniprogram_leave_prep_window


@pytest.fixture()
def prep_db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    tables = [
        Tenant.__table__,
        Store.__table__,
        Member.__table__,
        MemberCardOrder.__table__,
        MemberMealPeriodState.__table__,
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
        session.add(
            Member(
                id=601,
                tenant_id=1,
                store_id=1,
                phone="13000000601",
                name="纯晚",
                balance=0,
                is_active=True,
                delivery_start_date=date(2026, 6, 1),
                store_pickup=False,
            )
        )
        session.add(
            MemberMealPeriodState(
                member_id=601,
                meal_period=MealPeriod.DINNER.value,
                daily_meal_units=1,
                balance=8,
                meal_quota_total=8,
            )
        )
        session.add(
            MemberCardOrder(
                member_id=601,
                tenant_id=1,
                store_id=1,
                card_kind="周卡",
                pay_channel="微信",
                pay_status=CardOrderPayStatus.PAID.value,
                applied_to_member=True,
                meal_periods_snapshot=["dinner"],
                created_by="test",
            )
        )
        session.commit()
        yield session
    finally:
        session.close()
        engine.dispose()


def test_dinner_leave_not_blocked_when_only_lunch_on_prep_schedule(
    prep_db: Session, monkeypatch
) -> None:
    """锁窗内、会员仅晚餐应履约：改晚餐请假不应被午餐备餐锁误伤（若不在午餐日程）。"""
    m = prep_db.get(Member, 601)
    assert m is not None
    # 21:30 — 备餐锁窗内
    locked_now = datetime(2026, 6, 10, 21, 30, 0)
    monkeypatch.setattr(
        "app.services.member.leave.is_miniprogram_leave_prep_locked",
        lambda **_: True,
    )
    monkeypatch.setattr(
        "app.services.meal_period.lunch_schedule.member_on_lunch_delivery_schedule",
        lambda *a, **k: False,
    )
    monkeypatch.setattr(
        "app.services.dinner.schedule.member_on_dinner_delivery_schedule",
        lambda *a, **k: False,
    )
    # 不在任一餐段日程 → 不应阻断
    guard_miniprogram_leave_prep_window(
        prep_db, m, now=locked_now, leave_meal_period=MealPeriod.DINNER.value
    )


def test_legacy_prep_guard_blocks_without_meal_period(prep_db: Session, monkeypatch) -> None:
    m = prep_db.get(Member, 601)
    assert m is not None
    locked_now = datetime(2026, 6, 10, 21, 30, 0)
    monkeypatch.setattr(
        "app.services.member.leave.is_miniprogram_leave_prep_locked",
        lambda **_: True,
    )
    with pytest.raises(HTTPException) as exc:
        guard_miniprogram_leave_prep_window(prep_db, m, now=locked_now)
    assert exc.value.status_code == 400
