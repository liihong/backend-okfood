"""会员退卡退款：按最近一次仍有效开卡的实付计算应退。

已消费只统计这次开卡入账之后的配送扣次。
一顿没吃则退该工单实付全额；吃过则按已吃份数占本卡次数的比例从实付扣除。
不按菜单单价乘剩余次数，避免把 30 元菜价当成会员实际付的钱。
"""

from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import NamedTuple

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.timeutil import beijing_now_naive
from app.models.balance_log import BalanceLog
from app.models.delivery_log import DeliveryLog
from app.models.enums import BalanceReason, CardOrderPayStatus, DeliveryStatus, MealPeriod, PlanType
from app.models.member import Member
from app.models.member_card_order import MemberCardOrder
from app.models.member_membership_refund import MemberMembershipRefund
from app.schemas.admin import (
    MemberMembershipRefundConfirmIn,
    MemberMembershipRefundConsumptionRowOut,
    MemberMembershipRefundPreviewOut,
    RechargeIn,
)
from app.services.admin.admin_service import apply_member_recharge_delta
from app.services.member.member_operation_log_service import OP_MEMBERSHIP_REFUND, record_member_operation
from app.services.admin.menu_day_stock_service import resolve_dishes_for_dates_batch

# 与入账流水 detail 一致，例如「开卡工单#1775」
_CARD_ORDER_ID_RE = re.compile(r"开卡工单#(\d+)")

_TWO_PLACES = Decimal("0.01")


def _is_archive_member(member: Member) -> bool:
    pt = (member.plan_type or "").strip()
    return pt in (PlanType.WEEK.value, PlanType.MONTH.value)


class _LunchCardCredit(NamedTuple):
    """最近一次仍有效的午餐开卡。"""

    credited_at: datetime
    order_id: int
    meals_granted: int
    paid_yuan: Decimal


def card_paid_yuan_for_refund(amount: Decimal) -> Decimal:
    """开卡实收按元取整，与开卡工单列表「实收」一致。

    列表用四舍五入到整数元展示，例如抖音入账 169.80 在工单上看到的是 170。
    退卡用这个数，避免档案应退和工单实收对不上。
    """
    paid = Decimal(str(amount)).quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)
    return paid.quantize(Decimal("1"), rounding=ROUND_HALF_UP)


def refund_yuan_from_latest_card(
    *,
    card_paid_yuan: Decimal,
    meals_granted: int,
    meals_consumed: int,
    meals_remaining: int,
) -> Decimal:
    """按最近一张卡的实付算应退。

    本卡一份都没被用掉：退实付全额，不做除法，避免尾差。
    用掉一部分：已用份数 = 入账次数 − min(剩余, 入账 − 已配送)，按比例从实付扣除，尾差留在应退。
    """
    paid = Decimal(str(card_paid_yuan)).quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)
    granted = int(meals_granted)
    if paid <= 0 or granted <= 0:
        return Decimal("0.00")
    eaten = max(0, int(meals_consumed))
    remaining = max(0, int(meals_remaining))
    unused = min(remaining, max(0, granted - eaten))
    used = granted - unused
    if used <= 0:
        return paid
    if unused <= 0:
        return Decimal("0.00")
    used_charge = (paid * Decimal(used) / Decimal(granted)).quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)
    refund = (paid - used_charge).quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)
    if refund < 0:
        return Decimal("0.00")
    if refund > paid:
        return paid
    return refund


def select_deliveries_after_card_credit(
    credit_at: datetime | None,
    paired: list[tuple[datetime | None, date, int]],
) -> tuple[int, dict[date, int]]:
    """本卡周期内的配送扣次。

    paired 已按时间对齐：(扣次时刻, 配送业务日, 份数)。
    没有仍有效的开卡入账时不追溯历史，返回 0。
    扣次时刻不晚于开卡入账的，属于上一档卡，不计入。
    """
    if credit_at is None:
        return 0, {}
    units_by_date: dict[date, int] = {}
    total = 0
    for deducted_at, delivery_date, units in paired:
        if deducted_at is None or deducted_at <= credit_at:
            continue
        n = max(1, int(units))
        units_by_date[delivery_date] = int(units_by_date.get(delivery_date, 0)) + n
        total += n
    return total, units_by_date


