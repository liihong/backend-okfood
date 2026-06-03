from datetime import date, datetime, time

from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.timeutil import now_shanghai
from app.models.member import Member

# 小程序自助请假备餐锁窗：门店 leave_deadline_time（默认 21:00）起至次日 09:00 止。
MINIPROGRAM_LEAVE_PREP_UNLOCK_TIME = time(9, 0, 0)
MINIPROGRAM_LEAVE_PREP_LOCKED_MSG = (
    "您的菜品原材料已备好，不能请假，感谢理解和认可。"
)
MINIPROGRAM_PAUSE_DELIVERY_PREP_LOCKED_MSG = (
    "21点后无法操作暂停。明日餐品已准备，可配送后暂停"
)
MINIPROGRAM_NO_CARD_MSG = "请先购买自律卡包后再操作"
MINIPROGRAM_AWAITING_SETUP_MSG = "请先完善配送信息后再操作"


def is_miniprogram_leave_prep_locked(
    *,
    deadline_time: time,
    now: datetime | None = None,
    unlock_time: time = MINIPROGRAM_LEAVE_PREP_UNLOCK_TIME,
) -> bool:
    """上海墙钟：当日 deadline 起至次日 unlock 前禁止小程序自助请假相关操作。"""
    n = now if now is not None else now_shanghai()
    t = n.time()
    return t >= deadline_time or t < unlock_time


def miniprogram_prep_lock_affected_delivery_date(
    *,
    now: datetime,
    unlock_time: time = MINIPROGRAM_LEAVE_PREP_UNLOCK_TIME,
) -> date:
    """备餐锁窗内正在备餐的履约业务日（上海）：21:00 后起算次日；次日 09:00 前仍算当日。"""
    biz_today = now.date()
    if now.time() < unlock_time:
        return biz_today
    return date.fromordinal(biz_today.toordinal() + 1)


def guard_miniprogram_leave_prep_window(
    db: Session,
    member: Member,
    *,
    now: datetime | None = None,
) -> None:
    """备餐锁窗内：小程序禁止请假/取消请假等自助变更。"""
    from app.services.store_config_service import get_leave_deadline_time_for_store

    deadline = get_leave_deadline_time_for_store(db, int(member.store_id))
    if is_miniprogram_leave_prep_locked(deadline_time=deadline, now=now):
        raise HTTPException(status_code=400, detail=MINIPROGRAM_LEAVE_PREP_LOCKED_MSG)


def is_miniprogram_pause_delivery_prep_locked(
    db: Session,
    member: Member,
    *,
    now: datetime | None = None,
) -> bool:
    """备餐锁窗内且已在锁窗履约日配送大表：小程序不可暂停（已暂停会员不受限）。"""
    if bool(member.delivery_deferred):
        return False
    from app.services.courier_service import member_on_subscription_delivery_schedule
    from app.services.store_config_service import get_leave_deadline_time_for_store

    n = now if now is not None else now_shanghai()
    deadline = get_leave_deadline_time_for_store(db, int(member.store_id))
    if not is_miniprogram_leave_prep_locked(deadline_time=deadline, now=n):
        return False
    affected = miniprogram_prep_lock_affected_delivery_date(now=n)
    return member_on_subscription_delivery_schedule(
        member,
        delivery_date=affected,
        today=n.date(),
    )


def guard_miniprogram_pause_delivery_prep_window(
    db: Session,
    member: Member,
    *,
    now: datetime | None = None,
) -> None:
    """备餐锁窗内：已在履约日配送大表的会员禁止小程序暂停配送；恢复配送不受限。"""
    if is_miniprogram_pause_delivery_prep_locked(db, member, now=now):
        raise HTTPException(
            status_code=400,
            detail=MINIPROGRAM_PAUSE_DELIVERY_PREP_LOCKED_MSG,
        )


def guard_miniprogram_self_service_requires_balance(db: Session, member: Member) -> None:
    """小程序自助请假/暂停配送/份数等须已开卡（剩余餐次 > 0）。"""
    if int(member.balance) > 0:
        return
    from app.services.member_card_order_service import member_paid_card_awaiting_setup

    if member_paid_card_awaiting_setup(db, int(member.id)):
        raise HTTPException(status_code=400, detail=MINIPROGRAM_AWAITING_SETUP_MSG)
    raise HTTPException(status_code=400, detail=MINIPROGRAM_NO_CARD_MSG)


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
