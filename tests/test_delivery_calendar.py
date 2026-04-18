"""订阅配送日历：周日 + 法定节假日不配送；普通周六与补班周六规则。"""

from datetime import date

import pytest

pytest.importorskip("chinese_calendar")

from app.core.delivery_calendar import is_subscription_delivery_day


def test_sunday_never_delivery():
    # 普通周日
    assert is_subscription_delivery_day(date(2024, 6, 9)) is False
    # 法定补班周日仍不配送（业务约定）
    assert is_subscription_delivery_day(date(2024, 2, 4)) is False


def test_normal_weekday_and_saturday():
    assert is_subscription_delivery_day(date(2024, 6, 3)) is True
    assert is_subscription_delivery_day(date(2024, 6, 8)) is True


def test_national_day_weekday_off():
    assert is_subscription_delivery_day(date(2024, 10, 1)) is False


def test_saturday_in_golden_week_off():
    assert is_subscription_delivery_day(date(2024, 10, 5)) is False


def test_makeup_saturday_works():
    """补班周六：国务院安排工作的周六，应配送。"""
    assert is_subscription_delivery_day(date(2025, 10, 11)) is True
