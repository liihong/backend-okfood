"""请假餐段范围：午餐 / 晚餐 / 全天（仅请假接口使用，不影响菜单 meal_period 归一化）。

某一餐能否请：开卡工单含该餐，或该餐剩余次数大于 0。两者满足其一即可。
不改配送大表的次数判断。
"""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.enums import MealPeriod
from app.models.member import Member
from app.models.member_meal_period_state import MemberMealPeriodState
from app.services.meal_period.card_eligibility import member_entitled_meal_periods

# 全天请假：同时写入午餐（members）与晚餐（member_meal_period_state）
LEAVE_MEAL_PERIOD_ALL = "all"


def normalize_leave_meal_period(meal_period: str | None) -> str:
    """
    请假餐段归一化：lunch / dinner / all。
    未传参默认 lunch，与现网午餐请假一致。
    """
    p = (meal_period or MealPeriod.LUNCH.value).strip().lower()
    if p not in (MealPeriod.LUNCH.value, MealPeriod.DINNER.value, LEAVE_MEAL_PERIOD_ALL):
        raise HTTPException(
            status_code=400,
            detail="meal_period 须为 lunch（午餐）、dinner（晚餐）或 all（全天）",
        )
    return p


def leave_periods_open_for_request(
    entitled: frozenset[str],
    *,
    lunch_balance: int,
    dinner_balance: int,
) -> frozenset[str]:
    """工单含该餐，或该餐剩余次数大于 0，就可以请。全天请假用这个并集。"""
    opened: set[str] = set()
    for period in (MealPeriod.LUNCH.value, MealPeriod.DINNER.value):
        if period in entitled:
            opened.add(period)
    if int(lunch_balance or 0) > 0:
        opened.add(MealPeriod.LUNCH.value)
    if int(dinner_balance or 0) > 0:
        opened.add(MealPeriod.DINNER.value)
    return frozenset(opened)


def _dinner_balance(db: Session, member_id: int) -> int:
    """晚餐剩余次数。没有晚餐行视为 0，不在这里新建行。"""
    row = db.get(
        MemberMealPeriodState,
        {"member_id": int(member_id), "meal_period": MealPeriod.DINNER.value},
    )
    if row is None:
        return 0
    return max(0, int(row.balance or 0))


def leave_target_periods(db: Session, member: Member, leave_meal_period: str) -> frozenset[str]:
    """
    本次请假实际应写入的餐段集合。

    all = 工单餐段与「该餐剩余次数大于 0」的并集。
    单餐段只写对应池。午餐卡只加了晚餐次数时，可以只请晚餐。
    """
    entitled = member_entitled_meal_periods(db, int(member.id))
    opened = leave_periods_open_for_request(
        entitled,
        lunch_balance=int(member.balance or 0),
        dinner_balance=_dinner_balance(db, int(member.id)),
    )
    scope = normalize_leave_meal_period(leave_meal_period)
    if scope == LEAVE_MEAL_PERIOD_ALL:
        return opened
    if scope not in opened:
        label = "晚餐" if scope == MealPeriod.DINNER.value else "午餐"
        raise HTTPException(
            status_code=400,
            detail=f"当前没有{label}可请假：卡种不含该餐，且剩余次数为 0",
        )
    return frozenset({scope})
