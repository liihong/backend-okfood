"""餐段 normalize：非法值拒绝，未传默认午餐。"""

import pytest
from fastapi import HTTPException

from app.models.enums import MealPeriod
from app.services.meal_period.constants import DEFAULT_MEAL_PERIOD
from app.services.meal_period.normalize import normalize_meal_period


def test_normalize_defaults_to_lunch_when_none():
    assert normalize_meal_period(None) == MealPeriod.LUNCH.value
    assert normalize_meal_period("") == DEFAULT_MEAL_PERIOD


def test_normalize_accepts_dinner():
    assert normalize_meal_period("dinner") == MealPeriod.DINNER.value
    assert normalize_meal_period(" Dinner ") == MealPeriod.DINNER.value


def test_normalize_rejects_invalid_not_silent_lunch():
    with pytest.raises(HTTPException) as exc:
        normalize_meal_period("brunch")
    assert exc.value.status_code == 400
    assert "lunch" in exc.value.detail
