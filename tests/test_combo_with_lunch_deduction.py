"""全餐「与午餐一起配送」扣次：不改变纯午餐主路径。"""

from __future__ import annotations

from datetime import date, time
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models.balance_log import BalanceLog
from app.models.delivery_log import DeliveryLog
from app.models.enums import CardOrderPayStatus, CardPayChannel, DeliveryStatus, MealPeriod, PlanType
from app.models.member import Member
from app.models.member_card_order import MemberCardOrder
from app.models.member_meal_period_state import MemberMealPeriodState
from app.models.membership_card_template import MembershipCardTemplate
from app.models.store import Store
from app.models.tenant import Tenant
from app.services.meal_period.combo_with_lunch import (
    coerce_deliver_dinner_with_lunch,
    member_has_combo_delivered_with_lunch,
    snapshot_deliver_dinner_with_lunch_from_template,
    try_apply_dinner_deduction_with_lunch,
)


DELIVERY_DAY = date(2026, 8, 26)  # 周三，便于订阅履约日判定
_tpl_id = 0


def _next_tpl_id() -> int:
    global _tpl_id
    _tpl_id += 1
    return _tpl_id


@pytest.fixture()
def combo_db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    tables = [
        Tenant.__table__,
        Store.__table__,
        Member.__table__,
        MembershipCardTemplate.__table__,
        MemberCardOrder.__table__,
        MemberMealPeriodState.__table__,
        DeliveryLog.__table__,
        BalanceLog.__table__,
    ]
    Base.metadata.create_all(engine, tables=tables)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = SessionLocal()
    try:
        session.add_all(
            [
                Tenant(id=1, name="测试租户", is_active=True),
                Store(id=1, tenant_id=1, name="测试门店", leave_deadline_time=time(21, 0), is_active=True),
            ]
        )
        session.flush()
        yield session
    finally:
        session.close()
        engine.dispose()


def _member(db: Session, *, lunch: int = 10, dinner: int = 10) -> Member:
    m = Member(
        tenant_id=1,
        store_id=1,
        phone="13800001111",
        name="全餐测试",
        balance=lunch,
        daily_meal_units=1,
        meal_quota_total=lunch,
        plan_type=PlanType.MONTH.value,
        is_active=True,
        delivery_start_date=DELIVERY_DAY,
        delivery_deferred=False,
        store_pickup=False,
    )
    db.add(m)
    db.flush()
    db.add(
        MemberMealPeriodState(
            member_id=int(m.id),
            meal_period=MealPeriod.DINNER.value,
            daily_meal_units=1,
            balance=dinner,
            meal_quota_total=dinner,
        )
    )
    db.flush()
    return m


def _paid_order(
    db: Session,
    member: Member,
    *,
    periods: list[str],
    with_lunch: bool,
    template_flag: bool | None = None,
) -> MemberCardOrder:
    tpl = MembershipCardTemplate(
        id=_next_tpl_id(),
        tenant_id=1,
        store_id=1,
        kind_label="月卡",
        name="测试卡",
        meals_grant=24,
        meal_periods=list(periods),
        deliver_dinner_with_lunch=bool(template_flag if template_flag is not None else with_lunch),
        sale_price_yuan=Decimal("100.00"),
        is_active=True,
        sort_order=0,
    )
    db.add(tpl)
    db.flush()
    order = MemberCardOrder(
        member_id=int(member.id),
        tenant_id=1,
        store_id=1,
        membership_template_id=int(tpl.id),
        card_kind="月卡",
        pay_channel=CardPayChannel.OFFLINE.value,
        pay_status=CardOrderPayStatus.PAID.value,
        applied_to_member=True,
        meal_periods_snapshot=list(periods),
        deliver_dinner_with_lunch_snapshot=with_lunch,
        created_by="test",
    )
    db.add(order)
    db.flush()
    return order


def test_coerce_only_true_when_both_periods() -> None:
    assert coerce_deliver_dinner_with_lunch(["lunch"], True) is False
    assert coerce_deliver_dinner_with_lunch(["dinner"], True) is False
    assert coerce_deliver_dinner_with_lunch(["lunch", "dinner"], False) is False
    assert coerce_deliver_dinner_with_lunch(["lunch", "dinner"], True) is True


def test_snapshot_from_template_ignores_flag_without_both_periods(combo_db: Session) -> None:
    tpl = MembershipCardTemplate(
        id=_next_tpl_id(),
        tenant_id=1,
        store_id=1,
        kind_label="晚餐卡",
        name="只晚餐",
        meals_grant=24,
        meal_periods=["dinner"],
        deliver_dinner_with_lunch=True,
        is_active=True,
        sort_order=0,
    )
    combo_db.add(tpl)
    combo_db.flush()
    assert snapshot_deliver_dinner_with_lunch_from_template(tpl, ["dinner"]) is False
    assert snapshot_deliver_dinner_with_lunch_from_template(None, ["lunch", "dinner"]) is False


