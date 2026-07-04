"""模版餐段 snapshot 解析：JSON 字符串须正确识别 dinner。"""

from app.models.enums import MealPeriod
from app.models.membership_card_template import MembershipCardTemplate
from app.services.meal_period.template_periods import (
    meal_periods_from_template,
    normalize_meal_periods_list,
    resolve_meal_periods_for_card_order_credit,
)


def test_normalize_meal_periods_list_from_json_string():
    assert normalize_meal_periods_list('["dinner"]') == ["dinner"]


def test_normalize_meal_periods_list_from_list():
    assert normalize_meal_periods_list(["dinner"]) == ["dinner"]
    assert normalize_meal_periods_list(["lunch", "dinner"]) == ["lunch", "dinner"]


def test_normalize_meal_periods_list_empty_defaults_lunch():
    assert normalize_meal_periods_list(None) == ["lunch"]
    assert normalize_meal_periods_list("[]") == ["lunch"]


def test_meal_periods_from_template_infers_full_meal_from_name():
    """全餐卡模版 meal_periods 仍为默认午餐时，应从名称补全午+晚。"""
    tpl = MembershipCardTemplate(
        tenant_id=1,
        store_id=1,
        kind_label="周卡",
        name="午餐晚餐全餐卡",
        meals_grant=6,
        meal_periods=["lunch"],
        is_active=True,
    )
    assert meal_periods_from_template(tpl) == ["lunch", "dinner"]


def test_meal_periods_from_template_respects_explicit_dinner():
    tpl = MembershipCardTemplate(
        tenant_id=1,
        store_id=1,
        kind_label="周卡",
        name="晚餐周卡",
        meals_grant=6,
        meal_periods=["dinner"],
        is_active=True,
    )
    assert meal_periods_from_template(tpl) == ["dinner"]


def test_resolve_meal_periods_for_card_order_credit_unions_snapshot():
    """入账餐段：模版推断与工单快照取并集，避免漏晚餐。"""
    tpl = MembershipCardTemplate(
        tenant_id=1,
        store_id=1,
        kind_label="周卡",
        name="午餐晚餐全餐卡",
        meals_grant=6,
        meal_periods=["lunch"],
        is_active=True,
    )
    periods = resolve_meal_periods_for_card_order_credit(
        order_meal_periods_snapshot=["lunch"],
        template=tpl,
    )
    assert periods == ["lunch", "dinner"]


def test_resolve_meal_periods_empty_snapshot_does_not_force_lunch_on_dinner_template():
    """工单无快照时，纯晚餐模版不得因默认午餐并入午餐池。"""
    tpl = MembershipCardTemplate(
        tenant_id=1,
        store_id=1,
        kind_label="周卡",
        name="晚餐周卡",
        meals_grant=6,
        meal_periods=["dinner"],
        is_active=True,
    )
    periods = resolve_meal_periods_for_card_order_credit(
        order_meal_periods_snapshot=None,
        template=tpl,
    )
    assert periods == ["dinner"]
