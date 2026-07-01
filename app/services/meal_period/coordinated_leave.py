"""全天/多餐段请假编排：严格分池写入，午餐链路行为不变。"""

from __future__ import annotations

from datetime import date

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.timeutil import now_shanghai, today_shanghai
from app.models.enums import LeaveType, MealPeriod
from app.models.member import Member
from app.schemas.user import MemberOut
from app.services.member.member_address_service import get_default_address
from app.services.member.member_operation_log_service import (
    OP_LEAVE_CANCEL,
    OP_LEAVE_CLEAR_TOMORROW,
    OP_LEAVE_RANGE,
    OP_LEAVE_TOMORROW,
    record_member_operation,
)
from app.services.member.member_service import _to_member_out
from app.services.meal_period.dinner_units import get_or_create_dinner_state
from app.services.meal_period.leave_fields import (
    apply_leave_type_to_row,
    is_row_absent_on_delivery_date,
    leave_fields_snapshot,
)
from app.services.meal_period.leave_scope import LEAVE_MEAL_PERIOD_ALL, leave_target_periods


def _leave_operation_meta(typ: LeaveType, after: dict, *, scope_label: str) -> tuple[str, str]:
    """生成操作日志类型与摘要（scope_label 如「午餐」「晚餐」「全天」）。"""
    if typ == LeaveType.TOMORROW:
        return OP_LEAVE_TOMORROW, f"{scope_label}明天请假：{after.get('tomorrow_leave_target_date') or '-'}"
    if typ == LeaveType.RANGE:
        s = after.get("leave_range_start") or "-"
        e = after.get("leave_range_end") or "-"
        return OP_LEAVE_RANGE, f"{scope_label}区间请假：{s} ~ {e}"
    if typ == LeaveType.CLEAR_TOMORROW:
        return OP_LEAVE_CLEAR_TOMORROW, f"{scope_label}取消明天请假"
    return OP_LEAVE_CANCEL, f"{scope_label}取消所有请假"


def _try_notify_leave_cancel_after_prep(
    db: Session,
    *,
    member: Member,
    typ: LeaveType,
    before_absent_today: bool,
    after_absent_today: bool,
    source: str,
    meal_period: str,
) -> None:
    """推单后取消当日请假：按餐段通知运维（与午餐/晚餐单餐段逻辑一致）。"""
    if source != "miniprogram" or typ == LeaveType.TOMORROW:
        return
    if not before_absent_today or after_absent_today:
        return
    from app.services.delivery.delivery_day_lock_service import is_delivery_day_sheet_locked_for_period

    today_d = today_shanghai()
    if is_delivery_day_sheet_locked_for_period(
        db,
        store_id=int(member.store_id),
        delivery_date=today_d,
        meal_period=meal_period,
    ):
        return
    from app.services.admin.admin_system_notification_service import try_notify_delivery_sheet_manual_attention

    period_cn = {"lunch": "午餐", "dinner": "晚餐", LEAVE_MEAL_PERIOD_ALL: "全天"}.get(
        meal_period, "请假"
    )
    if typ == LeaveType.CANCEL:
        labels = [f"{period_cn}取消全部请假"]
    elif typ == LeaveType.CLEAR_TOMORROW:
        labels = [f"{period_cn}清除明天请假"]
    elif typ == LeaveType.RANGE:
        labels = [f"{period_cn}调整请假区间"]
    else:
        labels = [f"{period_cn}请假变更"]
    try_notify_delivery_sheet_manual_attention(
        db,
        store_id=int(member.store_id),
        action_labels_cn=labels,
        member_id=int(member.id),
        member_phone=str(member.phone or "").strip() or None,
        member_name=str(member.name or "").strip() or None,
    )


