"""午餐履约日程：在 subscription 规则上叠加午餐卡资格校验。"""

from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.models.enums import DeliverySheetView
from app.models.member import Member
from app.services.delivery.courier_service import member_on_subscription_delivery_schedule
from app.services.meal_period.card_eligibility import member_entitled_for_sheet


def member_on_lunch_delivery_schedule(
    db: Session,
    member: Member,
    *,
    delivery_date: date,
    today: date | None = None,
) -> bool:
    """
    会员在指定业务日是否应计入午餐配送大表（到家或自提）。
    在 members.balance/请假 规则之上，要求具备午餐卡资格（纯晚餐不进午餐日程）。
    """
    if not member_on_subscription_delivery_schedule(
        member, delivery_date=delivery_date, today=today
    ):
        return False
    return member_entitled_for_sheet(db, int(member.id), DeliverySheetView.LUNCH.value)
