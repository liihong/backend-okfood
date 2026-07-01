"""plan_type 以最近一笔已入账工单为准；管理端餐段展示标签。"""

from __future__ import annotations

from datetime import date, time

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models.enums import CardOrderPayStatus, PlanType
from app.models.member import Member
from app.models.member_card_order import MemberCardOrder
from app.models.store import Store
from app.models.tenant import Tenant
from app.services.meal_period.plan_type_sync import (
    format_plan_type_display,
    meal_scope_label_from_periods,
    sync_member_plan_type_from_latest_card_order,
)


@pytest.fixture()
def plan_sync_db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    tables = [
        Tenant.__table__,
        Store.__table__,
        Member.__table__,
        MemberCardOrder.__table__,
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
                id=401,
                tenant_id=1,
                store_id=1,
                phone="13000000401",
                name="多卡",
                balance=6,
                plan_type=PlanType.WEEK.value,
                is_active=True,
                delivery_start_date=date(2026, 6, 1),
            )
        )
        session.add(
            MemberCardOrder(
                id=10,
                member_id=401,
                tenant_id=1,
                store_id=1,
                card_kind="周卡",
                pay_channel="现金",
                pay_status=CardOrderPayStatus.PAID.value,
                applied_to_member=True,
                meal_periods_snapshot=["lunch"],
                created_by="admin",
            )
        )
        session.add(
            MemberCardOrder(
                id=20,
                member_id=401,
                tenant_id=1,
                store_id=1,
                card_kind="月卡",
                pay_channel="现金",
                pay_status=CardOrderPayStatus.PAID.value,
                applied_to_member=True,
                meal_periods_snapshot=["dinner"],
                created_by="admin",
            )
        )
        session.commit()
        yield session
    finally:
        session.close()


def test_meal_scope_label_from_periods() -> None:
    assert meal_scope_label_from_periods(frozenset({"lunch"})) == "午餐"
    assert meal_scope_label_from_periods(frozenset({"dinner"})) == "晚餐"
    assert meal_scope_label_from_periods(frozenset({"lunch", "dinner"})) == "全餐"


def test_format_plan_type_display() -> None:
    assert format_plan_type_display("周卡", frozenset({"lunch", "dinner"})) == "周卡 · 全餐"
    assert format_plan_type_display(None, frozenset({"dinner"})) == "次卡 · 晚餐"


def test_sync_member_plan_type_uses_latest_applied_order(plan_sync_db: Session) -> None:
    m = plan_sync_db.get(Member, 401)
    assert m is not None
    assert m.plan_type == PlanType.WEEK.value

    sync_member_plan_type_from_latest_card_order(plan_sync_db, m)
    plan_sync_db.commit()
    plan_sync_db.refresh(m)

    assert m.plan_type == PlanType.MONTH.value

    # 撤销最新工单后应回落到较早的周卡
    latest = plan_sync_db.get(MemberCardOrder, 20)
    assert latest is not None
    latest.applied_to_member = False
    plan_sync_db.add(latest)
    sync_member_plan_type_from_latest_card_order(plan_sync_db, m)
    plan_sync_db.commit()
    plan_sync_db.refresh(m)

    assert m.plan_type == PlanType.WEEK.value
