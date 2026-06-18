"""模版餐段 snapshot 解析：JSON 字符串须正确识别 dinner。"""

from app.services.meal_period.template_periods import normalize_meal_periods_list


def test_normalize_meal_periods_list_from_json_string():
    assert normalize_meal_periods_list('["dinner"]') == ["dinner"]


def test_normalize_meal_periods_list_from_list():
    assert normalize_meal_periods_list(["dinner"]) == ["dinner"]
    assert normalize_meal_periods_list(["lunch", "dinner"]) == ["lunch", "dinner"]


def test_normalize_meal_periods_list_empty_defaults_lunch():
    assert normalize_meal_periods_list(None) == ["lunch"]
    assert normalize_meal_periods_list("[]") == ["lunch"]
