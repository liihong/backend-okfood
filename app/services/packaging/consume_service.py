"""晚上按后厨出餐扣包装。

午餐和晚餐分开算、分开提交。一餐失败不会把另一餐已经扣掉的流水撤掉。
某一餐一旦写下运行记录，之后改日总份、换菜、请假都不再回写，差额留给每周校对。
未期初的品跳过，避免上线第一天整表变负数。
"""

from __future__ import annotations

import logging
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import MealPeriod
from app.models.packaging_consume_run import PackagingConsumeRun
from app.models.packaging_sku import PackagingSku
from app.models.packaging_slot_line import PackagingSlotLine
from app.models.packaging_standard_line import PackagingStandardLine
from app.models.packaging_stock import PackagingStock
from app.models.packaging_stock_txn import PackagingStockTxn
from app.models.weekly_menu_slot import WeeklyMenuSlot
from app.services.packaging.constants import (
    BAG_FLAG,
    MEAL_LABELS,
    PORTION_SOURCE_KITCHEN,
    TXN_CONSUME,
)
from app.services.packaging.deduction import DeductionPlan, RecipeQty, plan_meal_deduction
from app.services.packaging.portions import meal_portions
from app.services.packaging.stock_command_service import _sku_initialized

logger = logging.getLogger(__name__)


def consume_meal(
    db: Session,
    *,
    store_id: int,
    biz_date: date,
    meal_period: str,
) -> bool:
    """扣一餐。返回是否新写入。已有运行记录时直接返回，不改结存。"""
    period = meal_period
    existing = db.scalar(
        select(PackagingConsumeRun.id).where(
            PackagingConsumeRun.store_id == int(store_id),
            PackagingConsumeRun.biz_date == biz_date,
            PackagingConsumeRun.meal_period == period,
        )
    )
    if existing is not None:
        return False
    counted = meal_portions(db, store_id=store_id, biz_date=biz_date, meal_period=period)
    label = MEAL_LABELS.get(period, period)
    bag = db.scalar(
        select(PackagingSku).where(
            PackagingSku.store_id == int(store_id),
            PackagingSku.bag_flag == BAG_FLAG,
        )
    )
    box_lines = _slot_recipe(db, store_id=store_id, biz_date=biz_date, meal_period=period)
    standard_lines = _standard_recipe(db, store_id=store_id, bag_sku_id=int(bag.id) if bag else None)
    plan = plan_meal_deduction(
        meal_label=label,
        portions=counted.portions,
        portion_source=counted.source,
        bag_sku_id=int(bag.id) if bag is not None else None,
        bag_ready=bool(bag and bag.is_active and _sku_initialized(db, bag.id)),
        bag_name=bag.name if bag is not None else "",
        box_lines=box_lines,
        standard_lines=standard_lines,
    )
    _apply_plan(
        db,
        store_id=store_id,
        biz_date=biz_date,
        meal_period=period,
        meal_label=label,
        portions=counted.portions,
        portion_source=counted.source or PORTION_SOURCE_KITCHEN,
        plan=plan,
    )
    db.commit()
    return True


def _apply_plan(
    db: Session,
    *,
    store_id: int,
    biz_date: date,
    meal_period: str,
    meal_label: str,
    portions: int,
    portion_source: str,
    plan: DeductionPlan,
) -> None:
    source_text = "后厨出餐" if portion_source == PORTION_SOURCE_KITCHEN else "实发"
    for sku_id, qty in plan.quantities.items():
        if qty <= 0:
            continue
        sku = db.get(PackagingSku, int(sku_id))
        if sku is None or int(sku.store_id) != int(store_id):
            continue
        stock = db.get(PackagingStock, int(sku.id))
        if stock is None:
            stock = PackagingStock(sku_id=int(sku.id), store_id=int(store_id), qty=0)
            db.add(stock)
            db.flush()
        stock.qty = int(stock.qty) - int(qty)
        db.add(
            PackagingStockTxn(
                store_id=int(store_id),
                sku_id=int(sku.id),
                txn_type=TXN_CONSUME,
                qty_delta=-int(qty),
                qty_after=int(stock.qty),
                biz_date=biz_date,
                meal_period=meal_period,
                operator="system",
                remark=f"{meal_label}自动领用，{source_text}{int(portions)}份"[:200],
            )
        )
    note = "\n".join(plan.warnings)[:500] or None
    db.add(
        PackagingConsumeRun(
            store_id=int(store_id),
            biz_date=biz_date,
            meal_period=meal_period,
            portions=int(portions),
            portion_source=portion_source,
            note=note,
        )
    )


def _slot_recipe(
    db: Session, *, store_id: int, biz_date: date, meal_period: str
) -> list[RecipeQty]:
    anchor = biz_date - timedelta(days=biz_date.weekday())
    slot_no = biz_date.weekday() + 1
    menu_slot = db.scalar(
        select(WeeklyMenuSlot).where(
            WeeklyMenuSlot.store_id == int(store_id),
            WeeklyMenuSlot.week_start == anchor,
            WeeklyMenuSlot.slot == slot_no,
            WeeklyMenuSlot.meal_period == meal_period,
        )
    )
    if menu_slot is None:
        return []
    rows = db.scalars(
        select(PackagingSlotLine).where(PackagingSlotLine.slot_id == int(menu_slot.id))
    ).all()
    return _to_recipe(db, [(int(row.sku_id), int(row.qty_per_portion)) for row in rows])


def _standard_recipe(db: Session, *, store_id: int, bag_sku_id: int | None) -> list[RecipeQty]:
    rows = db.scalars(
        select(PackagingStandardLine).where(PackagingStandardLine.store_id == int(store_id))
    ).all()
    pairs = [
        (int(row.sku_id), int(row.qty_per_portion))
        for row in rows
        if bag_sku_id is None or int(row.sku_id) != int(bag_sku_id)
    ]
    return _to_recipe(db, pairs)


def _to_recipe(db: Session, pairs: list[tuple[int, int]]) -> list[RecipeQty]:
    result: list[RecipeQty] = []
    for sku_id, qty in pairs:
        sku = db.get(PackagingSku, sku_id)
        if sku is None or sku.bag_flag == BAG_FLAG:
            continue
        ready = bool(sku.is_active and _sku_initialized(db, sku.id))
        result.append(RecipeQty(sku_id=sku_id, qty_per_portion=qty, ready=ready, name=sku.name))
    return result


def meal_periods_for_day() -> tuple[str, str]:
    """当天必须两餐都跑，顺序固定为午餐然后晚餐。"""
    return (MealPeriod.LUNCH.value, MealPeriod.DINNER.value)
