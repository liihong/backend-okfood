"""v3 生命周期与 activation_mode 单元测试。"""

from __future__ import annotations

from datetime import date, time
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models.balance_log import BalanceLog
from app.models.enums import (
    CardOpenMode,
    CardOrderActivationMode,
    CardOrderPayStatus,
    CardPayChannel,
    MemberLifecycleCode,
)
from app.models.delivery_log import DeliveryLog
from app.models.member import Member
from app.models.member_address import MemberAddress
from app.models.member_card_order import MemberCardOrder
from app.models.member_meal_period_state import MemberMealPeriodState
from app.models.membership_card_template import MembershipCardTemplate
from app.models.store import Store
from app.models.tenant import Tenant
from app.services.member.member_card_order_service import _apply_paid_card_order_to_member_balance
from app.services.member.member_lifecycle_service import resolve_member_lifecycle, resolve_members_lifecycle_map


@pytest.fixture()
def v3_db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    tables = [
        Tenant.__table__,
        Store.__table__,
        Member.__table__,
        MemberAddress.__table__,
        MemberMealPeriodState.__table__,
        BalanceLog.__table__,
        DeliveryLog.__table__,
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
        yield session
    finally:
        session.close()
        engine.dispose()


def _member(
    db: Session,
    *,
    mid: int,
    phone: str,
    deferred: bool = False,
    start: date | None = None,
    balance: int = 0,
) -> Member:
    m = Member(
        id=mid,
        tenant_id=1,
        store_id=1,
        phone=phone,
        name="测试",
        balance=balance,
        is_active=balance > 0 and not deferred,
        delivery_start_date=start,
        delivery_deferred=deferred,
        store_pickup=False,
    )
    db.add(m)
    db.flush()
    return m


def test_renew_keep_schedule_with_activation_mode(v3_db: Session) -> None:
    _member(v3_db, mid=20, phone="15893835858", start=date(2026, 3, 1))
    order = MemberCardOrder(
        id=1,
        member_id=20,
        tenant_id=1,
        store_id=1,
        membership_template_id=1,
        card_kind="周卡",
        pay_channel=CardPayChannel.WECHAT.value,
        pay_status=CardOrderPayStatus.PAID.value,
        amount_yuan=Decimal("99.00"),
        applied_to_member=False,
        activation_mode=CardOrderActivationMode.KEEP_SCHEDULE.value,
        meal_periods_snapshot=["lunch"],
        created_by="admin",
    )
    v3_db.add(order)
    v3_db.flush()
    _apply_paid_card_order_to_member_balance(
        v3_db, order, operator="admin", open_mode=CardOpenMode.RENEW
    )
    v3_db.commit()
    m = v3_db.get(Member, 20)
    assert m is not None
    assert m.delivery_deferred is False
    assert m.delivery_start_date == date(2026, 3, 1)


def test_explicit_date_on_paused_member_without_address_stays_paused(v3_db: Session) -> None:
    _member(v3_db, mid=21, phone="13703997479", deferred=True, start=date(2026, 3, 1))
    order = MemberCardOrder(
        id=2,
        member_id=21,
        tenant_id=1,
        store_id=1,
        membership_template_id=1,
        card_kind="周卡",
        pay_channel=CardPayChannel.WECHAT.value,
        pay_status=CardOrderPayStatus.PAID.value,
        amount_yuan=Decimal("99.00"),
        applied_to_member=False,
        delivery_start_date=date(2026, 7, 10),
        activation_mode=CardOrderActivationMode.EXPLICIT_DATE.value,
        meal_periods_snapshot=["lunch"],
        created_by="admin",
    )
    v3_db.add(order)
    v3_db.flush()
    _apply_paid_card_order_to_member_balance(
        v3_db, order, operator="admin", open_mode=CardOpenMode.RENEW
    )
    v3_db.commit()
    m = v3_db.get(Member, 21)
    assert m is not None
    assert m.delivery_deferred is True
    assert m.delivery_start_date == date(2026, 7, 10)


def test_renew_keep_schedule_on_paused_member_stays_paused(v3_db: Session) -> None:
    _member(v3_db, mid=23, phone="13700000001", deferred=True, start=date(2026, 3, 1))
    order = MemberCardOrder(
        id=4,
        member_id=23,
        tenant_id=1,
        store_id=1,
        membership_template_id=1,
        card_kind="周卡",
        pay_channel=CardPayChannel.WECHAT.value,
        pay_status=CardOrderPayStatus.PAID.value,
        amount_yuan=Decimal("99.00"),
        applied_to_member=False,
        activation_mode=CardOrderActivationMode.KEEP_SCHEDULE.value,
        meal_periods_snapshot=["lunch"],
        created_by="admin",
    )
    v3_db.add(order)
    v3_db.flush()
    _apply_paid_card_order_to_member_balance(
        v3_db, order, operator="admin", open_mode=CardOpenMode.RENEW
    )
    v3_db.commit()
    m = v3_db.get(Member, 23)
    assert m is not None
    assert int(m.balance) == 5
    assert m.delivery_deferred is True
    assert m.is_active is False
    assert m.delivery_start_date == date(2026, 3, 1)


def test_miniprogram_resume_syncs_is_active(v3_db: Session) -> None:
    m = _member(v3_db, mid=24, phone="13700000002", deferred=True, start=date(2026, 3, 1), balance=3)
    v3_db.add(
        MemberAddress(
            id=1,
            member_id=24,
            contact_name="测试",
            contact_phone="13700000002",
            map_location_text="某小区",
            door_detail="1号",
            lng=121.0,
            lat=31.0,
            is_default=True,
        )
    )
    v3_db.commit()
    from app.services.member.member_delivery_state_service import apply_resume_delivery

    apply_resume_delivery(v3_db, m)
    v3_db.commit()
    m = v3_db.get(Member, 24)
    assert m is not None
    assert m.delivery_deferred is False
    assert m.is_active is True


def test_lifecycle_card_not_open(v3_db: Session) -> None:
    m = _member(v3_db, mid=22, phone="19900001111", deferred=True, balance=5)
    order = MemberCardOrder(
        id=3,
        member_id=22,
        tenant_id=1,
        store_id=1,
        membership_template_id=1,
        card_kind="周卡",
        pay_channel=CardPayChannel.WECHAT.value,
        pay_status=CardOrderPayStatus.PAID.value,
        amount_yuan=Decimal("99.00"),
        applied_to_member=True,
        activation_mode=CardOrderActivationMode.DEFER_NOT_OPEN.value,
        meal_periods_snapshot=["lunch"],
        created_by="admin",
    )
    v3_db.add(order)
    v3_db.commit()
    view = resolve_member_lifecycle(v3_db, m)
    assert view.code == MemberLifecycleCode.CARD_NOT_OPEN.value


def test_resolve_members_lifecycle_map_matches_single(v3_db: Session) -> None:
    """批量 lifecycle 与逐条 resolve 结果一致。"""
    m1 = _member(v3_db, mid=30, phone="19900001112", deferred=True, balance=5, start=date(2026, 3, 1))
    m2 = _member(v3_db, mid=31, phone="19900001113", deferred=False, balance=3, start=date(2026, 3, 1))
    v3_db.add(
        MemberCardOrder(
            id=10,
            member_id=30,
            tenant_id=1,
            store_id=1,
            membership_template_id=1,
            card_kind="周卡",
            pay_channel=CardPayChannel.WECHAT.value,
            pay_status=CardOrderPayStatus.PAID.value,
            amount_yuan=Decimal("99.00"),
            applied_to_member=True,
            activation_mode=CardOrderActivationMode.DEFER_NOT_OPEN.value,
            meal_periods_snapshot=["lunch"],
            created_by="admin",
        )
    )
    v3_db.commit()
    batch = resolve_members_lifecycle_map(v3_db, [m1, m2])
    for m in (m1, m2):
        single = resolve_member_lifecycle(v3_db, m)
        batched = batch[int(m.id)]
        assert batched.code == single.code
        assert batched.label == single.label
        assert batched.setup_alert == single.setup_alert
        assert batched.overlays == single.overlays
