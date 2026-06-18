"""会员退卡退款：按各消费日菜单单价扣款后退还余款。"""

from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.timeutil import beijing_now_naive
from app.models.enums import CardOrderPayStatus, PlanType
from app.models.member import Member
from app.models.member_card_order import MemberCardOrder
from app.models.member_membership_refund import MemberMembershipRefund
from app.schemas.admin import (
    MemberMembershipRefundConfirmIn,
    MemberMembershipRefundConsumptionRowOut,
    MemberMembershipRefundPreviewOut,
    RechargeIn,
)
from app.services.admin_service import apply_member_recharge_delta
from app.services.member_delivery_deduction_service import (
    delivery_meal_units_by_date,
    total_member_delivery_meal_units_consumed,
)
from app.services.member_operation_log_service import OP_MEMBERSHIP_REFUND, record_member_operation
from app.models.enums import MealPeriod
from app.services.menu_day_stock_service import resolve_dishes_for_dates_batch

_TWO_PLACES = Decimal("0.01")


def _is_archive_member(member: Member) -> bool:
    pt = (member.plan_type or "").strip()
    return pt in (PlanType.WEEK.value, PlanType.MONTH.value)


def _paid_total_yuan_for_member(db: Session, member_id: int) -> Decimal:
    val = db.scalar(
        select(func.coalesce(func.sum(MemberCardOrder.amount_yuan), 0)).where(
            MemberCardOrder.member_id == int(member_id),
            MemberCardOrder.pay_status == CardOrderPayStatus.PAID.value,
            MemberCardOrder.applied_to_member.is_(True),
        )
    )
    return Decimal(str(val or 0)).quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)


def _consumption_charge_for_member(
    db: Session,
    *,
    member_id: int,
    store_id: int,
) -> tuple[Decimal, list[MemberMembershipRefundConsumptionRowOut]]:
    units_by_date = delivery_meal_units_by_date(db, int(member_id))
    if not units_by_date:
        return Decimal("0.00"), []

    # 退卡扣款按午餐菜单单价（经典周/月卡默认午餐履约口径）
    dishes_by_date = resolve_dishes_for_dates_batch(
        db, units_by_date.keys(), store_id=int(store_id), meal_period=MealPeriod.LUNCH.value
    )
    items: list[MemberMembershipRefundConsumptionRowOut] = []
    missing: list[date] = []
    total = Decimal("0")

    for delivery_date in sorted(units_by_date.keys()):
        units = max(1, int(units_by_date[delivery_date]))
        dish = dishes_by_date.get(delivery_date)
        raw_price = None if dish is None else dish.single_order_price_yuan
        if raw_price is None:
            missing.append(delivery_date)
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

    if missing:
        labels = "、".join(d.isoformat() for d in missing[:5])
        suffix = "…" if len(missing) > 5 else ""
        raise HTTPException(
            status_code=400,
            detail=f"以下消费日未配置菜单单价，无法计算退卡：{labels}{suffix}",
        )

    return total.quantize(_TWO_PLACES, rounding=ROUND_HALF_UP), items


def _ensure_refundable_member(member: Member) -> None:
    if member.membership_refunded_at is not None:
        raise HTTPException(status_code=400, detail="该会员已办理退卡退款，不可重复操作")


def _compute_refund_preview(db: Session, member: Member) -> MemberMembershipRefundPreviewOut:
    _ensure_refundable_member(member)
    meals_consumed = total_member_delivery_meal_units_consumed(db, int(member.id))
    meals_remaining = int(member.balance or 0)
    meal_quota_total = int(member.meal_quota_total or 0)
    paid_total = _paid_total_yuan_for_member(db, int(member.id))
    consumed_value, consumption_items = _consumption_charge_for_member(
        db,
        member_id=int(member.id),
        store_id=int(member.store_id),
    )

    if meals_remaining <= 0:
        raise HTTPException(status_code=400, detail="该会员剩余次数为 0，无可退次数")
    if meal_quota_total <= 0:
        raise HTTPException(status_code=400, detail="该会员无开卡配额记录，无法计算退款")
    if paid_total <= 0:
        raise HTTPException(status_code=400, detail="未找到已入账的开卡实收记录，无法计算退款")

    refund_yuan = (paid_total - consumed_value).quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)
    if refund_yuan < 0:
        refund_yuan = Decimal("0.00")

    return MemberMembershipRefundPreviewOut(
        member_id=int(member.id),
        member_name=(member.name or "").strip() or None,
        member_phone=(member.phone or "").strip() or None,
        plan_type=(member.plan_type or "").strip() or None,
        meals_consumed=meals_consumed,
        meals_remaining=meals_remaining,
        meal_quota_total=meal_quota_total,
        paid_total_yuan=paid_total,
        consumed_value_yuan=consumed_value,
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
        f"退卡退款剩余{balance_before}次",
        f"已消费{preview.meals_consumed}次扣款{preview.consumed_value_yuan}元",
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
    m.membership_refunded_at = beijing_now_naive()

    avg_unit = Decimal("0.00")
    if preview.meals_consumed > 0:
        avg_unit = (preview.consumed_value_yuan / Decimal(preview.meals_consumed)).quantize(
            _TWO_PLACES, rounding=ROUND_HALF_UP
        )

    row = MemberMembershipRefund(
        tenant_id=int(m.tenant_id),
        store_id=int(m.store_id),
        member_id=int(m.id),
        meals_consumed=int(preview.meals_consumed),
        meals_refunded=balance_before,
        meal_quota_total=int(preview.meal_quota_total),
        paid_total_yuan=preview.paid_total_yuan,
        consumed_value_yuan=preview.consumed_value_yuan,
        unit_price_yuan=avg_unit,
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
        "consumed_value_yuan": str(preview.consumed_value_yuan),
    }
    record_member_operation(
        db,
        member_id=int(m.id),
        source="admin",
        operation_type=OP_MEMBERSHIP_REFUND,
        summary=(
            f"退卡退款：已消费扣款{preview.consumed_value_yuan}元，退剩余{balance_before}次，"
            f"应退{preview.refund_amount_yuan}元"
        ),
        before=before_snap,
        after=after_snap,
        ip_address=ip_address,
        operator=operator,
    )
    db.commit()
    return preview
