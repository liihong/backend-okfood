"""单次零售已售份数：取消订单不计入营业概览统计。"""

from __future__ import annotations

from datetime import date, time
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models.member import Member
from app.models.menu_dish import MenuDish
from app.models.single_meal_order import SingleMealOrder
from app.models.store import Store
from app.models.tenant import Tenant
from app.services.admin.menu_day_stock_service import paid_single_retail_portions_by_dates


@pytest.fixture()
def retail_stats_db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    tables = [
        Tenant.__table__,
        Store.__table__,
        Member.__table__,
        MenuDish.__table__,
        SingleMealOrder.__table__,
    ]
    Base.metadata.create_all(engine, tables=tables)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = SessionLocal()
    session.add(Tenant(id=1, name="t", is_active=True))
    session.add(
        Store(id=1, tenant_id=1, name="s", is_active=True, leave_deadline_time=time(21, 0))
    )
    session.add(Member(id=1, tenant_id=1, store_id=1, name="m", phone="13800000000", balance=0))
    session.add(MenuDish(id=1, store_id=1, name="饭", is_enabled=True))
    session.flush()
    yield session
    session.close()
    engine.dispose()


def _add_order(
    db: Session,
    *,
    oid: int,
    quantity: int,
    pay_status: str = "已支付",
    fulfillment_status: str = "pending",
) -> None:
    db.add(
        SingleMealOrder(
            id=oid,
            tenant_id=1,
            store_id=1,
            out_trade_no=f"smo{oid:06d}",
            member_id=1,
            dish_id=1,
            quantity=quantity,
            delivery_date=date(2026, 6, 13),
            routing_area="A",
            amount_yuan=Decimal("30.00"),
            pay_status=pay_status,
            fulfillment_status=fulfillment_status,
        )
    )


def test_paid_single_retail_excludes_cancelled_orders(retail_stats_db: Session):
    """会员卡取消后 pay_status 仍为已支付，须按 fulfillment_status 排除。"""
    _add_order(retail_stats_db, oid=1, quantity=1, fulfillment_status="pending")
    _add_order(retail_stats_db, oid=2, quantity=2, fulfillment_status="pending")
    _add_order(retail_stats_db, oid=3, quantity=1, fulfillment_status="cancelled")
    retail_stats_db.commit()

    out = paid_single_retail_portions_by_dates(
        retail_stats_db, [date(2026, 6, 13)], store_id=1
    )

    assert out[date(2026, 6, 13)] == 3


def test_paid_single_retail_excludes_unpaid_cancelled(retail_stats_db: Session):
    """未支付已取消不计入；已支付未取消仍计入。"""
    _add_order(retail_stats_db, oid=1, quantity=1, fulfillment_status="pending")
    _add_order(
        retail_stats_db,
        oid=2,
        quantity=1,
        pay_status="未支付",
        fulfillment_status="cancelled",
    )
    retail_stats_db.commit()

    out = paid_single_retail_portions_by_dates(
        retail_stats_db, [date(2026, 6, 13)], store_id=1
    )

    assert out[date(2026, 6, 13)] == 1


def test_paid_single_retail_includes_unpaid_pending(retail_stats_db: Session):
    """未支付待支付占用库存；取消后释放。"""
    _add_order(retail_stats_db, oid=1, quantity=2, fulfillment_status="pending")
    _add_order(
        retail_stats_db,
        oid=2,
        quantity=1,
        pay_status="未支付",
        fulfillment_status="pending",
    )
    retail_stats_db.commit()

    out = paid_single_retail_portions_by_dates(
        retail_stats_db, [date(2026, 6, 13)], store_id=1
    )

    assert out[date(2026, 6, 13)] == 3
