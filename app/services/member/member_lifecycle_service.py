"""会员档案只读生命周期视图（MemberLifecycleCode）；不落库，不影响配送大表 SQL。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.delivery_log import DeliveryLog
from app.models.enums import CardOrderActivationMode, DeliveryStatus, MemberLifecycleCode
from app.models.member import Member
from app.models.member_address import MemberAddress
from app.models.member_card_order import MemberCardOrder
from app.models.member_meal_period_state import MemberMealPeriodState
from app.services.member.member_card_order_service import (
    _member_delivery_setup_incomplete_with_addr,
    member_delivery_setup_incomplete,
)


_LIFECYCLE_LABELS: dict[str, str] = {
    MemberLifecycleCode.REFUNDED.value: "已退款",
    MemberLifecycleCode.CARD_NOT_OPEN.value: "暂不开卡",
    MemberLifecycleCode.PAUSED.value: "暂停配送",
    MemberLifecycleCode.AWAITING_SETUP.value: "待完善履约",
    MemberLifecycleCode.BALANCE_EXHAUSTED.value: "已过期",
    MemberLifecycleCode.NEVER_OPENED.value: "未开卡",
    MemberLifecycleCode.RENEW_PENDING.value: "待续费",
    MemberLifecycleCode.DELIVERING.value: "正常配送中",
}


@dataclass(frozen=True)
class MemberLifecycleView:
    code: str
    label: str
    setup_alert: bool = False
    overlays: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class _MemberLifecycleContext:
    """批量预载上下文，避免列表页逐会员查库。"""

    applied_card_order_ids: frozenset[int]
    delivery_history_ids: frozenset[int]
    latest_mode_by_id: dict[int, CardOrderActivationMode | None]
    dinner_state_by_id: dict[int, MemberMealPeriodState | None]
    default_addr_by_id: dict[int, MemberAddress | None]


def member_on_leave_on_date(member: Member, today: date) -> bool:
    """区间请假或仅明日请假是否覆盖指定业务日。"""
    if member.leave_range_start and member.leave_range_end:
        if member.leave_range_start <= today <= member.leave_range_end:
            return True
    if member.tomorrow_leave_target_date is not None and member.is_leaved_tomorrow:
        return today <= member.tomorrow_leave_target_date
    return False


def _member_has_any_period_balance_from_state(
    member: Member,
    dinner_row: MemberMealPeriodState | None,
) -> bool:
    """任一餐段有余次（午餐 members.balance，晚餐 member_meal_period_state）。"""
    if int(member.balance or 0) > 0:
        return True
    return dinner_row is not None and int(dinner_row.balance or 0) > 0


def _member_has_applied_card_order(db: Session, member_id: int) -> bool:
    n = db.scalar(
        select(func.count())
        .select_from(MemberCardOrder)
        .where(
            MemberCardOrder.member_id == int(member_id),
            MemberCardOrder.applied_to_member.is_(True),
        )
    )
    return int(n or 0) > 0


def _member_has_delivery_history(db: Session, member_id: int) -> bool:
    """是否曾有确认送达记录（用于排除 legacy 老会员误报待完善）。"""
    hit = db.scalar(
        select(func.count())
        .select_from(DeliveryLog)
        .where(
            DeliveryLog.member_id == int(member_id),
            DeliveryLog.status == DeliveryStatus.DELIVERED.value,
        )
        .limit(1)
    )
    return int(hit or 0) > 0


def _load_applied_card_order_member_ids(db: Session, member_ids: list[int]) -> frozenset[int]:
    ids = sorted({int(x) for x in member_ids if x is not None})
    if not ids:
        return frozenset()
    rows = db.scalars(
        select(MemberCardOrder.member_id)
        .where(
            MemberCardOrder.member_id.in_(ids),
            MemberCardOrder.applied_to_member.is_(True),
        )
        .distinct()
    ).all()
    return frozenset(int(x) for x in rows)


def _load_delivery_history_member_ids(db: Session, member_ids: list[int]) -> frozenset[int]:
    ids = sorted({int(x) for x in member_ids if x is not None})
    if not ids:
        return frozenset()
    rows = db.scalars(
        select(DeliveryLog.member_id)
        .where(
            DeliveryLog.member_id.in_(ids),
            DeliveryLog.status == DeliveryStatus.DELIVERED.value,
        )
        .distinct()
    ).all()
    return frozenset(int(x) for x in rows)


def _load_latest_activation_mode_map(
    db: Session, member_ids: list[int]
) -> dict[int, CardOrderActivationMode | None]:
    """各会员最近一条已入账工单的 activation_mode。"""
    ids = sorted({int(x) for x in member_ids if x is not None})
    out: dict[int, CardOrderActivationMode | None] = {mid: None for mid in ids}
    if not ids:
        return out
    latest_sq = (
        select(
            MemberCardOrder.member_id.label("mid"),
            func.max(MemberCardOrder.id).label("max_id"),
        )
        .where(
            MemberCardOrder.member_id.in_(ids),
            MemberCardOrder.applied_to_member.is_(True),
        )
        .group_by(MemberCardOrder.member_id)
    ).subquery("latest_card")
    rows = db.execute(
        select(MemberCardOrder.member_id, MemberCardOrder.activation_mode)
        .select_from(MemberCardOrder)
        .join(
            latest_sq,
            and_(
                MemberCardOrder.member_id == latest_sq.c.mid,
                MemberCardOrder.id == latest_sq.c.max_id,
            ),
        )
    ).all()
    for mid, raw_mode in rows:
        if raw_mode is None:
            out[int(mid)] = None
            continue
        raw = str(raw_mode).strip().lower()
        try:
            out[int(mid)] = CardOrderActivationMode(raw)
        except ValueError:
            out[int(mid)] = None
    return out


def _build_lifecycle_context(
    db: Session,
    member_ids: list[int],
    *,
    dinner_state_map: dict[int, MemberMealPeriodState] | None = None,
    default_addr_by_id: dict[int, MemberAddress | None] | None = None,
) -> _MemberLifecycleContext:
    ids = sorted({int(x) for x in member_ids if x is not None})
    dinner_by_id: dict[int, MemberMealPeriodState | None] = {mid: None for mid in ids}
    if dinner_state_map is not None:
        for mid in ids:
            dinner_by_id[mid] = dinner_state_map.get(mid)
    elif ids:
        from app.services.meal_period.units import load_dinner_meal_period_states_map

        loaded = load_dinner_meal_period_states_map(db, ids)
        for mid in ids:
            dinner_by_id[mid] = loaded.get(mid)
    addr_by_id: dict[int, MemberAddress | None] = {mid: None for mid in ids}
    if default_addr_by_id is not None:
        for mid in ids:
            addr_by_id[mid] = default_addr_by_id.get(mid)
    elif ids:
        from app.services.member.member_address_service import load_default_address_map

        loaded = load_default_address_map(db, ids)
        for mid in ids:
            addr_by_id[mid] = loaded.get(mid)
    return _MemberLifecycleContext(
        applied_card_order_ids=_load_applied_card_order_member_ids(db, ids),
        delivery_history_ids=_load_delivery_history_member_ids(db, ids),
        latest_mode_by_id=_load_latest_activation_mode_map(db, ids),
        dinner_state_by_id=dinner_by_id,
        default_addr_by_id=addr_by_id,
    )


def _is_legacy_immediate_delivery_member_ctx(member: Member, ctx: _MemberLifecycleContext) -> bool:
    """
    历史老会员即日生效：无起送日、未暂停、有余次且曾有履约或入账。
    此类会员不应触发「待完善」提醒。
    """
    if member.delivery_start_date is not None:
        return False
    if bool(member.delivery_deferred):
        return False
    mid = int(member.id)
    dinner_row = ctx.dinner_state_by_id.get(mid)
    if not _member_has_any_period_balance_from_state(member, dinner_row):
        return False
    return mid in ctx.delivery_history_ids or mid in ctx.applied_card_order_ids


def _member_needs_setup_alert_ctx(member: Member, ctx: _MemberLifecycleContext) -> bool:
    """已入账但缺起送日或配送到家缺地址（排除 legacy 老会员）。"""
    if member.membership_refunded_at is not None:
        return False
    mid = int(member.id)
    dinner_row = ctx.dinner_state_by_id.get(mid)
    if not _member_has_any_period_balance_from_state(member, dinner_row):
        return False
    if _is_legacy_immediate_delivery_member_ctx(member, ctx):
        return False
    if mid not in ctx.applied_card_order_ids:
        return False
    default_addr = ctx.default_addr_by_id.get(mid)
    return _member_delivery_setup_incomplete_with_addr(member, default_addr)


def _resolve_member_lifecycle_with_ctx(
    member: Member,
    *,
    on_leave_today: bool,
    ctx: _MemberLifecycleContext,
) -> MemberLifecycleView:
    """单一会员生命周期（使用预载上下文，不再逐条查库）。"""
    overlays: list[str] = []
    if on_leave_today:
        overlays.append("请假中")

    if member.membership_refunded_at is not None:
        return MemberLifecycleView(
            code=MemberLifecycleCode.REFUNDED.value,
            label=_LIFECYCLE_LABELS[MemberLifecycleCode.REFUNDED.value],
            overlays=tuple(overlays),
        )

    setup_alert = _member_needs_setup_alert_ctx(member, ctx)
    mid = int(member.id)
    latest_mode = ctx.latest_mode_by_id.get(mid)

    if latest_mode == CardOrderActivationMode.DEFER_NOT_OPEN and bool(member.delivery_deferred):
        return MemberLifecycleView(
            code=MemberLifecycleCode.CARD_NOT_OPEN.value,
            label=_LIFECYCLE_LABELS[MemberLifecycleCode.CARD_NOT_OPEN.value],
            setup_alert=setup_alert,
            overlays=tuple(overlays),
        )

    if setup_alert:
        return MemberLifecycleView(
            code=MemberLifecycleCode.AWAITING_SETUP.value,
            label=_LIFECYCLE_LABELS[MemberLifecycleCode.AWAITING_SETUP.value],
            setup_alert=True,
            overlays=tuple(overlays),
        )

    if bool(member.delivery_deferred):
        return MemberLifecycleView(
            code=MemberLifecycleCode.PAUSED.value,
            label=_LIFECYCLE_LABELS[MemberLifecycleCode.PAUSED.value],
            setup_alert=False,
            overlays=tuple(overlays),
        )

    dinner_row = ctx.dinner_state_by_id.get(mid)
    has_balance = _member_has_any_period_balance_from_state(member, dinner_row)
    if not has_balance:
        return MemberLifecycleView(
            code=MemberLifecycleCode.BALANCE_EXHAUSTED.value,
            label=_LIFECYCLE_LABELS[MemberLifecycleCode.BALANCE_EXHAUSTED.value],
            overlays=tuple(overlays),
        )

    if not member.is_active and mid not in ctx.applied_card_order_ids:
        return MemberLifecycleView(
            code=MemberLifecycleCode.NEVER_OPENED.value,
            label=_LIFECYCLE_LABELS[MemberLifecycleCode.NEVER_OPENED.value],
            overlays=tuple(overlays),
        )

    threshold = int(get_settings().LOW_BALANCE_THRESHOLD)
    lunch_bal = int(member.balance or 0)
    if member.is_active and not bool(member.delivery_deferred) and 0 < lunch_bal <= threshold:
        overlays = [*overlays, "待续费"]
        return MemberLifecycleView(
            code=MemberLifecycleCode.RENEW_PENDING.value,
            label=_LIFECYCLE_LABELS[MemberLifecycleCode.RENEW_PENDING.value],
            setup_alert=False,
            overlays=tuple(dict.fromkeys(overlays)),
        )

    return MemberLifecycleView(
        code=MemberLifecycleCode.DELIVERING.value,
        label=_LIFECYCLE_LABELS[MemberLifecycleCode.DELIVERING.value],
        setup_alert=False,
        overlays=tuple(overlays),
    )


def resolve_members_lifecycle_map(
    db: Session,
    members: list[Member],
    *,
    on_leave_by_id: dict[int, bool] | None = None,
    dinner_state_map: dict[int, MemberMealPeriodState] | None = None,
    default_addr_by_id: dict[int, MemberAddress | None] | None = None,
) -> dict[int, MemberLifecycleView]:
    """批量计算档案主状态，供管理端会员列表等场景使用。"""
    if not members:
        return {}
    member_ids = [int(m.id) for m in members]
    ctx = _build_lifecycle_context(
        db,
        member_ids,
        dinner_state_map=dinner_state_map,
        default_addr_by_id=default_addr_by_id,
    )
    leave_map = on_leave_by_id or {}
    return {
        int(m.id): _resolve_member_lifecycle_with_ctx(
            m,
            on_leave_today=bool(leave_map.get(int(m.id), False)),
            ctx=ctx,
        )
        for m in members
    }


def _is_legacy_immediate_delivery_member(db: Session, member: Member) -> bool:
    """
    历史老会员即日生效：无起送日、未暂停、有余次且曾有履约或入账。
    此类会员不应触发「待完善」提醒。
    """
    if member.delivery_start_date is not None:
        return False
    if bool(member.delivery_deferred):
        return False
    from app.services.meal_period.balance import member_has_any_period_balance

    if not member_has_any_period_balance(db, member):
        return False
    mid = int(member.id)
    return _member_has_delivery_history(db, mid) or _member_has_applied_card_order(db, mid)


def member_needs_setup_alert(db: Session, member: Member) -> bool:
    """已入账但缺起送日或配送到家缺地址（排除 legacy 老会员）。"""
    if member.membership_refunded_at is not None:
        return False
    from app.services.meal_period.balance import member_has_any_period_balance

    if not member_has_any_period_balance(db, member):
        return False
    if _is_legacy_immediate_delivery_member(db, member):
        return False
    if not _member_has_applied_card_order(db, int(member.id)):
        return False
    return member_delivery_setup_incomplete(db, member)


def resolve_member_lifecycle(db: Session, member: Member, *, on_leave_today: bool = False) -> MemberLifecycleView:
    """单一入口：计算档案主状态标签（只读）。"""
    mid = int(member.id)
    ctx = _build_lifecycle_context(db, [mid])
    return _resolve_member_lifecycle_with_ctx(member, on_leave_today=on_leave_today, ctx=ctx)
