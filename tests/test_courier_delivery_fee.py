"""骑手配送费计价单元测试。"""

from decimal import Decimal

import pytest

from app.core.courier_delivery_fee import courier_delivery_fee_yuan_for_meal_units


@pytest.fixture
def _patch_delivery_config(monkeypatch):
    """默认模拟库内配置：首份 4 元，每多一份 +1 元。"""

    def _set(base: str | Decimal, extra: str | Decimal):
        b = Decimal(base)
        e = Decimal(extra)
        monkeypatch.setattr(
            "app.core.courier_delivery_fee.get_courier_delivery_fee_config",
            lambda _db: (b, e),
        )

    return _set


def test_fee_one_unit(_patch_delivery_config):
    _patch_delivery_config("4.00", "1.00")
    assert courier_delivery_fee_yuan_for_meal_units(None, 1) == Decimal("4.00")


def test_fee_three_units(_patch_delivery_config):
    _patch_delivery_config("4.00", "1.00")
    assert courier_delivery_fee_yuan_for_meal_units(None, 3) == Decimal("6.00")


def test_fee_invalid_falls_back_to_one_unit(_patch_delivery_config):
    _patch_delivery_config("4.00", "1.00")
    assert courier_delivery_fee_yuan_for_meal_units(None, 0) == Decimal("4.00")
    assert courier_delivery_fee_yuan_for_meal_units(None, -1) == Decimal("4.00")


def test_fee_custom_config(_patch_delivery_config):
    _patch_delivery_config("5.00", "2.00")
    assert courier_delivery_fee_yuan_for_meal_units(None, 1) == Decimal("5.00")
    assert courier_delivery_fee_yuan_for_meal_units(None, 3) == Decimal("9.00")


@pytest.mark.parametrize(
    "units,expected",
    [
        (1, Decimal("4.00")),
        (2, Decimal("5.00")),
        (10, Decimal("13.00")),
    ],
)
def test_fee_formula(_patch_delivery_config, units: int, expected: Decimal):
    _patch_delivery_config("4.00", "1.00")
    assert courier_delivery_fee_yuan_for_meal_units(None, units) == expected
