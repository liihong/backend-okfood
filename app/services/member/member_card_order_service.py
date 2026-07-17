from datetime import date
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.timeutil import (
    min_admin_card_order_delivery_start_shanghai,
    min_member_delivery_start_shanghai,
    shanghai_naive_range_for_calendar_day,
)
from app.models.enums import (
    CardOpenMode,
    CardOrderActivationMode,
    CardOrderKind,
    CardOrderPayStatus,
    CardPayChannel,
    CouponLockedOrderBiz,
    PlanType,
)
from app.models.member import Member
from app.models.member_address import MemberAddress
from app.models.member_card_order import MemberCardOrder
from app.models.membership_card_template import MembershipCardTemplate
from app.schemas.admin import CardOrderCreateIn, CardOrderOut, CardOrderPatchIn, RechargeIn
from app.services.admin.admin_service import apply_member_recharge_delta
from app.utils.sql_like import escape_like_fragment
from app.services.member.member_address_service import upsert_default_address_from_admin_map_pick
from app.services.member.member_delivery_state_service import compute_activation_mode_for_create
from app.services.admin.catalog_admin_service import get_membership_template_row
from app.services.shared.store_config_service import get_member_card_prices_yuan
from app.services.marketing.coupon_checkout_service import (
    mark_member_coupon_used_for_order,
    release_member_coupon_for_order,
)

MINIPROGRAM_OFFLINE_CLAIM_ORDER_CREATOR = "miniprogram-offline"
MINIPROGRAM_SELF_SERVICE_ORDER_CREATOR = "miniprogram"
DOUYIN_REDEEM_ORDER_CREATOR = "douyin_redeem"
# 小程序自助购卡 + 抖音自助验券（待完善履约口径一致）
SELF_SERVICE_CARD_ORDER_CREATORS: frozenset[str] = frozenset(
    {
        MINIPROGRAM_SELF_SERVICE_ORDER_CREATOR,
        DOUYIN_REDEEM_ORDER_CREATOR,
    }
)


def _quota_for_card_kind(kind: str) -> tuple[PlanType, int]:
    k = (kind or "").strip()
    if k == CardOrderKind.WEEK.value:
        return PlanType.WEEK, 6
    if k == CardOrderKind.MONTH.value:
        return PlanType.MONTH, 24
    if k == CardOrderKind.TIMES.value:
        return PlanType.TIMES, 1
    raise HTTPException(status_code=400, detail="无效开卡类型")


def _plan_for_membership_template(tpl: MembershipCardTemplate) -> PlanType:
    """计划类型影响会员 plan_type 与是否累加 meal_quota_total（配合 bump_meal_quota_total）。"""
    kl = (tpl.kind_label or "").strip()
    pk = (tpl.period_kind or "").strip().lower()
    if "月" in kl or pk == "monthly":
        return PlanType.MONTH
    if "周" in kl or pk == "weekly":
        return PlanType.WEEK
    mg = int(tpl.meals_grant)
    if mg >= 18:
        return PlanType.MONTH
    if mg >= 6:
        return PlanType.WEEK
    return PlanType.TIMES


def enum_card_kind_for_template(tpl: MembershipCardTemplate) -> str:
    """库表 card_kind 枚举仅允许周卡/月卡/次卡：与 _plan_for_membership_template 对齐便于后台展示。"""
    p = _plan_for_membership_template(tpl)
    if p == PlanType.MONTH:
        return CardOrderKind.MONTH.value
    if p == PlanType.WEEK:
        return CardOrderKind.WEEK.value
    return CardOrderKind.TIMES.value


def _format_amount_yuan(v: Decimal | None) -> str | None:
    if v is None:
        return None
    return format(v, "f")


def _amount_yuan_for_card_kind_str(db: Session, card_kind: str, *, store_id: int | None = None) -> Decimal:
    k = (card_kind or "").strip()
    if k == CardOrderKind.WEEK.value:
        week_p, _ = get_member_card_prices_yuan(db, store_id=store_id)
        return week_p
    if k == CardOrderKind.MONTH.value:
        _, month_p = get_member_card_prices_yuan(db, store_id=store_id)
        return month_p
    if k == CardOrderKind.TIMES.value:
        return get_settings().MEMBER_CARD_TIMES_PRICE_YUAN
    raise HTTPException(status_code=400, detail="无效开卡类型")


def ensure_miniprogram_offline_claim_order(
    db: Session,
    member_id: int,
    *,
    card_kind: str,
    delivery_start_date: date,
) -> MemberCardOrder:
    """小程序端「已支付(线下)」：生成或更新一条未缴/渠道为线下的开卡工单，待后台标记已缴后同步入账。"""
    if delivery_start_date < min_member_delivery_start_shanghai():
        raise HTTPException(
            status_code=400,
            detail="起送日期须不早于明日（上海业务日）",
        )
    m = db.get(Member, member_id)
    if not m or m.deleted_at is not None:
        raise HTTPException(status_code=404, detail="用户不存在")
    if int(m.balance) > 0:
        raise HTTPException(status_code=400, detail="仅剩余次数为 0 时可登记线下开卡")
    k = (card_kind or "").strip()
    if k not in (CardOrderKind.WEEK.value, CardOrderKind.MONTH.value, CardOrderKind.TIMES.value):
        raise HTTPException(status_code=400, detail="开卡类型须为周卡、月卡或次卡")
    amt = _amount_yuan_for_card_kind_str(db, k, store_id=int(m.store_id))
    rmk = "小程序：用户自报已线下/其他方式缴费，待后台核对后标记已缴并同步入账"
    q = select(MemberCardOrder).where(
        MemberCardOrder.member_id == int(member_id),
        MemberCardOrder.pay_status == CardOrderPayStatus.UNPAID.value,
        MemberCardOrder.applied_to_member.is_(False),
        MemberCardOrder.pay_channel == CardPayChannel.OFFLINE.value,
        MemberCardOrder.created_by == MINIPROGRAM_OFFLINE_CLAIM_ORDER_CREATOR,
    )
    order = db.scalars(q.order_by(MemberCardOrder.id.desc()).limit(1)).first()
    if order is not None:
        order.card_kind = k
        order.delivery_start_date = delivery_start_date
        order.amount_yuan = amt
        order.remark = rmk
        order.out_trade_no = None
        order.wx_transaction_id = None
        db.flush()
        return order
    order = MemberCardOrder(
        member_id=int(member_id),
        tenant_id=int(m.tenant_id),
        store_id=int(m.store_id),
        card_kind=k,
        pay_channel=CardPayChannel.OFFLINE.value,
        pay_status=CardOrderPayStatus.UNPAID.value,
        amount_yuan=amt,
        remark=rmk,
        delivery_start_date=delivery_start_date,
        applied_to_member=False,
        out_trade_no=None,
        wx_transaction_id=None,
        created_by=MINIPROGRAM_OFFLINE_CLAIM_ORDER_CREATOR,
    )
    db.add(order)
    db.flush()
    return order


