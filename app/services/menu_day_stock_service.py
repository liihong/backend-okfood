"""日菜单总库存存于 weekly_menu_slot.total_stock。单次卡剩余=总份数−应配送(订阅)−已付单次。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.delivery_calendar import is_subscription_delivery_day
from app.models.menu_dish import MenuDish
from app.models.menu_schedule import MenuSchedule
from app.models.single_meal_order import SingleMealOrder
from app.models.weekly_menu_slot import WeeklyMenuSlot
from app.services.courier_service import eligible_members_for_delivery, eligible_members_for_store_pickup
from app.services.member_service import effective_daily_meal_units


def _week_start(d: date) -> date:
    return d - timedelta(days=d.weekday())


def resolve_dish_for_calendar_date(db: Session, menu_date: date) -> MenuDish | None:
    """某日周槽位或按日排期上的菜品；无排期则 None。"""
    anchor = _week_start(menu_date)
    slot = menu_date.weekday() + 1
    row = db.execute(
        select(WeeklyMenuSlot, MenuDish)
        .join(MenuDish, WeeklyMenuSlot.dish_id == MenuDish.id)
        .where(WeeklyMenuSlot.week_start == anchor, WeeklyMenuSlot.slot == slot)
    ).first()
    if row:
        return row[1]
    row2 = db.execute(
        select(MenuSchedule, MenuDish)
        .join(MenuDish, MenuSchedule.dish_id == MenuDish.id)
        .where(MenuSchedule.menu_date == menu_date)
    ).first()
    if row2:
        return row2[1]
    return None


def subscription_total_meals_on_date(db: Session, menu_date: date) -> int:
    """当日应配送的会员份数（到家+门店自提；与配送大表同一规则；非法定配送日则为 0）。"""
    if not is_subscription_delivery_day(menu_date):
        return 0
    del_members, _ = eligible_members_for_delivery(db, delivery_date=menu_date, delivery_region_id=None)
    pick_members, _ = eligible_members_for_store_pickup(db, delivery_date=menu_date)
    total = 0
    for m in del_members:
        total += effective_daily_meal_units(m)
    for m in pick_members:
        total += effective_daily_meal_units(m)
    return total


def paid_single_portions_sum(db: Session, dish_id: int, menu_date: date) -> int:
    v = db.scalar(
        select(func.coalesce(func.sum(SingleMealOrder.quantity), 0)).where(
            SingleMealOrder.delivery_date == menu_date,
            SingleMealOrder.dish_id == dish_id,
            SingleMealOrder.pay_status == "已支付",
        )
    )
    return int(v or 0)


def weekly_slot_row_for_dish_date(db: Session, dish_id: int, menu_date: date) -> WeeklyMenuSlot | None:
    """与单次点餐同周槽+同一道菜的行；仅周排期有库存字段。"""
    anchor = _week_start(menu_date)
    slot = menu_date.weekday() + 1
    return db.scalar(
        select(WeeklyMenuSlot).where(
            WeeklyMenuSlot.week_start == anchor,
            WeeklyMenuSlot.slot == slot,
            WeeklyMenuSlot.dish_id == dish_id,
        )
    )


@dataclass(frozen=True)
class SingleOrderStockInfo:
    """周槽 total_stock 为 NULL 时不限制单次卡份数；纯按日排期无周槽时也不限制。"""

    limited: bool
    total_stock: int | None
    subscription_meals: int
    paid_single_portions: int
    remaining: int | None

    def to_detail_dict(self) -> dict[str, Any]:
        return {
            "single_stock_limited": self.limited,
            "single_stock_total": self.total_stock,
            "subscription_meals_for_day": self.subscription_meals,
            "single_stock_paid_portions": self.paid_single_portions,
            "single_stock_remaining": self.remaining,
        }


def single_order_stock_for_dish_date(db: Session, dish_id: int, menu_date: date) -> SingleOrderStockInfo:
    w = weekly_slot_row_for_dish_date(db, dish_id, menu_date)
    scheduled = resolve_dish_for_calendar_date(db, menu_date)
    sub = subscription_total_meals_on_date(db, menu_date) if scheduled and int(scheduled.id) == int(dish_id) else 0
    paid = paid_single_portions_sum(db, dish_id, menu_date)
    if w is None or w.total_stock is None:
        return SingleOrderStockInfo(
            limited=False, total_stock=None, subscription_meals=sub, paid_single_portions=paid, remaining=None
        )
    cap = int(w.total_stock or 0)
    single_cap = max(0, cap - sub)
    rem = max(0, single_cap - paid)
    return SingleOrderStockInfo(
        limited=True, total_stock=cap, subscription_meals=sub, paid_single_portions=paid, remaining=rem
    )


def assert_single_order_stock_available(db: Session, dish_id: int, menu_date: date, quantity: int) -> None:
    info = single_order_stock_for_dish_date(db, dish_id, menu_date)
    if not info.limited or info.remaining is None:
        return
    if quantity > int(info.remaining):
        raise HTTPException(
            status_code=400,
            detail=f"该日单次卡剩余{info.remaining}份，请减少份数或改日再试",
        )


def set_weekly_slot_total_stock(db: Session, week_start: date, slot: int, total_stock: int | None) -> None:
    """更新周槽日总份；NULL=不限制。槽位须已有菜品行。"""
    if slot < 1 or slot > 7:
        raise HTTPException(status_code=400, detail="slot 须在 1～7 之间")
    anchor = _week_start(week_start)
    w = db.scalar(
        select(WeeklyMenuSlot).where(WeeklyMenuSlot.week_start == anchor, WeeklyMenuSlot.slot == slot)
    )
    if total_stock is None:
        if w is not None:
            w.total_stock = None
            db.commit()
        return
    if not w:
        raise HTTPException(status_code=400, detail="该日期槽位无菜品，请先选菜再设总库存")
    if total_stock < 0:
        raise HTTPException(status_code=400, detail="总库存不能为负数")
    w.total_stock = int(total_stock)
    db.commit()


def _paid_sums_for_dates_dishes(
    db: Session, dates: list[date], dish_ids: set[int]
) -> dict[tuple[date, int], int]:
    if not dates or not dish_ids:
        return {}
    rows = db.execute(
        select(SingleMealOrder.delivery_date, SingleMealOrder.dish_id, func.coalesce(func.sum(SingleMealOrder.quantity), 0))
        .where(
            SingleMealOrder.delivery_date.in_(dates),
            SingleMealOrder.dish_id.in_(dish_ids),
            SingleMealOrder.pay_status == "已支付",
        )
        .group_by(SingleMealOrder.delivery_date, SingleMealOrder.dish_id)
    ).all()
    return {(d, int(did)): int(s or 0) for d, did, s in rows}


def weekly_slot_stock_extras(
    db: Session, week_start_anchor: date, slot_payload: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """为每槽位附加 subscription_meals_for_day、single_stock_remaining；total_stock 由调用方自 payload 已带明。"""
    if not slot_payload:
        return []
    dates = [week_start_anchor + timedelta(days=i) for i in range(7)]
    sub_by_date = {d: subscription_total_meals_on_date(db, d) for d in dates}
    dish_ids: set[int] = set()
    for s in slot_payload:
        if s.get("dish_id") is not None:
            dish_ids.add(int(s["dish_id"]))
    paid = _paid_sums_for_dates_dishes(db, dates, dish_ids)
    out: list[dict[str, Any]] = []
    for s in slot_payload:
        sl = int(s.get("slot", 0) or 0)
        menu_date = week_start_anchor + timedelta(days=sl - 1) if 1 <= sl <= 7 else week_start_anchor
        did = s.get("dish_id")
        base = {**s}
        if did is None:
            base["total_stock"] = None
            base["subscription_meals_for_day"] = 0
            base["single_stock_remaining"] = None
            out.append(base)
            continue
        did_i = int(did)
        scheduled = resolve_dish_for_calendar_date(db, menu_date)
        sub = sub_by_date.get(menu_date, 0) if scheduled and int(scheduled.id) == did_i else 0
        paid_n = paid.get((menu_date, did_i), 0)
        base["subscription_meals_for_day"] = sub
        cap_raw = s.get("total_stock")
        if cap_raw is None:
            base["total_stock"] = None
            base["single_stock_remaining"] = None
        else:
            cap = int(cap_raw)
            base["total_stock"] = cap
            single_cap = max(0, cap - sub)
            base["single_stock_remaining"] = max(0, single_cap - paid_n)
        out.append(base)
    return out
