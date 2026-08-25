"""会员档案库「正常配送中」筛选：与 lifecycle DELIVERING 且无请假叠层一致。"""

from __future__ import annotations

from datetime import date, time, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.timeutil import beijing_now_naive, today_shanghai
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
from app.services.member.member_lifecycle_service import resolve_member_lifecycle


@pytest.fixture()
def member_archive_db() -> Session:
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
    balance: int = 6,
    is_active: bool = True,
    delivery_deferred: bool = False,
    delivery_start_date: date | None = date(2026, 1, 1),
    membership_refunded_at=None,
    leave_range_start: date | None = None,
    leave_range_end: date | None = None,
) -> Member:
    m = Member(
        tenant_id=1,
        store_id=1,
        phone=phone,
        name=phone,
        balance=balance,
        meal_quota_total=6,
        plan_type=PlanType.WEEK.value,
        is_active=is_active,
        delivery_deferred=delivery_deferred,
        delivery_start_date=delivery_start_date,
        membership_refunded_at=membership_refunded_at,
        leave_range_start=leave_range_start,
        leave_range_end=leave_range_end,
    )
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


def _count_delivering(db: Session) -> int:
    return _member_filter_count(db, store_id=1, delivering_only=True)


def test_delivering_filter_includes_active_members(member_archive_db: Session) -> None:
    m = _week_member(member_archive_db, phone="13800008001", balance=6)
    view = resolve_member_lifecycle(member_archive_db, m)
    assert view.label == "正常配送中"
    assert _count_delivering(member_archive_db) == 1


def test_delivering_filter_excludes_renew_pending(member_archive_db: Session) -> None:
    """午餐余次 <= 低余额阈值的待续费不应计入正常配送中。"""
    _week_member(member_archive_db, phone="13800008002", balance=2)
    _week_member(member_archive_db, phone="13800008003", balance=6)
    assert _count_delivering(member_archive_db) == 1


def test_delivering_filter_excludes_on_leave(member_archive_db: Session) -> None:
    today = today_shanghai()
    _week_member(member_archive_db, phone="13800008004", balance=6)
    _week_member(
        member_archive_db,
        phone="13800008005",
        balance=6,
        leave_range_start=today - timedelta(days=1),
        leave_range_end=today + timedelta(days=3),
    )
    assert _count_delivering(member_archive_db) == 1


def test_delivering_filter_excludes_paused(member_archive_db: Session) -> None:
    _week_member(
        member_archive_db,
        phone="13800008006",
        balance=6,
        is_active=False,
        delivery_deferred=True,
    )
    _week_member(member_archive_db, phone="13800008007", balance=6)
    assert _count_delivering(member_archive_db) == 1


def test_delivering_filter_excludes_awaiting_setup(member_archive_db: Session) -> None:
    """缺起送日、从未送达的已入账会员属待完善，不计入正常配送中。"""
    m = Member(
        tenant_id=1,
        store_id=1,
        phone="13800008008",
        name="setup",
        balance=6,
        meal_quota_total=6,
        plan_type=PlanType.WEEK.value,
        is_active=True,
        delivery_deferred=False,
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
    assert _count_delivering(member_archive_db) == 0


def test_delivering_filter_excludes_never_opened_and_refunded(member_archive_db: Session) -> None:
    _week_member(
        member_archive_db,
        phone="13800008009",
        balance=6,
        is_active=False,
        delivery_start_date=None,
    )
    _week_member(
        member_archive_db,
        phone="13800008010",
        balance=6,
        membership_refunded_at=beijing_now_naive(),
    )
    assert _count_delivering(member_archive_db) == 0
