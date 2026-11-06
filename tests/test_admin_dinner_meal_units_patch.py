"""管理端晚餐份数与午餐份数分开提交。"""

from app.schemas.admin import AdminMemberPatchIn


def test_lunch_units_patch_does_not_set_dinner_units() -> None:
    """只传午餐份数时，晚餐字段保持不修改。"""
    body = AdminMemberPatchIn.model_validate({"phone": "13598831121", "daily_meal_units": 2})
    assert body.daily_meal_units == 2
    assert body.dinner_daily_meal_units is None
    assert "dinner_daily_meal_units" not in body.model_fields_set


def test_dinner_units_patch_does_not_set_lunch_units() -> None:
    """只传晚餐份数时，不带午餐份数。"""
    body = AdminMemberPatchIn.model_validate(
        {"phone": "13598831121", "dinner_daily_meal_units": "1"}
    )
    assert body.dinner_daily_meal_units == 1
    assert body.daily_meal_units is None
    assert "daily_meal_units" not in body.model_fields_set


def test_lunch_and_dinner_units_can_differ() -> None:
    body = AdminMemberPatchIn.model_validate(
        {"phone": "13598831121", "daily_meal_units": 2, "dinner_daily_meal_units": 1}
    )
    assert body.daily_meal_units == 2
    assert body.dinner_daily_meal_units == 1
