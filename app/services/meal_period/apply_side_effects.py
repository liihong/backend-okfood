"""开卡入账后：若工单含晚餐餐段，初始化 member_meal_period_state（不影响 members 餐段标记）。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.enums import MealPeriod
from app.models.member import Member
from app.models.member_meal_period_state import MemberMealPeriodState
from app.services.meal_period.template_periods import normalize_meal_periods_list


def ensure_meal_period_states_after_card_apply(
    db: Session,
    member: Member,
    meal_periods_snapshot: object,
) -> None:
    """
    购卡入账后按 snapshot 确保晚餐运营态行存在（默认 1 份）。
    午餐份数/请假仍走 members 表，此处不写入 lunch 行。
    """
    periods = normalize_meal_periods_list(meal_periods_snapshot)
    if MealPeriod.DINNER.value not in periods:
        return
    mid = int(member.id)
    existing = db.get(
        MemberMealPeriodState,
        {"member_id": mid, "meal_period": MealPeriod.DINNER.value},
    )
    if existing is not None:
        return
    db.add(
        MemberMealPeriodState(
            member_id=mid,
            meal_period=MealPeriod.DINNER.value,
            daily_meal_units=1,
        )
    )
    db.flush()
