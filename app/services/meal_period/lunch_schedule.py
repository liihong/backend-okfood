"""午餐履约日程：按午餐剩余次数和午餐暂停，不看开卡工单餐段。"""

from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.models.member import Member
from app.services.delivery.courier_service import member_on_subscription_delivery_schedule


def member_on_lunch_delivery_schedule(
    db: Session,
    member: Member,
    *,
    delivery_date: date,
    today: date | None = None,
) -> bool:
    """
    会员在指定业务日是否应计入午餐配送大表（到家或自提）。

    ``member_on_subscription_delivery_schedule`` 已要求午餐剩余次数不少于当日份数，
    并看整体暂停、请假、起送日、周六不送。这里不再要求工单含午餐。
    单独暂停午餐只挡本函数，不改变晚餐日程。
    """
    if not member_on_subscription_delivery_schedule(
        member, delivery_date=delivery_date, today=today
    ):
        return False
    from app.services.member.member_card_order_service import member_paid_card_awaiting_setup

    if member_paid_card_awaiting_setup(db, int(member.id)):
        return False
    # 原午餐规则都过了，再挡单独暂停。不改晚餐日程，也不改请假字段。
    from app.services.meal_period.lunch_pause import lunch_schedule_allows_delivery

    return lunch_schedule_allows_delivery(
        lunch_delivery_paused=bool(getattr(member, "lunch_delivery_paused", False))
    )
