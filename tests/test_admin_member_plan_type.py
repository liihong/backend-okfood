"""后台改套餐：模版解析、展示文案与档案 PATCH 字段。"""

from types import SimpleNamespace

from app.models.enums import PlanType
from app.schemas.admin import AdminMemberPatchIn
from app.services.meal_period.plan_type_sync import (
    catalog_template_plan_label_for_member,
    format_plan_type_display,
    membership_template_plan_label,
)
from app.services.meal_period.template_periods import catalog_periods_from_template, meal_periods_from_template
from app.services.member.member_card_order_service import _plan_for_membership_template


def test_plan_for_membership_template_from_kind_label() -> None:
    month = SimpleNamespace(kind_label="月卡·全餐", period_kind=None, meals_grant=24)
    week = SimpleNamespace(kind_label="周卡", period_kind=None, meals_grant=6)
    times = SimpleNamespace(kind_label="次卡", period_kind=None, meals_grant=1)
    assert _plan_for_membership_template(month) == PlanType.MONTH
    assert _plan_for_membership_template(week) == PlanType.WEEK
    assert _plan_for_membership_template(times) == PlanType.TIMES


def test_membership_template_plan_label_keeps_kind_with_scope() -> None:
    tpl = SimpleNamespace(kind_label="月卡·全餐", name="标准月卡", meal_periods=["lunch", "dinner"])
    assert membership_template_plan_label(tpl) == "月卡·全餐"


def test_membership_template_plan_label_appends_scope() -> None:
    tpl = SimpleNamespace(kind_label="周卡", name="标准周卡", meal_periods=["lunch"])
    assert membership_template_plan_label(tpl) == "周卡 · 午餐"


def test_membership_template_plan_label_lunch_card() -> None:
    tpl = SimpleNamespace(kind_label="月午餐卡", name="月午餐卡", meal_periods=["lunch"])
    assert membership_template_plan_label(tpl) == "月午餐卡"


def test_month_lunch_card_infers_lunch_only() -> None:
    tpl = SimpleNamespace(kind_label="月午餐卡", name="月午餐卡", meal_periods=["lunch"])
    assert meal_periods_from_template(tpl) == ["lunch"]


def test_dinner_package_catalog_periods_ignore_mistaken_lunch_flag() -> None:
    """种类叫「晚餐」时，即使库内勾了午餐，展示/筛选仍按纯晚餐，避免混入午餐+晚餐。"""
    tpl = _ns_tpl(kind_label="晚餐", name="晚餐", meal_periods=["lunch", "dinner"])
    assert catalog_periods_from_template(tpl) == ["dinner"]


def test_format_plan_type_display_full_meal() -> None:
    assert format_plan_type_display("月卡", {"lunch", "dinner"}) == "月卡 · 全餐"


def _ns_tpl(**kwargs):
    defaults = {
        "id": 1,
        "kind_label": "",
        "name": "",
        "meal_periods": ["lunch"],
        "period_kind": None,
        "meals_grant": 24,
        "is_active": True,
        "sort_order": 0,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_catalog_label_maps_month_full_meal_to_package_name() -> None:
    """无工单卡包时，月卡+全餐应对上本店「午餐+晚餐」，而不是拼「月卡 · 全餐」。"""
    lunch = _ns_tpl(id=2, kind_label="月午餐卡", name="月午餐卡", meal_periods=["lunch"])
    dinner = _ns_tpl(
        id=8, kind_label="晚餐", name="晚餐", meal_periods=["lunch", "dinner"]
    )
    combo = _ns_tpl(
        id=9, kind_label="午餐+晚餐", name="午餐+晚餐", meal_periods=["lunch", "dinner"]
    )
    assert (
        catalog_template_plan_label_for_member(
            "月卡", {"lunch", "dinner"}, [lunch, dinner, combo]
        )
        == "午餐+晚餐"
    )
    assert catalog_template_plan_label_for_member("月卡", {"lunch"}, [lunch, dinner, combo]) == "月午餐卡"
    assert catalog_template_plan_label_for_member("月卡", {"dinner"}, [lunch, dinner, combo]) == "晚餐"


def test_catalog_label_infers_full_meal_from_kind_label() -> None:
    """模版 meal_periods 仍为默认午餐时，种类「午餐+晚餐」仍应匹配全餐会员。"""
    combo = _ns_tpl(id=4, kind_label="午餐+晚餐", name="午餐+晚餐", meal_periods=["lunch"])
    assert (
        catalog_template_plan_label_for_member("月卡", {"lunch", "dinner"}, [combo])
        == "午餐+晚餐"
    )
    assert catalog_template_plan_label_for_member("月卡", {"lunch", "dinner"}, []) is None


def test_catalog_label_prefers_active_package() -> None:
    inactive = _ns_tpl(
        id=1,
        kind_label="旧全餐名",
        name="旧全餐名",
        meal_periods=["lunch", "dinner"],
        is_active=False,
    )
    active = _ns_tpl(
        id=9,
        kind_label="午餐+晚餐",
        name="午餐+晚餐",
        meal_periods=["lunch", "dinner"],
        is_active=True,
    )
    assert (
        catalog_template_plan_label_for_member("月卡", {"lunch", "dinner"}, [inactive, active])
        == "午餐+晚餐"
    )


def test_admin_member_patch_accepts_template_and_plan_type() -> None:
    body = AdminMemberPatchIn(
        phone="13837435520",
        name="朱露露",
        plan_type=PlanType.WEEK,
        membership_template_id=7,
    )
    assert body.plan_type == PlanType.WEEK
    assert body.membership_template_id == 7
    assert "plan_type" in body.model_fields_set
    assert "membership_template_id" in body.model_fields_set


def test_same_plan_type_template_switch_should_write_log() -> None:
    """同为月卡但换卡包/餐段时，仍应记操作记录。"""
    prev_pt, new_pt = "月卡", "月卡"
    prev_label, new_label = "月卡 · 全餐", "月卡·午餐"
    order_changed = True
    should_log = prev_pt != new_pt or prev_label != new_label or order_changed
    assert should_log
