"""晚餐次数独立池：入账/扣次不影响 members.balance。"""

from __future__ import annotations

from datetime import date, time

from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models.balance_log import BalanceLog
from app.models.enums import MealPeriod, PlanType
from app.models.member import Member
from app.models.member_card_order import MemberCardOrder
from app.models.member_meal_period_state import MemberMealPeriodState
from app.models.membership_card_template import MembershipCardTemplate
from app.models.store import Store
from app.models.tenant import Tenant
from app.schemas.admin import CardOrderCreateIn, RechargeIn
from app.services.admin_service import apply_member_recharge_delta
from app.services.meal_period.balance import apply_dinner_recharge_delta
from app.services.member_card_order_service import (
    apply_paid_card_order_to_member_if_pending,
    create_card_order,
    revoke_paid_card_order_member_sync,
)


@pytest.fixture()
def dinner_balance_db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    tables = [
        Tenant.__table__,
        Store.__table__,
        Member.__table__,
        MemberMealPeriodState.__table__,
        MembershipCardTemplate.__table__,
        MemberCardOrder.__table__,
        BalanceLog.__table__,
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
                id=201,
                tenant_id=1,
                store_id=1,
                phone="13000000201",
                name="晚餐续卡",
                balance=5,
                meal_quota_total=5,
                is_active=True,
                delivery_start_date=date(2026, 6, 1),
                store_pickup=False,
            )
        )
        session.add(
            MembershipCardTemplate(
                id=4,
                tenant_id=1,
                store_id=1,
                kind_label="周卡",
                name="晚餐周卡",
                meals_grant=6,
                meal_periods=["dinner"],
                is_active=True,
            )
        )
        session.commit()
        yield session
    finally:
        session.close()
        engine.dispose()


def test_dinner_recharge_does_not_touch_lunch_balance(dinner_balance_db: Session):
    m = dinner_balance_db.get(Member, 201)
    assert m is not None
    lunch_before = int(m.balance)
    apply_dinner_recharge_delta(
        dinner_balance_db,
        m,
        amount=6,
        plan_type=PlanType.WEEK,
        bump_meal_quota_total=True,
        operator="test",
        log_detail="晚餐入账",
    )
    dinner_balance_db.commit()
    dinner_balance_db.refresh(m)
    row = dinner_balance_db.get(
        MemberMealPeriodState,
        {"member_id": 201, "meal_period": MealPeriod.DINNER.value},
    )
    assert row is not None
    assert int(m.balance) == lunch_before
    assert int(row.balance) == 6
    assert int(row.meal_quota_total) == 6
    log = dinner_balance_db.scalars(
        select(BalanceLog).where(BalanceLog.meal_period == "dinner")
    ).first()
    assert log is not None
    assert int(log.change) == 6


def test_create_card_order_dinner_template_credits_dinner_only(dinner_balance_db: Session):
    body = CardOrderCreateIn(
        phone="13000000201",
        open_mode="renew",
        membership_template_id=4,
        pay_channel="微信",
        pay_status="已缴",
        amount_yuan=188,
    )
    create_card_order(
        dinner_balance_db,
        body,
        operator="admin",
        tenant_id=1,
        store_id=1,
    )
    m = dinner_balance_db.get(Member, 201)
    row = dinner_balance_db.get(
        MemberMealPeriodState,
        {"member_id": 201, "meal_period": MealPeriod.DINNER.value},
    )
    assert m is not None and row is not None
    assert int(m.balance) == 5
    assert int(row.balance) == 6
    assert int(row.meal_quota_total) == 6


def test_dinner_balance_independent_from_members_balance(dinner_balance_db: Session):
    """午餐 balance=0 时，晚餐池仍可有次数（大表筛选读 member_meal_period_state）。"""
    m = dinner_balance_db.get(Member, 201)
    assert m is not None
    m.balance = 0
    dinner_balance_db.add(
        MemberMealPeriodState(
            member_id=201,
            meal_period=MealPeriod.DINNER.value,
            daily_meal_units=1,
            balance=6,
            meal_quota_total=6,
        )
    )
    dinner_balance_db.commit()
    row = dinner_balance_db.get(
        MemberMealPeriodState,
        {"member_id": 201, "meal_period": MealPeriod.DINNER.value},
    )
    from app.services.meal_period.balance import dinner_balance_and_quota

    bal, quota = dinner_balance_and_quota(row)
    assert bal == 6
    assert quota == 6
    assert int(m.balance) == 0


