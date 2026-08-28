"""午晚餐大表：纯午餐已送达会员不得被 extra_delivered 补回。"""

from __future__ import annotations

from datetime import date, time
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models.delivery_log import DeliveryLog
from app.models.enums import (
    CardOrderPayStatus,
    CardPayChannel,
    DeliverySheetView,
    DeliveryStatus,
    MealPeriod,
    PlanType,
)
from app.models.member import Member
from app.models.member_address import MemberAddress
from app.models.member_card_order import MemberCardOrder
from app.models.member_meal_period_state import MemberMealPeriodState
from app.models.membership_card_template import MembershipCardTemplate
from app.models.store import Store
from app.models.tenant import Tenant
from app.services.delivery.delivery_sheet_service import _merge_extra_delivered_for_sheet_view
from app.services.meal_period.card_eligibility import filter_member_groups_for_sheet_view

# 周五，订阅履约日
DELIVERY_DAY = date(2026, 8, 28)
_tpl_id = 0


def _next_tpl_id() -> int:
    global _tpl_id
    _tpl_id += 1
    return _tpl_id


@pytest.fixture()
def sheet_db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    tables = [
        Tenant.__table__,
        Store.__table__,
        Member.__table__,
        MemberAddress.__table__,
        MembershipCardTemplate.__table__,
        MemberCardOrder.__table__,
        MemberMealPeriodState.__table__,
        DeliveryLog.__table__,
    ]
    Base.metadata.create_all(engine, tables=tables)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = SessionLocal()
    try:
        session.add_all(
            [
                Tenant(id=1, name="测试租户", is_active=True),
                Store(
                    id=1,
                    tenant_id=1,
                    name="测试门店",
                    leave_deadline_time=time(21, 0),
                    is_active=True,
                ),
            ]
        )
        session.flush()
        yield session
    finally:
        session.close()
        engine.dispose()


def _lunch_only_member(db: Session, *, phone: str, name: str, balance: int = 8) -> Member:
    """无开卡工单的经典月卡午餐会员（与现网 黄永祥 同类：资格靠余额兜底）。"""
    m = Member(
        tenant_id=1,
        store_id=1,
        phone=phone,
        name=name,
        balance=balance,
        daily_meal_units=1,
        meal_quota_total=24,
        plan_type=PlanType.MONTH.value,
        is_active=True,
        delivery_start_date=DELIVERY_DAY,
        delivery_deferred=False,
        store_pickup=False,
    )
    db.add(m)
    db.flush()
    return m


def _dual_member(db: Session, *, phone: str, name: str, lunch: int = 10, dinner: int = 10) -> Member:
    m = Member(
        tenant_id=1,
        store_id=1,
        phone=phone,
        name=name,
        balance=lunch,
        daily_meal_units=1,
        meal_quota_total=lunch,
        plan_type=PlanType.MONTH.value,
        is_active=True,
        delivery_start_date=DELIVERY_DAY,
        delivery_deferred=False,
        store_pickup=False,
    )
    db.add(m)
    db.flush()
    db.add(
        MemberMealPeriodState(
            member_id=int(m.id),
            meal_period=MealPeriod.DINNER.value,
            daily_meal_units=1,
            balance=dinner,
            meal_quota_total=dinner,
        )
    )
    tpl = MembershipCardTemplate(
        id=_next_tpl_id(),
        tenant_id=1,
        store_id=1,
        kind_label="午晚餐卡",
        name="午晚餐月卡",
        meals_grant=24,
        meal_periods=["lunch", "dinner"],
        sale_price_yuan=Decimal("100.00"),
        is_active=True,
        sort_order=0,
    )
    db.add(tpl)
    db.flush()
    db.add(
        MemberCardOrder(
            member_id=int(m.id),
            tenant_id=1,
            store_id=1,
            membership_template_id=int(tpl.id),
            card_kind="月卡",
            pay_channel=CardPayChannel.OFFLINE.value,
            pay_status=CardOrderPayStatus.PAID.value,
            applied_to_member=True,
            meal_periods_snapshot=["lunch", "dinner"],
            created_by="test",
        )
    )
    db.flush()
    return m


def _delivered_lunch(db: Session, member: Member) -> None:
    db.add(
        DeliveryLog(
            member_id=int(member.id),
            delivery_date=DELIVERY_DAY,
            meal_period=MealPeriod.LUNCH.value,
            status=DeliveryStatus.DELIVERED.value,
        )
    )
    db.flush()


def _run_lunch_dinner_merge(
    db: Session,
    *,
    members: list[Member],
    delivered_ids: set[int],
) -> list[int]:
    """复现大表：先按双餐段过滤，再补回已送达。"""
    pu: list[Member] = []
    members, pu = filter_member_groups_for_sheet_view(
        db, DeliverySheetView.LUNCH_DINNER.value, members, pu
    )
    members, pu = _merge_extra_delivered_for_sheet_view(
        db,
        view=DeliverySheetView.LUNCH_DINNER.value,
        members=members,
        pu_members=pu,
        default_by_id={},
        pu_defaults={},
        delivery_date=DELIVERY_DAY,
        region_filter_id=None,
        store_id=1,
        tenant_id=1,
        day_delivered_member_ids=delivered_ids,
    )
    return [int(m.id) for m in members]


def test_lunch_only_already_delivered_stays_out_of_lunch_dinner_tab(sheet_db: Session):
    """
    黄永祥这类单月卡午餐会员：仍在午餐应送名单、今日午餐已送达。
    过滤掉双餐段后，extra_delivered 会误把他们当「名单外已送达」补回；修复后不得出现。
    """
    db = sheet_db
    lunch_only = _lunch_only_member(db, phone="13782238330", name="黄永祥")
    dual = _dual_member(db, phone="13800002222", name="双餐段")
    _delivered_lunch(db, lunch_only)

    ids = _run_lunch_dinner_merge(
        db,
        members=[lunch_only, dual],
        delivered_ids={int(lunch_only.id)},
    )
    assert int(dual.id) in ids
    assert int(lunch_only.id) not in ids


def test_lunch_dinner_still_keeps_dual_member_after_lunch_balance_zero(sheet_db: Session):
    """双餐段会员扣午餐次后余额为 0，仍应靠已送达补回留在午晚餐 Tab。"""
    db = sheet_db
    dual = _dual_member(db, phone="13800003333", name="双餐扣次后", lunch=0, dinner=10)
    _delivered_lunch(db, dual)

    ids = _run_lunch_dinner_merge(
        db,
        members=[],
        delivered_ids={int(dual.id)},
    )
    assert ids == [int(dual.id)]


def test_lunch_sheet_still_keeps_zero_balance_lunch_only_delivered(sheet_db: Session):
    """午餐 Tab：无工单、扣次后余额 0 的纯午餐已送达会员仍须补回，不能被二次过滤掉。"""
    db = sheet_db
    lunch_only = _lunch_only_member(db, phone="13700001111", name="纯午餐扣次后", balance=0)
    _delivered_lunch(db, lunch_only)

    members, pu = filter_member_groups_for_sheet_view(
        db, DeliverySheetView.LUNCH.value, [lunch_only], []
    )
    members, pu = _merge_extra_delivered_for_sheet_view(
        db,
        view=DeliverySheetView.LUNCH.value,
        members=members,
        pu_members=pu,
        default_by_id={},
        pu_defaults={},
        delivery_date=DELIVERY_DAY,
        region_filter_id=None,
        store_id=1,
        tenant_id=1,
        day_delivered_member_ids={int(lunch_only.id)},
    )
    assert [int(m.id) for m in members] == [int(lunch_only.id)]
