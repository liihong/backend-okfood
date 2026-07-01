"""请假餐段范围：午餐 / 晚餐 / 全天（仅请假接口使用，不影响菜单 meal_period 归一化）。"""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.enums import MealPeriod
from app.models.member import Member
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


def leave_target_periods(db: Session, member: Member, leave_meal_period: str) -> frozenset[str]:
    """
    本次请假实际应写入的餐段集合。
    all = 会员已开通餐段的并集；单餐段则仅写对应池，严格与午/晚餐隔离。
    """
    entitled = member_entitled_meal_periods(db, int(member.id))
    scope = normalize_leave_meal_period(leave_meal_period)
    if scope == LEAVE_MEAL_PERIOD_ALL:
        return frozenset(entitled)
    if scope not in entitled:
        label = "晚餐" if scope == MealPeriod.DINNER.value else "午餐"
        raise HTTPException(status_code=400, detail=f"当前会员卡不含{label}配送，无法操作该餐段请假")
    return frozenset({scope})
