"""晚餐请假：委托统一编排层，本模块保留兼容入口。"""

from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.models.enums import LeaveType
from app.schemas.user import MemberOut
from app.services.meal_period.coordinated_leave import coordinated_leave_request
from app.models.enums import MealPeriod


def dinner_leave_request(
    db: Session,
    member_id: int,
    typ: LeaveType,
    start: date | None,
    end: date | None,
    *,
    skip_leave_deadline: bool = False,
    ip_address: str | None = None,
    source: str = "miniprogram",
    operator: str | None = None,
) -> MemberOut:
    """晚餐餐段请假/取消；写入 member_meal_period_state，不影响午餐请假。"""
    return coordinated_leave_request(
        db,
        member_id,
        typ,
        start,
        end,
        leave_meal_period=MealPeriod.DINNER.value,
        skip_leave_deadline=skip_leave_deadline,
        ip_address=ip_address,
        source=source,
        operator=operator,
    )
