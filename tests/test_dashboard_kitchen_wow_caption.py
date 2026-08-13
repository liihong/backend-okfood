"""营业概览「同比上周」：后厨出餐总数差值文案。"""

from app.services.admin.admin_service import _dashboard_meals_week_over_week_caption


def test_kitchen_wow_caption_delta() -> None:
    assert _dashboard_meals_week_over_week_caption(meals=200, baseline_meals=217) == "较上周-17"
    assert _dashboard_meals_week_over_week_caption(meals=220, baseline_meals=200) == "较上周+20"
    assert _dashboard_meals_week_over_week_caption(meals=200, baseline_meals=200) == "较上周持平"


def test_kitchen_wow_caption_missing_side() -> None:
    assert _dashboard_meals_week_over_week_caption(meals=None, baseline_meals=200) == ""
    assert _dashboard_meals_week_over_week_caption(meals=200, baseline_meals=None) == ""
    assert _dashboard_meals_week_over_week_caption(meals=None, baseline_meals=None) == ""
