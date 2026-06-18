"""日库存统一口径：后厨出餐 − 分配 + 损耗流水 = 剩余（只读，不可直接改值）。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.day_stock_adjustment_log import DayStockAdjustmentLog
from app.models.enums import DayStockAdjustmentReason, MealPeriod
from app.models.store_kitchen_plan import StoreKitchenPlan
from app.services.menu_day_stock_service import (
    paid_single_retail_portions_by_dates,
    weekly_menu_day_total_stock,
)
from app.services.meal_period.constants import DEFAULT_MEAL_PERIOD
from app.services.meal_period.normalize import normalize_meal_period

# 普通客服单次报损耗份数上限（绝对值）
_MAX_ADJUSTMENT_ABS_DELTA = 20

_REASON_LABELS: dict[str, str] = {
    DayStockAdjustmentReason.SPILL.value: "配送撒漏",
    DayStockAdjustmentReason.KITCHEN_TASTE.value: "后厨试吃",
    DayStockAdjustmentReason.KITCHEN_WASTE.value: "后厨报损",
    DayStockAdjustmentReason.COMP_MEAL.value: "客诉补餐",
    DayStockAdjustmentReason.COUNT_CORRECTION.value: "盘点校正",
    DayStockAdjustmentReason.OTHER.value: "其他",
}


@dataclass(frozen=True)
class DayStockBreakdown:
    """单餐段日库存拆解（顶卡、周菜单、单次可售校验共用）。"""

    meal_period: str
    kitchen_output: int | None
    delivery_total: int
    pickup_total: int
    single_retail_total: int
    waste_total: int
    adjustment_delta_sum: int
    remaining: int | None

    @property
    def sold_subscription_total(self) -> int:
        return int(self.delivery_total) + int(self.pickup_total)


def sum_adjustment_deltas(
    db: Session, *, store_id: int, business_date: date, meal_period: str
) -> int:
    """流水 delta 合计（负=减可售，正=回补）。"""
    return sum_adjustment_deltas_by_dates(
        db,
        store_id=int(store_id),
        dates=[business_date],
        meal_period=meal_period,
    ).get(business_date, 0)


def sum_adjustment_deltas_by_dates(
    db: Session, *, store_id: int, dates: Iterable[date], meal_period: str
) -> dict[date, int]:
    """批量获取多日损耗/回补流水 delta 合计（按餐段隔离）。"""
    period = normalize_meal_period(meal_period)
    uniq = list(dict.fromkeys(dates))
    if not uniq:
        return {}
    rows = db.execute(
        select(
            DayStockAdjustmentLog.business_date,
            func.coalesce(func.sum(DayStockAdjustmentLog.delta), 0),
        )
        .where(
            DayStockAdjustmentLog.store_id == int(store_id),
            DayStockAdjustmentLog.business_date.in_(uniq),
            DayStockAdjustmentLog.meal_period == period,
        )
        .group_by(DayStockAdjustmentLog.business_date)
    ).all()
    out = {d: 0 for d in uniq}
    for d, s in rows:
        if d is not None:
            out[d] = int(s or 0)
    return out


def waste_total_display(adjustment_delta_sum: int) -> int:
    """展示用损耗份数（正数）：流水 delta 为负的部分取反相加，再减去正数回补。"""
    # waste_total 仅展示「消耗」侧；remaining 用 raw sum(delta)
    return max(0, -int(adjustment_delta_sum))


def _prep_metrics_for_period(
    db: Session, *, store_id: int, business_date: date, meal_period: str
):
    from app.core.timeutil import today_shanghai
    from app.services.delivery_day_lock_service import (
        has_dinner_delivery_sheet_sf_push_on_date,
        is_delivery_day_sheet_frozen_after_sf_push,
    )
    from app.services.delivery_sheet_service import (
        delivery_sheet_metrics_for_date,
        delivery_sheet_metrics_for_dinner_date,
        delivery_sheet_metrics_pending_sql_for_future_date,
        delivery_sheet_metrics_via_sql_for_unlocked_date,
    )

    sid = int(store_id)
    d = business_date
    period = normalize_meal_period(meal_period)
    cal_today = today_shanghai()

    if period == MealPeriod.DINNER.value:
        if d > cal_today:
            return delivery_sheet_metrics_pending_sql_for_dinner_future_date(
                db, delivery_date=d, store_id=sid
            )
        if has_dinner_delivery_sheet_sf_push_on_date(db, store_id=sid, delivery_date=d):
            return delivery_sheet_metrics_for_dinner_date(db, delivery_date=d, store_id=sid)
        return delivery_sheet_metrics_for_dinner_date(db, delivery_date=d, store_id=sid)

    if d > cal_today:
        return delivery_sheet_metrics_pending_sql_for_future_date(db, delivery_date=d, store_id=sid)
    if is_delivery_day_sheet_frozen_after_sf_push(db, store_id=sid, delivery_date=d):
        return delivery_sheet_metrics_for_date(db, delivery_date=d, store_id=sid)
    return delivery_sheet_metrics_via_sql_for_unlocked_date(db, delivery_date=d, store_id=sid)


def get_day_stock_breakdown(
    db: Session,
    *,
    store_id: int,
    business_date: date,
    meal_period: str,
) -> DayStockBreakdown:
    """剩余 = 后厨出餐 − 到家配送 − 自提(午) − 单次零售 + sum(流水 delta)。"""
    sid = int(store_id)
    period = normalize_meal_period(meal_period)
    kitchen = weekly_menu_day_total_stock(db, business_date, store_id=sid, meal_period=period)
    metrics = _prep_metrics_for_period(db, store_id=sid, business_date=business_date, meal_period=period)
    home_total = int(metrics.home_pending_meal_total) + int(metrics.home_delivered_meal_total)
    pickup_total = int(metrics.pickup_meal_total) if period == MealPeriod.LUNCH.value else 0
    retail_map = paid_single_retail_portions_by_dates(db, [business_date], store_id=sid, meal_period=period)
    retail = int(retail_map.get(business_date, 0))
    delta_sum = sum_adjustment_deltas(db, store_id=sid, business_date=business_date, meal_period=period)
    waste_disp = waste_total_display(delta_sum)

    if kitchen is None:
        remaining = None
    else:
        remaining = max(
            0,
            int(kitchen) - home_total - pickup_total - retail + delta_sum,
        )

    return DayStockBreakdown(
        meal_period=period,
        kitchen_output=kitchen,
        delivery_total=home_total,
        pickup_total=pickup_total,
        single_retail_total=retail,
        waste_total=waste_disp,
        adjustment_delta_sum=delta_sum,
        remaining=remaining,
    )


def list_day_stock_adjustments(
    db: Session,
    *,
    store_id: int,
    business_date: date,
    meal_period: str,
) -> list[dict]:
    period = normalize_meal_period(meal_period)
    rows = db.scalars(
        select(DayStockAdjustmentLog)
        .where(
            DayStockAdjustmentLog.store_id == int(store_id),
            DayStockAdjustmentLog.business_date == business_date,
            DayStockAdjustmentLog.meal_period == period,
        )
        .order_by(DayStockAdjustmentLog.created_at.desc(), DayStockAdjustmentLog.id.desc())
    ).all()
    out: list[dict] = []
    for r in rows:
        code = str(r.reason_code)
        out.append(
            {
                "id": int(r.id),
                "business_date": r.business_date.isoformat(),
                "meal_period": r.meal_period,
                "delta": int(r.delta),
                "reason_code": code,
                "reason_label": _REASON_LABELS.get(code, code),
                "remark": r.remark,
                "operator": r.operator,
                "created_at": r.created_at.isoformat(sep=" ", timespec="seconds") if r.created_at else None,
            }
        )
    return out


def create_day_stock_adjustment(
    db: Session,
    *,
    store_id: int,
    business_date: date,
    meal_period: str,
    delta: int,
    reason_code: str,
    remark: str | None,
    operator: str,
) -> DayStockBreakdown:
    """写入损耗/回补流水；校验后返回最新 breakdown。"""
    sid = int(store_id)
    period = normalize_meal_period(meal_period)
    try:
        d = int(delta)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="delta 须为整数")
    if d == 0:
        raise HTTPException(status_code=400, detail="delta 不能为 0")

    code = (reason_code or "").strip().lower()
    valid_codes = {e.value for e in DayStockAdjustmentReason}
    if code not in valid_codes:
        raise HTTPException(status_code=400, detail=f"reason_code 无效，可选：{', '.join(sorted(valid_codes))}")

    if code == DayStockAdjustmentReason.OTHER.value and not (remark or "").strip():
        raise HTTPException(status_code=400, detail="原因选「其他」时须填写备注")

    if code != DayStockAdjustmentReason.COUNT_CORRECTION.value and d > 0:
        raise HTTPException(status_code=400, detail="仅盘点校正允许正数回补")

    if abs(d) > _MAX_ADJUSTMENT_ABS_DELTA and code != DayStockAdjustmentReason.COUNT_CORRECTION.value:
        raise HTTPException(status_code=400, detail=f"单次调整绝对值不能超过 {_MAX_ADJUSTMENT_ABS_DELTA} 份")

    before = get_day_stock_breakdown(db, store_id=sid, business_date=business_date, meal_period=period)
    if before.kitchen_output is None:
        raise HTTPException(status_code=400, detail="该餐段尚未配置后厨出餐，无法报损耗")

    rem = before.remaining if before.remaining is not None else 0
    if rem + d < 0:
        raise HTTPException(
            status_code=400,
            detail=f"调整后剩余将为 {rem + d} 份，不能小于 0（当前剩余 {rem} 份）",
        )

    row = DayStockAdjustmentLog(
        store_id=sid,
        business_date=business_date,
        meal_period=period,
        delta=d,
        reason_code=code,
        remark=(remark or "").strip() or None,
        operator=(operator or "admin")[:64],
    )
    db.add(row)
    db.commit()
    return get_day_stock_breakdown(db, store_id=sid, business_date=business_date, meal_period=period)


def sync_store_kitchen_plan_row(
    db: Session,
    *,
    store_id: int,
    business_date: date,
    meal_period: str,
    planned_total: int,
    updated_by: str | None = None,
) -> None:
    """后厨出餐写入周槽后，同步 store_kitchen_plans 便于日级归档。"""
    period = normalize_meal_period(meal_period)
    sid = int(store_id)
    row = db.get(StoreKitchenPlan, {"store_id": sid, "business_date": business_date, "meal_period": period})
    total = max(0, int(planned_total))
    if row is None:
        db.add(
            StoreKitchenPlan(
                store_id=sid,
                business_date=business_date,
                meal_period=period,
                planned_total=total,
                updated_by=updated_by,
            )
        )
    else:
        row.planned_total = total
        row.updated_by = updated_by
    db.flush()


def breakdown_to_dict(b: DayStockBreakdown) -> dict:
    return {
        "meal_period": b.meal_period,
        "kitchen_output": b.kitchen_output,
        "delivery_total": b.delivery_total,
        "pickup_total": b.pickup_total,
        "single_retail_total": b.single_retail_total,
        "waste_total": b.waste_total,
        "adjustment_delta_sum": b.adjustment_delta_sum,
        "remaining": b.remaining,
    }
