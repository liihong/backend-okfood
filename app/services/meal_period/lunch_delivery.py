"""午餐应配送名单：复用 eligible_members_for_delivery + 卡资格过滤。"""

from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.models.enums import DeliverySheetView
from app.models.member import Member
from app.models.member_address import MemberAddress
from app.services.delivery.courier_service import eligible_members_for_delivery
from app.services.meal_period.card_eligibility import filter_members_for_sheet_view


def eligible_members_for_lunch_delivery(
    db: Session,
    *,
    delivery_date: date,
    delivery_region_id: int | None = None,
    tenant_id: int | None = None,
    store_id: int | None = None,
) -> tuple[list[Member], dict[int, MemberAddress | None]]:
    """
    午餐到家应配送会员：SQL 口径与 ``eligible_members_for_delivery`` 一致，
    并过滤纯晚餐会员（避免误充午餐池后进入骑手/单次扣次名单）。
    """
    members, defaults = eligible_members_for_delivery(
        db,
        delivery_date=delivery_date,
        delivery_region_id=delivery_region_id,
        tenant_id=tenant_id,
        store_id=store_id,
    )
    if not members:
        return [], {}
    filtered = filter_members_for_sheet_view(db, members, DeliverySheetView.LUNCH.value)
    if len(filtered) == len(members):
        return members, defaults
    allowed = {int(m.id) for m in filtered}
    return filtered, {k: v for k, v in defaults.items() if int(k) in allowed}
