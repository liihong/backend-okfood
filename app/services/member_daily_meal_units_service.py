"""会员每配送日份数：次日生效队列与定时落库（方案 B）。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.member import Member
from app.services.member_service import MAX_DAILY_MEAL_UNITS, effective_daily_meal_units


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
