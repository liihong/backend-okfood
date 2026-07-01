"""晚餐应配送会员筛选（平行于午餐 eligible，不修改 courier_service 现有函数）。"""

from __future__ import annotations

from datetime import date

from sqlalchemy import and_, not_, or_, select
from sqlalchemy.orm import Session

from app.core.delivery_calendar import is_subscription_delivery_day
from app.core.timeutil import today_shanghai
from app.models.enums import DeliverySheetView, MealPeriod
from app.models.member import Member
from app.models.member_address import MemberAddress
from app.models.member_meal_period_state import MemberMealPeriodState
from app.services.delivery.courier_service import (
    _member_not_skip_subscription_saturday,
    _member_scope_clause,
)
from app.services.meal_period.card_eligibility import (
    _periods_match_sheet,
    members_entitled_meal_periods_map,
)
from app.services.meal_period.leave import is_dinner_absent_on_delivery_date
from app.services.meal_period.units import (
    dinner_daily_meal_units_from_state,
    load_dinner_meal_period_states_map,
)
from app.services.member.member_address_service import default_address_pick_subquery


def eligible_members_for_dinner_delivery(
    db: Session,
    *,
    delivery_date: date,
    delivery_region_id: int | None = None,
    tenant_id: int | None = None,
    store_id: int | None = None,
) -> tuple[list[Member], dict[int, MemberAddress | None]]:
    """
    晚餐到家应配送会员：日程规则与午餐相同；余额/请假/餐段资格仅按 dinner 口径。
    午餐请假不再阻断晚餐（午/晚餐严格分池）；纯午餐卡不会进入晚餐大表。
    """
    if not is_subscription_delivery_day(delivery_date):
        return [], {}

    today = today_shanghai()
    d = delivery_date
    started = or_(
        Member.delivery_start_date.is_(None),
        Member.delivery_start_date <= d,
    )
    daf = default_address_pick_subquery()
    dinner_state = (
        select(MemberMealPeriodState)
        .where(
            MemberMealPeriodState.member_id == Member.id,
            MemberMealPeriodState.meal_period == MealPeriod.DINNER.value,
            MemberMealPeriodState.balance >= 1,
        )
        .correlate(Member)
        .exists()
    )
    q = (
        select(Member, MemberAddress)
        .outerjoin(daf, daf.c.mid == Member.id)
        .outerjoin(MemberAddress, MemberAddress.id == daf.c.addr_id)
        .where(
            Member.deleted_at.is_(None),
            Member.is_active.is_(True),
            dinner_state,
            Member.store_pickup.is_(False),
            started,
            _member_not_skip_subscription_saturday(d),
            _member_scope_clause(tenant_id=tenant_id, store_id=store_id),
        )
    )
    if delivery_region_id is not None:
        q = q.where(MemberAddress.delivery_region_id == delivery_region_id)

    rows = db.execute(q).all()
    if not rows:
        return [], {}

    member_ids = [int(m.id) for m, _ in rows]
    entitled_map = members_entitled_meal_periods_map(db, member_ids)
    dinner_view = DeliverySheetView.DINNER.value
    candidates: list[tuple[Member, MemberAddress | None]] = [
        (m, addr)
        for m, addr in rows
        if _periods_match_sheet(entitled_map.get(int(m.id), frozenset()), dinner_view)
    ]
    if not candidates:
        return [], {}

    state_map = load_dinner_meal_period_states_map(db, [int(m.id) for m, _ in candidates])

    members: list[Member] = []
    defaults: dict[int, MemberAddress | None] = {}
    for m, addr in candidates:
        state_row = state_map.get(int(m.id))
        units = dinner_daily_meal_units_from_state(state_row)
        d_bal = max(0, int(state_row.balance or 0)) if state_row is not None else 0
        if d_bal < units:
            continue
        # 仅晚餐分餐段请假判定；午餐 members 表请假不影响晚餐名单
        if is_dinner_absent_on_delivery_date(state_row, d, today=today):
            continue
        members.append(m)
        defaults[m.id] = addr

    return members, defaults