def _member_delivery_setup_incomplete_with_addr(
    member: Member,
    default_address: MemberAddress | None,
) -> bool:
    """配送到家缺默认地址 / 无起送日（已知默认地址时不再查库）。"""
    if member.delivery_start_date is None:
        return True
    if bool(member.store_pickup):
        return False
    return default_address is None


def member_delivery_setup_incomplete(
    db: Session,
    member: Member,
    *,
    default_address: MemberAddress | None | object = ...,
) -> bool:
    """配送到家订阅：无起送日，或配送到家但无默认地址，视为待完善履约信息。"""
    if default_address is not ...:
        return _member_delivery_setup_incomplete_with_addr(member, default_address)  # type: ignore[arg-type]
    if member.delivery_start_date is None:
        return True
    if bool(member.store_pickup):
        return False
    from app.services.member.member_address_service import get_default_address

    return get_default_address(db, int(member.id)) is None


def member_paid_card_awaiting_setup(db: Session, member_id: int) -> bool:
    """
    小程序自助购卡 / 抖音自助验券：已缴且履约信息未齐备（无起送日，或配送到家无默认地址）。
    曾确认送达后仅缺起送日的不视为待完善（多为主动暂停/历史清空），走恢复配送。
    支付成功即入账，与 balance 无关；用于「我的」引导完善配送后再派单。
    仅只读判断，不修改会员档案。
    """
    m = db.get(Member, int(member_id))
    if not m or m.deleted_at is not None:
        return False
    order = _latest_self_service_paid_card_order(db, int(member_id))
    if order is None:
        return False
    if not member_delivery_setup_incomplete(db, m):
        return False
    # 与 lifecycle「待完善」口径对齐：曾送达则不再引导待完善
    from app.models.delivery_log import DeliveryLog
    from app.models.enums import DeliveryStatus

    hit = db.scalar(
        select(func.count())
        .select_from(DeliveryLog)
        .where(
            DeliveryLog.member_id == int(member_id),
            DeliveryLog.status == DeliveryStatus.DELIVERED.value,
        )
        .limit(1)
    )
    if int(hit or 0) > 0:
        return False
    return True


def _latest_self_service_paid_card_order(
    db: Session,
    member_id: int,
    *,
    applied_to_member: bool | None = None,
    delivery_start_missing: bool = False,
) -> MemberCardOrder | None:
    """最近一条小程序自助 / 抖音验券已缴开卡工单。"""
    filters = [
        MemberCardOrder.member_id == int(member_id),
        MemberCardOrder.created_by.in_(tuple(SELF_SERVICE_CARD_ORDER_CREATORS)),
        MemberCardOrder.pay_status == CardOrderPayStatus.PAID.value,
    ]
    if applied_to_member is not None:
        filters.append(MemberCardOrder.applied_to_member.is_(applied_to_member))
    if delivery_start_missing:
        filters.append(MemberCardOrder.delivery_start_date.is_(None))
    return db.scalars(
        select(MemberCardOrder)
        .where(*filters)
        .order_by(MemberCardOrder.id.desc())
        .limit(1)
    ).first()


def _latest_miniprogram_self_service_card_order(
    db: Session,
    member_id: int,
    *,
    applied_to_member: bool | None = None,
    delivery_start_missing: bool = False,
) -> MemberCardOrder | None:
    """兼容旧调用：仅小程序自助工单。"""
    filters = [
        MemberCardOrder.member_id == int(member_id),
        MemberCardOrder.created_by == MINIPROGRAM_SELF_SERVICE_ORDER_CREATOR,
        MemberCardOrder.pay_status == CardOrderPayStatus.PAID.value,
    ]
    if applied_to_member is not None:
        filters.append(MemberCardOrder.applied_to_member.is_(applied_to_member))
    if delivery_start_missing:
        filters.append(MemberCardOrder.delivery_start_date.is_(None))
    return db.scalars(
        select(MemberCardOrder)
        .where(*filters)
        .order_by(MemberCardOrder.id.desc())
        .limit(1)
    ).first()


def _latest_miniprogram_card_order_for_delivery_start_write(
    db: Session, member_id: int
) -> MemberCardOrder | None:
    """
    完善配送信息时写入工单起送日。

    - 续卡：创建工单时常已带起送日，且支付后多为「已缴」。
    - 新用户购卡包：工单创建时无起送日；若支付回调/拉单滞后，工单仍为「未缴」，
      亦须把起送日写入该笔微信自助工单，避免 profile 已保存而开卡工单仍为空。
    """
    order = _latest_miniprogram_self_service_card_order(
        db, member_id, applied_to_member=False
    )
    if order is not None:
        return order
    order = _latest_miniprogram_self_service_card_order(
        db, member_id, delivery_start_missing=True
    )
    if order is not None:
        return order
    return db.scalars(
        select(MemberCardOrder)
        .where(
            MemberCardOrder.member_id == int(member_id),
            MemberCardOrder.created_by == MINIPROGRAM_SELF_SERVICE_ORDER_CREATOR,
            MemberCardOrder.pay_status == CardOrderPayStatus.UNPAID.value,
            MemberCardOrder.pay_channel == CardPayChannel.WECHAT.value,
            MemberCardOrder.applied_to_member.is_(False),
        )
        .order_by(MemberCardOrder.id.desc())
        .limit(1)
    ).first()