def _is_lunch_pool(raw: object) -> bool:
    """退卡只结算午餐次数池。空餐段按午餐，与历史流水默认一致。"""
    p = str(raw or MealPeriod.LUNCH.value).strip().lower()
    return p != MealPeriod.DINNER.value


def _card_order_id_from_detail(detail: str | None) -> int | None:
    if not detail:
        return None
    matched = _CARD_ORDER_ID_RE.search(detail)
    if not matched:
        return None
    try:
        return int(matched.group(1))
    except (TypeError, ValueError):
        return None


def _latest_effective_lunch_card(db: Session, member_id: int) -> _LunchCardCredit | None:
    """最近一次仍有效的午餐开卡：实付、入账次数、入账时刻。

    工单须为已缴且已入账。已撤销或已退款的工单不能当锚点。
    实收取该工单 amount_yuan，再四舍五入到元（与开卡工单列表「实收」一致）。
    同一工单若有多笔午餐入账，次数相加，窗口从最早一笔入账起算。
    """
    mid = int(member_id)
    rows = list(
        db.scalars(
            select(BalanceLog)
            .where(
                BalanceLog.member_id == mid,
                BalanceLog.reason == BalanceReason.RECHARGE.value,
                BalanceLog.change > 0,
                BalanceLog.detail.like("%开卡工单#%"),
            )
            .order_by(BalanceLog.created_at.desc(), BalanceLog.id.desc())
        ).all()
    )
    target_order: MemberCardOrder | None = None
    target_order_id: int | None = None
    for bl in rows:
        if not _is_lunch_pool(bl.meal_period):
            continue
        order_id = _card_order_id_from_detail(bl.detail)
        if order_id is None:
            continue
        order = db.get(MemberCardOrder, order_id)
        if order is None or int(order.member_id) != mid:
            continue
        if not bool(order.applied_to_member):
            continue
        if (order.pay_status or "").strip() != CardOrderPayStatus.PAID.value:
            continue
        target_order = order
        target_order_id = order_id
        break
    if target_order is None or target_order_id is None:
        return None
    granted = 0
    credited_at: datetime | None = None
    for bl in rows:
        if not _is_lunch_pool(bl.meal_period):
            continue
        if _card_order_id_from_detail(bl.detail) != target_order_id:
            continue
        granted += max(0, int(bl.change))
        if bl.created_at is not None and (credited_at is None or bl.created_at < credited_at):
            credited_at = bl.created_at
    if credited_at is None or granted <= 0:
        return None
    paid_raw = target_order.amount_yuan
    paid = Decimal("0.00") if paid_raw is None else card_paid_yuan_for_refund(Decimal(str(paid_raw)))
    return _LunchCardCredit(
        credited_at=credited_at,
        order_id=int(target_order_id),
        meals_granted=granted,
        paid_yuan=paid,
    )


def _paired_lunch_delivery_deductions(
    db: Session, member_id: int
) -> list[tuple[datetime | None, date, int]]:
    """午餐配送扣次与配送日按发生顺序对齐。先对齐再按开卡时刻截断，避免张冠李戴。"""
    mid = int(member_id)
    deductions = [
        bl
        for bl in db.scalars(
            select(BalanceLog)
            .where(
                BalanceLog.member_id == mid,
                BalanceLog.reason == BalanceReason.DELIVERY.value,
                BalanceLog.change < 0,
            )
            .order_by(BalanceLog.created_at.asc(), BalanceLog.id.asc())
        ).all()
        if _is_lunch_pool(bl.meal_period)
    ]
    deliveries = [
        dl
        for dl in db.scalars(
            select(DeliveryLog)
            .where(
                DeliveryLog.member_id == mid,
                DeliveryLog.status == DeliveryStatus.DELIVERED.value,
            )
            .order_by(DeliveryLog.updated_at.asc(), DeliveryLog.id.asc())
        ).all()
        if _is_lunch_pool(dl.meal_period)
    ]
    paired: list[tuple[datetime | None, date, int]] = []
    for index, bl in enumerate(deductions):
        units = max(1, abs(int(bl.change)))
        delivery = deliveries[index] if index < len(deliveries) else None
        if delivery is not None:
            business_date = delivery.delivery_date
        elif bl.created_at is not None:
            business_date = bl.created_at.date()
        else:
            continue
        paired.append((bl.created_at, business_date, units))
    return paired


