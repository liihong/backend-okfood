"""晚餐每配送日份数：读写在 member_meal_period_state，推单冻结逻辑与午餐平行。"""

from __future__ import annotations

from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.timeutil import today_shanghai
from app.models.enums import MealPeriod
from app.models.member import Member
from app.models.member_meal_period_state import MemberMealPeriodState
from app.services.member.member_service import MAX_DAILY_MEAL_UNITS
from app.services.meal_period.units import effective_daily_meal_units_for_period

DailyMealUnitsChangeMode = Literal["immediate", "scheduled", "unchanged"]


def get_or_create_dinner_state(db: Session, member_id: int) -> MemberMealPeriodState:
    """确保晚餐运营态行存在（购卡入账时也会初始化；此处兜底）。"""
    mid = int(member_id)
    row = db.get(
        MemberMealPeriodState,
        {"member_id": mid, "meal_period": MealPeriod.DINNER.value},
    )
    if row is not None:
        return row
    row = MemberMealPeriodState(
        member_id=mid,
        meal_period=MealPeriod.DINNER.value,
        daily_meal_units=1,
    )
    db.add(row)
    db.flush()
    return row


def pending_dinner_daily_meal_units(row: MemberMealPeriodState | None) -> int | None:
    raw = getattr(row, "daily_meal_units_pending", None) if row else None
    if raw is None:
        return None
    try:
        u = int(raw)
    except (TypeError, ValueError):
        return None
    if u < 1 or u > MAX_DAILY_MEAL_UNITS:
        return None
    return u


def prep_preview_dinner_daily_meal_units(row: MemberMealPeriodState | None) -> int:
    """营业概览明日晚餐备餐预览份数：pending 优先，否则取当日生效值。"""
    pending = pending_dinner_daily_meal_units(row)
    if pending is not None:
        return pending
    from app.services.meal_period.units import dinner_daily_meal_units_from_state

    return dinner_daily_meal_units_from_state(row)


def dinner_delivery_sheet_pushed_today(db: Session, *, store_id: int) -> bool:
    from app.services.delivery.delivery_day_lock_service import has_dinner_delivery_sheet_sf_push_on_date

    return has_dinner_delivery_sheet_sf_push_on_date(
        db,
        store_id=int(store_id),
        delivery_date=today_shanghai(),
    )


def set_dinner_daily_meal_units_change(
    db: Session,
    member: Member,
    units: int,
) -> DailyMealUnitsChangeMode:
    """晚餐份数变更：未推晚餐大表则立即生效，已推单则写 pending。"""
    target = max(1, min(int(units), MAX_DAILY_MEAL_UNITS))
    row = get_or_create_dinner_state(db, int(member.id))
    current = effective_daily_meal_units_for_period(db, member, MealPeriod.DINNER.value)
    if target == current:
        changed = row.daily_meal_units_pending is not None
        row.daily_meal_units_pending = None
        return "immediate" if changed else "unchanged"

    if dinner_delivery_sheet_pushed_today(db, store_id=int(member.store_id)):
        prev_pending = row.daily_meal_units_pending
        if prev_pending is not None and int(prev_pending) == target:
            return "unchanged"
        row.daily_meal_units_pending = target
        return "scheduled"

    row.daily_meal_units = target
    row.daily_meal_units_pending = None
    return "immediate"


def apply_all_pending_dinner_daily_meal_units(db: Session) -> int:
    """00:01 任务：将晚餐 pending 份数落库（仅处理未删除会员的有效行）。"""
    rows = db.scalars(
        select(MemberMealPeriodState)
        .join(Member, Member.id == MemberMealPeriodState.member_id)
        .where(
            MemberMealPeriodState.meal_period == MealPeriod.DINNER.value,
            MemberMealPeriodState.daily_meal_units_pending.isnot(None),
            Member.deleted_at.is_(None),
        )
    ).all()
    n = 0
    for row in rows:
        pending = pending_dinner_daily_meal_units(row)
        if pending is None:
            row.daily_meal_units_pending = None
            continue
        row.daily_meal_units = pending
        row.daily_meal_units_pending = None
        n += 1
    return n
