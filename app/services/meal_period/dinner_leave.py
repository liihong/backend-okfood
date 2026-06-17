"""晚餐请假：写入 member_meal_period_state，业务规则与午餐 leave_request 平行。"""

from __future__ import annotations

from datetime import date

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.timeutil import min_leave_start_shanghai, now_shanghai, today_shanghai, tomorrow_shanghai
from app.models.enums import LeaveType, MealPeriod
from app.models.member import Member
from app.services.member_operation_log_service import (
    OP_LEAVE_CANCEL,
    OP_LEAVE_CLEAR_TOMORROW,
    OP_LEAVE_RANGE,
    OP_LEAVE_TOMORROW,
    record_member_operation,
)


def _ensure_dinner_entitled(db: Session, member: Member) -> None:
    periods = member_entitled_meal_periods(db, int(member.id))
    if MealPeriod.DINNER.value not in periods:
        raise HTTPException(status_code=400, detail="当前会员卡不含晚餐配送，无法操作晚餐请假")


def _dinner_leave_snapshot(row) -> dict:
    return {
        "is_leaved_tomorrow": bool(row.is_leaved_tomorrow),
        "tomorrow_leave_target_date": (
            row.tomorrow_leave_target_date.isoformat() if row.tomorrow_leave_target_date else None
        ),
        "leave_range_start": row.leave_range_start.isoformat() if row.leave_range_start else None,
        "leave_range_end": row.leave_range_end.isoformat() if row.leave_range_end else None,
    }


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
    """晚餐餐段请假/取消；午餐字段不受影响。"""
    m = db.get(Member, member_id)
    if not m or m.deleted_at is not None:
        raise HTTPException(status_code=404, detail="用户不存在")
    _ensure_dinner_entitled(db, m)

    row = get_or_create_dinner_state(db, int(member_id))
    now = now_shanghai()
    prev = _dinner_leave_snapshot(row)
    today_d = today_shanghai()
    before_absent_today = is_absent_on_delivery_date_for_leave_fields(
        leave_range_start=row.leave_range_start,
        leave_range_end=row.leave_range_end,
        is_leaved_tomorrow=bool(row.is_leaved_tomorrow),
        tomorrow_leave_target_date=row.tomorrow_leave_target_date,
        delivery_date=today_d,
        today=today_d,
    )

    if source == "miniprogram":
        from app.services.leave import guard_member_self_leave_during_sf_fulfillment

        guard_member_self_leave_during_sf_fulfillment(db, m, meal_period=MealPeriod.DINNER.value)
        if typ not in (LeaveType.CANCEL, LeaveType.CLEAR_TOMORROW):
            guard_miniprogram_self_service_requires_balance(db, m)
        guard_miniprogram_leave_prep_window(db, m, now=now)

    if typ == LeaveType.CANCEL:
        row.is_leaved_tomorrow = False
        row.tomorrow_leave_target_date = None
        row.leave_range_start = None
        row.leave_range_end = None
    elif typ == LeaveType.CLEAR_TOMORROW:
        row.is_leaved_tomorrow = False
        row.tomorrow_leave_target_date = None
    elif typ == LeaveType.TOMORROW:
        t_target = tomorrow_shanghai()
        row.tomorrow_leave_target_date = t_target
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

    after_absent_today = is_absent_on_delivery_date_for_leave_fields(
        leave_range_start=row.leave_range_start,
        leave_range_end=row.leave_range_end,
        is_leaved_tomorrow=bool(row.is_leaved_tomorrow),
        tomorrow_leave_target_date=row.tomorrow_leave_target_date,
        delivery_date=today_d,
        today=today_d,
    )
    after = _dinner_leave_snapshot(row)

    if typ == LeaveType.TOMORROW:
        op_type = OP_LEAVE_TOMORROW
        summary = f"晚餐明天请假：{after['tomorrow_leave_target_date'] or '-'}"
    elif typ == LeaveType.RANGE:
        op_type = OP_LEAVE_RANGE
        summary = f"晚餐区间请假：{after['leave_range_start'] or '-'} ~ {after['leave_range_end'] or '-'}"
    elif typ == LeaveType.CLEAR_TOMORROW:
        op_type = OP_LEAVE_CLEAR_TOMORROW
        summary = "晚餐取消明天请假"
    else:
        op_type = OP_LEAVE_CANCEL
        summary = "晚餐取消所有请假"

    record_member_operation(
        db,
        member_id=member_id,
        operation_type=op_type,
        summary=summary,
        before=prev,
        after=after,
        ip_address=ip_address,
        source=source,
        operator=operator,
    )

    if (
        source == "miniprogram"
        and typ != LeaveType.TOMORROW
        and before_absent_today
        and not after_absent_today
    ):
        from app.services.delivery_day_lock_service import is_delivery_day_sheet_locked_for_period

        if not is_delivery_day_sheet_locked_for_period(
            db, store_id=int(m.store_id), delivery_date=today_d, meal_period=MealPeriod.DINNER.value
        ):
            leave_lab = ["晚餐请假变更"]
            if typ == LeaveType.CANCEL:
                leave_lab = ["晚餐取消全部请假"]
            elif typ == LeaveType.CLEAR_TOMORROW:
                leave_lab = ["晚餐清除明天请假"]
            elif typ == LeaveType.RANGE:
                leave_lab = ["晚餐调整请假区间"]
            from app.services.admin_system_notification_service import try_notify_delivery_sheet_manual_attention

            try_notify_delivery_sheet_manual_attention(
                db,
                store_id=int(m.store_id),
                action_labels_cn=leave_lab,
                member_id=int(m.id),
                member_phone=str(m.phone or "").strip() or None,
                member_name=str(m.name or "").strip() or None,
            )

    db.commit()
    db.refresh(m)
    return _to_member_out(db, m, get_default_address(db, member_id))
