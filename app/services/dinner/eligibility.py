"""晚餐应配送会员筛选（平行于午餐 eligible，不修改 courier_service 现有函数）。"""

from __future__ import annotations

from datetime import date

from sqlalchemy import and_, not_, or_, select
from sqlalchemy.orm import Session

from app.core.delivery_calendar import is_subscription_delivery_day
from app.core.timeutil import today_shanghai
from app.models.enums import MealPeriod
from app.models.member import Member
from app.models.member_address import MemberAddress
from app.models.member_meal_period_state import MemberMealPeriodState
from app.services.delivery.courier_service import (
    _member_not_skip_subscription_saturday,
    _member_scope_clause,
    subscription_delivery_started_clause,
)
from app.services.member.member_delivery_state_service import sql_not_blocked_by_pause_on_date
from app.services.meal_period.dinner_pause import dinner_schedule_allows_delivery
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
    晚餐到家应配送会员：日程与午餐相同；余额、请假、暂停只看晚餐。
    午餐请假不再阻断晚餐。不按开卡工单餐段排除：午餐卡只加了晚餐次数也会进。
    暂停晚餐的人不进，除非当天就是指定配送日。
    """
    if not is_subscription_delivery_day(delivery_date):
        return [], {}

    today = today_shanghai()
    d = delivery_date
    started = subscription_delivery_started_clause(d)
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
            sql_not_blocked_by_pause_on_date(delivery_date),
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
    # 不查工单餐段。赠送晚餐若仍暂停，只有指定配送日能进名单。
    state_map = load_dinner_meal_period_states_map(db, member_ids)
    candidates: list[tuple[Member, MemberAddress | None]] = []
    for m, addr in rows:
        mid = int(m.id)
        state_row = state_map.get(mid)
        # 暂停与指定日只过滤晚餐名单，上面的会员整体暂停仍走 sql_not_blocked_by_pause_on_date
        if not dinner_schedule_allows_delivery(
            entitled=False,
            dinner_delivery_paused=bool(state_row.dinner_delivery_paused) if state_row is not None else False,
            dinner_deliver_on=state_row.dinner_deliver_on if state_row is not None else None,
            delivery_date=d,
        ):
            continue
        candidates.append((m, addr))
    if not candidates:
        return [], {}

    members: list[Member] = []
    defaults: dict[int, MemberAddress | None] = {}
    from app.services.member.member_card_order_service import member_paid_card_awaiting_setup

    for m, addr in candidates:
        state_row = state_map.get(int(m.id))
        units = dinner_daily_meal_units_from_state(state_row)
        d_bal = max(0, int(state_row.balance or 0)) if state_row is not None else 0
        if d_bal < units:
            continue
        # 仅晚餐分餐段请假判定；午餐 members 表请假不影响晚餐名单
        if is_dinner_absent_on_delivery_date(state_row, d, today=today):
            continue
        if member_paid_card_awaiting_setup(db, int(m.id)):
            continue
        members.append(m)
        defaults[m.id] = addr

    return members, defaults


def filter_member_groups_with_dinner_counts(
    db: Session,
    delivery_date: date,
    *member_groups: list[Member],
) -> tuple[list[Member], ...]:
    """午晚餐运维 Tab 用：调用方已经按午餐次数筛过。

    只留下晚餐剩余次数不少于当日份数、晚餐日程允许、且晚餐未请假的人。
    不看开卡工单餐段，也不排除门店自提。暂停晚餐时，仅指定配送日留下。
    """
    combined: list[Member] = []
    for group in member_groups:
        combined.extend(group)
    if not combined:
        return tuple([] for _ in member_groups)
    today = today_shanghai()
    state_map = load_dinner_meal_period_states_map(db, [int(m.id) for m in combined])

    def _keep(member: Member) -> bool:
        row = state_map.get(int(member.id))
        paused = bool(row.dinner_delivery_paused) if row is not None else False
        deliver_on = row.dinner_deliver_on if row is not None else None
        if not dinner_schedule_allows_delivery(
            entitled=False,
            dinner_delivery_paused=paused,
            dinner_deliver_on=deliver_on,
            delivery_date=delivery_date,
        ):
            return False
        units = dinner_daily_meal_units_from_state(row)
        balance = max(0, int(row.balance or 0)) if row is not None else 0
        if balance < units:
            return False
        return not is_dinner_absent_on_delivery_date(row, delivery_date, today=today)

    return tuple([m for m in group if _keep(m)] for group in member_groups)