def _consumption_charge_for_units(
    db: Session,
    *,
    store_id: int,
    units_by_date: dict[date, int],
) -> tuple[Decimal, list[MemberMembershipRefundConsumptionRowOut]]:
    if not units_by_date:
        return Decimal("0.00"), []

    # 已消费明细按午餐菜单单价列出（仅供核对，不参与应退计算）
    dishes_by_date = resolve_dishes_for_dates_batch(
        db, units_by_date.keys(), store_id=int(store_id), meal_period=MealPeriod.LUNCH.value
    )
    items: list[MemberMembershipRefundConsumptionRowOut] = []
    total = Decimal("0")

    for delivery_date in sorted(units_by_date.keys()):
        units = max(1, int(units_by_date[delivery_date]))
        dish = dishes_by_date.get(delivery_date)
        raw_price = None if dish is None else dish.single_order_price_yuan
        # 已消费明细仅供核对；缺单价的日期跳过，不阻断按剩余次数退款
        if raw_price is None:
            continue
        unit_price = Decimal(str(raw_price)).quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)
        line_total = (unit_price * Decimal(units)).quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)
        total += line_total
        items.append(
            MemberMembershipRefundConsumptionRowOut(
                delivery_date=delivery_date,
                meal_units=units,
                dish_name=(dish.name or "").strip() or None if dish else None,
                unit_price_yuan=unit_price,
                line_total_yuan=line_total,
            )
        )

    return total.quantize(_TWO_PLACES, rounding=ROUND_HALF_UP), items


def _ensure_refundable_member(member: Member) -> None:
    if member.membership_refunded_at is not None:
        raise HTTPException(status_code=400, detail="该会员已办理退卡退款，不可重复操作")


def _compute_refund_preview(db: Session, member: Member) -> MemberMembershipRefundPreviewOut:
    _ensure_refundable_member(member)
    meals_remaining = int(member.balance or 0)
    if meals_remaining <= 0:
        raise HTTPException(status_code=400, detail="该会员剩余次数为 0，无可退次数")

    card = _latest_effective_lunch_card(db, int(member.id))
    if card is None:
        raise HTTPException(status_code=400, detail="没有仍有效的开卡工单，无法按实付计算退款")
    if card.paid_yuan <= 0:
        raise HTTPException(
            status_code=400,
            detail=f"最近一次开卡工单#{card.order_id}实付为 0，无法计算退款",
        )

    meals_consumed, units_by_date = select_deliveries_after_card_credit(
        card.credited_at,
        _paired_lunch_delivery_deductions(db, int(member.id)),
    )
    meal_quota_total = int(member.meal_quota_total or 0)
    consumed_value, consumption_items = _consumption_charge_for_units(
        db,
        store_id=int(member.store_id),
        units_by_date=units_by_date,
    )
    refund_yuan = refund_yuan_from_latest_card(
        card_paid_yuan=card.paid_yuan,
        meals_granted=card.meals_granted,
        meals_consumed=meals_consumed,
        meals_remaining=meals_remaining,
    )
    # 单次实付只用于展示，应退全额时不拿它再乘一次
    unit_price = (card.paid_yuan / Decimal(card.meals_granted)).quantize(
        _TWO_PLACES, rounding=ROUND_HALF_UP
    )

    return MemberMembershipRefundPreviewOut(
        member_id=int(member.id),
        member_name=(member.name or "").strip() or None,
        member_phone=(member.phone or "").strip() or None,
        plan_type=(member.plan_type or "").strip() or None,
        meals_consumed=meals_consumed,
        meals_remaining=meals_remaining,
        meal_quota_total=meal_quota_total,
        latest_card_credited_at=card.credited_at,
        card_paid_yuan=card.paid_yuan,
        meals_granted=card.meals_granted,
        paid_total_yuan=card.paid_yuan,
        consumed_value_yuan=consumed_value,
        unit_price_yuan=unit_price,
        consumption_items=consumption_items,
        refund_amount_yuan=refund_yuan,
    )


