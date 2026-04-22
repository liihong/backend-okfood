"""骑手配送费计价单元测试。"""

from decimal import Decimal

import pytest

from app.core.config import get_settings
from app.core.courier_delivery_fee import courier_delivery_fee_yuan_for_meal_units


@pytest.fixture(autouse=True)
def _fresh_settings_cache():
    """避免用例间共用 get_settings() 的 lru_cache（如 monkeypatch 环境变量后污染后续用例）。"""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_fee_one_unit():
    s = get_settings()
    assert courier_delivery_fee_yuan_for_meal_units(1) == s.COURIER_DELIVERY_BASE_YUAN


def test_fee_three_units():
    assert courier_delivery_fee_yuan_for_meal_units(3) == Decimal("6.00")


def test_fee_invalid_falls_back_to_one_unit():
    s = get_settings()
    assert courier_delivery_fee_yuan_for_meal_units(0) == s.COURIER_DELIVERY_BASE_YUAN
    assert courier_delivery_fee_yuan_for_meal_units(-1) == s.COURIER_DELIVERY_BASE_YUAN


def test_fee_respects_env(monkeypatch):
    monkeypatch.setenv("COURIER_DELIVERY_BASE_YUAN", "5")
    monkeypatch.setenv("COURIER_DELIVERY_EXTRA_PER_UNIT_YUAN", "2")
    assert courier_delivery_fee_yuan_for_meal_units(1) == Decimal("5.00")
    assert courier_delivery_fee_yuan_for_meal_units(3) == Decimal("9.00")


@pytest.mark.parametrize(
    "units,expected",
    [
        (1, Decimal("4.00")),
        (2, Decimal("5.00")),
        (10, Decimal("13.00")),
    ],
)
def test_fee_formula(units: int, expected: Decimal):
    assert courier_delivery_fee_yuan_for_meal_units(units) == expected
