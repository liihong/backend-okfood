"""分餐段有效份数：午餐完全委托现有 member_service，晚餐读 member_meal_period_state。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import MealPeriod
from app.models.member import Member
from app.models.member_meal_period_state import MemberMealPeriodState
from app.services.member.member_service import effective_daily_meal_units

MAX_DAILY_MEAL_UNITS = 50


def dinner_daily_meal_units_from_state(row: MemberMealPeriodState | None) -> int:
    """从已加载的晚餐运营态行解析份数，无记录时默认 1。"""
    if row is None:
        return 1
    try:
        u = int(row.daily_meal_units)
    except (TypeError, ValueError):
        return 1
    return max(1, min(u, MAX_DAILY_MEAL_UNITS))


def load_dinner_meal_period_states_map(
    db: Session, member_ids: list[int]
) -> dict[int, MemberMealPeriodState]:
    """批量加载晚餐 member_meal_period_state，避免大表逐会员 db.get。"""
    ids = sorted({int(x) for x in member_ids if x is not None})
    if not ids:
        return {}
    rows = db.scalars(
        select(MemberMealPeriodState).where(
            MemberMealPeriodState.member_id.in_(ids),
            MemberMealPeriodState.meal_period == MealPeriod.DINNER.value,
        )
    ).all()
    return {int(r.member_id): r for r in rows}


def effective_daily_meal_units_for_period(db: Session, member: Member, meal_period: str) -> int:
    """
    指定餐段的每配送日份数。
    lunch：与现网 effective_daily_meal_units 完全一致；
    dinner：读 member_meal_period_state，无记录时默认 1。
    """
    period = (meal_period or MealPeriod.LUNCH.value).strip().lower()
    if period == MealPeriod.LUNCH.value:
        return effective_daily_meal_units(member)
    row = db.get(
        MemberMealPeriodState,
        {"member_id": int(member.id), "meal_period": MealPeriod.DINNER.value},
    )
    return dinner_daily_meal_units_from_state(row)
