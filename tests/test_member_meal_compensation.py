"""补餐赔付：余额入账、操作审计与消费记录展示。"""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.balance_log import BalanceLog
from app.models.enums import BalanceReason
from app.models.member import Member
from app.models.member_operation_log import MemberOperationLog
from app.schemas.admin import MemberMealCompensationIn
from app.services.admin.member_delivery_deduction_service import _meal_compensation_items
from app.services.admin.member_meal_compensation_service import admin_member_meal_compensation
from app.services.member.member_operation_log_service import OP_MEAL_COMPENSATION


@pytest.fixture()
def compensation_member(db: Session) -> Member:
    m = Member(
        tenant_id=1,
        store_id=1,
        phone="13800000111",
        name="补餐测试",
        balance=2,
        meal_quota_total=5,
        plan_type="周卡",
        is_active=True,
        delivery_start_date=date(2020, 1, 1),
    )
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


def test_meal_compensation_increases_balance_and_logs(db: Session, compensation_member: Member) -> None:
    mid = int(compensation_member.id)
    out = admin_member_meal_compensation(
        db,
        member_id=mid,
        store_id=1,
        body=MemberMealCompensationIn(meal_units=1, remark="漏送配菜"),
        operator="admin:tester",
    )
    assert out.balance_before == 2
    assert out.balance_after == 3
    assert out.meal_units == 1

    m = db.get(Member, mid)
    assert m is not None
    assert int(m.balance) == 3

    bl = db.scalars(
        select(BalanceLog).where(
            BalanceLog.member_id == mid,
            BalanceLog.reason == BalanceReason.MEAL_COMPENSATION.value,
        )
    ).all()
    assert len(bl) == 1
    assert bl[0].change == 1
    assert "漏送配菜" in (bl[0].detail or "")

    op = db.scalars(
        select(MemberOperationLog).where(
            MemberOperationLog.member_id == mid,
            MemberOperationLog.operation_type == OP_MEAL_COMPENSATION,
        )
    ).all()
    assert len(op) == 1
    assert "补餐" in op[0].summary


def test_meal_compensation_shown_in_consumption_records(db: Session, compensation_member: Member) -> None:
    mid = int(compensation_member.id)
    admin_member_meal_compensation(
        db,
        member_id=mid,
        store_id=1,
        body=MemberMealCompensationIn(meal_units=2),
        operator="admin:tester",
    )
    comp_rows = _meal_compensation_items(db, mid)
    assert len(comp_rows) == 1
    assert comp_rows[0].meal_units == 2
    assert comp_rows[0].deduction_kind == "meal_compensation"
