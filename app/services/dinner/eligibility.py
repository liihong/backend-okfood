"""晚餐应配送会员筛选（平行于午餐 eligible，不修改 courier_service 现有函数）。"""

from __future__ import annotations

from datetime import date

from sqlalchemy import and_, literal, not_, or_, select
from sqlalchemy.orm import Session

from app.core.delivery_calendar import is_subscription_delivery_day
from app.core.timeutil import today_shanghai
from app.models.enums import CardOrderPayStatus, DeliverySheetView, MealPeriod
from app.models.member import Member
from app.models.member_address import MemberAddress
from app.models.member_card_order import MemberCardOrder
from app.models.member_meal_period_state import MemberMealPeriodState
from app.services.courier_service import (
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
from app.services.member_address_service import default_address_pick_subquery


def _any_dinner_entitled_orders_in_scope(
    db: Session,
    *,
    tenant_id: int | None,
    store_id: int | None,
) -> bool:
    """门店是否存在已入账且快照含 dinner 的工单；无则晚餐大表必为空。"""
    q = select(MemberCardOrder.id).where(
        MemberCardOrder.pay_status == CardOrderPayStatus.PAID.value,
        MemberCardOrder.applied_to_member.is_(True),
        MemberCardOrder.meal_periods_snapshot.contains("dinner"),
    )
    if store_id is not None:
        q = q.where(MemberCardOrder.store_id == int(store_id))
    elif tenant_id is not None:
        q = q.where(MemberCardOrder.tenant_id == int(tenant_id))
    return db.scalar(q.limit(1)) is not None


def eligible_members_for_dinner_delivery(
    db: Session,
    *,
    delivery_date: date,
    delivery_region_id: int | None = None,
    tenant_id: int | None = None,
    store_id: int | None = None,
) -> tuple[list[Member], dict[int, MemberAddress | None]]:
    """
    晚餐到家应配送会员：日程规则与午餐相同，余额/请假/餐段资格按 dinner 口径。
    纯午餐卡不会进入晚餐大表；批量查餐段资格与晚餐运营态，避免逐会员 N+1。
    """
    if not is_subscription_delivery_day(delivery_date):
        return [], {}
    if not _any_dinner_entitled_orders_in_scope(db, tenant_id=tenant_id, store_id=store_id):
        return [], {}

    today = today_shanghai()
    d = delivery_date
    tomorrow = date.fromordinal(today.toordinal() + 1)
    in_leave_range = and_(
        Member.leave_range_start.is_not(None),
        Member.leave_range_end.is_not(None),
        Member.leave_range_start <= d,
        Member.leave_range_end >= d,
    )
    target_hit = and_(
        Member.is_leaved_tomorrow.is_(True),
        Member.tomorrow_leave_target_date == d,
    )
    legacy_tomorrow = and_(
        Member.is_leaved_tomorrow.is_(True),
        Member.tomorrow_leave_target_date.is_(None),
        literal(d) == literal(tomorrow),
    )
    # 午餐区间请假仍阻止进入晚餐名单（整段暂停）；分餐段请假在下方 dinner state 再判
    lunch_absent = or_(in_leave_range, target_hit, legacy_tomorrow)

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
            not_(lunch_absent),
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

    # 先筛晚餐卡资格，再批量加载晚餐运营态
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
        if is_dinner_absent_on_delivery_date(state_row, d, today=today):
            continue
        members.append(m)
        defaults[m.id] = addr

    return members, defaults
