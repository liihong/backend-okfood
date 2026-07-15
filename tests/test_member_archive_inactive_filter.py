"""会员档案库「未开卡」筛选：与 lifecycle NEVER_OPENED 口径一致。"""

from __future__ import annotations

from datetime import date, time

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

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
    is_active: bool = False,
    delivery_deferred: bool = False,
    delivery_start_date: date | None = None,
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
    )
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


def test_inactive_filter_excludes_expired_members(member_archive_db: Session) -> None:
    """次数用尽（已过期）不应出现在未开卡列表。"""
    _week_member(
        member_archive_db,
        phone="13800003001",
        balance=0,
        delivery_start_date=date(2026, 5, 4),
    )
    _week_member(member_archive_db, phone="13800003002", balance=6)

    count = _member_filter_count(member_archive_db, store_id=1, inactive_only=True)
    assert count == 1


def test_inactive_filter_excludes_applied_card_order_members(member_archive_db: Session) -> None:
    """已入账开卡工单的会员（配送中等）不应出现在未开卡列表。"""
    applied = _week_member(member_archive_db, phone="13800004001", balance=6)
    never_opened = _week_member(member_archive_db, phone="13800004002", balance=3)
    member_archive_db.add(
        MemberCardOrder(
            tenant_id=1,
            store_id=1,
            member_id=int(applied.id),
            card_kind=PlanType.WEEK.value,
            pay_channel="微信",
            pay_status=CardOrderPayStatus.PAID.value,
            applied_to_member=True,
            created_by="admin_test",
        )
    )
    member_archive_db.commit()

    count = _member_filter_count(member_archive_db, store_id=1, inactive_only=True)
    assert count == 1
    assert never_opened.phone == "13800004002"
