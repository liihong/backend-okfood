"""00:01 没把预约份数落库时，推单前要提醒；推单后的 pending 是正常次日预约。"""

from app.services.admin.admin_system_notification_service import (
    pending_meal_units_alert_message,
    pending_meal_units_apply_warning,
    stuck_pending_meal_unit_counts,
)


def test_pending_before_push_is_a_failed_apply() -> None:
    lunch, dinner = stuck_pending_meal_unit_counts(
        lunch_pending=3,
        dinner_pending=1,
        lunch_sheet_pushed_today=False,
        dinner_sheet_pushed_today=False,
    )
    assert (lunch, dinner) == (3, 1)
    text = pending_meal_units_alert_message(lunch_stuck=lunch, dinner_stuck=dinner)
    assert "午餐待落库 3 人" in text
    assert "晚餐待落库 1 人" in text


def test_pending_after_push_is_not_a_failure() -> None:
    assert stuck_pending_meal_unit_counts(
        lunch_pending=4,
        dinner_pending=2,
        lunch_sheet_pushed_today=True,
        dinner_sheet_pushed_today=True,
    ) == (0, 0)


def test_only_the_unpushed_meal_period_is_alerted() -> None:
    assert stuck_pending_meal_unit_counts(
        lunch_pending=2,
        dinner_pending=5,
        lunch_sheet_pushed_today=True,
        dinner_sheet_pushed_today=False,
    ) == (0, 5)
    warning = pending_meal_units_apply_warning(lunch_pushed=True, dinner_pushed=False)
    assert "午餐" in warning
    assert "已经冻结的大表名单不会改" in warning