def apply_delivery_start_to_pending_miniprogram_card_order(
    db: Session,
    member_id: int,
    delivery_start_date: date,
) -> MemberCardOrder | None:
    """
    小程序用户完善配送信息时，将起送日写入最近一条自助开卡工单。
    优先未入账工单；若客服已先入账单但工单仍缺起送日，则补写以便后台列表展示。
    """
    if delivery_start_date < min_member_delivery_start_shanghai():
        return None
    order = _latest_miniprogram_card_order_for_delivery_start_write(db, member_id)
    if order is None:
        return None
    order.delivery_start_date = delivery_start_date
    db.flush()
    member = db.get(Member, int(member_id))
    from app.services.admin.admin_system_notification_service import (
        _meal_period_label_for_card_order,
        refresh_miniprogram_card_order_pending_notification,
    )

    refresh_miniprogram_card_order_pending_notification(
        db,
        store_id=int(order.store_id),
        order_id=int(order.id),
        card_kind=(order.card_kind or "").strip(),
        member_id=int(member_id),
        member_phone=(member.phone if member else None),
        member_name=(member.name if member else None),
        delivery_start_date=delivery_start_date,
        meal_period_label=_meal_period_label_for_card_order(db, order),
    )
    return order


def _meal_periods_for_order(
    order: MemberCardOrder,
    *,
    tpl: MembershipCardTemplate | None = None,
    db: Session | None = None,
) -> list[str]:
    """已入账用工单快照；未入账优先读绑定模版，经典卡默认午餐。"""
    from app.services.meal_period.template_periods import (
        classic_card_meal_periods_snapshot,
        meal_periods_from_template,
        normalize_meal_periods_list,
    )

    snap = getattr(order, "meal_periods_snapshot", None)
    if order.applied_to_member and snap is not None:
        return normalize_meal_periods_list(snap)
    tpl_id = getattr(order, "membership_template_id", None)
    if tpl_id is not None:
        resolved_tpl = tpl
        if resolved_tpl is None and db is not None:
            resolved_tpl = db.get(MembershipCardTemplate, int(tpl_id))
        if resolved_tpl:
            return meal_periods_from_template(resolved_tpl)
    return classic_card_meal_periods_snapshot()


def _order_to_out_from_maps(
    order: MemberCardOrder,
    *,
    member_map: dict[int, Member],
    tpl_map: dict[int, MembershipCardTemplate],
) -> CardOrderOut:
    """单条工单序列化（使用预加载的会员/模版 map，避免 N+1）。"""
    m = member_map.get(int(order.member_id))
    name = (m.name if m else "") or ""
    phone = (m.phone if m else "") or ""
    ca = order.created_at.isoformat() if order.created_at else ""
    ua = order.updated_at.isoformat() if order.updated_at else ""
    ds = order.delivery_start_date.isoformat() if order.delivery_start_date else None
    wn = (m.wechat_name if m else None) or None
    if wn is not None:
        wn = str(wn).strip() or None
    tpl_id = getattr(order, "membership_template_id", None)
    tpl = tpl_map.get(int(tpl_id)) if tpl_id is not None else None
    tpl_label: str | None = None
    if tpl:
        tpl_label = f"{tpl.name}（{tpl.kind_label}）"
    out_no = (order.out_trade_no or "").strip() or None
    act_mode = (getattr(order, "activation_mode", None) or "").strip() or None
    return CardOrderOut(
        id=int(order.id),
        member_id=int(order.member_id),
        member_phone=phone,
        member_name=name,
        member_wechat_name=wn,
        out_trade_no=out_no,
        delivery_start_date=ds,
        activation_mode=act_mode,
        card_kind=order.card_kind,
        pay_channel=order.pay_channel,
        pay_status=order.pay_status,
        amount_yuan=_format_amount_yuan(order.amount_yuan),
        remark=order.remark,
        applied_to_member=bool(order.applied_to_member),
        created_by=order.created_by,
        created_at=ca,
        updated_at=ua,
        membership_template_id=int(tpl_id) if tpl_id is not None else None,
        template_product_label=tpl_label,
        meal_periods=_meal_periods_for_order(order, tpl=tpl),
    )


def _load_member_map(db: Session, member_ids: list[int]) -> dict[int, Member]:
    """批量加载会员，供列表序列化复用。"""
    if not member_ids:
        return {}
    rows = db.scalars(select(Member).where(Member.id.in_(member_ids))).all()
    return {int(m.id): m for m in rows}


def _load_template_map(db: Session, template_ids: list[int]) -> dict[int, MembershipCardTemplate]:
    """批量加载会员卡模版，供列表序列化复用。"""
    if not template_ids:
        return {}
    rows = db.scalars(select(MembershipCardTemplate).where(MembershipCardTemplate.id.in_(template_ids))).all()
    return {int(t.id): t for t in rows}


def _orders_to_out_batch(db: Session, orders: list[MemberCardOrder]) -> list[CardOrderOut]:
    """批量序列化工单列表，Member/Template 各查一次。"""
    if not orders:
        return []
    member_ids = list({int(o.member_id) for o in orders})
    tpl_ids = list(
        {
            int(o.membership_template_id)
            for o in orders
            if getattr(o, "membership_template_id", None) is not None
        }
    )
    member_map = _load_member_map(db, member_ids)
    tpl_map = _load_template_map(db, tpl_ids)
    return [_order_to_out_from_maps(o, member_map=member_map, tpl_map=tpl_map) for o in orders]


def _order_to_out(db: Session, order: MemberCardOrder) -> CardOrderOut:
    return _orders_to_out_batch(db, [order])[0]


