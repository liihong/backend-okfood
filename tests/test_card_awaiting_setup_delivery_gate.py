"""卡包购卡待完善配送：不入应配送名单、不可推顺丰、paid_card_awaiting_setup 口径。"""

from __future__ import annotations

from datetime import date, time
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models.enums import CardOrderPayStatus, CardPayChannel
from app.models.balance_log import BalanceLog
from app.models.member import Member
from app.models.member_address import MemberAddress
from app.models.member_card_order import MemberCardOrder
from app.models.member_meal_period_state import MemberMealPeriodState
from app.models.membership_card_template import MembershipCardTemplate
from app.models.store import Store
from app.models.tenant import Tenant
from app.services.delivery.courier_service import (
    member_on_any_entitled_delivery_schedule,
)
from app.services.delivery.sf_same_city_service import (
    _Agg,
    _validate_agg_subscription_sf_readiness,
)
from app.services.member.member_card_order_service import (
    DOUYIN_REDEEM_ORDER_CREATOR,
    MINIPROGRAM_SELF_SERVICE_ORDER_CREATOR,
    _apply_paid_card_order_to_member_balance,
    member_paid_card_awaiting_setup,
)


@pytest.fixture()
def gate_db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    tables = [
        Tenant.__table__,
        Store.__table__,
        Member.__table__,
        MemberAddress.__table__,
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
                name="测试卡包",
                kind_label="周卡",
                meals_grant=5,
                sale_price_yuan=Decimal("99.00"),
                is_active=True,
            )
        )
        session.add(
            Member(
                id=10,
                tenant_id=1,
                store_id=1,
                phone="17638193515",
                name="新用户",
                balance=0,
                is_active=False,
                delivery_start_date=None,
                delivery_deferred=False,
                store_pickup=False,
            )
        )
        session.commit()
        yield session
    finally:
        session.close()
        engine.dispose()


def _paid_template_order(db: Session, *, delivery_start_date: date | None) -> MemberCardOrder:
    order = MemberCardOrder(
        member_id=10,
        tenant_id=1,
        store_id=1,
        membership_template_id=1,
        card_kind="周卡",
        pay_channel=CardPayChannel.WECHAT.value,
        pay_status=CardOrderPayStatus.PAID.value,
        amount_yuan=Decimal("99.00"),
        applied_to_member=False,
        delivery_start_date=delivery_start_date,
        meal_periods_snapshot=["lunch"],
        created_by=MINIPROGRAM_SELF_SERVICE_ORDER_CREATOR,
    )
    db.add(order)
    db.flush()
    return order


def test_card_credit_without_start_defers_delivery(gate_db: Session) -> None:
    order = _paid_template_order(gate_db, delivery_start_date=None)
    _apply_paid_card_order_to_member_balance(gate_db, order, operator="test")
    gate_db.commit()
    m = gate_db.get(Member, 10)
    assert m is not None
    assert int(m.balance) == 5
    assert m.is_active is False
    assert m.delivery_deferred is True
    assert m.delivery_start_date is None
    assert member_paid_card_awaiting_setup(gate_db, 10) is True


def test_deferred_member_not_on_delivery_schedule(gate_db: Session, monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.delivery.courier_service.is_subscription_delivery_day",
        lambda _d: True,
    )
    order = _paid_template_order(gate_db, delivery_start_date=None)
    _apply_paid_card_order_to_member_balance(gate_db, order, operator="test")
    gate_db.commit()
    m = gate_db.get(Member, 10)
    assert m is not None
    assert member_on_any_entitled_delivery_schedule(
        gate_db, m, delivery_date=date(2026, 7, 7)
    ) is False


