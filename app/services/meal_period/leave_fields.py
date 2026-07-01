"""餐段请假字段读写：Member（午餐）与 MemberMealPeriodState（晚餐）字段同名，逻辑共用。"""

from __future__ import annotations

from datetime import date, datetime

from fastapi import HTTPException

from app.core.timeutil import min_leave_start_shanghai, tomorrow_shanghai
from app.models.enums import LeaveType
from app.services.member.leave import is_absent_on_delivery_date_for_leave_fields


def leave_fields_snapshot(row) -> dict[str, str | None]:
    """采集请假字段快照（ISO 日期字符串），供操作日志 before/after。"""
    return {
        "is_leaved_tomorrow": bool(getattr(row, "is_leaved_tomorrow", False)),
        "tomorrow_leave_target_date": (
            row.tomorrow_leave_target_date.isoformat()
            if getattr(row, "tomorrow_leave_target_date", None)
            else None
        ),
        "leave_range_start": (
            row.leave_range_start.isoformat() if getattr(row, "leave_range_start", None) else None
        ),
        "leave_range_end": (
            row.leave_range_end.isoformat() if getattr(row, "leave_range_end", None) else None
        ),
    }


def is_row_absent_on_delivery_date(row, delivery_date: date, *, today: date) -> bool:
    """基于单行请假字段判断指定业务日是否缺席（午/晚餐池通用）。"""
    return is_absent_on_delivery_date_for_leave_fields(
        leave_range_start=getattr(row, "leave_range_start", None),
        leave_range_end=getattr(row, "leave_range_end", None),
        is_leaved_tomorrow=bool(getattr(row, "is_leaved_tomorrow", False)),
        tomorrow_leave_target_date=getattr(row, "tomorrow_leave_target_date", None),
        delivery_date=delivery_date,
        today=today,
    )


def apply_leave_type_to_row(
    row,
    typ: LeaveType,
    start: date | None,
    end: date | None,
    *,
    skip_leave_deadline: bool,
    now: datetime,
) -> None:
    """
    对含请假字段的对象执行变更（Member 或 MemberMealPeriodState）。
    业务规则与现网午餐 leave_request 完全一致。
    """
    if typ == LeaveType.CANCEL:
        row.is_leaved_tomorrow = False
        row.tomorrow_leave_target_date = None
        row.leave_range_start = None
        row.leave_range_end = None
    elif typ == LeaveType.CLEAR_TOMORROW:
        row.is_leaved_tomorrow = False
        row.tomorrow_leave_target_date = None
    elif typ == LeaveType.TOMORROW:
        row.tomorrow_leave_target_date = tomorrow_shanghai()
        row.is_leaved_tomorrow = True
    elif typ == LeaveType.RANGE:
        if not start or not end:
            raise HTTPException(status_code=400, detail="区间请假需提供 start 与 end")
        if end < start:
            raise HTTPException(status_code=400, detail="结束日期不能早于开始日期")
        if not skip_leave_deadline:
            min_day = min_leave_start_shanghai(now)
            if start < min_day or end < min_day:
                raise HTTPException(status_code=400, detail="区间请假须从明天起选日期")
        row.leave_range_start = start
        row.leave_range_end = end
        row.is_leaved_tomorrow = False
        row.tomorrow_leave_target_date = None
    else:
        raise HTTPException(status_code=400, detail="不支持的请假类型")
