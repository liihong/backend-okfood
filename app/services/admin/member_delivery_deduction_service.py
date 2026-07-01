"""会员端 / 管理端：消费记录（套餐送达扣次 + 单次购买会员卡扣次）。"""

from __future__ import annotations

import re
from datetime import date, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.timeutil import today_shanghai
from app.models.balance_log import BalanceLog
from app.models.delivery_log import DeliveryLog
from app.models.enums import BalanceReason, DeliveryStatus
from app.models.single_meal_order import SingleMealOrder
from app.schemas.user import DeliveryDeductionOut

_ADMIN_MEMBER_DELIVERED_DATES_LIMIT = 2000
_SINGLE_MEAL_ORDER_ID_RE = re.compile(r"single_meal_orders\.id=(\d+)")
_DEDUCTION_KIND_SUBSCRIPTION = "subscription"
_DEDUCTION_KIND_SINGLE_MEAL = "single_meal"
_DEDUCTION_KIND_MEAL_COMPENSATION = "meal_compensation"


def _balance_log_business_date(created_at: datetime | None) -> date:
    """余额流水业务日：按北京时间 naive 的日期部分。"""
    if created_at is None:
        return today_shanghai()
    return created_at.date()


def _delivery_meal_units_by_date(db: Session, member_id: int) -> dict[date, int]:
    """按确认送达时间序，将 delivery_logs 与 balance_logs（配送扣次）一一配对得每日份数。"""
    mid = int(member_id)
    dl_rows = db.scalars(
        select(DeliveryLog)
        .where(
            DeliveryLog.member_id == mid,
            DeliveryLog.status == DeliveryStatus.DELIVERED.value,
        )
        .order_by(DeliveryLog.updated_at.asc(), DeliveryLog.id.asc())
    ).all()
    bl_rows = db.scalars(
        select(BalanceLog)
        .where(
            BalanceLog.member_id == mid,
            BalanceLog.reason == BalanceReason.DELIVERY.value,
            BalanceLog.change < 0,
        )
        .order_by(BalanceLog.created_at.asc(), BalanceLog.id.asc())
    ).all()
    out: dict[date, int] = {}
    for i, dl in enumerate(dl_rows):
        if i < len(bl_rows):
            units = abs(int(bl_rows[i].change))
        else:
            units = 1
        out[dl.delivery_date] = max(1, units)
    return out


def delivery_meal_units_by_date(db: Session, member_id: int) -> dict[date, int]:
    """会员各配送业务日已消费份数（供退卡按日菜单单价扣款）。"""
    return _delivery_meal_units_by_date(db, member_id)


def total_member_delivery_meal_units_consumed(db: Session, member_id: int) -> int:
    """累计已消费份数：仅套餐配送扣次 balance_logs 绝对值之和（退卡计价用）。"""
    mid = int(member_id)
    val = db.scalar(
        select(func.coalesce(func.sum(func.abs(BalanceLog.change)), 0)).where(
            BalanceLog.member_id == mid,
            BalanceLog.reason == BalanceReason.DELIVERY.value,
            BalanceLog.change < 0,
        )
    )
    return int(val or 0)


def _parse_single_meal_order_id_from_balance_detail(detail: str | None) -> int | None:
    if not detail:
        return None
    m = _SINGLE_MEAL_ORDER_ID_RE.search(detail)
    if not m:
        return None
    try:
        return int(m.group(1))
    except (TypeError, ValueError):
        return None


def _single_meal_deduction_items(db: Session, member_id: int) -> list[DeliveryDeductionOut]:
    """单次购买：会员卡支付扣次（已退款订单不计入）。"""
    mid = int(member_id)
    bl_rows = db.scalars(
        select(BalanceLog)
        .where(
            BalanceLog.member_id == mid,
            BalanceLog.reason == BalanceReason.SINGLE_MEAL.value,
            BalanceLog.change < 0,
        )
        .order_by(BalanceLog.created_at.desc(), BalanceLog.id.desc())
    ).all()
    items: list[DeliveryDeductionOut] = []
    for bl in bl_rows:
        oid = _parse_single_meal_order_id_from_balance_detail(bl.detail)
        if oid is None:
            continue
        order = db.get(SingleMealOrder, oid)
        if not order or int(order.member_id) != mid:
            continue
        if (order.pay_status or "").strip() == "已退款":
            continue
        items.append(
            DeliveryDeductionOut(
                delivery_date=order.delivery_date,
                meal_units=max(1, abs(int(bl.change))),
                deduction_kind=_DEDUCTION_KIND_SINGLE_MEAL,
            )
        )
    return items


