"""会员端：套餐配送确认送达时的扣次记录（按配送业务日）。"""

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.balance_log import BalanceLog
from app.models.delivery_log import DeliveryLog
from app.models.enums import BalanceReason, DeliveryStatus
from app.schemas.user import DeliveryDeductionOut

_ADMIN_MEMBER_DELIVERED_DATES_LIMIT = 2000


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


def total_member_delivery_meal_units_consumed(db: Session, member_id: int) -> int:
    """累计已消费份数：配送扣次 balance_logs 绝对值之和。"""
    mid = int(member_id)
    val = db.scalar(
        select(func.coalesce(func.sum(func.abs(BalanceLog.change)), 0)).where(
            BalanceLog.member_id == mid,
            BalanceLog.reason == BalanceReason.DELIVERY.value,
            BalanceLog.change < 0,
        )
    )
    return int(val or 0)


def list_member_delivery_deductions(
    db: Session,
    member_id: int,
    *,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[DeliveryDeductionOut], int, int]:
    page = max(1, page)
    page_size = min(50, max(1, page_size))
    mid = int(member_id)
    filt = (DeliveryLog.member_id == mid) & (DeliveryLog.status == DeliveryStatus.DELIVERED.value)
    total = int(db.scalar(select(func.count()).select_from(DeliveryLog).where(filt)) or 0)
    base = select(DeliveryLog).where(filt).order_by(DeliveryLog.delivery_date.desc(), DeliveryLog.id.desc())
    offset = (page - 1) * page_size
    rows = db.scalars(base.offset(offset).limit(page_size)).all()
    units_map = _delivery_meal_units_by_date(db, mid)
    items = [
        DeliveryDeductionOut(
            delivery_date=r.delivery_date,
            meal_units=units_map.get(r.delivery_date, 1),
        )
        for r in rows
    ]
    total_meals = total_member_delivery_meal_units_consumed(db, mid)
    return items, total, total_meals


def list_member_delivered_dates_admin(
    db: Session,
    member_id: int,
) -> tuple[list[DeliveryDeductionOut], int, int, bool]:
    """管理端：某会员已确认送达的去重配送业务日（新在前）。`truncated` 表示超过单次返回上限。"""
    cap = _ADMIN_MEMBER_DELIVERED_DATES_LIMIT
    mid = int(member_id)
    filt = (DeliveryLog.member_id == mid) & (DeliveryLog.status == DeliveryStatus.DELIVERED.value)
    subq = select(DeliveryLog.delivery_date).where(filt).distinct().subquery()
    total = int(db.scalar(select(func.count()).select_from(subq)) or 0)
    dates = db.scalars(
        select(DeliveryLog.delivery_date).where(filt).distinct().order_by(DeliveryLog.delivery_date.desc()).limit(cap)
    ).all()
    truncated = total > len(dates)
    units_map = _delivery_meal_units_by_date(db, mid)
    total_meals = total_member_delivery_meal_units_consumed(db, mid)
    items = [
        DeliveryDeductionOut(delivery_date=d, meal_units=units_map.get(d, 1))
        for d in dates
    ]
    return items, total, total_meals, truncated
