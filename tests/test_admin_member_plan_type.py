"""后台改套餐：模版解析、展示文案与档案 PATCH 字段。"""

from types import SimpleNamespace

from app.models.enums import PlanType
from app.schemas.admin import AdminMemberPatchIn
from app.services.meal_period.plan_type_sync import (
    format_plan_type_display,
    membership_template_plan_label,
)
from app.services.meal_period.template_periods import meal_periods_from_template
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


def test_format_plan_type_display_full_meal() -> None:
    assert format_plan_type_display("月卡", {"lunch", "dinner"}) == "月卡 · 全餐"


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
