"""会员档案库「已暂停」筛选：不应包含已退卡退款或次数用尽的会员。"""

from __future__ import annotations

from datetime import date, time

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.timeutil import beijing_now_naive
from app.db.base import Base
from app.models.delivery_log import DeliveryLog
from app.models.enums import CardOrderPayStatus, PlanType
from app.models.member import Member
from app.models.member_address import MemberAddress
from app.models.member_card_order import MemberCardOrder
from app.models.member_meal_period_state import MemberMealPeriodState
from app.models.store import Store
from app.models.tenant import Tenant
from app.services.admin.admin_service import _member_filter_count


@pytest.fixture()
def member_archive_db() -> Session:
    """档案库筛选所需最小表集。"""
    engine = create_engine("sqlite:///:memory:")
    tables = [
        Tenant.__table__,
        Store.__table__,
        Member.__table__,
        MemberAddress.__table__,
        MemberCardOrder.__table__,
        DeliveryLog.__table__,
        MemberMealPeriodState.__table__,
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


def _week_member(
    db: Session,
    *,
    phone: str,
    delivery_deferred: bool,
    balance: int = 3,
    membership_refunded_at=None,
) -> Member:
    m = Member(
        tenant_id=1,
        store_id=1,
        phone=phone,
        name=phone,
        balance=balance,
        meal_quota_total=6,
        plan_type=PlanType.WEEK.value,
        is_active=False,
        delivery_deferred=delivery_deferred,
        delivery_start_date=date(2026, 1, 1),
        membership_refunded_at=membership_refunded_at,
    )
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


def test_paused_filter_excludes_refunded_members(member_archive_db: Session) -> None:
    paused = _week_member(member_archive_db, phone="13800001001", delivery_deferred=True)
    _week_member(
        member_archive_db,
        phone="13800001002",
        delivery_deferred=True,
        membership_refunded_at=beijing_now_naive(),
    )

    count = _member_filter_count(member_archive_db, store_id=1, delivery_deferred_only=True)
    assert count == 1
    assert paused.phone == "13800001001"


def test_paused_filter_excludes_zero_balance_members(member_archive_db: Session) -> None:
    """次数用尽但 delivery_deferred 仍为 true 的档案不应计入已暂停。"""
    _week_member(
        member_archive_db,
        phone="13800002001",
        delivery_deferred=True,
        balance=0,
    )
    _week_member(
        member_archive_db,
        phone="13800002002",
        delivery_deferred=True,
        balance=2,
    )

    count = _member_filter_count(member_archive_db, store_id=1, delivery_deferred_only=True)
    assert count == 1


def test_paused_filter_excludes_awaiting_setup_members(member_archive_db: Session) -> None:
    """delivery_deferred=true 但 lifecycle 会判待完善（缺起送日、从未送达）的不应计入已暂停。"""
    m = Member(
        tenant_id=1,
        store_id=1,
        phone="13800007001",
        name="setup",
        balance=6,
        meal_quota_total=6,
        plan_type=PlanType.WEEK.value,
        is_active=False,
        delivery_deferred=True,
        delivery_start_date=None,
    )
    member_archive_db.add(m)
    member_archive_db.flush()
    member_archive_db.add(
        MemberCardOrder(
            tenant_id=1,
            store_id=1,
            member_id=int(m.id),
            card_kind=PlanType.WEEK.value,
            pay_channel="微信",
            pay_status=CardOrderPayStatus.PAID.value,
            applied_to_member=True,
            created_by="admin_test",
        )
    )
    member_archive_db.commit()

    count = _member_filter_count(member_archive_db, store_id=1, delivery_deferred_only=True)
    assert count == 0


def test_paused_filter_excludes_on_leave_members(member_archive_db: Session) -> None:
    """请假中会员不应出现在已暂停筛选（与 lifecycle 主状态互斥）。"""
    from datetime import timedelta

    from app.core.timeutil import today_shanghai

    today = today_shanghai()
    _week_member(
        member_archive_db,
        phone="13800007002",
        delivery_deferred=True,
        balance=6,
    )
    member_archive_db.add(
        Member(
            tenant_id=1,
            store_id=1,
            phone="13800007003",
            name="leave",
            balance=6,
            meal_quota_total=6,
            plan_type=PlanType.WEEK.value,
            is_active=False,
            delivery_deferred=True,
            delivery_start_date=date(2026, 1, 1),
            leave_range_start=today - timedelta(days=1),
            leave_range_end=today + timedelta(days=5),
        )
    )
    member_archive_db.commit()

    count = _member_filter_count(member_archive_db, store_id=1, delivery_deferred_only=True)
    assert count == 1