def _member_has_prior_applied_card_order(
    db: Session, member_id: int, *, exclude_order_id: int | None = None
) -> bool:
    """是否已有其它已入账开卡工单（用于续卡/补单时禁止误标暂停配送）。"""
    q = select(func.count()).select_from(MemberCardOrder).where(
        MemberCardOrder.member_id == int(member_id),
        MemberCardOrder.applied_to_member.is_(True),
    )
    if exclude_order_id is not None:
        q = q.where(MemberCardOrder.id != int(exclude_order_id))
    return int(db.scalar(q) or 0) > 0


def _apply_delivery_activation_after_card_credit(
    db: Session,
    member: Member,
    order: MemberCardOrder,
    *,
    open_mode: CardOpenMode | None = None,
    defer_delivery_activation: bool = False,
) -> None:
    """入账后的配送门禁写入（委托 member_delivery_state_service）。"""
    from app.services.member.member_delivery_state_service import (
        apply_card_order_activation_after_credit,
        resolve_effective_activation_mode,
    )

    if not (order.activation_mode or "").strip():
        mode = resolve_effective_activation_mode(
            order,
            open_mode=open_mode,
            defer_delivery_activation=defer_delivery_activation,
            member=member,
            db=db,
        )
        order.activation_mode = mode.value
        db.add(order)
    apply_card_order_activation_after_credit(
        db,
        member,
        order,
        open_mode=open_mode,
        defer_delivery_activation=defer_delivery_activation,
    )


def _apply_paid_card_order_to_member_balance(
    db: Session,
    order: MemberCardOrder,
    *,
    operator: str,
    open_mode: CardOpenMode | None = None,
    defer_delivery_activation: bool = False,
) -> None:
    """已缴且未入账：按卡型叠加次数/总配额；续卡默认延续档案起送日与配送状态。"""
    m = db.get(Member, order.member_id)
    if not m:
        raise HTTPException(status_code=404, detail="会员不存在")
    # 老会员自助续卡：工单不填起送日时沿用档案起送日（小程序购卡、抖音验券一致）
    if (
        order.delivery_start_date is None
        and (order.created_by or "").strip() in SELF_SERVICE_CARD_ORDER_CREATORS
        and m.delivery_start_date is not None
    ):
        order.delivery_start_date = m.delivery_start_date
    tpl_id = getattr(order, "membership_template_id", None)
    if tpl_id is not None:
        tpl = db.get(MembershipCardTemplate, int(tpl_id))
        if not tpl:
            raise HTTPException(status_code=404, detail="会员卡模版不存在")
        plan = _plan_for_membership_template(tpl)
        amt = int(tpl.meals_grant)
        kind_label = f"{tpl.name}（{tpl.kind_label}）"
        from app.services.meal_period.template_periods import resolve_meal_periods_for_card_order_credit

        order.meal_periods_snapshot = resolve_meal_periods_for_card_order_credit(
            order_meal_periods_snapshot=order.meal_periods_snapshot,
            template=tpl,
        )
    else:
        plan, amt = _quota_for_card_kind(order.card_kind)
        kind_label = order.card_kind
        from app.services.meal_period.template_periods import resolve_meal_periods_for_card_order_credit

        order.meal_periods_snapshot = resolve_meal_periods_for_card_order_credit(
            order_meal_periods_snapshot=order.meal_periods_snapshot,
            template=None,
            use_classic_lunch_only=True,
        )
    parts = [
        f"开卡工单#{order.id}",
        f"{kind_label}",
        f"同步入账+{amt}次",
        f"渠道{order.pay_channel}",
    ]
    ay = _format_amount_yuan(order.amount_yuan)
    if ay is not None:
        parts.append(f"实收{ay}元")
    id_bits: list[str] = []
    wn = (m.wechat_name or "").strip()
    if wn:
        id_bits.append(f"微信{wn[:100]}")
    ph = (m.phone or "").strip()
    if ph:
        id_bits.append(f"手机{ph}")
    if id_bits:
        parts.append("，".join(id_bits))
    rmk = (order.remark or "").strip()
    if rmk:
        parts.append(f"备注{rmk[:180]}")
    log_detail = "；".join(parts)
    bump_quota = tpl_id is not None
    from app.models.enums import MealPeriod
    from app.services.meal_period.balance import (
        apply_dinner_recharge_delta,
        reset_dinner_quota_on_membership_reopen,
    )
    periods = list(order.meal_periods_snapshot or [])
    # 退卡后重新开卡：清除退款标记并重置总次数，避免状态仍为「已退款」、剩余/总叠加旧周期
    if m.membership_refunded_at is not None:
        m.membership_refunded_at = None
        m.meal_quota_total = 0
        reset_dinner_quota_on_membership_reopen(db, int(m.id))
    if MealPeriod.LUNCH.value in periods:
        apply_member_recharge_delta(
            db,
            RechargeIn(phone=m.phone, amount=amt, plan_type=plan, bump_meal_quota_total=bump_quota),
            operator=operator,
            log_detail=log_detail,
            member_id=int(m.id),
            skip_plan_type_update=True,
        )
    if MealPeriod.DINNER.value in periods:
        apply_dinner_recharge_delta(
            db,
            m,
            amount=amt,
            plan_type=plan,
            bump_meal_quota_total=bump_quota,
            skip_plan_type_update=True,
            operator=operator,
            log_detail=log_detail,
        )
    _apply_delivery_activation_after_card_credit(
        db,
        m,
        order,
        open_mode=open_mode,
        defer_delivery_activation=defer_delivery_activation,
    )
    from app.services.meal_period.apply_side_effects import ensure_meal_period_states_after_card_apply

    ensure_meal_period_states_after_card_apply(db, m, order.meal_periods_snapshot)
    order.applied_to_member = True
    from app.services.meal_period.plan_type_sync import sync_member_plan_type_from_latest_card_order

    sync_member_plan_type_from_latest_card_order(db, m)