def test_lunch_only_order_never_triggers_combo(combo_db: Session) -> None:
    m = _member(combo_db)
    _paid_order(combo_db, m, periods=["lunch"], with_lunch=True)
    assert member_has_combo_delivered_with_lunch(combo_db, int(m.id)) is False
    assert try_apply_dinner_deduction_with_lunch(
        combo_db, m, delivery_date=DELIVERY_DAY, operator="test"
    ) is False
    dinner = combo_db.get(
        MemberMealPeriodState,
        {"member_id": int(m.id), "meal_period": MealPeriod.DINNER.value},
    )
    assert int(dinner.balance) == 10
    assert m.balance == 10


def test_split_combo_does_not_deduct_dinner_on_lunch(combo_db: Session) -> None:
    m = _member(combo_db)
    _paid_order(combo_db, m, periods=["lunch", "dinner"], with_lunch=False)
    assert member_has_combo_delivered_with_lunch(combo_db, int(m.id)) is False
    assert try_apply_dinner_deduction_with_lunch(
        combo_db, m, delivery_date=DELIVERY_DAY, operator="test"
    ) is False
    dinner = combo_db.get(
        MemberMealPeriodState,
        {"member_id": int(m.id), "meal_period": MealPeriod.DINNER.value},
    )
    assert int(dinner.balance) == 10


def test_together_combo_deducts_dinner_and_is_idempotent(combo_db: Session) -> None:
    m = _member(combo_db)
    _paid_order(combo_db, m, periods=["lunch", "dinner"], with_lunch=True)
    assert try_apply_dinner_deduction_with_lunch(
        combo_db, m, delivery_date=DELIVERY_DAY, operator="test"
    ) is True
    dinner = combo_db.get(
        MemberMealPeriodState,
        {"member_id": int(m.id), "meal_period": MealPeriod.DINNER.value},
    )
    assert int(dinner.balance) == 9
    assert m.balance == 10
    log = combo_db.scalar(
        select(DeliveryLog).where(
            DeliveryLog.member_id == int(m.id),
            DeliveryLog.delivery_date == DELIVERY_DAY,
            DeliveryLog.meal_period == MealPeriod.DINNER.value,
        )
    )
    assert log is not None
    assert log.status == DeliveryStatus.DELIVERED.value
    assert try_apply_dinner_deduction_with_lunch(
        combo_db, m, delivery_date=DELIVERY_DAY, operator="test"
    ) is False
    combo_db.refresh(dinner)
    assert int(dinner.balance) == 9


def test_insufficient_dinner_does_not_raise_or_change_lunch(combo_db: Session) -> None:
    m = _member(combo_db, lunch=10, dinner=0)
    _paid_order(combo_db, m, periods=["lunch", "dinner"], with_lunch=True)
    assert try_apply_dinner_deduction_with_lunch(
        combo_db, m, delivery_date=DELIVERY_DAY, operator="test"
    ) is False
    assert m.balance == 10
    dinner = combo_db.get(
        MemberMealPeriodState,
        {"member_id": int(m.id), "meal_period": MealPeriod.DINNER.value},
    )
    assert int(dinner.balance) == 0


def test_template_edit_does_not_change_applied_snapshot(combo_db: Session) -> None:
    m = _member(combo_db)
    order = _paid_order(combo_db, m, periods=["lunch", "dinner"], with_lunch=True)
    tpl = combo_db.get(MembershipCardTemplate, int(order.membership_template_id))
    assert tpl is not None
    tpl.deliver_dinner_with_lunch = False
    combo_db.flush()
    assert member_has_combo_delivered_with_lunch(combo_db, int(m.id)) is True


def test_legacy_snapshot_false_follows_template_together(combo_db: Session) -> None:
    """历史全餐卡快照默认 false：模版勾选一起配送时午餐送达仍连带扣晚餐。"""
    m = _member(combo_db)
    _paid_order(combo_db, m, periods=["lunch", "dinner"], with_lunch=False, template_flag=True)
    assert member_has_combo_delivered_with_lunch(combo_db, int(m.id)) is True
    assert try_apply_dinner_deduction_with_lunch(
        combo_db, m, delivery_date=DELIVERY_DAY, operator="test"
    ) is True
    dinner = combo_db.get(
        MemberMealPeriodState,
        {"member_id": int(m.id), "meal_period": MealPeriod.DINNER.value},
    )
    assert int(dinner.balance) == 9
    assert m.balance == 10
    # 已送达则幂等，晚餐不会扣第二次
    assert try_apply_dinner_deduction_with_lunch(
        combo_db, m, delivery_date=DELIVERY_DAY, operator="test"
    ) is False
    combo_db.refresh(dinner)
    assert int(dinner.balance) == 9


