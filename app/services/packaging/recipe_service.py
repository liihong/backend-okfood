"""用盒和每份标配。

打包袋由晚上的任务按每餐一只扣，保存配方时拒绝把它写进来，避免扣两次。
换菜才覆盖槽位用盒；只改日总份不走这里。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.menu_dish import MenuDish
from app.models.packaging_dish_line import PackagingDishLine
from app.models.packaging_sku import PackagingSku
from app.models.packaging_slot_line import PackagingSlotLine
from app.models.packaging_standard_line import PackagingStandardLine
from app.models.weekly_menu_slot import WeeklyMenuSlot
from app.services.meal_period.normalize import normalize_meal_period
from app.services.packaging.constants import BAG_FLAG


@dataclass(frozen=True)
class RecipeLineIn:
    sku_id: int
    qty_per_portion: int


def list_dish_recipes(db: Session, *, store_id: int) -> list[dict]:
    dishes = db.scalars(
        select(MenuDish)
        .where(MenuDish.store_id == int(store_id))
        .order_by(MenuDish.id.asc())
    ).all()
    lines = db.scalars(
        select(PackagingDishLine).where(PackagingDishLine.store_id == int(store_id))
    ).all()
    grouped: dict[int, list[dict]] = {}
    sku_ids = {int(line.sku_id) for line in lines}
    names = _sku_name_map(db, sku_ids)
    for line in lines:
        grouped.setdefault(int(line.dish_id), []).append(
            {
                "sku_id": int(line.sku_id),
                "sku_name": names.get(int(line.sku_id), ""),
                "qty_per_portion": int(line.qty_per_portion),
            }
        )
    return [
        {
            "dish_id": int(dish.id),
            "dish_name": dish.name,
            "is_enabled": bool(dish.is_enabled),
            "lines": grouped.get(int(dish.id), []),
        }
        for dish in dishes
    ]


def replace_dish_lines(
    db: Session, dish_id: int, lines: list[RecipeLineIn], *, store_id: int
) -> list[dict]:
    dish = _require_dish(db, dish_id, store_id=store_id)
    cleaned = _validate_lines(db, lines, store_id=store_id)
    db.execute(
        delete(PackagingDishLine).where(
            PackagingDishLine.store_id == int(store_id),
            PackagingDishLine.dish_id == int(dish.id),
        )
    )
    for item in cleaned:
        db.add(
            PackagingDishLine(
                store_id=int(store_id),
                dish_id=int(dish.id),
                sku_id=item.sku_id,
                qty_per_portion=item.qty_per_portion,
            )
        )
    db.commit()
    return [row for row in list_dish_recipes(db, store_id=store_id) if row["dish_id"] == int(dish.id)]


def list_standard_lines(db: Session, *, store_id: int) -> list[dict]:
    rows = db.scalars(
        select(PackagingStandardLine)
        .where(PackagingStandardLine.store_id == int(store_id))
        .order_by(PackagingStandardLine.id.asc())
    ).all()
    names = _sku_name_map(db, {int(row.sku_id) for row in rows})
    units = _sku_unit_map(db, {int(row.sku_id) for row in rows})
    return [
        {
            "sku_id": int(row.sku_id),
            "sku_name": names.get(int(row.sku_id), ""),
            "unit": units.get(int(row.sku_id), ""),
            "qty_per_portion": int(row.qty_per_portion),
        }
        for row in rows
    ]


def replace_standard_lines(db: Session, lines: list[RecipeLineIn], *, store_id: int) -> list[dict]:
    cleaned = _validate_lines(db, lines, store_id=store_id)
    db.execute(delete(PackagingStandardLine).where(PackagingStandardLine.store_id == int(store_id)))
    for item in cleaned:
        db.add(
            PackagingStandardLine(
                store_id=int(store_id),
                sku_id=item.sku_id,
                qty_per_portion=item.qty_per_portion,
            )
        )
    db.commit()
    return list_standard_lines(db, store_id=store_id)


def get_slot_lines(
    db: Session,
    *,
    store_id: int,
    week_start: date,
    slot: int,
    meal_period: str,
) -> dict:
    period = normalize_meal_period(meal_period)
    menu_slot = _require_menu_slot(
        db, store_id=store_id, week_start=week_start, slot=slot, meal_period=period
    )
    rows = db.scalars(
        select(PackagingSlotLine)
        .where(PackagingSlotLine.slot_id == int(menu_slot.id))
        .order_by(PackagingSlotLine.id.asc())
    ).all()
    names = _sku_name_map(db, {int(row.sku_id) for row in rows})
    return {
        "slot_id": int(menu_slot.id),
        "dish_id": int(menu_slot.dish_id),
        "meal_period": period,
        "slot": int(slot),
        "lines": [
            {
                "sku_id": int(row.sku_id),
                "sku_name": names.get(int(row.sku_id), ""),
                "qty_per_portion": int(row.qty_per_portion),
            }
            for row in rows
        ],
    }


def replace_slot_lines(
    db: Session,
    *,
    store_id: int,
    week_start: date,
    slot: int,
    meal_period: str,
    lines: list[RecipeLineIn],
) -> dict:
    """保存这一餐的用盒，并写回菜品默认，下周同一道菜不用重设。"""
    period = normalize_meal_period(meal_period)
    menu_slot = _require_menu_slot(
        db, store_id=store_id, week_start=week_start, slot=slot, meal_period=period
    )
    cleaned = _validate_lines(db, lines, store_id=store_id)
    _replace_slot_rows(db, store_id=store_id, slot_id=int(menu_slot.id), lines=cleaned)
    _replace_dish_rows(db, store_id=store_id, dish_id=int(menu_slot.dish_id), lines=cleaned)
    db.commit()
    return get_slot_lines(
        db, store_id=store_id, week_start=week_start, slot=slot, meal_period=period
    )


def slot_usage(db: Session, *, store_id: int, week_start: date) -> list[dict]:
    """给本周菜单显示哪些槽还没设用盒。没有菜品的槽不返回。"""
    anchor = _monday(week_start)
    slots = db.scalars(
        select(WeeklyMenuSlot).where(
            WeeklyMenuSlot.store_id == int(store_id),
            WeeklyMenuSlot.week_start == anchor,
        )
    ).all()
    if not slots:
        return []
    slot_ids = [int(row.id) for row in slots]
    counted = db.execute(
        select(PackagingSlotLine.slot_id, PackagingSlotLine.id).where(
            PackagingSlotLine.slot_id.in_(slot_ids)
        )
    ).all()
    has_line = {int(slot_id) for slot_id, _line_id in counted}
    return [
        {
            "slot": int(row.slot),
            "meal_period": row.meal_period,
            "has_boxes": int(row.id) in has_line,
        }
        for row in slots
    ]


def copy_dish_defaults_onto_slot(db: Session, *, slot_id: int, store_id: int) -> None:
    """换菜后用新菜的默认用盒覆盖本槽。没有默认就清空，晚上会提示未设用盒。"""
    menu_slot = db.get(WeeklyMenuSlot, int(slot_id))
    if menu_slot is None or int(menu_slot.store_id) != int(store_id):
        return
    defaults = db.scalars(
        select(PackagingDishLine).where(
            PackagingDishLine.store_id == int(store_id),
            PackagingDishLine.dish_id == int(menu_slot.dish_id),
        )
    ).all()
    # 自动抄写时跳过打包袋和已停用品，不因为一条脏数据让整次换菜同步失败。
    cleaned = _filter_copy_lines(db, defaults, store_id=store_id)
    _replace_slot_rows(db, store_id=store_id, slot_id=int(menu_slot.id), lines=cleaned)
    db.commit()


def _replace_slot_rows(
    db: Session, *, store_id: int, slot_id: int, lines: list[RecipeLineIn]
) -> None:
    db.execute(delete(PackagingSlotLine).where(PackagingSlotLine.slot_id == int(slot_id)))
    for item in lines:
        db.add(
            PackagingSlotLine(
                store_id=int(store_id),
                slot_id=int(slot_id),
                sku_id=item.sku_id,
                qty_per_portion=item.qty_per_portion,
            )
        )


def _replace_dish_rows(
    db: Session, *, store_id: int, dish_id: int, lines: list[RecipeLineIn]
) -> None:
    db.execute(
        delete(PackagingDishLine).where(
            PackagingDishLine.store_id == int(store_id),
            PackagingDishLine.dish_id == int(dish_id),
        )
    )
    for item in lines:
        db.add(
            PackagingDishLine(
                store_id=int(store_id),
                dish_id=int(dish_id),
                sku_id=item.sku_id,
                qty_per_portion=item.qty_per_portion,
            )
        )


def _filter_copy_lines(db: Session, rows: list[PackagingDishLine], *, store_id: int) -> list[RecipeLineIn]:
    cleaned: list[RecipeLineIn] = []
    seen: set[int] = set()
    for row in rows:
        sku_id = int(row.sku_id)
        if sku_id in seen:
            continue
        sku = db.get(PackagingSku, sku_id)
        if sku is None or int(sku.store_id) != int(store_id):
            continue
        if sku.bag_flag == BAG_FLAG or not sku.is_active:
            continue
        qty = int(row.qty_per_portion)
        if qty < 1:
            continue
        seen.add(sku_id)
        cleaned.append(RecipeLineIn(sku_id=sku_id, qty_per_portion=qty))
    return cleaned


def _validate_lines(
    db: Session,
    lines: list[RecipeLineIn],
    *,
    store_id: int,
    allow_empty: bool = True,
) -> list[RecipeLineIn]:
    if not lines and not allow_empty:
        raise HTTPException(status_code=400, detail="请至少选择一种耗材")
    seen: set[int] = set()
    cleaned: list[RecipeLineIn] = []
    for item in lines:
        sku_id = int(item.sku_id)
        if sku_id in seen:
            raise HTTPException(status_code=400, detail="同一耗材不能重复添加")
        seen.add(sku_id)
        qty = int(item.qty_per_portion)
        if qty < 1:
            raise HTTPException(status_code=400, detail="每份数量至少为 1")
        sku = db.get(PackagingSku, sku_id)
        if sku is None or int(sku.store_id) != int(store_id):
            raise HTTPException(status_code=404, detail="耗材不存在")
        if sku.bag_flag == BAG_FLAG:
            raise HTTPException(status_code=400, detail="打包袋按每餐一只自动扣，不能放进用盒或标配")
        if not sku.is_active:
            raise HTTPException(status_code=400, detail=f"{sku.name}已停用")
        cleaned.append(RecipeLineIn(sku_id=sku_id, qty_per_portion=qty))
    return cleaned


def _require_dish(db: Session, dish_id: int, *, store_id: int) -> MenuDish:
    dish = db.get(MenuDish, int(dish_id))
    if dish is None or int(dish.store_id) != int(store_id):
        raise HTTPException(status_code=404, detail="菜品不存在")
    return dish


def _require_menu_slot(
    db: Session, *, store_id: int, week_start: date, slot: int, meal_period: str
) -> WeeklyMenuSlot:
    if slot < 1 or slot > 7:
        raise HTTPException(status_code=400, detail="slot 须为 1 到 7")
    row = db.scalar(
        select(WeeklyMenuSlot).where(
            WeeklyMenuSlot.store_id == int(store_id),
            WeeklyMenuSlot.week_start == _monday(week_start),
            WeeklyMenuSlot.slot == int(slot),
            WeeklyMenuSlot.meal_period == meal_period,
        )
    )
    if row is None:
        raise HTTPException(status_code=400, detail="请先在本周菜单选择菜品")
    return row


def _sku_name_map(db: Session, sku_ids: set[int]) -> dict[int, str]:
    if not sku_ids:
        return {}
    rows = db.scalars(select(PackagingSku).where(PackagingSku.id.in_(sku_ids))).all()
    return {int(row.id): row.name for row in rows}


def _sku_unit_map(db: Session, sku_ids: set[int]) -> dict[int, str]:
    if not sku_ids:
        return {}
    rows = db.scalars(select(PackagingSku).where(PackagingSku.id.in_(sku_ids))).all()
    return {int(row.id): row.unit for row in rows}


def _monday(day: date) -> date:
    return day - timedelta(days=day.weekday())