def _meal_compensation_items(db: Session, member_id: int) -> list[DeliveryDeductionOut]:
    """补餐赔付：正向入账 balance_logs（供消费记录页展示补送记录）。"""
    mid = int(member_id)
    bl_rows = db.scalars(
        select(BalanceLog)
        .where(
            BalanceLog.member_id == mid,
            BalanceLog.reason == BalanceReason.MEAL_COMPENSATION.value,
            BalanceLog.change > 0,
        )
        .order_by(BalanceLog.created_at.desc(), BalanceLog.id.desc())
    ).all()
    return [
        DeliveryDeductionOut(
            delivery_date=_balance_log_business_date(bl.created_at),
            meal_units=max(1, int(bl.change)),
            deduction_kind=_DEDUCTION_KIND_MEAL_COMPENSATION,
        )
        for bl in bl_rows
    ]


def _subscription_deduction_items(db: Session, member_id: int) -> list[DeliveryDeductionOut]:
    """订阅套餐：已确认送达的配送业务日（去重，一日一条）。"""
    mid = int(member_id)
    filt = (DeliveryLog.member_id == mid) & (DeliveryLog.status == DeliveryStatus.DELIVERED.value)
    dates = db.scalars(
        select(DeliveryLog.delivery_date).where(filt).distinct().order_by(DeliveryLog.delivery_date.desc())
    ).all()
    units_map = _delivery_meal_units_by_date(db, mid)
    return [
        DeliveryDeductionOut(
            delivery_date=d,
            meal_units=units_map.get(d, 1),
            deduction_kind=_DEDUCTION_KIND_SUBSCRIPTION,
        )
        for d in dates
    ]


def _merged_consumption_items(db: Session, member_id: int) -> list[DeliveryDeductionOut]:
    items = (
        _subscription_deduction_items(db, member_id)
        + _single_meal_deduction_items(db, member_id)
        + _meal_compensation_items(db, member_id)
    )
    return sorted(items, key=lambda x: x.delivery_date, reverse=True)


def total_member_consumption_meal_units(db: Session, member_id: int) -> int:
    """消费记录页累计份数：套餐送达扣次 + 单次购买会员卡扣次（不含已退款单次）。"""
    delivery_total = total_member_delivery_meal_units_consumed(db, member_id)
    mid = int(member_id)
    single_total = 0
    for row in _single_meal_deduction_items(db, mid):
        single_total += int(row.meal_units)
    return delivery_total + single_total


def list_member_delivery_deductions(
    db: Session,
    member_id: int,
    *,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[DeliveryDeductionOut], int, int]:
    page = max(1, page)
    page_size = min(50, max(1, page_size))
    all_items = _merged_consumption_items(db, int(member_id))
    total = len(all_items)
    offset = (page - 1) * page_size
    items = all_items[offset : offset + page_size]
    total_meals = total_member_consumption_meal_units(db, member_id)
    return items, total, total_meals


def list_member_delivered_dates_admin(
    db: Session,
    member_id: int,
) -> tuple[list[DeliveryDeductionOut], int, int, bool]:
    """管理端：消费记录（套餐送达 + 单次购买会员卡扣次，新在前）。`truncated` 表示超过单次返回上限。"""
    cap = _ADMIN_MEMBER_DELIVERED_DATES_LIMIT
    all_items = _merged_consumption_items(db, int(member_id))
    total = len(all_items)
    items = all_items[:cap]
    truncated = total > len(items)
    total_meals = total_member_consumption_meal_units(db, member_id)
    return items, total, total_meals, truncated
