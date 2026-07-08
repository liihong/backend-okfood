"""财务实收汇总：商城订单已支付金额应计入窗口统计。"""

from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.timeutil import shanghai_naive_range_for_calendar_day
from app.db.base import Base
from app.models.member import Member
from app.models.member_card_order import MemberCardOrder
from app.models.member_membership_refund import MemberMembershipRefund
from app.models.single_meal_order import SingleMealOrder
from app.models.store import Store
from app.models.store_retail_order import StoreRetailOrder
from app.models.tenant import Tenant
from app.services.admin.finance_received_service import _window_paid


@pytest.fixture()
def finance_db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    tables = [
        Tenant.__table__,
        Store.__table__,
        Member.__table__,
        MemberCardOrder.__table__,
        SingleMealOrder.__table__,
        MemberMembershipRefund.__table__,
        StoreRetailOrder.__table__,
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
                id=10,
                tenant_id=1,
                store_id=1,
                phone="13800000001",
                name="商城客",
                balance=0,
                is_active=True,
                delivery_deferred=False,
                store_pickup=False,
            )
        )
        day = date(2026, 7, 8)
        d0, _ = shanghai_naive_range_for_calendar_day(day)
        session.add(
            StoreRetailOrder(
                id=1,
                tenant_id=1,
                store_id=1,
                out_trade_no="SRO20260708001",
                member_id=10,
                retail_product_id=1,
                product_title="果蔬汁套餐",
                fulfillment_date=day,
                routing_area="A区",
                amount_yuan=Decimal("88.00"),
                pay_status="已支付",
                pay_channel="微信",
                created_at=d0.replace(hour=10, minute=30),
            )
        )
        session.add(
            StoreRetailOrder(
                id=2,
                tenant_id=1,
                store_id=1,
                out_trade_no="SRO20260708002",
                member_id=10,
                retail_product_id=1,
                product_title="已退款单",
                fulfillment_date=day,
                routing_area="A区",
                amount_yuan=Decimal("50.00"),
                pay_status="已退款",
                pay_channel="微信",
                created_at=d0.replace(hour=11, minute=0),
            )
        )
        session.commit()
        yield session
    finally:
        session.close()


def test_window_paid_includes_store_retail_orders(finance_db: Session) -> None:
    day = date(2026, 7, 8)
    d0, d1 = shanghai_naive_range_for_calendar_day(day)
    window = _window_paid(finance_db, start=d0, end=d1, store_id=1)

    assert window.store_retail_orders.count == 1
    assert window.store_retail_orders.amount_yuan == Decimal("88.00")
    assert window.total_amount_yuan == Decimal("88.00")
    assert window.total_count == 1
    assert window.net_total_amount_yuan == Decimal("88.00")