def _meals_grant_units_for_card_order(db: Session, order: MemberCardOrder) -> tuple[int, bool]:
    """返回开卡工单入账份数及是否曾累加 meal_quota_total（卡包模版）。"""
    tpl_id = getattr(order, "membership_template_id", None)
    if tpl_id is not None:
        tpl = db.get(MembershipCardTemplate, int(tpl_id))
        if not tpl:
            raise ValueError("会员卡模版不存在，无法撤销入账")
        return max(1, int(tpl.meals_grant)), True
    _, amt = _quota_for_card_kind(order.card_kind)
    return max(1, int(amt)), False


def _actual_credit_periods_for_card_order(db: Session, order: MemberCardOrder) -> frozenset[str]:
    """
    查开卡工单正向入账流水，确定实际写入的餐段。

    兼容晚餐卡误入午餐次数池的历史数据：退款扣次须与入账池一致。
    """
    from app.models.balance_log import BalanceLog
    from app.models.enums import BalanceReason, MealPeriod

    detail_prefix = f"开卡工单#{int(order.id)}"
    rows = db.scalars(
        select(BalanceLog).where(
            BalanceLog.member_id == int(order.member_id),
            BalanceLog.change > 0,
            BalanceLog.reason == BalanceReason.RECHARGE.value,
            BalanceLog.detail.like(f"%{detail_prefix}%"),
        )
    ).all()
    if not rows:
        return frozenset()
    out: set[str] = set()
    for row in rows:
        p = (row.meal_period or MealPeriod.LUNCH.value).strip().lower()
        if p in (MealPeriod.LUNCH.value, MealPeriod.DINNER.value):
            out.add(p)
    return frozenset(out)


def _revoke_target_periods_for_card_order(db: Session, order: MemberCardOrder) -> frozenset[str]:
    """撤销入账扣次餐段：优先按实际入账流水，否则按工单快照/模版。"""
    actual = _actual_credit_periods_for_card_order(db, order)
    if actual:
        return actual
    return frozenset(_meal_periods_for_order(order, db=db))


def revoke_paid_card_order_member_sync(db: Session, order: MemberCardOrder, *, operator: str) -> None:
    """微信原路退款前：若工单已同步入账，按餐段快照扣回次数/总配额并标记未入账。"""
    if not order.applied_to_member:
        return
    m = db.get(Member, int(order.member_id))
    if not m or m.deleted_at is not None:
        raise ValueError("会员不存在，无法撤销入账")
    from app.models.enums import MealPeriod
    from app.services.meal_period.balance import (
        apply_dinner_recharge_delta,
        sync_member_is_active_from_period_balances,
    )
    from app.models.member_meal_period_state import MemberMealPeriodState

    periods = _revoke_target_periods_for_card_order(db, order)
    units, bump_quota_total = _meals_grant_units_for_card_order(db, order)
    detail = f"开卡工单#{int(order.id)}微信退款撤销入账-{units}次"
    if MealPeriod.LUNCH.value in periods:
        bal = int(m.balance or 0)
        if bal < units:
            raise ValueError(
                f"会员午餐剩余次数 {bal} 不足扣回本次入账 {units} 次，无法原路退款；请先在会员档案调整次数",
            )
        apply_member_recharge_delta(
            db,
            RechargeIn(phone=m.phone, amount=-units, plan_type=None),
            operator=operator,
            log_detail=detail,
            member_id=int(m.id),
        )
        if bump_quota_total:
            m.meal_quota_total = max(0, int(m.meal_quota_total or 0) - units)
            db.add(m)
    if MealPeriod.DINNER.value in periods:
        row = db.get(
            MemberMealPeriodState,
            {"member_id": int(m.id), "meal_period": MealPeriod.DINNER.value},
        )
        d_bal = int(row.balance or 0) if row else 0
        if d_bal < units:
            raise ValueError(
                f"会员晚餐剩余次数 {d_bal} 不足扣回本次入账 {units} 次，无法原路退款；请先在会员档案调整次数",
            )
        apply_dinner_recharge_delta(
            db,
            m,
            amount=-units,
            plan_type=None,
            operator=operator,
            log_detail=detail,
        )
        if bump_quota_total and row is not None:
            row.meal_quota_total = max(0, int(row.meal_quota_total or 0) - units)
            db.add(row)
    sync_member_is_active_from_period_balances(db, m)
    order.applied_to_member = False
    db.add(order)
    from app.services.meal_period.plan_type_sync import sync_member_plan_type_from_latest_card_order

    sync_member_plan_type_from_latest_card_order(db, m)


def apply_paid_card_order_to_member_if_pending(db: Session, order: MemberCardOrder, *, operator: str) -> None:
    """支付回调等场景：仅当已缴且未入账时入账（可重复调用）。"""
    if order.applied_to_member:
        return
    if order.pay_status != CardOrderPayStatus.PAID.value:
        return
    renew = _member_has_prior_applied_card_order(db, int(order.member_id), exclude_order_id=int(order.id))
    _apply_paid_card_order_to_member_balance(
        db,
        order,
        operator=operator,
        open_mode=CardOpenMode.RENEW if renew else None,
    )


def _sync_order_to_member(
    db: Session,
    order: MemberCardOrder,
    *,
    operator: str,
    open_mode: CardOpenMode | None = None,
    defer_delivery_activation: bool = False,
) -> None:
    if order.applied_to_member:
        raise HTTPException(status_code=400, detail="该工单已入账，请勿重复同步")
    if order.pay_status != CardOrderPayStatus.PAID.value:
        raise HTTPException(status_code=400, detail="仅「已缴」工单可同步会员次数")
    if open_mode is None and _member_has_prior_applied_card_order(
        db, int(order.member_id), exclude_order_id=int(order.id)
    ):
        open_mode = CardOpenMode.RENEW
    _apply_paid_card_order_to_member_balance(
        db,
        order,
        operator=operator,
        open_mode=open_mode,
        defer_delivery_activation=defer_delivery_activation,
    )


