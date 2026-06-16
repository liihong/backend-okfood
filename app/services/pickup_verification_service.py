"""首页门店自提快速核销舱：轻量列表（订阅自提 + 单次零售自提，不构建完整配送大表）。"""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.constants import STUB_MEMBER_NAME
from app.core.delivery_calendar import is_subscription_delivery_day
from app.models.member import Member
from app.models.menu_dish import MenuDish
from app.models.single_meal_order import SingleMealOrder
from app.schemas.admin import (
    PickupVerificationListOut,
    PickupVerificationRetailRowOut,
    PickupVerificationSubscriptionRowOut,
)
from app.services.courier_service import (
    eligible_members_for_store_pickup,
    extra_delivered_ineligible_subscribers,
)
from app.services.delivery_sheet_service import (
    _member_balance_quota,
    _store_delivered_member_ids_on_date,
)


def _retail_member_display_name(member: Member | None) -> str:
    """与订单管理单次零售列表一致：档案非占位时用 members.name。"""
    profile = ((member.name or "").strip() if member else "") or ""
    if profile and profile != STUB_MEMBER_NAME:
        return profile
    return profile


def _subscription_pickup_rows(
    db: Session,
    *,
    store_id: int,
    delivery_date: date,
) -> list[PickupVerificationSubscriptionRowOut]:
    """订阅门店自提会员：复用大表同源 eligible + 已扣次补录，但不构建到家分组。"""
    if not is_subscription_delivery_day(delivery_date):
        return []

    sid = int(store_id)
    d = delivery_date
    pu_members, _pu_defaults = eligible_members_for_store_pickup(db, delivery_date=d, store_id=sid)
    day_delivered_ids = _store_delivered_member_ids_on_date(db, store_id=sid, delivery_date=d)
    _ex_h, _ex_dh, ex_pu, _ex_pud = extra_delivered_ineligible_subscribers(
        db,
        delivery_date=d,
        already_home=set(),
        already_pickup={int(m.id) for m in pu_members},
        delivery_region_id=None,
        store_id=sid,
        day_delivered_member_ids=day_delivered_ids,
    )
    all_pu = list(pu_members) + list(ex_pu)

    rows: list[PickupVerificationSubscriptionRowOut] = []
    for mem in sorted(all_pu, key=lambda x: (x.id in day_delivered_ids, (x.phone or ""))):
        bal, quota = _member_balance_quota(mem)
        rows.append(
            PickupVerificationSubscriptionRowOut(
                member_id=int(mem.id),
                name=(mem.name or "").strip(),
                phone=(mem.phone or "").strip(),
                balance=bal,
                meal_quota_total=quota,
                is_delivered=int(mem.id) in day_delivered_ids,
            )
        )
    return rows


def _retail_pickup_rows(
    db: Session,
    *,
    store_id: int,
    delivery_date: date,
) -> list[PickupVerificationRetailRowOut]:
    """单次零售门店自提：单条 SQL 联表，不含分页 count 与地址加载。"""
    stmt = (
        select(SingleMealOrder, Member, MenuDish)
        .join(Member, Member.id == SingleMealOrder.member_id)
        .join(MenuDish, MenuDish.id == SingleMealOrder.dish_id)
        .where(
            SingleMealOrder.store_id == int(store_id),
            SingleMealOrder.delivery_date == delivery_date,
            SingleMealOrder.store_pickup.is_(True),
            SingleMealOrder.pay_status == "已支付",
            SingleMealOrder.fulfillment_status.notin_(("cancelled", "sf_cancelled")),
        )
    )
    rows: list[PickupVerificationRetailRowOut] = []
    for order, member, dish in db.execute(stmt).all():
        f = str(order.fulfillment_status or "").strip().lower()
        rows.append(
            PickupVerificationRetailRowOut(
                order_id=int(order.id),
                name=_retail_member_display_name(member),
                phone=(member.phone or "").strip(),
                dish_title=(dish.name or "").strip() or "餐品",
                quantity=max(1, int(order.quantity or 1)),
                is_delivered=f == "delivered",
            )
        )
    rows.sort(key=lambda r: (r.is_delivered, r.phone))
    return rows


def list_pickup_verification_panel(
    db: Session,
    *,
    store_id: int,
    delivery_date: date,
) -> PickupVerificationListOut:
    """首页核销舱专用：订阅 + 零售自提合并列表。"""
    sub_rows = _subscription_pickup_rows(db, store_id=store_id, delivery_date=delivery_date)
    retail_rows = _retail_pickup_rows(db, store_id=store_id, delivery_date=delivery_date)
    combined = [*sub_rows, *retail_rows]
    pending = sum(1 for r in combined if not r.is_delivered)
    return PickupVerificationListOut(
        delivery_date=delivery_date,
        pending_count=pending,
        rows=combined,
    )
