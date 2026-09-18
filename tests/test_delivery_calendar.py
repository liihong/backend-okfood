"""订阅配送业务日：补班周日与普通周日口径。"""

from datetime import date

from app.core.delivery_calendar import is_subscription_delivery_day


def test_regular_sunday_not_delivery_day() -> None:
    """普通周日（非国务院补班）不配送。"""
    d = date(2026, 9, 13)  # 周日，非调休补班
    assert d.weekday() == 6
    assert is_subscription_delivery_day(d) is False


def test_makeup_work_sunday_is_delivery_day() -> None:
    """国庆调休补班周日随国务院工作日，视为配送日。"""
    d = date(2026, 9, 20)
    assert d.weekday() == 6
    assert is_subscription_delivery_day(d) is True


def test_weekday_monday_is_delivery_day() -> None:
    d = date(2026, 9, 21)
    assert is_subscription_delivery_day(d) is True
