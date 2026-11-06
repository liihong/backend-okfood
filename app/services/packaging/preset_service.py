"""把手写清单和每道菜的默认餐具写入门店。

只补还没有的档案和还没设用盒的菜品，不覆盖已经盘过或已经设过的数据。
结存写成 0，但不写流水。没有流水就算未盘点，晚上的任务不会扣，避免在盘点前把库存扣成负数。
打包袋不放进菜品用盒。它已经是「每餐一只」，再写进菜品会扣两次。
"""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.menu_dish import MenuDish
from app.models.packaging_dish_line import PackagingDishLine
from app.models.packaging_sku import PackagingSku
from app.models.packaging_slot_line import PackagingSlotLine
from app.models.packaging_stock import PackagingStock
from app.models.store import Store
from app.models.weekly_menu_slot import WeeklyMenuSlot
from app.services.packaging.constants import BAG_FLAG
from app.services.packaging.recipe_service import copy_dish_defaults_onto_slot
from app.services.packaging.sku_service import import_default_skus

logger = logging.getLogger(__name__)

# 每道菜默认餐具。数量 1、单位「双」表示一双筷子，不是两根。
DEFAULT_DISH_UTENSILS: tuple[tuple[str, int], ...] = (
    ("筷子", 1),
    ("小勺", 1),
)


def preset_active_stores(db: Session) -> list[dict]:
    """给每个启用中的门店补齐清单、零库存和菜品默认餐具。"""
    store_ids = list(
        db.scalars(select(Store.id).where(Store.is_active.is_(True)).order_by(Store.id.asc())).all()
    )
    return [preset_store(db, store_id=int(store_id)) for store_id in store_ids]


def preset_store(db: Session, *, store_id: int) -> dict:
    """当前门店：导入清单、结存置 0、没设用盒的菜品补上筷子和小勺。"""
    created_skus = import_default_skus(db, store_id=int(store_id))
    zero_stocks = _ensure_zero_stocks(db, store_id=int(store_id))
    dishes = _fill_dish_utensils(db, store_id=int(store_id))
    slots = _fill_empty_slots_from_dish(db, store_id=int(store_id))
    db.commit()
    return {
        "store_id": int(store_id),
        "created_skus": created_skus,
        "zero_stocks": zero_stocks,
        "dishes": dishes,
        "slots": slots,
    }


def apply_default_utensils_to_new_dish(db: Session, *, store_id: int, dish_id: int) -> None:
    """新建菜品后补默认餐具。门店还没有筷子或小勺时直接跳过，不影响菜品保存。"""
    if _dish_has_lines(db, dish_id):
        return
    if _add_utensil_lines(db, store_id=int(store_id), dish_id=int(dish_id)):
        db.commit()


def _ensure_zero_stocks(db: Session, *, store_id: int) -> int:
    """没有结存行的品补一行 0。已有结存或流水的不改。"""
    skus = db.scalars(select(PackagingSku).where(PackagingSku.store_id == int(store_id))).all()
    added = 0
    for sku in skus:
        stock = db.get(PackagingStock, int(sku.id))
        if stock is not None:
            continue
        db.add(PackagingStock(sku_id=int(sku.id), store_id=int(store_id), qty=0))
        added += 1
    db.flush()
    return added


def _fill_dish_utensils(db: Session, *, store_id: int) -> int:
    dishes = db.scalars(select(MenuDish.id).where(MenuDish.store_id == int(store_id))).all()
    filled = 0
    for dish_id in dishes:
        if _dish_has_lines(db, int(dish_id)):
            continue
        if _add_utensil_lines(db, store_id=store_id, dish_id=int(dish_id)):
            filled += 1
    db.flush()
    return filled


def _fill_empty_slots_from_dish(db: Session, *, store_id: int) -> int:
    """本周已经排了菜、但还没设用盒的槽，抄上该菜的默认餐具。"""
    slots = db.scalars(select(WeeklyMenuSlot).where(WeeklyMenuSlot.store_id == int(store_id))).all()
    filled = 0
    for slot in slots:
        has_line = db.scalar(
            select(PackagingSlotLine.id).where(PackagingSlotLine.slot_id == int(slot.id)).limit(1)
        )
        if has_line is not None:
            continue
        has_dish_line = _dish_has_lines(db, int(slot.dish_id))
        if not has_dish_line:
            continue
        copy_dish_defaults_onto_slot(db, slot_id=int(slot.id), store_id=int(store_id))
        filled += 1
    return filled


def _add_utensil_lines(db: Session, *, store_id: int, dish_id: int) -> bool:
    names = {name for name, _qty in DEFAULT_DISH_UTENSILS}
    skus = db.scalars(
        select(PackagingSku).where(
            PackagingSku.store_id == int(store_id),
            PackagingSku.name.in_(names),
            PackagingSku.is_active.is_(True),
        )
    ).all()
    by_name = {row.name: row for row in skus}
    added = False
    for name, qty in DEFAULT_DISH_UTENSILS:
        sku = by_name.get(name)
        if sku is None or sku.bag_flag == BAG_FLAG:
            continue
        db.add(
            PackagingDishLine(
                store_id=int(store_id),
                dish_id=int(dish_id),
                sku_id=int(sku.id),
                qty_per_portion=int(qty),
            )
        )
        added = True
    return added


def _dish_has_lines(db: Session, dish_id: int) -> bool:
    found = db.scalar(
        select(PackagingDishLine.id).where(PackagingDishLine.dish_id == int(dish_id)).limit(1)
    )
    return found is not None
