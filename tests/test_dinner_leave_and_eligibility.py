"""晚餐分餐段修复：请假隔离、资格筛选、全天请假、激活态。"""

from __future__ import annotations

from datetime import date, time

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models.enums import LeaveType, MealPeriod
from app.models.member import Member
from app.models.member_address import MemberAddress
from app.models.member_card_order import MemberCardOrder
from app.models.member_meal_period_state import MemberMealPeriodState
from app.models.enums import CardOrderPayStatus
from app.models.store import Store
from app.models.tenant import Tenant
from app.services.dinner.eligibility import eligible_members_for_dinner_delivery
from app.services.meal_period.balance import sync_member_is_active_from_period_balances
from app.services.member.member_service import leave_request


@pytest.fixture()
def dinner_leave_db_base() -> Session:
    engine = create_engine("sqlite:///:memory:")
    tables = [
        Tenant.__table__,
        Store.__table__,
        Member.__table__,
        MemberAddress.__table__,
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
                id=301,
                tenant_id=1,
                store_id=1,
                phone="13000000301",
                name="双餐段",
                balance=10,
                is_active=True,
                delivery_start_date=date(2026, 6, 1),
                store_pickup=False,
                is_leaved_tomorrow=False,
                leave_range_start=date(2026, 7, 1),
                leave_range_end=date(2026, 7, 5),
            )
        )
        session.add(
            MemberMealPeriodState(
                member_id=301,
                meal_period=MealPeriod.DINNER.value,
                daily_meal_units=1,
                balance=8,
                meal_quota_total=8,
            )
        )
        session.add(
            MemberCardOrder(
                member_id=301,
                tenant_id=1,
                store_id=1,
                card_kind="周卡",
                pay_channel="微信",
                pay_status=CardOrderPayStatus.PAID.value,
                applied_to_member=True,
                meal_periods_snapshot=["lunch", "dinner"],
                created_by="test",
            )
        )
        session.commit()
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture()
def dinner_leave_db(dinner_leave_db_base: Session, monkeypatch):
    monkeypatch.setattr(
        "app.services.meal_period.coordinated_leave.record_member_operation",
        lambda *a, **k: None,
    )
    monkeypatch.setattr(
        "app.services.meal_period.coordinated_leave._to_member_out",
        lambda db, m, addr: m,
    )
    monkeypatch.setattr(
        "app.services.meal_period.coordinated_leave.get_default_address",
        lambda db, mid: None,
    )
    return dinner_leave_db_base


def test_lunch_leave_does_not_block_dinner_eligibility(dinner_leave_db: Session):
    """午餐区间请假不应阻止进入晚餐大表。"""
    d = date(2026, 7, 3)
    members, _ = eligible_members_for_dinner_delivery(
        dinner_leave_db, delivery_date=d, store_id=1
    )
    assert any(int(m.id) == 301 for m in members)


def test_dinner_only_member_activates_without_delivery_start_date(dinner_leave_db: Session):
    """纯晚餐有余次时，即使 delivery_start_date 为空也应激活。"""
    m = dinner_leave_db.get(Member, 301)
    assert m is not None
    m.balance = 0
    m.delivery_start_date = None
    m.is_active = False
    dinner_leave_db.commit()
    sync_member_is_active_from_period_balances(dinner_leave_db, m)
    assert m.is_active is True


def test_all_day_leave_writes_both_pools(dinner_leave_db: Session, monkeypatch):
    """全天请假应同时写入午餐与晚餐请假字段。"""
    m = dinner_leave_db.get(Member, 301)
    assert m is not None
    m.leave_range_start = None
    m.leave_range_end = None
    dinner_leave_db.commit()

    monkeypatch.setattr(
        "app.services.meal_period.coordinated_leave._try_notify_leave_cancel_after_prep",
        lambda *a, **k: None,
    )

    leave_request(
        dinner_leave_db,
        301,
        LeaveType.TOMORROW,
        None,
        None,
        source="admin",
        meal_period="all",
    )
    dinner_leave_db.refresh(m)
    row = dinner_leave_db.get(
        MemberMealPeriodState,
        {"member_id": 301, "meal_period": MealPeriod.DINNER.value},
    )
    assert m.is_leaved_tomorrow is True
    assert row is not None
    assert row.is_leaved_tomorrow is True


def test_dinner_only_leave_does_not_touch_lunch_fields(dinner_leave_db: Session, monkeypatch):
    """晚餐单餐段请假不影响午餐 members 表请假字段。"""
    m = dinner_leave_db.get(Member, 301)
    assert m is not None
    m.is_leaved_tomorrow = False
    m.leave_range_start = None
    m.leave_range_end = None
    dinner_leave_db.commit()

    monkeypatch.setattr(
        "app.services.meal_period.coordinated_leave.leave_target_periods",
        lambda db, m, scope: frozenset({MealPeriod.DINNER.value}),
    )
    monkeypatch.setattr(
        "app.services.meal_period.coordinated_leave._try_notify_leave_cancel_after_prep",
        lambda *a, **k: None,
    )

    leave_request(
        dinner_leave_db,
        301,
        LeaveType.TOMORROW,
        None,
        None,
        source="admin",
        meal_period="dinner",
    )
    dinner_leave_db.refresh(m)
    row = dinner_leave_db.get(
        MemberMealPeriodState,
        {"member_id": 301, "meal_period": MealPeriod.DINNER.value},
    )
    assert m.is_leaved_tomorrow is False
    assert row is not None
    assert row.is_leaved_tomorrow is True