def test_legacy_null_start_still_on_schedule_when_not_deferred(gate_db: Session, monkeypatch) -> None:
    """历史老会员：起送日为空且未暂停，仍按即日生效计入履约日程。"""
    monkeypatch.setattr(
        "app.services.delivery.courier_service.is_subscription_delivery_day",
        lambda _d: True,
    )
    """历史老会员：起送日为空且未暂停，仍按即日生效进入应配送名单。"""
    m = gate_db.get(Member, 10)
    assert m is not None
    m.balance = 5
    m.is_active = True
    m.delivery_deferred = False
    m.delivery_start_date = None
    gate_db.commit()
    assert member_on_any_entitled_delivery_schedule(
        gate_db, m, delivery_date=date(2026, 7, 7)
    ) is True


def test_existing_bad_state_excluded_from_schedule(gate_db: Session, monkeypatch) -> None:
    """存量：已入账且 is_active 但缺起送日/地址，仍须排除在履约日程外。"""
    monkeypatch.setattr(
        "app.services.delivery.courier_service.is_subscription_delivery_day",
        lambda _d: True,
    )
    order = _paid_template_order(gate_db, delivery_start_date=None)
    _apply_paid_card_order_to_member_balance(gate_db, order, operator="test")
    m = gate_db.get(Member, 10)
    assert m is not None
    # 模拟修复前错误状态：已激活、未标 delivery_deferred
    m.is_active = True
    m.delivery_deferred = False
    gate_db.commit()
    assert member_paid_card_awaiting_setup(gate_db, 10) is True
    assert member_on_any_entitled_delivery_schedule(
        gate_db, m, delivery_date=date(2026, 7, 7)
    ) is False


def test_sf_push_rejects_deferred_member(gate_db: Session) -> None:
    order = _paid_template_order(gate_db, delivery_start_date=None)
    _apply_paid_card_order_to_member_balance(gate_db, order, operator="test")
    gate_db.commit()
    agg = _Agg(
        stop_id="stop1",
        group_area="未分配",
        address_line="（未设置默认配送地址）",
        sub_lines=[{"member_id": 10, "units": 1, "is_delivered": False, "name": "新用户", "phone": "17638193515"}],
        singles=[],
    )
    err = _validate_agg_subscription_sf_readiness(
        gate_db, agg, delivery_date=date(2026, 7, 7)
    )
    assert err is not None
    assert "待完善配送" in err


def test_awaiting_setup_false_after_start_and_address(gate_db: Session) -> None:
    order = _paid_template_order(gate_db, delivery_start_date=None)
    _apply_paid_card_order_to_member_balance(gate_db, order, operator="test")
    m = gate_db.get(Member, 10)
    assert m is not None
    m.delivery_start_date = date(2026, 7, 7)
    m.delivery_deferred = False
    m.is_active = True
    gate_db.add(
        MemberAddress(
            member_id=10,
            contact_name="新用户",
            contact_phone="17638193515",
            map_location_text="测试路1号",
            door_detail="",
            lng=113.88,
            lat=35.30,
            is_default=True,
        )
    )
    gate_db.commit()
    assert member_paid_card_awaiting_setup(gate_db, 10) is False


def test_douyin_redeem_awaiting_setup_same_as_miniprogram(gate_db: Session) -> None:
    """抖音验券入账后纳入待完善口径，与小程序购卡一致（只读判断，不改档案）。"""
    order = MemberCardOrder(
        member_id=10,
        tenant_id=1,
        store_id=1,
        membership_template_id=1,
        card_kind="周卡",
        pay_channel=CardPayChannel.DOUYIN.value,
        pay_status=CardOrderPayStatus.PAID.value,
        amount_yuan=Decimal("188.00"),
        applied_to_member=False,
        delivery_start_date=None,
        activation_mode="defer_not_open",
        meal_periods_snapshot=["lunch"],
        created_by=DOUYIN_REDEEM_ORDER_CREATOR,
    )
    gate_db.add(order)
    gate_db.flush()
    _apply_paid_card_order_to_member_balance(gate_db, order, operator=DOUYIN_REDEEM_ORDER_CREATOR)
    gate_db.commit()
    m = gate_db.get(Member, 10)
    assert m is not None
    assert int(m.balance) == 5
    assert m.delivery_deferred is True
    assert member_paid_card_awaiting_setup(gate_db, 10) is True