def test_separate_lunch_and_dinner_cards_not_combo(combo_db: Session) -> None:
    m = _member(combo_db)
    _paid_order(combo_db, m, periods=["lunch"], with_lunch=False)
    _paid_order(combo_db, m, periods=["dinner"], with_lunch=False, template_flag=False)
    assert member_has_combo_delivered_with_lunch(combo_db, int(m.id)) is False


def test_lunch_fulfillment_without_flag_only_deducts_lunch(combo_db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services.admin import admin_delivery_fulfillment_service as svc

    monkeypatch.setattr(svc, "is_subscription_delivery_day", lambda _d: True)
    m = _member(combo_db)
    _paid_order(combo_db, m, periods=["lunch"], with_lunch=False)
    out = svc._subscription_fulfilled_apply(
        combo_db,
        member_id=int(m.id),
        delivery_date=DELIVERY_DAY,
        operator_tag="admin:test",
        kind="home",
        ok_ids={int(m.id)},
        meal_period="lunch",
    )
    assert out is not None
    combo_db.flush()
    combo_db.refresh(m)
    assert m.balance == 9
    dinner = combo_db.get(
        MemberMealPeriodState,
        {"member_id": int(m.id), "meal_period": MealPeriod.DINNER.value},
    )
    assert int(dinner.balance) == 10
    dinner_log = combo_db.scalar(
        select(DeliveryLog).where(
            DeliveryLog.member_id == int(m.id),
            DeliveryLog.meal_period == MealPeriod.DINNER.value,
        )
    )
    assert dinner_log is None


def test_lunch_fulfillment_with_flag_deducts_both(combo_db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services.admin import admin_delivery_fulfillment_service as svc

    monkeypatch.setattr(svc, "is_subscription_delivery_day", lambda _d: True)
    m = _member(combo_db)
    _paid_order(combo_db, m, periods=["lunch", "dinner"], with_lunch=True)
    out = svc._subscription_fulfilled_apply(
        combo_db,
        member_id=int(m.id),
        delivery_date=DELIVERY_DAY,
        operator_tag="admin:test",
        kind="home",
        ok_ids={int(m.id)},
        meal_period="lunch",
    )
    assert out is not None
    combo_db.flush()
    combo_db.refresh(m)
    assert m.balance == 9
    dinner = combo_db.get(
        MemberMealPeriodState,
        {"member_id": int(m.id), "meal_period": MealPeriod.DINNER.value},
    )
    assert int(dinner.balance) == 9
    lunch_log = combo_db.scalar(
        select(DeliveryLog).where(
            DeliveryLog.member_id == int(m.id),
            DeliveryLog.meal_period == MealPeriod.LUNCH.value,
        )
    )
    dinner_log = combo_db.scalar(
        select(DeliveryLog).where(
            DeliveryLog.member_id == int(m.id),
            DeliveryLog.meal_period == MealPeriod.DINNER.value,
        )
    )
    assert lunch_log is not None and lunch_log.status == DeliveryStatus.DELIVERED.value
    assert dinner_log is not None and dinner_log.status == DeliveryStatus.DELIVERED.value


def test_legacy_member_lunch_fulfillment_deducts_both_and_dinner_sheet_is_idempotent(
    combo_db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """老会员快照 false、模版勾选一起配送：午餐扣午+晚；再标晚餐送达不重复扣。"""
    from app.services.admin import admin_delivery_fulfillment_service as svc

    monkeypatch.setattr(svc, "is_subscription_delivery_day", lambda _d: True)
    m = _member(combo_db)
    _paid_order(combo_db, m, periods=["lunch", "dinner"], with_lunch=False, template_flag=True)
    out = svc._subscription_fulfilled_apply(
        combo_db,
        member_id=int(m.id),
        delivery_date=DELIVERY_DAY,
        operator_tag="admin:test",
        kind="home",
        ok_ids={int(m.id)},
        meal_period="lunch",
    )
    assert out is not None
    combo_db.flush()
    combo_db.refresh(m)
    assert m.balance == 9
    dinner = combo_db.get(
        MemberMealPeriodState,
        {"member_id": int(m.id), "meal_period": MealPeriod.DINNER.value},
    )
    assert int(dinner.balance) == 9
    dinner_again = svc._subscription_fulfilled_apply(
        combo_db,
        member_id=int(m.id),
        delivery_date=DELIVERY_DAY,
        operator_tag="admin:test",
        kind="home",
        ok_ids={int(m.id)},
        meal_period="dinner",
    )
    assert dinner_again is None
    combo_db.refresh(dinner)
    assert int(dinner.balance) == 9
    assert m.balance == 9
