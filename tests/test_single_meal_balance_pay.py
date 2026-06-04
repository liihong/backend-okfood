"""单次点餐会员卡次数支付：资格评估与退次幂等。"""

from __future__ import annotations

from datetime import date, time
from decimal import Decimal
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models.balance_log import BalanceLog
from app.models.member import Member
from app.models.single_meal_order import SingleMealOrder
from app.models.store import Store
from app.models.tenant import Tenant
from app.services.single_meal_balance_pay_service import (
    MEMBER_CARD_PAY_CHANNEL,
    evaluate_single_meal_balance_pay,
    restore_member_balance_for_cancelled_single_meal,
)


@pytest.fixture()
def balance_pay_db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    tables = [
        Tenant.__table__,
        Store.__table__,
        Member.__table__,
        BalanceLog.__table__,
        SingleMealOrder.__table__,
    ]
    Base.metadata.create_all(engine, tables=tables)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = SessionLocal()
    session.add(Tenant(id=1, name="t", is_active=True))
    session.add(
        Store(id=1, tenant_id=1, name="s", is_active=True, leave_deadline_time=time(21, 0))
    )
    session.flush()
    yield session
    session.close()
    engine.dispose()


def _week_member(db: Session, *, balance: int, daily: int = 1) -> Member:
    m = Member(
        tenant_id=1,
        store_id=1,
        phone="13800000001",
        name="测试",
        balance=balance,
        meal_quota_total=6,
        plan_type="周卡",
        is_active=True,
        delivery_start_date=date(2020, 1, 1),
        delivery_deferred=False,
        store_pickup=False,
        daily_meal_units=daily,
    )
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


@patch(
    "app.services.single_meal_balance_pay_service.member_subscription_delivery_pending_today",
    return_value=(False, 0),
)
def test_evaluate_balance_pay_ok_without_reserve(_mock_pending, balance_pay_db: Session) -> None:
    m = _week_member(balance_pay_db, balance=4)
    ev = evaluate_single_meal_balance_pay(balance_pay_db, m, quantity=2)
    assert ev.can_use is True
    assert ev.required_balance == 2


@patch(
    "app.services.single_meal_balance_pay_service.member_subscription_delivery_pending_today",
    return_value=(True, 1),
)
def test_evaluate_balance_pay_blocked_last_time_for_today(_mock_pending, balance_pay_db: Session) -> None:
    m = _week_member(balance_pay_db, balance=1)
    ev = evaluate_single_meal_balance_pay(balance_pay_db, m, quantity=1)
    assert ev.can_use is False
    assert "微信支付" in ev.message


@patch(
    "app.services.single_meal_balance_pay_service.member_subscription_delivery_pending_today",
    return_value=(True, 2),
)
def test_evaluate_balance_pay_needs_qty_plus_reserve(_mock_pending, balance_pay_db: Session) -> None:
    m = _week_member(balance_pay_db, balance=3, daily=2)
    ev = evaluate_single_meal_balance_pay(balance_pay_db, m, quantity=2)
    assert ev.can_use is False
    assert ev.reserve_for_today == 2
    assert ev.required_balance == 4


@patch(
    "app.services.single_meal_balance_pay_service.member_subscription_delivery_pending_today",
    return_value=(False, 0),
)
def test_evaluate_rejects_times_card(_mock_pending, balance_pay_db: Session) -> None:
    m = _week_member(balance_pay_db, balance=10)
    m.plan_type = "次卡"
    balance_pay_db.add(m)
    balance_pay_db.commit()
    ev = evaluate_single_meal_balance_pay(balance_pay_db, m, quantity=1)
    assert ev.can_use is False


def test_restore_balance_idempotent(balance_pay_db: Session) -> None:
    m = _week_member(balance_pay_db, balance=2)
    order = SingleMealOrder(
        id=9001,
        tenant_id=1,
        store_id=1,
        out_trade_no="SMO_TEST001",
        member_id=int(m.id),
        dish_id=1,
        delivery_date=date(2026, 6, 5),
        routing_area="测试",
        amount_yuan=Decimal("0"),
        pay_status="已支付",
        pay_channel=MEMBER_CARD_PAY_CHANNEL,
        fulfillment_status="pending",
        quantity=2,
    )
    balance_pay_db.add(order)
    balance_pay_db.commit()
    balance_pay_db.refresh(order)

    assert restore_member_balance_for_cancelled_single_meal(
        balance_pay_db, order=order, operator="test"
    ) is True
    balance_pay_db.commit()
    balance_pay_db.refresh(m)
    assert int(m.balance) == 4

    assert restore_member_balance_for_cancelled_single_meal(
        balance_pay_db, order=order, operator="test"
    ) is False
    balance_pay_db.commit()
    balance_pay_db.refresh(m)
    assert int(m.balance) == 4
