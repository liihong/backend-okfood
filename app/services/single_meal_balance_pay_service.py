"""单次点餐：会员卡次数支付（周卡/月卡）与取消退次。"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.timeutil import today_shanghai
from app.models.balance_log import BalanceLog
from app.models.delivery_log import DeliveryLog
from app.models.enums import BalanceReason, DeliveryStatus
from app.models.member import Member
from app.models.member_address import MemberAddress
from app.models.single_meal_order import SingleMealOrder
from app.services.courier_service import (
    eligible_members_for_delivery,
    eligible_members_for_store_pickup,
)
from app.services.member_service import effective_daily_meal_units
from app.services.single_meal_order_service import (
    _notify_single_meal_order_paid_cs_review,
    primary_courier_for_region_id,
)

MEMBER_CARD_PAY_CHANNEL = "会员卡"
_BALANCE_PLAN_TYPES = frozenset({"周卡", "月卡"})


@dataclass(frozen=True)
class SingleMealBalancePayEligibility:
    """会员卡次数支付资格（供小程序确认页展示）。"""

    can_use: bool
    message: str
    balance: int
    meal_quota_total: int
    plan_type: str | None
    reserve_for_today: int
    required_balance: int


def member_subscription_delivery_pending_today(db: Session, member: Member) -> tuple[bool, int]:
    """
    当日是否仍有未完成的套餐订阅履约（在大表名单内且 delivery_log 未 delivered）。

    返回 (pending, reserve_units)；pending 为 false 时 reserve_units 为 0。
    暂停配送（delivery_deferred / 未激活）不在大表内，视为无需预留。
    """
    if bool(member.delivery_deferred) or not bool(member.is_active):
        return False, 0
    today = today_shanghai()
    mid = int(member.id)
    sid = int(member.store_id)
    if bool(member.store_pickup):
        members, _ = eligible_members_for_store_pickup(db, delivery_date=today, store_id=sid)
    else:
        members, _ = eligible_members_for_delivery(db, delivery_date=today, store_id=sid)
    if not any(int(m.id) == mid for m in members):
        return False, 0
    log = db.scalar(
        select(DeliveryLog).where(
            DeliveryLog.member_id == mid,
            DeliveryLog.delivery_date == today,
        )
    )
    if log and (log.status or "").strip() == DeliveryStatus.DELIVERED.value:
        return False, 0
    return True, effective_daily_meal_units(member)


def evaluate_single_meal_balance_pay(
    db: Session,
    member: Member,
    *,
    quantity: int,
) -> SingleMealBalancePayEligibility:
    """评估是否可用会员卡次数支付（不修改数据）。"""
    qty = max(1, int(quantity))
    bal = max(0, int(member.balance or 0))
    quota = max(0, int(member.meal_quota_total or 0))
    plan = (str(member.plan_type).strip() if member.plan_type is not None else "") or None
    pending, reserve = member_subscription_delivery_pending_today(db, member)
    required = qty + (reserve if pending else 0)

    if plan not in _BALANCE_PLAN_TYPES:
        return SingleMealBalancePayEligibility(
            can_use=False,
            message="仅周卡/月卡可使用次数支付",
            balance=bal,
            meal_quota_total=quota,
            plan_type=plan,
            reserve_for_today=reserve if pending else 0,
            required_balance=required,
        )
    if bal < qty:
        return SingleMealBalancePayEligibility(
            can_use=False,
            message="剩余次数不足，请使用微信支付",
            balance=bal,
            meal_quota_total=quota,
            plan_type=plan,
            reserve_for_today=reserve if pending else 0,
            required_balance=required,
        )
    if bal < required:
        return SingleMealBalancePayEligibility(
            can_use=False,
            message="今日套餐配送需预留次数，请切换为微信支付",
            balance=bal,
            meal_quota_total=quota,
            plan_type=plan,
            reserve_for_today=reserve if pending else 0,
            required_balance=required,
        )
    return SingleMealBalancePayEligibility(
        can_use=True,
        message="",
        balance=bal,
        meal_quota_total=quota,
        plan_type=plan,
        reserve_for_today=reserve if pending else 0,
        required_balance=required,
    )


def _assert_balance_pay_allowed_for_order(db: Session, member: Member, order: SingleMealOrder) -> int:
    """校验订单可用次数支付；返回扣减份数。"""
    if int(order.member_coupon_id or 0) > 0:
        raise HTTPException(status_code=400, detail="次数支付不可使用优惠券，请重新下单或改用微信支付")
    qty = max(1, int(order.quantity or 1))
    ev = evaluate_single_meal_balance_pay(db, member, quantity=qty)
    if not ev.can_use:
        raise HTTPException(status_code=400, detail=ev.message or "无法使用次数支付，请使用微信支付")
    return qty


def _apply_single_meal_paid_fulfillment(db: Session, order: SingleMealOrder) -> None:
    """支付成功后写入履约状态（与微信入账一致，不含支付渠道字段）。"""
    if str(order.fulfillment_status or "").strip().lower() == "cancelled":
        order.fulfillment_status = "pending"
    if bool(getattr(order, "store_pickup", False)):
        order.courier_id = None
    else:
        pay_addr = db.get(MemberAddress, order.member_address_id)
        order.courier_id = primary_courier_for_region_id(
            db, int(pay_addr.delivery_region_id) if pay_addr and pay_addr.delivery_region_id else None
        )
    _notify_single_meal_order_paid_cs_review(db, order)


def _maybe_reactivate_member_after_balance_restore(member: Member) -> None:
    """退次后若仍有剩余次数且非暂停配送，恢复计划激活（与扣次后 balance<=0 置 inactive 对称）。"""
    if int(member.balance or 0) <= 0:
        return
    if bool(member.delivery_deferred):
        return
    if (str(member.plan_type or "").strip()) not in _BALANCE_PLAN_TYPES:
        return
    if member.delivery_start_date is None:
        return
    member.is_active = True


def pay_single_meal_order_with_member_balance(
    db: Session,
    *,
    member_id: int,
    order_id: int,
) -> SingleMealOrder:
    """会员卡次数支付：扣减 balance、入账订单（幂等）。"""
    from app.services.single_meal_order_service import expire_stale_unpaid_single_meal_orders

    expire_stale_unpaid_single_meal_orders(db, member_id=member_id)
    order = db.scalar(
        select(SingleMealOrder)
        .where(SingleMealOrder.id == int(order_id), SingleMealOrder.member_id == int(member_id))
        .with_for_update()
    )
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    if (order.pay_status or "").strip() == "已支付":
        db.commit()
        db.refresh(order)
        return order
    if (order.pay_status or "").strip() == "已退款":
        raise HTTPException(status_code=400, detail="订单已退款")
    if str(order.fulfillment_status or "").strip().lower() == "cancelled":
        raise HTTPException(status_code=400, detail="订单已关闭，请重新下单")

    member = db.execute(select(Member).where(Member.id == int(member_id)).with_for_update()).scalar_one_or_none()
    if not member or member.deleted_at is not None:
        raise HTTPException(status_code=404, detail="用户不存在")

    qty = _assert_balance_pay_allowed_for_order(db, member, order)
    balance_before = int(member.balance or 0)
    member.balance = balance_before - qty
    if int(member.balance) <= 0:
        member.is_active = False
    db.add(
        BalanceLog(
            member_id=int(member.id),
            change=-qty,
            reason=BalanceReason.SINGLE_MEAL.value,
            operator="member:miniprogram",
            detail=f"single_meal_orders.id={int(order.id)}",
        )
    )

    order.pay_status = "已支付"
    order.pay_channel = MEMBER_CARD_PAY_CHANNEL
    order.amount_yuan = Decimal("0.00")
    _apply_single_meal_paid_fulfillment(db, order)
    db.add(order)
    db.commit()
    db.refresh(order)

    try:
        from app.services.member_renew_subscribe_service import try_send_renew_remind_after_balance_change

        try_send_renew_remind_after_balance_change(db, member, balance_before=balance_before)
    except Exception:
        pass

    return order


def restore_member_balance_for_cancelled_single_meal(
    db: Session,
    *,
    order: SingleMealOrder,
    operator: str,
) -> bool:
    """
    已用会员卡支付的订单取消时退次；幂等（仅 pay_channel=会员卡 且未写过退次流水时执行）。

    返回是否本次实际退次。
    """
    if (order.pay_channel or "").strip() != MEMBER_CARD_PAY_CHANNEL:
        return False
    if (order.pay_status or "").strip() != "已支付":
        return False
    oid = int(order.id)
    detail_key = f"single_meal_revoke.id={oid}"
    existing = db.scalar(
        select(BalanceLog.id).where(
            BalanceLog.member_id == int(order.member_id),
            BalanceLog.detail == detail_key,
        )
    )
    if existing is not None:
        return False

    qty = max(1, int(order.quantity or 1))
    member = db.execute(
        select(Member).where(Member.id == int(order.member_id)).with_for_update()
    ).scalar_one_or_none()
    if not member or member.deleted_at is not None:
        raise HTTPException(status_code=404, detail="用户不存在")

    member.balance = int(member.balance or 0) + qty
    _maybe_reactivate_member_after_balance_restore(member)
    db.add(
        BalanceLog(
            member_id=int(member.id),
            change=qty,
            reason=BalanceReason.REFUND.value,
            operator=(operator or "system")[:50],
            detail=detail_key,
        )
    )
    order.pay_status = "已退款"
    db.add(member)
    db.add(order)
    return True


def is_member_card_paid_single_meal(order: SingleMealOrder) -> bool:
    return (order.pay_channel or "").strip() == MEMBER_CARD_PAY_CHANNEL
