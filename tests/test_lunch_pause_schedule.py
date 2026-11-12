"""午餐单独暂停：只断言午餐日程开关，不连晚餐暂停，也不改请假字段。"""

from types import SimpleNamespace

from app.services.meal_period.lunch_pause import (
    lunch_schedule_allows_delivery,
    sql_lunch_not_paused,
)


def test_default_not_paused_still_allows_lunch() -> None:
    """字段默认否时，午餐仍按原规则可进名单。"""
    assert lunch_schedule_allows_delivery(lunch_delivery_paused=False) is True


def test_missing_flag_defaults_to_allow() -> None:
    """旧对象没有该字段时按未暂停处理，避免测试替身或未补丁对象被误挡。"""
    member = SimpleNamespace()
    paused = bool(getattr(member, "lunch_delivery_paused", False))
    assert lunch_schedule_allows_delivery(lunch_delivery_paused=paused) is True


def test_paused_lunch_does_not_touch_dinner_leave_or_whole_pause() -> None:
    """勾了暂停午餐只让午餐日程为否。整体暂停、激活、请假、晚餐暂停都保持原值。"""
    member = SimpleNamespace(
        lunch_delivery_paused=True,
        delivery_deferred=False,
        is_active=True,
        is_leaved_tomorrow=False,
        leave_range_start=None,
        leave_range_end=None,
        dinner_delivery_paused=False,
    )
    assert (
        lunch_schedule_allows_delivery(
            lunch_delivery_paused=bool(getattr(member, "lunch_delivery_paused", False))
        )
        is False
    )
    assert member.delivery_deferred is False
    assert member.is_active is True
    assert member.is_leaved_tomorrow is False
    assert member.leave_range_start is None
    assert member.leave_range_end is None
    assert member.dinner_delivery_paused is False


def test_sql_clause_targets_lunch_column_only() -> None:
    """午餐 SQL 条件只引用午餐暂停列，不引用整体暂停或请假列。"""
    rendered = str(sql_lunch_not_paused())
    assert "lunch_delivery_paused" in rendered
    assert "delivery_deferred" not in rendered
    assert "leave_range" not in rendered
