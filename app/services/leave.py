from datetime import date, time

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.enums import LeaveType
from app.models.member import Member


def is_absent_on_delivery_date(member: Member, delivery_date: date, *, today: date) -> bool:
    """
    判断会员在指定配送日是否视为「请假/不配送」。

    规则：
    - 长期区间：leave_range_start ~ leave_range_end 闭区间命中即缺席；
    - 「仅明天请假」：与 members 表一致，须 **仍勾选** is_leaved_tomorrow 且 tomorrow_leave_target_date
      有值时，仅该业务日缺席；无 target 时回退为配送日=业务今天+1（旧数据）。
    - 已撤销但 target 未清理的脏数据：不按 target 判缺席，避免大表/骑手误排除。
    """
    if member.leave_range_start and member.leave_range_end:
        if member.leave_range_start <= delivery_date <= member.leave_range_end:
            return True
    if member.tomorrow_leave_target_date is not None and member.is_leaved_tomorrow:
        return delivery_date == member.tomorrow_leave_target_date
    if member.is_leaved_tomorrow and member.tomorrow_leave_target_date is None:
        tomorrow = date.fromordinal(today.toordinal() + 1)
        return delivery_date == tomorrow
    return False


def is_leave_deadline_passed(now_time, deadline) -> bool:
    """当前时间是否已超过「当日请假截止」时刻（仅比较 time，口径为北京时间）。"""
    d = deadline if deadline is not None else time(21, 0, 0)
    return now_time > d


def guard_member_self_cancel_leave(db: Session, member: Member, typ: LeaveType) -> None:
    """会员自助取消请假：若取消会改变「当日已向顺丰推单」业务日的缺席状态，则须联系客服。"""
    from app.core.timeutil import today_shanghai
    from app.services.sf_order_fulfillment_service import member_has_active_sf_push_on_delivery_date

    if typ != LeaveType.CANCEL:
        return

    biz_today = today_shanghai()
    if not is_absent_on_delivery_date(member, biz_today, today=biz_today):
        return

    if member_has_active_sf_push_on_delivery_date(
        db,
        member_id=int(member.id),
        store_id=int(member.store_id),
        delivery_date=biz_today,
    ):
        raise HTTPException(
            status_code=400,
            detail="当日配送已向顺丰推单，无法自助取消请假，请联系客服处理",
        )
