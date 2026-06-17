"""分餐段请假：午餐委托 members 表现有字段；晚餐读 member_meal_period_state。"""

from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.models.enums import MealPeriod
from app.models.member import Member
from app.models.member_meal_period_state import MemberMealPeriodState
from app.services.leave import is_absent_on_delivery_date, is_absent_on_delivery_date_for_leave_fields


def is_dinner_absent_on_delivery_date(
    state_row: MemberMealPeriodState | None,
    delivery_date: date,
    *,
    today: date,
) -> bool:
    """晚餐分餐段请假：基于已加载的 member_meal_period_state 行判断。"""
    if state_row is None:
        return False
    return is_absent_on_delivery_date_for_leave_fields(
        leave_range_start=state_row.leave_range_start,
        leave_range_end=state_row.leave_range_end,
        is_leaved_tomorrow=bool(state_row.is_leaved_tomorrow),
        tomorrow_leave_target_date=state_row.tomorrow_leave_target_date,
        delivery_date=delivery_date,
        today=today,
    )


def is_absent_on_delivery_date_for_period(
    db: Session,
    member: Member,
    delivery_date: date,
    *,
    meal_period: str,
    today: date,
) -> bool:
    """指定餐段是否在业务日请假；lunch 与现网 is_absent_on_delivery_date 完全一致。"""
    period = (meal_period or MealPeriod.LUNCH.value).strip().lower()
    if period == MealPeriod.LUNCH.value:
        return is_absent_on_delivery_date(member, delivery_date, today=today)
    row = db.get(
        MemberMealPeriodState,
        {"member_id": int(member.id), "meal_period": MealPeriod.DINNER.value},
    )
    return is_dinner_absent_on_delivery_date(row, delivery_date, today=today)