def coordinated_leave_request(
    db: Session,
    member_id: int,
    typ: LeaveType,
    start: date | None,
    end: date | None,
    *,
    leave_meal_period: str,
    skip_leave_deadline: bool = False,
    ip_address: str | None = None,
    source: str = "miniprogram",
    operator: str | None = None,
) -> MemberOut:
    """
    统一请假入口的分餐段/全天编排。
    leave_meal_period: lunch | dinner | all
    """
    m = db.get(Member, member_id)
    if not m or m.deleted_at is not None:
        raise HTTPException(status_code=404, detail="用户不存在")

    targets = leave_target_periods(db, m, leave_meal_period)
    if not targets:
        raise HTTPException(status_code=400, detail="当前会员卡无可请假餐段")

    now = now_shanghai()
    today_d = today_shanghai()

    if source == "miniprogram":
        from app.services.member.leave import (
            guard_member_self_leave_during_sf_fulfillment,
            guard_miniprogram_leave_prep_window,
            guard_miniprogram_self_service_requires_balance,
        )

        for period in sorted(targets):
            guard_member_self_leave_during_sf_fulfillment(db, m, meal_period=period)
        if typ not in (LeaveType.CANCEL, LeaveType.CLEAR_TOMORROW):
            guard_miniprogram_self_service_requires_balance(db, m)
        guard_miniprogram_leave_prep_window(db, m, now=now, leave_meal_period=leave_meal_period)

    # 变更前：午餐字段 + 晚餐字段（若有）
    prev_lunch = leave_fields_snapshot(m)
    dinner_row = None
    prev_dinner: dict | None = None
    if MealPeriod.DINNER.value in targets:
        dinner_row = get_or_create_dinner_state(db, int(member_id))
        prev_dinner = leave_fields_snapshot(dinner_row)

    before_absent_lunch = is_row_absent_on_delivery_date(m, today_d, today=today_d)
    before_absent_dinner = (
        is_row_absent_on_delivery_date(dinner_row, today_d, today=today_d)
        if dinner_row is not None
        else False
    )

    if MealPeriod.LUNCH.value in targets:
        apply_leave_type_to_row(
            m, typ, start, end, skip_leave_deadline=skip_leave_deadline, now=now
        )
    if dinner_row is not None:
        apply_leave_type_to_row(
            dinner_row, typ, start, end, skip_leave_deadline=skip_leave_deadline, now=now
        )
        db.add(dinner_row)

    after_lunch = leave_fields_snapshot(m)
    after_dinner = leave_fields_snapshot(dinner_row) if dinner_row is not None else None

    after_absent_lunch = is_row_absent_on_delivery_date(m, today_d, today=today_d)
    after_absent_dinner = (
        is_row_absent_on_delivery_date(dinner_row, today_d, today=today_d)
        if dinner_row is not None
        else False
    )

    scope = leave_meal_period.strip().lower()
    if scope == LEAVE_MEAL_PERIOD_ALL:
        scope_label = "全天"
        combined_after = {
            "lunch": after_lunch,
            "dinner": after_dinner,
        }
        combined_prev = {"lunch": prev_lunch, "dinner": prev_dinner}
        op_type, summary = _leave_operation_meta(typ, after_lunch, scope_label=scope_label)
        record_member_operation(
            db,
            member_id=member_id,
            operation_type=op_type,
            summary=summary,
            before=combined_prev,
            after=combined_after,
            ip_address=ip_address,
            source=source,
            operator=operator,
        )
        # 全天取消：午/晚餐推单各自判断是否需要运维跟进
        if MealPeriod.LUNCH.value in targets:
            _try_notify_leave_cancel_after_prep(
                db,
                member=m,
                typ=typ,
                before_absent_today=before_absent_lunch,
                after_absent_today=after_absent_lunch,
                source=source,
                meal_period=MealPeriod.LUNCH.value,
            )
        if MealPeriod.DINNER.value in targets:
            _try_notify_leave_cancel_after_prep(
                db,
                member=m,
                typ=typ,
                before_absent_today=before_absent_dinner,
                after_absent_today=after_absent_dinner,
                source=source,
                meal_period=MealPeriod.DINNER.value,
            )
    elif MealPeriod.DINNER.value in targets and dinner_row is not None:
        op_type, summary = _leave_operation_meta(typ, after_dinner or {}, scope_label="晚餐")
        record_member_operation(
            db,
            member_id=member_id,
            operation_type=op_type,
            summary=summary,
            before=prev_dinner or {},
            after=after_dinner or {},
            ip_address=ip_address,
            source=source,
            operator=operator,
        )
        _try_notify_leave_cancel_after_prep(
            db,
            member=m,
            typ=typ,
            before_absent_today=before_absent_dinner,
            after_absent_today=after_absent_dinner,
            source=source,
            meal_period=MealPeriod.DINNER.value,
        )
    else:
        # 午餐单餐段：操作日志与现网字段结构保持一致
        op_type, summary = _leave_operation_meta(typ, after_lunch, scope_label="午餐")
        record_member_operation(
            db,
            member_id=member_id,
            operation_type=op_type,
            summary=summary,
            before=prev_lunch,
            after=after_lunch,
            ip_address=ip_address,
            source=source,
            operator=operator,
        )
        _try_notify_leave_cancel_after_prep(
            db,
            member=m,
            typ=typ,
            before_absent_today=before_absent_lunch,
            after_absent_today=after_absent_lunch,
            source=source,
            meal_period=MealPeriod.LUNCH.value,
        )

    db.commit()
    db.refresh(m)
    return _to_member_out(db, m, get_default_address(db, member_id))
