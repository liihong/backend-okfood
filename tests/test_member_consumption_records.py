"""消费记录：合并套餐送达与单次购买会员卡扣次。"""

from __future__ import annotations

from datetime import date, time
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models.balance_log import BalanceLog
from app.models.delivery_log import DeliveryLog
from app.models.enums import BalanceReason, DeliveryStatus
from app.models.member import Member
from app.models.single_meal_order import SingleMealOrder
from app.models.store import Store
from app.models.tenant import Tenant
from app.services.admin.member_delivery_deduction_service import (
    list_member_delivery_deductions,
    total_member_consumption_meal_units,
)


@pytest.fixture()
def consumption_db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    tables = [
        Tenant.__table__,
        Store.__table__,
        Member.__table__,
        BalanceLog.__table__,
        DeliveryLog.__table__,
        SingleMealOrder.__table__,
    ]
    Base.metadata.create_all(engine, tables=tables)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = SessionLocal()
    session.add(Tenant(id=1, name="t", is_active=True))
    session.add(Store(id=1, tenant_id=1, name="s", leave_deadline_time=time(21, 0), is_active=True))
    session.flush()
    m = Member(
        tenant_id=1,
        store_id=1,
        phone="13800000099",
        name="消费测试",
        balance=3,
        meal_quota_total=6,
        plan_type="周卡",
        is_active=True,
        delivery_start_date=date(2020, 1, 1),
    )
    session.add(m)
    session.flush()
    mid = int(m.id)
    session.add(
        DeliveryLog(
            member_id=mid,
            delivery_date=date(2026, 5, 6),
            meal_period="lunch",
            status=DeliveryStatus.DELIVERED.value,
        )
    )
    session.add(
        BalanceLog(
            member_id=mid,
            change=-1,
            reason=BalanceReason.DELIVERY.value,
            operator="system",
        )
    )
    order = SingleMealOrder(
        id=1,
        tenant_id=1,
        store_id=1,
        out_trade_no="smo_test_1",
        member_id=mid,
        dish_id=1,
        quantity=2,
        delivery_date=date(2026, 6, 1),
        routing_area="A",
        amount_yuan=Decimal("0"),
        pay_status="已支付",
        pay_channel="会员卡",
    )
    session.add(order)
    session.flush()
    session.add(
        BalanceLog(
            member_id=mid,
            change=-2,
            reason=BalanceReason.SINGLE_MEAL.value,
            operator="member:miniprogram",
            detail=f"single_meal_orders.id={int(order.id)}",
        )
    )
    session.commit()
    yield session
    session.close()
    engine.dispose()


def test_merged_consumption_includes_single_meal(consumption_db: Session) -> None:
    mid = int(consumption_db.scalar(select(Member.id)) or 0)
    items, total, total_meals = list_member_delivery_deductions(consumption_db, mid, page=1, page_size=20)
    kinds = {x.deduction_kind for x in items}
    assert total == 2
    assert total_meals == 3
    assert "subscription" in kinds
    assert "single_meal" in kinds
    single_rows = [x for x in items if x.deduction_kind == "single_meal"]
    assert len(single_rows) == 1
    assert single_rows[0].meal_units == 2
    assert single_rows[0].delivery_date == date(2026, 6, 1)
    assert total_member_consumption_meal_units(consumption_db, mid) == 3
