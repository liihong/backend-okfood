"""午餐应配送名单：与 eligible_members_for_delivery 同一口径，按午餐剩余次数。"""

from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.models.member import Member
from app.models.member_address import MemberAddress
from app.services.delivery.courier_service import eligible_members_for_delivery


def eligible_members_for_lunch_delivery(
    db: Session,
    *,
    delivery_date: date,
    delivery_region_id: int | None = None,
    tenant_id: int | None = None,
    store_id: int | None = None,
) -> tuple[list[Member], dict[int, MemberAddress | None]]:
    """
    午餐到家应配送会员。

    与 ``eligible_members_for_delivery`` 相同：午餐剩余次数不少于当日份数，
    并看午餐暂停、整体暂停、请假、起送日、周六不送。
    不按开卡工单餐段排除。周晚餐卡只要午餐还有次数，仍进午餐名单。
    """
    return eligible_members_for_delivery(
        db,
        delivery_date=delivery_date,
        delivery_region_id=delivery_region_id,
        tenant_id=tenant_id,
        store_id=store_id,
    )
