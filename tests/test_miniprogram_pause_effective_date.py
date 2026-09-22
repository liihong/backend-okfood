"""小程序暂停从明天生效：当天大表仍在，明天排除；后台立刻暂停不受影响。"""

from datetime import date
from types import SimpleNamespace

from app.services.delivery.courier_service import member_on_subscription_delivery_schedule
from app.services.member.member_delivery_state_service import (
    apply_delivery_blocked,
    apply_miniprogram_pause_delivery,
    apply_pause_delivery,
    pause_blocks_delivery_date,
)


class _DummyDb:
    def add(self, _obj):
        return None


def _member(**kwargs):
    defaults = {
        "deleted_at": None,
        "is_active": True,
        "delivery_deferred": False,
        "pause_effective_date": None,
        "balance": 10,
        "daily_meal_units": 1,
        "leave_range_start": None,
        "leave_range_end": None,
        "is_leaved_tomorrow": False,
        "tomorrow_leave_target_date": None,
        "delivery_start_date": date(2026, 9, 1),
        "skip_subscription_saturday": False,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_pause_blocks_only_from_effective_date() -> None:
    today = date(2026, 9, 22)
    tomorrow = date(2026, 9, 23)
    m = _member(pause_effective_date=tomorrow)
    assert pause_blocks_delivery_date(m, today) is False
    assert pause_blocks_delivery_date(m, tomorrow) is True


def test_immediate_deferred_still_blocks_today() -> None:
    today = date(2026, 9, 22)
    m = _member(delivery_deferred=True, pause_effective_date=None)
    assert pause_blocks_delivery_date(m, today) is True


def test_pending_pause_keeps_today_schedule() -> None:
    today = date(2026, 9, 22)
    tomorrow = date(2026, 9, 23)
    m = _member(pause_effective_date=tomorrow)
    assert member_on_subscription_delivery_schedule(m, delivery_date=today, today=today) is True
    assert member_on_subscription_delivery_schedule(m, delivery_date=tomorrow, today=today) is False


def test_admin_immediate_pause_clears_pending_date() -> None:
    member = SimpleNamespace(
        delivery_deferred=False,
        is_active=True,
        pause_effective_date=date(2026, 9, 23),
    )
    apply_pause_delivery(_DummyDb(), member)
    assert member.delivery_deferred is True
    assert member.is_active is False
    assert member.pause_effective_date is None


def test_apply_delivery_blocked_clears_pending_date() -> None:
    member = SimpleNamespace(
        delivery_deferred=False,
        is_active=True,
        pause_effective_date=date(2026, 9, 23),
    )
    apply_delivery_blocked(_DummyDb(), member)
    assert member.pause_effective_date is None


def test_miniprogram_pause_defers_when_on_today_sheet(monkeypatch) -> None:
    today = date(2026, 9, 22)
    member = _member()
    monkeypatch.setattr(
        "app.services.meal_period.lunch_schedule.member_on_lunch_delivery_schedule",
        lambda *args, **kwargs: True,
    )
    monkeypatch.setattr(
        "app.services.dinner.schedule.member_on_dinner_delivery_schedule",
        lambda *args, **kwargs: False,
    )
    mode = apply_miniprogram_pause_delivery(
        _DummyDb(),
        member,
        now=SimpleNamespace(date=lambda: today, time=lambda: None),
    )
    assert mode == "tomorrow"
    assert member.delivery_deferred is False
    assert member.is_active is True
    assert member.pause_effective_date == date(2026, 9, 23)


def test_miniprogram_pause_immediate_when_not_on_today_sheet(monkeypatch) -> None:
    today = date(2026, 9, 22)
    member = _member()
    monkeypatch.setattr(
        "app.services.meal_period.lunch_schedule.member_on_lunch_delivery_schedule",
        lambda *args, **kwargs: False,
    )
    monkeypatch.setattr(
        "app.services.dinner.schedule.member_on_dinner_delivery_schedule",
        lambda *args, **kwargs: False,
    )
    mode = apply_miniprogram_pause_delivery(
        _DummyDb(),
        member,
        now=SimpleNamespace(date=lambda: today),
    )
    assert mode == "immediate"
    assert member.delivery_deferred is True
    assert member.pause_effective_date is None


def test_leave_fields_unused_by_pause_helper() -> None:
    """预约暂停判定不读请假字段，避免和请假逻辑缠在一起。"""
    today = date(2026, 9, 22)
    m = _member(
        pause_effective_date=date(2026, 9, 23),
        leave_range_start=today,
        leave_range_end=today,
        is_leaved_tomorrow=True,
    )
    assert pause_blocks_delivery_date(m, today) is False
    assert pause_blocks_delivery_date(m, date(2026, 9, 23)) is True
