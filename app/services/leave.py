from datetime import date, time

from fastapi import HTTPException
from sqlalchemy.orm import Session

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


SF_SELF_SERVICE_LOCK_DURING_FULFILLMENT_MSG = (
    "当日配送已向顺丰推单，配送全部完成前无法自助修改，请联系客服"
)
SF_SELF_SERVICE_LOCK_LEAVE_MSG = (
    "当日配送已向顺丰推单，配送全部完成前无法自助修改请假，请联系客服处理"
)


def guard_member_self_service_during_sf_fulfillment(
    db: Session,
    member: Member,
    *,
    delivery_date: date | None = None,
) -> None:
    """
    当前会员当日命中顺丰推单且其配送尚未完成：禁止小程序自助改地址/份数等。
    管理端调用须自行跳过（勿传入本 guard）。
    """
    from app.core.timeutil import today_shanghai
    from app.services.sf_order_fulfillment_service import member_sf_self_service_locked_on_delivery_date

    d = delivery_date if delivery_date is not None else today_shanghai()
    if member_sf_self_service_locked_on_delivery_date(
        db,
        member_id=int(member.id),
        store_id=int(member.store_id),
        delivery_date=d,
    ):
        raise HTTPException(status_code=400, detail=SF_SELF_SERVICE_LOCK_DURING_FULFILLMENT_MSG)


def guard_member_self_leave_during_sf_fulfillment(db: Session, member: Member) -> None:
    """当前会员当日顺丰推单配送未完成：禁止小程序自助请假相关操作。"""
    try:
        guard_member_self_service_during_sf_fulfillment(db, member)
    except HTTPException:
        raise HTTPException(status_code=400, detail=SF_SELF_SERVICE_LOCK_LEAVE_MSG) from None
