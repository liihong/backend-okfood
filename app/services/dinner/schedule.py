"""晚餐履约日程判定：与 eligible_members_for_dinner_delivery 单会员口径一致。"""

from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.core.delivery_calendar import is_subscription_delivery_day
from app.core.timeutil import today_shanghai
from app.models.enums import DeliverySheetView, MealPeriod
from app.models.member import Member
from app.models.member_meal_period_state import MemberMealPeriodState
from app.services.meal_period.card_eligibility import member_entitled_for_sheet
from app.services.meal_period.leave import is_dinner_absent_on_delivery_date
from app.services.meal_period.units import dinner_daily_meal_units_from_state


def member_on_dinner_delivery_schedule(
    db: Session,
    member: Member,
    *,
    delivery_date: date,
    today: date | None = None,
) -> bool:
    """
    会员在指定业务日是否应计入晚餐配送大表（到家）。
    仅读晚餐池；午餐 members 表请假/余额不影响本判定。
    """
    if not is_subscription_delivery_day(delivery_date):
        return False
    if member.deleted_at is not None:
        return False
    if not bool(member.is_active):
        return False
    if bool(member.delivery_deferred):
        return False
    if bool(member.store_pickup):
        return False
    if not member_entitled_for_sheet(db, int(member.id), DeliverySheetView.DINNER.value):
        return False
    from app.services.member.member_card_order_service import member_paid_card_awaiting_setup

    if member_paid_card_awaiting_setup(db, int(member.id)):
        return False
    ds = member.delivery_start_date
    if ds is not None and ds > delivery_date:
        return False
    if delivery_date.weekday() == 5 and bool(member.skip_subscription_saturday):
        return False

    row = db.get(
        MemberMealPeriodState,
        {"member_id": int(member.id), "meal_period": MealPeriod.DINNER.value},
    )
    units = dinner_daily_meal_units_from_state(row)
    d_bal = max(0, int(row.balance or 0)) if row is not None else 0
    if d_bal < units:
        return False
    biz_today = today if today is not None else today_shanghai()
    return not is_dinner_absent_on_delivery_date(row, delivery_date, today=biz_today)