def test_miniprogram_finalize_dinner_template_credits_dinner_only(dinner_balance_db: Session):
    """小程序购卡支付回调：晚餐模版入账至 member_meal_period_state，不写 members.balance。"""
    order = MemberCardOrder(
        member_id=201,
        tenant_id=1,
        store_id=1,
        membership_template_id=4,
        card_kind="周卡",
        pay_channel="微信",
        pay_status="已缴",
        amount_yuan=Decimal("168.00"),
        applied_to_member=False,
        meal_periods_snapshot=["dinner"],
        created_by="miniprogram",
    )
    dinner_balance_db.add(order)
    dinner_balance_db.flush()
    apply_paid_card_order_to_member_if_pending(
        dinner_balance_db, order, operator="wechat_notify"
    )
    dinner_balance_db.commit()
    m = dinner_balance_db.get(Member, 201)
    row = dinner_balance_db.get(
        MemberMealPeriodState,
        {"member_id": 201, "meal_period": MealPeriod.DINNER.value},
    )
    assert m is not None and row is not None
    assert order.applied_to_member is True
    assert order.meal_periods_snapshot == ["dinner"]
    assert int(m.balance) == 5
    assert int(row.balance) == 6
    assert int(row.meal_quota_total) == 6


def test_revoke_dinner_card_order_deducts_dinner_not_lunch(dinner_balance_db: Session):
    """微信原路退款撤销入账：晚餐卡只扣晚餐次数池，不动午餐 balance。"""
    order = MemberCardOrder(
        member_id=201,
        tenant_id=1,
        store_id=1,
        membership_template_id=4,
        card_kind="周卡",
        pay_channel="微信",
        pay_status="已缴",
        amount_yuan=Decimal("168.00"),
        applied_to_member=False,
        meal_periods_snapshot=["dinner"],
        created_by="miniprogram",
    )
    dinner_balance_db.add(order)
    dinner_balance_db.flush()
    apply_paid_card_order_to_member_if_pending(
        dinner_balance_db, order, operator="wechat_notify"
    )
    dinner_balance_db.commit()
    m = dinner_balance_db.get(Member, 201)
    row = dinner_balance_db.get(
        MemberMealPeriodState,
        {"member_id": 201, "meal_period": MealPeriod.DINNER.value},
    )
    assert m is not None and row is not None
    assert int(m.balance) == 5
    assert int(row.balance) == 6

    revoke_paid_card_order_member_sync(
        dinner_balance_db, order, operator="admin:mall_card_wechat_refund"
    )
    dinner_balance_db.commit()
    dinner_balance_db.refresh(m)
    dinner_balance_db.refresh(row)
    assert order.applied_to_member is False
    assert int(m.balance) == 5
    assert int(row.balance) == 0
    assert int(row.meal_quota_total) == 0


def test_revoke_mis_credited_dinner_order_deducts_lunch_pool(dinner_balance_db: Session):
    """历史误入午餐池的晚餐卡：退款按入账流水从午餐池扣回。"""
    from app.models.balance_log import BalanceLog
    from app.models.enums import BalanceReason

    m = dinner_balance_db.get(Member, 201)
    assert m is not None
    m.balance = 6
    m.meal_quota_total = 11
    order = MemberCardOrder(
        member_id=201,
        tenant_id=1,
        store_id=1,
        membership_template_id=4,
        card_kind="周卡",
        pay_channel="微信",
        pay_status="已缴",
        amount_yuan=Decimal("168.00"),
        applied_to_member=True,
        meal_periods_snapshot=["dinner"],
        created_by="miniprogram",
    )
    dinner_balance_db.add(order)
    dinner_balance_db.flush()
    # 模拟历史 bug：晚餐卡入账流水写在午餐池
    dinner_balance_db.add(
        BalanceLog(
            member_id=201,
            meal_period=MealPeriod.LUNCH.value,
            change=6,
            reason=BalanceReason.RECHARGE.value,
            operator="legacy",
            detail=f"开卡工单#{order.id}；晚餐卡误入午餐池+6次",
        )
    )
    dinner_balance_db.commit()

    revoke_paid_card_order_member_sync(
        dinner_balance_db, order, operator="admin:mall_card_wechat_refund"
    )
    dinner_balance_db.commit()
    dinner_balance_db.refresh(m)
    assert order.applied_to_member is False
    assert int(m.balance) == 0
    assert int(m.meal_quota_total) == 5


def test_lunch_recharge_still_uses_members_balance(dinner_balance_db: Session):
    m = dinner_balance_db.get(Member, 201)
    assert m is not None
    apply_member_recharge_delta(
        dinner_balance_db,
        RechargeIn(phone=m.phone, amount=2, plan_type=PlanType.WEEK),
        operator="test",
        member_id=201,
    )
    dinner_balance_db.commit()
    dinner_balance_db.refresh(m)
    assert int(m.balance) == 7
    row = dinner_balance_db.get(
        MemberMealPeriodState,
        {"member_id": 201, "meal_period": MealPeriod.DINNER.value},
    )
    assert row is None or int(row.balance or 0) == 0
