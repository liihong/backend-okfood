"""老会员续卡：保持配送安排时禁止误标 delivery_deferred。"""

from __future__ import annotations

from datetime import date, time
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models.enums import CardOpenMode, CardOrderPayStatus, CardPayChannel
from app.models.balance_log import BalanceLog
from app.models.member import Member
from app.models.member_card_order import MemberCardOrder
from app.models.member_meal_period_state import MemberMealPeriodState
from app.models.membership_card_template import MembershipCardTemplate
from app.models.store import Store
from app.models.tenant import Tenant
from app.services.delivery.courier_service import member_on_subscription_delivery_schedule
from app.services.member.member_card_order_service import _apply_paid_card_order_to_member_balance


@pytest.fixture()
def renew_db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    tables = [
        Tenant.__table__,
        Store.__table__,
        Member.__table__,
        MemberMealPeriodState.__table__,
        BalanceLog.__table__,
        MembershipCardTemplate.__table__,
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
            MembershipCardTemplate(
                id=1,
                tenant_id=1,
                store_id=1,
                name="周卡",
                kind_label="周卡",
                meals_grant=5,
                sale_price_yuan=Decimal("99.00"),
                is_active=True,
            )
        )
        session.add(
            Member(
                id=20,
                tenant_id=1,
                store_id=1,
                phone="15893835858",
                name="续卡老客",
                balance=0,
                is_active=False,
                delivery_start_date=date(2026, 3, 1),
                delivery_deferred=False,
                store_pickup=False,
            )
        )
        session.commit()
        yield session
    finally:
        session.close()
        engine.dispose()


def _renew_order(db: Session, *, order_id: int = 1) -> MemberCardOrder:
    order = MemberCardOrder(
        id=order_id,
        member_id=20,
        tenant_id=1,
        store_id=1,
        membership_template_id=1,
        card_kind="周卡",
        pay_channel=CardPayChannel.WECHAT.value,
        pay_status=CardOrderPayStatus.PAID.value,
        amount_yuan=Decimal("99.00"),
        applied_to_member=False,
        delivery_start_date=None,
        meal_periods_snapshot=["lunch"],
        created_by="admin",
    )
    db.add(order)
    db.flush()
    return order


def test_renew_keep_schedule_does_not_pause_delivery(renew_db: Session, monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.delivery.courier_service.is_subscription_delivery_day",
        lambda _d: True,
    )
    order = _renew_order(renew_db)
    _apply_paid_card_order_to_member_balance(
        renew_db,
        order,
        operator="admin",
        open_mode=CardOpenMode.RENEW,
        defer_delivery_activation=False,
    )
    renew_db.commit()
    m = renew_db.get(Member, 20)
    assert m is not None
    assert int(m.balance) == 5
    assert m.delivery_deferred is False
    assert m.is_active is True
    assert m.delivery_start_date == date(2026, 3, 1)
    assert member_on_subscription_delivery_schedule(m, delivery_date=date(2026, 7, 8)) is True


def test_renew_explicit_defer_still_pauses(renew_db: Session) -> None:
    order = _renew_order(renew_db, order_id=2)
    _apply_paid_card_order_to_member_balance(
        renew_db,
        order,
        operator="admin",
        open_mode=CardOpenMode.RENEW,
        defer_delivery_activation=True,
    )
    renew_db.commit()
    m = renew_db.get(Member, 20)
    assert m is not None
    assert int(m.balance) == 5
    assert m.delivery_deferred is True
    assert m.is_active is False
