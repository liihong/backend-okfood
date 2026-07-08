"""会员配送门禁写入网关：集中更新 delivery_deferred / is_active / 起送日（不改 courier SQL）。

禁止在大表 eligible 逻辑中使用本模块的推断；大表仍读 delivery_deferred 等现有字段。
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import CardOpenMode, CardOrderActivationMode
from app.models.member import Member
from app.models.member_card_order import MemberCardOrder


def member_has_default_delivery_address(db: Session, member_id: int) -> bool:
    """配送到家时是否已有默认地址。"""
    from app.services.member.member_address_service import get_default_address

    return get_default_address(db, int(member_id)) is not None


def member_fulfillment_ready(db: Session, member: Member) -> bool:
    """
    履约信息是否齐备（用于 explicit_date 恢复配送）。
    须已有起送日；门店自提不再要求地址；配送到家须默认地址。
    """
    if member.delivery_start_date is None:
        return False
    if bool(member.store_pickup):
        return True
    return member_has_default_delivery_address(db, int(member.id))


def apply_delivery_blocked(db: Session, member: Member) -> None:
    """订阅大表门禁：阻断履约（暂停/暂不开卡/待完善）。"""
    member.delivery_deferred = True
    member.is_active = False
    db.add(member)


def apply_delivery_unblocked(db: Session, member: Member) -> None:
    """解除阻断并依餐段余额同步 is_active。"""
    member.delivery_deferred = False
    from app.services.meal_period.balance import sync_member_is_active_from_period_balances

    sync_member_is_active_from_period_balances(db, member)
    db.add(member)


def apply_pause_delivery(db: Session, member: Member) -> None:
    """用户/后台暂停：保留 delivery_start_date，仅阻断门禁。"""
    apply_delivery_blocked(db, member)


def apply_resume_delivery(db: Session, member: Member) -> None:
    """恢复配送：须履约信息齐备。"""
    if member_fulfillment_ready(db, member):
        apply_delivery_unblocked(db, member)
    else:
        apply_delivery_blocked(db, member)


def resolve_effective_activation_mode(
    order: MemberCardOrder,
    *,
    open_mode: CardOpenMode | None = None,
    defer_delivery_activation: bool = False,
    member: Member | None = None,
    db: Session | None = None,
) -> CardOrderActivationMode:
    """
    解析工单入账模式。优先读 order.activation_mode；NULL 时 legacy 推断（与改造前行为兼容）。
    """
    from app.services.member.member_card_order_service import (
        MINIPROGRAM_SELF_SERVICE_ORDER_CREATOR,
        _member_has_prior_applied_card_order,
    )

    raw = (getattr(order, "activation_mode", None) or "").strip().lower()
    if raw:
        try:
            return CardOrderActivationMode(raw)
        except ValueError:
            pass

    if defer_delivery_activation:
        return CardOrderActivationMode.DEFER_NOT_OPEN
    if order.delivery_start_date is not None:
        return CardOrderActivationMode.EXPLICIT_DATE

    is_renew = open_mode == CardOpenMode.RENEW
    if not is_renew and db is not None and member is not None:
        is_renew = _member_has_prior_applied_card_order(
            db, int(member.id), exclude_order_id=int(order.id)
        )

    if is_renew:
        return CardOrderActivationMode.KEEP_SCHEDULE

    if (order.created_by or "").strip() == MINIPROGRAM_SELF_SERVICE_ORDER_CREATOR:
        return CardOrderActivationMode.DEFER_NOT_OPEN

    if open_mode == CardOpenMode.NEW_MEMBER:
        return CardOrderActivationMode.DEFER_NOT_OPEN

    return CardOrderActivationMode.KEEP_SCHEDULE


def apply_card_order_activation_after_credit(
    db: Session,
    member: Member,
    order: MemberCardOrder,
    *,
    open_mode: CardOpenMode | None = None,
    defer_delivery_activation: bool = False,
) -> None:
    """
    开卡入账后的配送状态写入（须在 +次数 之后调用）。

    规则摘要：
    - keep_schedule：不改起送日/地址/deferred，仅 sync is_active；
    - explicit_date：写起送日；地址或自提齐备则恢复配送，否则 deferred；
    - defer_not_open / defer_pause：deferred=true，不改起送日。
    """
    mode = resolve_effective_activation_mode(
        order,
        open_mode=open_mode,
        defer_delivery_activation=defer_delivery_activation,
        member=member,
        db=db,
    )
    if mode == CardOrderActivationMode.KEEP_SCHEDULE:
        from app.services.meal_period.balance import sync_member_is_active_from_period_balances

        sync_member_is_active_from_period_balances(db, member)
        db.add(member)
        return

    if mode == CardOrderActivationMode.DEFER_NOT_OPEN:
        apply_delivery_blocked(db, member)
        return

    if mode == CardOrderActivationMode.DEFER_PAUSE:
        apply_delivery_blocked(db, member)
        return

    if mode == CardOrderActivationMode.EXPLICIT_DATE:
        if order.delivery_start_date is not None:
            member.delivery_start_date = order.delivery_start_date
        # R3：须履约信息齐备才解除暂停；仅写起送日不得 auto resume
        if member_fulfillment_ready(db, member):
            apply_delivery_unblocked(db, member)
        else:
            apply_delivery_blocked(db, member)
        return

    from app.services.meal_period.balance import sync_member_is_active_from_period_balances

    sync_member_is_active_from_period_balances(db, member)
    db.add(member)


def compute_activation_mode_for_create(
    *,
    open_mode: CardOpenMode,
    defer_delivery_activation: bool,
    delivery_start_date: date | None,
) -> str:
    """后台/小程序创单时写入工单的 activation_mode。"""
    if defer_delivery_activation:
        return CardOrderActivationMode.DEFER_NOT_OPEN.value
    if delivery_start_date is not None:
        return CardOrderActivationMode.EXPLICIT_DATE.value
    if open_mode == CardOpenMode.RENEW:
        return CardOrderActivationMode.KEEP_SCHEDULE.value
    return CardOrderActivationMode.DEFER_NOT_OPEN.value


def latest_applied_order_activation_mode(
    db: Session, member_id: int
) -> CardOrderActivationMode | None:
    """最近一条已入账工单的 activation_mode（展示「暂不开卡」用）。"""
    row = db.scalar(
        select(MemberCardOrder.activation_mode)
        .where(
            MemberCardOrder.member_id == int(member_id),
            MemberCardOrder.applied_to_member.is_(True),
        )
        .order_by(MemberCardOrder.id.desc())
        .limit(1)
    )
    if not row:
        return None
    raw = str(row).strip().lower()
    try:
        return CardOrderActivationMode(raw)
    except ValueError:
        return None