def member_membership_refund_preview(db: Session, *, member_id: int, store_id: int) -> MemberMembershipRefundPreviewOut:
    m = db.get(Member, int(member_id))
    if not m or m.deleted_at is not None:
        raise HTTPException(status_code=404, detail="会员不存在")
    if int(m.store_id) != int(store_id):
        raise HTTPException(status_code=404, detail="会员不存在")
    if not _is_archive_member(m):
        raise HTTPException(status_code=400, detail="仅周卡/月卡会员档案支持退卡退款")
    return _compute_refund_preview(db, m)


def member_membership_refund_confirm(
    db: Session,
    *,
    member_id: int,
    store_id: int,
    body: MemberMembershipRefundConfirmIn,
    operator: str,
    ip_address: str | None = None,
) -> MemberMembershipRefundPreviewOut:
    m = db.get(Member, int(member_id))
    if not m or m.deleted_at is not None:
        raise HTTPException(status_code=404, detail="会员不存在")
    if int(m.store_id) != int(store_id):
        raise HTTPException(status_code=404, detail="会员不存在")
    if not _is_archive_member(m):
        raise HTTPException(status_code=400, detail="仅周卡/月卡会员档案支持退卡退款")

    preview = _compute_refund_preview(db, m)
    confirm_amt = Decimal(str(body.confirm_refund_yuan)).quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)
    if confirm_amt != preview.refund_amount_yuan:
        raise HTTPException(
            status_code=400,
            detail=f"确认金额与当前计算不一致（应为 {preview.refund_amount_yuan} 元），请刷新后重试",
        )

    balance_before = int(m.balance)
    if balance_before <= 0:
        raise HTTPException(status_code=400, detail="该会员剩余次数为 0，无法退卡")

    remark = (body.remark or "").strip() or None
    log_bits = [
        f"退卡按最近开卡实付{preview.card_paid_yuan}元",
        f"入账{preview.meals_granted}次",
        f"开卡后已消费{preview.meals_consumed}次",
        f"应退{preview.refund_amount_yuan}元",
    ]
    if remark:
        log_bits.append(f"备注{remark[:180]}")
    log_detail = "；".join(log_bits)

    before_snap = {
        "balance": balance_before,
        "meal_quota_total": int(m.meal_quota_total or 0),
        "is_active": bool(m.is_active),
        "delivery_deferred": bool(m.delivery_deferred),
    }

    apply_member_recharge_delta(
        db,
        RechargeIn(phone=m.phone, amount=-balance_before, plan_type=None),
        operator=operator,
        log_detail=log_detail,
        member_id=int(m.id),
    )
    # 清零展示用总次数；历史配额与已消费次数已写入 member_membership_refunds
    m.meal_quota_total = 0
    m.is_active = False
    m.delivery_deferred = True
    m.pause_effective_date = None
    m.membership_refunded_at = beijing_now_naive()

    row = MemberMembershipRefund(
        tenant_id=int(m.tenant_id),
        store_id=int(m.store_id),
        member_id=int(m.id),
        meals_consumed=int(preview.meals_consumed),
        meals_refunded=balance_before,
        meal_quota_total=int(preview.meal_quota_total),
        paid_total_yuan=preview.paid_total_yuan,
        consumed_value_yuan=preview.consumed_value_yuan,
        unit_price_yuan=preview.unit_price_yuan,
        refund_amount_yuan=preview.refund_amount_yuan,
        remark=remark,
        operator=operator[:64],
    )
    db.add(row)
    db.flush()

    after_snap = {
        "balance": int(m.balance),
        "meal_quota_total": int(m.meal_quota_total or 0),
        "is_active": bool(m.is_active),
        "delivery_deferred": bool(m.delivery_deferred),
        "refund_id": int(row.id),
        "refund_amount_yuan": str(preview.refund_amount_yuan),
        "unit_price_yuan": str(preview.unit_price_yuan),
    }
    record_member_operation(
        db,
        member_id=int(m.id),
        source="admin",
        operation_type=OP_MEMBERSHIP_REFUND,
        summary=(
            f"退卡退款：最近开卡实付{preview.card_paid_yuan}元，"
            f"开卡后已消费{preview.meals_consumed}次，应退{preview.refund_amount_yuan}元"
        ),
        before=before_snap,
        after=after_snap,
        ip_address=ip_address,
        operator=operator,
    )
    db.commit()
    return preview
