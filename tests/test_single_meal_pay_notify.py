"""单次零售：支付回调入账与系统消息（uk 不冲突、通知失败不回滚支付）。"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.integrations.wechat_pay_v2 import WechatPayNotifyParsed
from app.models.admin_system_notification import AdminSystemNotification
from app.models.member import Member
from app.models.member_coupon import MemberCoupon
from app.models.menu_dish import MenuDish
from app.models.single_meal_order import SingleMealOrder
from app.models.store import Store
from app.models.tenant import Tenant
from app.services.admin_system_notification_service import (
    KIND_SINGLE_MEAL_ORDER_PAID,
    _single_meal_order_paid_business_date_for_uk,
    _single_meal_order_paid_notification_marker,
    create_single_meal_order_paid_notification,
)
from app.services.single_meal_order_service import finalize_single_meal_order_wechat_pay


@pytest.fixture()
def single_meal_db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    tables = [
        Tenant.__table__,
        Store.__table__,
        Member.__table__,
        MenuDish.__table__,
        MemberCoupon.__table__,
        SingleMealOrder.__table__,
        AdminSystemNotification.__table__,
    ]
    Base.metadata.create_all(engine, tables=tables)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = SessionLocal()
    try:
        from datetime import time

        session.add(Tenant(id=1, name="测试租户", is_active=True))
        session.add(
            Store(
                id=1,
                tenant_id=1,
                name="测试门店",
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
                name="测试会员",
                balance=0,
                meal_quota_total=0,
                wx_mini_openid="openid_smo_test",
                is_active=True,
                store_pickup=False,
            )
        )
        session.add(
            MenuDish(
                id=100,
                store_id=1,
                name="测试餐品",
                is_enabled=True,
                single_order_price_yuan=Decimal("32.00"),
            )
        )
        session.flush()
        yield session
    finally:
        session.close()
        engine.dispose()


def _add_unpaid_order(
    db: Session,
    *,
    order_id: int,
    out_no: str,
    delivery_day: date,
    store_pickup: bool = False,
) -> SingleMealOrder:
    row = SingleMealOrder(
        id=int(order_id),
        tenant_id=1,
        store_id=1,
        out_trade_no=out_no,
        member_id=10,
        dish_id=100,
        member_address_id=None,
        store_pickup=store_pickup,
        quantity=1,
        delivery_date=delivery_day,
        routing_area="门店自提" if store_pickup else "测试片区",
        amount_yuan=Decimal("32.00"),
        pay_status="未支付",
        pay_channel=None,
        fulfillment_status="pending",
        courier_id=None,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def test_same_delivery_day_two_notifications_no_uk_conflict(single_meal_db: Session) -> None:
    """同供餐日多笔订单：每单独立通知，business_date 槽位互不冲突。"""
    day = date(2026, 6, 1)
    _add_unpaid_order(single_meal_db, order_id=153, out_no="OKF153", delivery_day=day)
    _add_unpaid_order(single_meal_db, order_id=154, out_no="OKF154", delivery_day=day)

    n1 = create_single_meal_order_paid_notification(
        single_meal_db,
        store_id=1,
        order_id=153,
        delivery_date=day,
        dish_name="测试餐品",
        quantity=1,
        amount_yuan="32.00",
        store_pickup=True,
        member_id=10,
        member_phone="13800000001",
        member_name="测试会员",
    )
    n2 = create_single_meal_order_paid_notification(
        single_meal_db,
        store_id=1,
        order_id=154,
        delivery_date=day,
        dish_name="测试餐品",
        quantity=1,
        amount_yuan="32.00",
        store_pickup=True,
        member_id=10,
        member_phone="13800000001",
        member_name="测试会员",
    )
    single_meal_db.commit()

    assert n1 is not None and n2 is not None
    assert n1.id != n2.id
    assert n1.business_date != n2.business_date
    assert n1.business_date == _single_meal_order_paid_business_date_for_uk(153)
    assert n2.skip_reason == _single_meal_order_paid_notification_marker(154)
    assert "2026-06-01" in (n1.message or "")
    assert "trace=" in (n2.message or "")

    cnt = single_meal_db.scalar(
        select(func.count())
        .select_from(AdminSystemNotification)
        .where(AdminSystemNotification.kind == KIND_SINGLE_MEAL_ORDER_PAID)
    )
    assert int(cnt or 0) == 2


def test_notification_idempotent_on_retry(single_meal_db: Session) -> None:
    day = date(2026, 6, 1)
    first = create_single_meal_order_paid_notification(
        single_meal_db,
        store_id=1,
        order_id=200,
        delivery_date=day,
        dish_name="餐",
        quantity=1,
        amount_yuan="32.00",
        store_pickup=False,
        member_id=10,
        member_phone=None,
        member_name=None,
    )
    single_meal_db.commit()
    second = create_single_meal_order_paid_notification(
        single_meal_db,
        store_id=1,
        order_id=200,
        delivery_date=day,
        dish_name="餐",
        quantity=1,
        amount_yuan="32.00",
        store_pickup=False,
        member_id=10,
        member_phone=None,
        member_name=None,
    )
    single_meal_db.commit()
    assert first is not None and second is not None
    assert int(first.id) == int(second.id)


def test_finalize_wechat_pay_creates_notification(single_meal_db: Session) -> None:
    _add_unpaid_order(
        single_meal_db, order_id=154, out_no="OKF154", delivery_day=date(2026, 6, 1), store_pickup=True
    )
    ok, reason = finalize_single_meal_order_wechat_pay(
        single_meal_db,
        WechatPayNotifyParsed(out_trade_no="OKF154", transaction_id="420000TEST154", total_fee=3200),
    )
    assert ok is True
    assert reason == "paid"

    order = single_meal_db.get(SingleMealOrder, 154)
    assert order is not None
    assert order.pay_status == "已支付"
    assert order.wx_transaction_id == "420000TEST154"

    note = single_meal_db.scalar(
        select(AdminSystemNotification).where(
            AdminSystemNotification.skip_reason == _single_meal_order_paid_notification_marker(154)
        )
    )
    assert note is not None
    assert "2026-06-01" in (note.message or "")


def test_finalize_wechat_pay_succeeds_when_notification_raises(single_meal_db: Session) -> None:
    """通知写入异常时，支付仍应 commit（savepoint 隔离）。"""
    _add_unpaid_order(
        single_meal_db, order_id=155, out_no="OKF155", delivery_day=date(2026, 6, 1), store_pickup=True
    )
    with patch(
        "app.services.single_meal_order_service.create_single_meal_order_paid_notification",
        side_effect=RuntimeError("模拟通知库异常"),
    ):
        ok, reason = finalize_single_meal_order_wechat_pay(
            single_meal_db,
            WechatPayNotifyParsed(out_trade_no="OKF155", transaction_id="420000TEST155", total_fee=3200),
        )
    assert ok is True
    assert reason == "paid"
    order = single_meal_db.get(SingleMealOrder, 155)
    assert order is not None
    assert order.pay_status == "已支付"


def test_finalize_second_order_same_day_after_first(single_meal_db: Session) -> None:
    """模拟回调：同供餐日第二笔在首笔通知已存在后仍能入账。"""
    day = date(2026, 6, 1)
    _add_unpaid_order(single_meal_db, order_id=160, out_no="OKF160", delivery_day=day, store_pickup=True)
    _add_unpaid_order(single_meal_db, order_id=161, out_no="OKF161", delivery_day=day, store_pickup=True)

    ok1, _ = finalize_single_meal_order_wechat_pay(
        single_meal_db,
        WechatPayNotifyParsed(out_trade_no="OKF160", transaction_id="tx160", total_fee=3200),
    )
    ok2, _ = finalize_single_meal_order_wechat_pay(
        single_meal_db,
        WechatPayNotifyParsed(out_trade_no="OKF161", transaction_id="tx161", total_fee=3200),
    )
    assert ok1 is True and ok2 is True
    assert single_meal_db.get(SingleMealOrder, 160).pay_status == "已支付"
    assert single_meal_db.get(SingleMealOrder, 161).pay_status == "已支付"
    cnt = single_meal_db.scalar(
        select(func.count())
        .select_from(AdminSystemNotification)
        .where(AdminSystemNotification.kind == KIND_SINGLE_MEAL_ORDER_PAID)
    )
    assert int(cnt or 0) == 2
