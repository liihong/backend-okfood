"""待完善履约：缺起送日/地址的已入账会员不应显示为配送中。"""

from __future__ import annotations

from datetime import time

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


def _applied_member_without_start_date(db: Session, *, phone: str) -> Member:
    m = Member(
        tenant_id=1,
        store_id=1,
        phone=phone,
        name=phone,
        balance=6,
        meal_quota_total=6,
        plan_type=PlanType.WEEK.value,
        is_active=True,
        delivery_deferred=False,
        delivery_start_date=None,
    )
    db.add(m)
    db.flush()
    db.add(
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
    db.commit()
    db.refresh(m)
    return m


def test_lifecycle_shows_awaiting_setup_without_delivery_start_date(member_archive_db: Session) -> None:
    m = _applied_member_without_start_date(member_archive_db, phone="13800005001")

    view = resolve_member_lifecycle(member_archive_db, m)

    assert view.code == "awaiting_setup"
    assert view.label == "待完善"


def test_awaiting_setup_filter_includes_admin_applied_orders(member_archive_db: Session) -> None:
    _applied_member_without_start_date(member_archive_db, phone="13800005002")
    _applied_member_without_start_date(member_archive_db, phone="13800005003")

    count = _member_filter_count(member_archive_db, store_id=1, awaiting_setup_only=True)
    assert count == 2


def test_awaiting_setup_filter_excludes_paused_members(member_archive_db: Session) -> None:
    """主动暂停（delivery_deferred）不应出现在待完善筛选列表。"""
    m = Member(
        tenant_id=1,
        store_id=1,
        phone="13800006001",
        name="paused",
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

    count = _member_filter_count(member_archive_db, store_id=1, awaiting_setup_only=True)
    assert count == 0
