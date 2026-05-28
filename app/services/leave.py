from datetime import date

from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.member import Member


def is_absent_on_delivery_date_for_leave_fields(
    *,
    leave_range_start: date | None,
    leave_range_end: date | None,
    is_leaved_tomorrow: bool,
    tomorrow_leave_target_date: date | None,
    delivery_date: date,
    today: date,
) -> bool:
    """
    请假字段快照版：语义与 ``is_absent_on_delivery_date`` 完全一致，便于在 ORM 对象未落库前后对比变更。
    """
    if leave_range_start and leave_range_end:
        if leave_range_start <= delivery_date <= leave_range_end:
            return True
    if tomorrow_leave_target_date is not None and is_leaved_tomorrow:
        return delivery_date == tomorrow_leave_target_date
    if is_leaved_tomorrow and tomorrow_leave_target_date is None:
        tomorrow = date.fromordinal(today.toordinal() + 1)
        return delivery_date == tomorrow
    return False


def is_absent_from_leave_snapshot_dict(
    snapshot: dict[str, Any],
    *,
    delivery_date: date,
    today: date,
) -> bool:
    """
    从 leave_request 记录的 ``prev`` / ``after`` 字典解析请假字段后判缺席；
    ``leave_range_*`` 与 ``tomorrow_leave_target_date`` 为 ISO 日期字符串或 None。
    """
    rs_raw = snapshot.get("leave_range_start")
    re_raw = snapshot.get("leave_range_end")
    lrs = date.fromisoformat(str(rs_raw)) if rs_raw else None
    lre = date.fromisoformat(str(re_raw)) if re_raw else None
    tt_raw = snapshot.get("tomorrow_leave_target_date")
    ttd = date.fromisoformat(str(tt_raw)) if tt_raw else None
    iso_tomorrow = bool(snapshot.get("is_leaved_tomorrow", False))
    return is_absent_on_delivery_date_for_leave_fields(
        leave_range_start=lrs,
        leave_range_end=lre,
        is_leaved_tomorrow=iso_tomorrow,
        tomorrow_leave_target_date=ttd,
        delivery_date=delivery_date,
        today=today,
    )


def is_absent_on_delivery_date(member: Member, delivery_date: date, *, today: date) -> bool:
    """
    判断会员在指定配送日是否视为「请假/不配送」。

    规则：
    - 长期区间：leave_range_start ~ leave_range_end 闭区间命中即缺席；
    - 「仅明天请假」：与 members 表一致，须 **仍勾选** is_leaved_tomorrow 且 tomorrow_leave_target_date
      有值时，仅该业务日缺席；无 target 时回退为配送日=业务今天+1（旧数据）。
    - 已撤销但 target 未清理的脏数据：不按 target 判缺席，避免大表/骑手误排除。
    """
    return is_absent_on_delivery_date_for_leave_fields(
        leave_range_start=getattr(member, "leave_range_start", None),
        leave_range_end=getattr(member, "leave_range_end", None),
        is_leaved_tomorrow=bool(member.is_leaved_tomorrow),
        tomorrow_leave_target_date=getattr(member, "tomorrow_leave_target_date", None),
        delivery_date=delivery_date,
        today=today,
    )


SF_SELF_SERVICE_LOCK_DURING_FULFILLMENT_MSG = (
    "您的订单已经同步顺丰配送，完成后可进行操作"
)
SF_SELF_SERVICE_LOCK_LEAVE_MSG = (
    "您的订单已经同步顺丰配送，完成后可修改请假"
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
        member_phone=(member.phone or "").strip() or None,
    ):
        raise HTTPException(status_code=400, detail=SF_SELF_SERVICE_LOCK_DURING_FULFILLMENT_MSG)


def guard_member_self_leave_during_sf_fulfillment(db: Session, member: Member) -> None:
    """当前会员当日顺丰推单配送未完成：禁止小程序自助请假相关操作。"""
    try:
        guard_member_self_service_during_sf_fulfillment(db, member)
    except HTTPException:
        raise HTTPException(status_code=400, detail=SF_SELF_SERVICE_LOCK_LEAVE_MSG) from None
