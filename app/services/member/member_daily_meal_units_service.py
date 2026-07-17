"""会员每配送日份数：未推单立即生效；已大表推单则写 pending，由定时任务落库。"""

from __future__ import annotations

from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.timeutil import today_shanghai
from app.models.member import Member
from app.services.member.member_service import MAX_DAILY_MEAL_UNITS, effective_daily_meal_units

DailyMealUnitsChangeMode = Literal["immediate", "scheduled", "unchanged"]


def clamp_daily_meal_units(units: int) -> int:
    """与 DB 校验及 effective_daily_meal_units 封顶一致。"""
    try:
        u = int(units)
    except (TypeError, ValueError):
        return 1
    return max(1, min(u, MAX_DAILY_MEAL_UNITS))


def pending_daily_meal_units(member: Member) -> int | None:
    """待次日生效份数；无预约或非法值时返回 None。"""
    raw = getattr(member, "daily_meal_units_pending", None)
    if raw is None:
        return None
    try:
        u = int(raw)
    except (TypeError, ValueError):
        return None
    if u < 1 or u > MAX_DAILY_MEAL_UNITS:
        return None
    return u


def prep_preview_lunch_daily_meal_units(member: Member) -> int:
    """营业概览明日午餐备餐预览份数：pending 优先，否则取当日生效值。"""
    pending = pending_daily_meal_units(member)
    if pending is not None:
        return pending
    return effective_daily_meal_units(member)


def delivery_sheet_pushed_today_for_store(db: Session, *, store_id: int) -> bool:
    """当日该门店是否已有成功的智能配送大表（订阅合并）顺丰推单。"""
    from app.services.delivery.delivery_day_lock_service import has_delivery_sheet_sf_push_on_date

    return has_delivery_sheet_sf_push_on_date(
        db,
        store_id=int(store_id),
        delivery_date=today_shanghai(),
    )


def set_member_daily_meal_units_change(
    db: Session,
    member: Member,
    units: int,
) -> DailyMealUnitsChangeMode:
    """
    写入份数变更：当日未大表推单则立即更新 ``daily_meal_units``；已推单则写 ``pending``。

    与推单后冻结快照兼容：推单前改动能被当日大表/顺丰创单读到。
    """
    target = clamp_daily_meal_units(units)
    current = effective_daily_meal_units(member)
    if target == current:
        changed = member.daily_meal_units_pending is not None
        member.daily_meal_units_pending = None
        return "immediate" if changed else "unchanged"

    if delivery_sheet_pushed_today_for_store(db, store_id=int(member.store_id)):
        prev_pending = member.daily_meal_units_pending
        if prev_pending is not None and int(prev_pending) == target:
            return "unchanged"
        member.daily_meal_units_pending = target
        return "scheduled"

    member.daily_meal_units = target
    member.daily_meal_units_pending = None
    return "immediate"


def queue_daily_meal_units_change(member: Member, units: int) -> bool:
    """
    预约次日生效的每配送日份数（不改动当日 daily_meal_units）。

    若目标值与当日已生效值相同，则清空 pending（视为取消预约）。
    返回是否产生字段变更（供操作日志判断）。
    """
    target = clamp_daily_meal_units(units)
    current = effective_daily_meal_units(member)
    if target == current:
        changed = member.daily_meal_units_pending is not None
        member.daily_meal_units_pending = None
        return changed
    prev_pending = member.daily_meal_units_pending
    if prev_pending is not None and int(prev_pending) == target:
        return False
    member.daily_meal_units_pending = target
    return True


def apply_all_pending_daily_meal_units(db: Session) -> int:
    """
    将 daily_meal_units_pending 写入 daily_meal_units 并清空 pending。
    供每日 00:01 定时任务调用；返回实际落库会员数。
    """
    rows = db.scalars(
        select(Member).where(
            Member.deleted_at.is_(None),
            Member.daily_meal_units_pending.isnot(None),
        )
    ).all()
    n = 0
    for m in rows:
        pending = pending_daily_meal_units(m)
        if pending is None:
            m.daily_meal_units_pending = None
            continue
        m.daily_meal_units = pending
        m.daily_meal_units_pending = None
        n += 1
    return n