def list_card_orders_paged(
    db: Session,
    *,
    q: str | None,
    pay_status: str | None,
    page: int,
    page_size: int,
    include_history: bool = False,
    store_id: int | None = None,
    order_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> tuple[list[CardOrderOut], int | None, bool]:
    """分页列表。返回 (items, total, has_more)；全量历史第 2 页起跳过 COUNT，total 为 None。"""
    join_on = Member.id == MemberCardOrder.member_id
    filters = []
    needs_member_join = False
    if store_id is not None:
        filters.append(MemberCardOrder.store_id == int(store_id))
    if order_id is not None:
        filters.append(MemberCardOrder.id == int(order_id))
    elif not include_history:
        # 默认工作台：隐藏「已缴且已同步入账」的完结单；其余（未缴、已缴待入账等）仍显示
        filters.append(
            or_(
                MemberCardOrder.pay_status != CardOrderPayStatus.PAID.value,
                MemberCardOrder.applied_to_member.is_(False),
            )
        )
    if q and q.strip():
        needs_member_join = True
        esc = escape_like_fragment(q.strip())
        filters.append(
            or_(
                Member.phone.like(f"{esc}%", escape="\\"),
                Member.name.like(f"%{esc}%", escape="\\"),
                Member.wechat_name.like(f"%{esc}%", escape="\\"),
            )
        )
    ps = (pay_status or "").strip()
    if ps in (
        CardOrderPayStatus.UNPAID.value,
        CardOrderPayStatus.PAID.value,
        CardOrderPayStatus.REFUNDED.value,
        CardOrderPayStatus.CANCELLED.value,
    ):
        filters.append(MemberCardOrder.pay_status == ps)
    # 按工单创建时间（上海自然日）筛选：左闭右开，与财务/抖音核销等口径一致
    if date_from is not None:
        start_bj, _ = shanghai_naive_range_for_calendar_day(date_from)
        filters.append(MemberCardOrder.created_at >= start_bj)
    if date_to is not None:
        _, end_bj = shanghai_naive_range_for_calendar_day(date_to)
        filters.append(MemberCardOrder.created_at < end_bj)

    page = max(1, page)
    page_size = min(max(1, page_size), 100)
    # 全量历史深分页：第 2 页起用 limit+1 探测 has_more，跳过全表 COUNT
    skip_count = bool(include_history and page > 1 and order_id is None)
    fetch_limit = page_size + 1 if skip_count else page_size

    total: int | None
    if skip_count:
        total = None
    else:
        count_stmt = select(func.count()).select_from(MemberCardOrder)
        if needs_member_join:
            count_stmt = count_stmt.join(Member, join_on)
        for f in filters:
            count_stmt = count_stmt.where(f)
        total = int(db.scalar(count_stmt) or 0)

    list_stmt = select(MemberCardOrder)
    if needs_member_join:
        list_stmt = list_stmt.join(Member, join_on)
    list_stmt = (
        list_stmt.order_by(MemberCardOrder.created_at.desc(), MemberCardOrder.id.desc())
        .offset((page - 1) * page_size)
        .limit(fetch_limit)
    )
    for f in filters:
        list_stmt = list_stmt.where(f)
    rows = db.scalars(list_stmt).all()

    if skip_count:
        has_more = len(rows) > page_size
        rows = rows[:page_size]
    else:
        has_more = page * page_size < int(total or 0)

    return _orders_to_out_batch(db, rows), total, has_more


def list_mall_template_card_orders_for_order_day(
    db: Session,
    *,
    store_id: int,
    order_day: date,
    q: str | None,
    pay_status: str | None,
    page: int,
    page_size: int,
) -> tuple[list[CardOrderOut], int]:
    """当日（上海自然日）创建的、绑定会员卡模版的开卡工单（小程序商城卡包等）。"""
    start_bj, end_bj = shanghai_naive_range_for_calendar_day(order_day)
    join_on = Member.id == MemberCardOrder.member_id
    filters = [
        MemberCardOrder.store_id == int(store_id),
        MemberCardOrder.membership_template_id.isnot(None),
        MemberCardOrder.created_at >= start_bj,
        MemberCardOrder.created_at < end_bj,
    ]
    if q and q.strip():
        esc = escape_like_fragment(q.strip())
        filters.append(
            or_(
                Member.phone.like(f"{esc}%", escape="\\"),
                Member.name.like(f"%{esc}%", escape="\\"),
                Member.wechat_name.like(f"%{esc}%", escape="\\"),
            )
        )
    ps = (pay_status or "").strip()
    if ps in (
        CardOrderPayStatus.UNPAID.value,
        CardOrderPayStatus.PAID.value,
        CardOrderPayStatus.REFUNDED.value,
        CardOrderPayStatus.CANCELLED.value,
    ):
        filters.append(MemberCardOrder.pay_status == ps)

    page = max(1, page)
    page_size = min(max(1, page_size), 100)

    count_stmt = select(func.count()).select_from(MemberCardOrder).join(Member, join_on)
    for f in filters:
        count_stmt = count_stmt.where(f)
    total = int(db.scalar(count_stmt) or 0)

    list_stmt = (
        select(MemberCardOrder)
        .join(Member, join_on)
        .order_by(MemberCardOrder.created_at.desc(), MemberCardOrder.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    for f in filters:
        list_stmt = list_stmt.where(f)
    rows = db.scalars(list_stmt).all()
    return [_order_to_out(db, r) for r in rows], total


def create_card_order(
    db: Session, body: CardOrderCreateIn, *, operator: str, tenant_id: int, store_id: int
) -> CardOrderOut:
    phone = body.phone.strip()
    m = db.execute(
        select(Member).where(
            Member.phone == phone,
            Member.store_id == int(store_id),
            Member.deleted_at.is_(None),
        )
    ).scalar_one_or_none()
    if not m:
        if body.open_mode == CardOpenMode.RENEW:
            raise HTTPException(status_code=404, detail="会员不存在")
        nm = (body.name or "").strip()
        if not nm:
            raise HTTPException(status_code=400, detail="新会员开卡须填写会员姓名")
        wx_raw = (body.wechat_name or "").strip()
        m = Member(
            phone=phone[:20],
            name=nm[:100],
            tenant_id=int(tenant_id),
            store_id=int(store_id),
            wechat_name=wx_raw[:100] if wx_raw else None,
            remarks=None,
            avatar_url=None,
            balance=0,
            daily_meal_units=1,
            meal_quota_total=0,
            plan_type=None,
            is_active=False,
            is_leaved_tomorrow=False,
            leave_range_start=None,
            leave_range_end=None,
            wx_mini_openid=None,
        )
        db.add(m)
        db.flush()
    elif body.open_mode == CardOpenMode.NEW_MEMBER:
        # 仅「新会员开卡」写入姓名/微信；老会员续卡只认手机号，不覆盖档案
        if body.name is not None:
            nm = body.name.strip()
            if nm:
                m.name = nm[:100]
        if body.wechat_name is not None:
            wx = body.wechat_name.strip()
            m.wechat_name = wx[:100] if wx else None
    if body.delivery_start_date is not None:
        # 后台开卡工单允许选当日；小程序仍走 min_member_delivery_start_shanghai（最早明日）
        if body.delivery_start_date < min_admin_card_order_delivery_start_shanghai():
            raise HTTPException(
                status_code=400,
                detail="起送日期须不早于当日（上海业务日）",
            )
    if body.delivery_address is not None:
        da = body.delivery_address
        cphone = (da.contact_phone or "").strip() or phone
        upsert_default_address_from_admin_map_pick(
            db,
            member_id=m.id,
            contact_name=(m.name or "").strip() or phone[:20],
            contact_phone=cphone[:20],
            map_location_text=da.map_location_text,
            door_detail=da.door_detail,
            lng=float(da.lng),
            lat=float(da.lat),
            tenant_id=int(tenant_id),
        )
    tpl: MembershipCardTemplate | None = None
    card_kind_value: str
    if body.membership_template_id is not None:
        tpl = get_membership_template_row(
            db,
            template_id=int(body.membership_template_id),
            tenant_id=int(tenant_id),
            store_id=int(store_id),
        )
        if not bool(tpl.is_active):
            raise HTTPException(status_code=400, detail="该卡包模版未开启或已下架")
        card_kind_value = enum_card_kind_for_template(tpl)
    else:
        card_kind_value = body.card_kind.value  # type: ignore[union-attr]
    order = MemberCardOrder(
        member_id=m.id,
        tenant_id=int(tenant_id),
        store_id=int(store_id),
        membership_template_id=int(tpl.id) if tpl is not None else None,
        card_kind=card_kind_value,
        pay_channel=body.pay_channel.value,
        pay_status=body.pay_status.value,
        amount_yuan=body.amount_yuan,
        remark=body.remark,
        delivery_start_date=body.delivery_start_date,
        activation_mode=compute_activation_mode_for_create(
            open_mode=body.open_mode,
            defer_delivery_activation=bool(body.defer_delivery_activation),
            delivery_start_date=body.delivery_start_date,
        ),
        created_by=operator,
    )
    db.add(order)
    db.flush()
    # 已缴即入账：与是否传 sync_member 无关（避免勾选遗漏导致剩余次数仍为 0）
    if body.pay_status == CardOrderPayStatus.PAID:
        _sync_order_to_member(
            db,
            order,
            operator=operator,
            open_mode=body.open_mode,
            defer_delivery_activation=bool(body.defer_delivery_activation),
        )
    db.commit()
    db.refresh(order)
    return _order_to_out(db, order)


def delete_card_order(db: Session, order_id: int, *, store_id: int | None = None) -> None:
    """删除无效/重复工单：仅未缴且未同步入账可删。"""
    order = db.get(MemberCardOrder, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="工单不存在")
    if store_id is not None and int(order.store_id) != int(store_id):
        raise HTTPException(status_code=404, detail="工单不存在")
    if order.applied_to_member:
        raise HTTPException(status_code=400, detail="已同步入账的工单不可删除")
    if order.pay_status == CardOrderPayStatus.PAID.value:
        raise HTTPException(
            status_code=400,
            detail="已缴工单不可删除；若实为误标请先在「更新」中改回未缴后再删",
        )
    if order.pay_status == CardOrderPayStatus.REFUNDED.value:
        raise HTTPException(status_code=400, detail="已微信退款的工单不可删除")
    release_member_coupon_for_order(
        db, order_biz=CouponLockedOrderBiz.MEMBER_CARD, order_id=int(order_id)
    )
    db.delete(order)
    db.commit()


def update_card_order(
    db: Session, order_id: int, body: CardOrderPatchIn, *, operator: str, store_id: int | None = None
) -> CardOrderOut:
    order = db.get(MemberCardOrder, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="工单不存在")
    if store_id is not None and int(order.store_id) != int(store_id):
        raise HTTPException(status_code=404, detail="工单不存在")

    if order.pay_status == CardOrderPayStatus.REFUNDED.value:
        raise HTTPException(status_code=400, detail="已微信退款的工单不可编辑")

    want_sync = "sync_member" in body.model_fields_set and body.sync_member is True
    patch = body.model_dump(exclude_unset=True)
    patch.pop("sync_member", None)
    updating_card_kind = "card_kind" in body.model_fields_set
    updating_template = "membership_template_id" in body.model_fields_set
    if updating_card_kind or updating_template:
        if order.applied_to_member:
            raise HTTPException(status_code=400, detail="已入账的工单不可修改卡类型")
        patch.pop("card_kind", None)
        patch.pop("membership_template_id", None)
        if updating_template:
            if body.membership_template_id is None:
                raise HTTPException(status_code=400, detail="请选择卡包模版")
            tpl = get_membership_template_row(
                db,
                template_id=int(body.membership_template_id),
                tenant_id=int(order.tenant_id),
                store_id=int(order.store_id),
            )
            if not bool(tpl.is_active):
                raise HTTPException(status_code=400, detail="该卡包模版未开启或已下架")
            order.membership_template_id = int(tpl.id)
            order.card_kind = enum_card_kind_for_template(tpl)
            order.meal_periods_snapshot = None
        elif body.card_kind is None:
            raise HTTPException(status_code=400, detail="卡类型无效")
        else:
            order.card_kind = body.card_kind.value
            order.membership_template_id = None
            order.meal_periods_snapshot = None

    if not patch and not updating_card_kind and not updating_template and not want_sync:
        raise HTTPException(status_code=400, detail="请至少提交一项修改")

    if "pay_status" in patch and body.pay_status is not None:
        if order.applied_to_member and body.pay_status == CardOrderPayStatus.UNPAID:
            raise HTTPException(status_code=400, detail="已入账的工单不可改回未缴")
        was_paid = order.pay_status == CardOrderPayStatus.PAID.value
        order.pay_status = body.pay_status.value
        if not was_paid and body.pay_status == CardOrderPayStatus.PAID:
            mark_member_coupon_used_for_order(
                db, order_biz=CouponLockedOrderBiz.MEMBER_CARD, order_id=int(order.id)
            )

    if "pay_channel" in patch and body.pay_channel is not None:
        order.pay_channel = body.pay_channel.value

    if "amount_yuan" in patch:
        order.amount_yuan = body.amount_yuan

    if "remark" in patch:
        order.remark = body.remark

    if "delivery_start_date" in patch:
        ds = body.delivery_start_date
        if order.applied_to_member and ds is None and order.delivery_start_date is not None:
            raise HTTPException(status_code=400, detail="已入账工单不可清空起送日")
        # 后台更新工单允许选当日；小程序仍走 min_member_delivery_start_shanghai（最早明日）
        if ds is not None and ds < min_admin_card_order_delivery_start_shanghai():
            raise HTTPException(
                status_code=400,
                detail="起送日期须不早于当日（上海业务日）",
            )
        order.delivery_start_date = ds
        if order.applied_to_member:
            mem = db.get(Member, order.member_id)
            if mem:
                mem.delivery_start_date = order.delivery_start_date

    db.flush()
    if want_sync:
        if order.pay_status != CardOrderPayStatus.PAID.value:
            raise HTTPException(status_code=400, detail="仅「已缴」工单可同步入账")
        if order.applied_to_member:
            raise HTTPException(status_code=400, detail="该工单已入账，请勿重复同步")
        _sync_order_to_member(db, order, operator=operator)
        if (order.created_by or "").strip() == MINIPROGRAM_SELF_SERVICE_ORDER_CREATOR:
            from app.services.admin.admin_system_notification_service import (
                acknowledge_miniprogram_card_order_pending_notifications,
            )

            acknowledge_miniprogram_card_order_pending_notifications(
                db,
                store_id=int(order.store_id),
                order_id=int(order.id),
                admin_username=operator,
            )

    db.commit()
    db.refresh(order)
    return _order_to_out(db, order)


def create_paid_card_order_for_douyin_redeem(
    db: Session,
    *,
    member: Member,
    card_kind: str | None = None,
    membership_template_id: int | None = None,
    delivery_start_date: date | None = None,
    amount_yuan: Decimal | None = None,
    remark: str | None = None,
    operator: str = "douyin_redeem",
) -> MemberCardOrder:
    """抖音验券成功后创建已缴开卡工单并同步入账。"""
    tpl: MembershipCardTemplate | None = None
    ck = (card_kind or "").strip()
    if membership_template_id is not None:
        tpl = db.get(MembershipCardTemplate, int(membership_template_id))
        if not tpl or int(tpl.store_id) != int(member.store_id):
            raise HTTPException(status_code=404, detail="会员卡模版不存在")
        if not bool(tpl.is_active):
            raise HTTPException(status_code=400, detail="该卡包已下架")
        ck = enum_card_kind_for_template(tpl)
        if amount_yuan is None:
            price = tpl.sale_price_yuan if tpl.sale_price_yuan is not None else tpl.list_price_yuan
            amount_yuan = Decimal(price).quantize(Decimal("0.01")) if price is not None else Decimal("0.00")
    else:
        if ck not in (CardOrderKind.WEEK.value, CardOrderKind.MONTH.value):
            raise HTTPException(status_code=400, detail="无效开卡类型")
        if amount_yuan is None:
            amount_yuan = _amount_yuan_for_card_kind_str(db, ck, store_id=int(member.store_id))

    if delivery_start_date is not None and delivery_start_date < min_member_delivery_start_shanghai():
        raise HTTPException(status_code=400, detail="起送日期须不早于明日（上海业务日）")

    # 老会员续卡：与小程序购卡一致，保持配送安排，不得误标暂停配送
    is_renewal = _member_has_prior_applied_card_order(db, int(member.id))
    if delivery_start_date is not None:
        activation_mode = CardOrderActivationMode.EXPLICIT_DATE.value
    elif is_renewal:
        activation_mode = CardOrderActivationMode.KEEP_SCHEDULE.value
    else:
        activation_mode = CardOrderActivationMode.DEFER_NOT_OPEN.value

    order = MemberCardOrder(
        member_id=int(member.id),
        tenant_id=int(member.tenant_id),
        store_id=int(member.store_id),
        membership_template_id=int(tpl.id) if tpl is not None else None,
        card_kind=ck,
        pay_channel=CardPayChannel.DOUYIN.value,
        pay_status=CardOrderPayStatus.PAID.value,
        amount_yuan=amount_yuan,
        remark=(remark or "抖音验券兑换")[:500],
        delivery_start_date=delivery_start_date,
        activation_mode=activation_mode,
        applied_to_member=False,
        out_trade_no=None,
        wx_transaction_id=None,
        created_by=operator,
    )
    db.add(order)
    db.flush()
    _apply_paid_card_order_to_member_balance(
        db,
        order,
        operator=operator,
        open_mode=CardOpenMode.RENEW if is_renewal else None,
    )
    return order
