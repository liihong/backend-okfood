"""营业概览明日备餐 preview 份数口径（pending 纳入预览，不影响当日生效值）。"""

from types import SimpleNamespace

from app.services.meal_period.dinner_units import prep_preview_dinner_daily_meal_units
from app.services.member.member_daily_meal_units_service import prep_preview_lunch_daily_meal_units


def test_prep_preview_lunch_uses_pending_when_set():
    m = SimpleNamespace(daily_meal_units=1, daily_meal_units_pending=3)
    assert prep_preview_lunch_daily_meal_units(m) == 3


def test_prep_preview_lunch_falls_back_to_effective():
    m = SimpleNamespace(daily_meal_units=2, daily_meal_units_pending=None)
    assert prep_preview_lunch_daily_meal_units(m) == 2


def test_prep_preview_dinner_uses_pending_when_set():
    row = SimpleNamespace(daily_meal_units=1, daily_meal_units_pending=4)
    assert prep_preview_dinner_daily_meal_units(row) == 4


def test_prep_preview_dinner_falls_back_to_effective():
    row = SimpleNamespace(daily_meal_units=2, daily_meal_units_pending=None)
    assert prep_preview_dinner_daily_meal_units(row) == 2
