"""餐段卡资格：纯晚餐卡不进午餐大表，纯午餐卡不进晚餐大表。"""

from __future__ import annotations

from datetime import date, time

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models.member import Member
from app.models.enums import CardOrderPayStatus
from app.models.member_card_order import MemberCardOrder
from app.models.member_meal_period_state import MemberMealPeriodState
from app.models.store import Store
from app.models.tenant import Tenant
from app.services.meal_period.card_eligibility import (
    filter_members_for_sheet_view,
    member_entitled_meal_periods,
)


@pytest.fixture()
def eligibility_db() -> Session:
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
        # 纯晚餐卡会员
        session.add(
            Member(
                id=101,
                tenant_id=1,
                store_id=1,
                phone="13000000101",
                name="晚餐会员",
                balance=0,
                is_active=True,
                delivery_start_date=date(2026, 1, 1),
                store_pickup=False,
            )
        )
        session.add(
            MemberMealPeriodState(
                member_id=101,
                meal_period="dinner",
                daily_meal_units=1,
                balance=10,
                meal_quota_total=10,
            )
        )
        session.add(
            MemberCardOrder(
                id=1,
                tenant_id=1,
                store_id=1,
                member_id=101,
                card_kind="weekly",
                pay_channel="offline",
                pay_status=CardOrderPayStatus.PAID.value,
                applied_to_member=True,
                meal_periods_snapshot=["dinner"],
                created_by="test",
            )
        )
        # 纯午餐卡会员
        session.add(
            Member(
                id=102,
                tenant_id=1,
                store_id=1,
                phone="13000000102",
                name="午餐会员",
                balance=10,
                is_active=True,
                store_pickup=False,
            )
        )
        session.add(
            MemberCardOrder(
                id=2,
                tenant_id=1,
                store_id=1,
                member_id=102,
                card_kind="weekly",
                pay_channel="offline",
                pay_status=CardOrderPayStatus.PAID.value,
                applied_to_member=True,
                meal_periods_snapshot=["lunch"],
                created_by="test",
            )
        )
        session.commit()
        yield session
    finally:
        session.close()
        engine.dispose()


def test_member_entitled_meal_periods_from_orders(eligibility_db: Session):
    assert member_entitled_meal_periods(eligibility_db, 101) == frozenset({"dinner"})
    assert member_entitled_meal_periods(eligibility_db, 102) == frozenset({"lunch"})


def test_filter_lunch_excludes_pure_dinner(eligibility_db: Session):
    members = [
        eligibility_db.get(Member, 101),
        eligibility_db.get(Member, 102),
    ]
    out = filter_members_for_sheet_view(eligibility_db, members, "lunch")
    ids = {m.id for m in out}
    assert 102 in ids
    assert 101 not in ids


def test_filter_dinner_excludes_pure_lunch(eligibility_db: Session):
    members = [
        eligibility_db.get(Member, 101),
        eligibility_db.get(Member, 102),
    ]
    out = filter_members_for_sheet_view(eligibility_db, members, "dinner")
    ids = {m.id for m in out}
    assert 101 in ids
    assert 102 not in ids