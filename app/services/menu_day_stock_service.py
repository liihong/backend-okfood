"""日菜单总库存存于 weekly_menu_slot.total_stock。单次卡剩余=总份数−应配送(与配送大表一致)−已付单次。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Iterable

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.delivery_calendar import is_subscription_delivery_day
from app.models.menu_dish import MenuDish
from app.models.menu_schedule import MenuSchedule
from app.models.single_meal_order import SingleMealOrder
from app.models.weekly_menu_slot import WeeklyMenuSlot
from app.services.delivery_sheet_service import (
    _total_meal_units_locked_date_sql,
    meal_units_totals_for_delivery_dates,
    total_meal_units_sql_sum_only,
)


def _week_start(d: date) -> date:
    return d - timedelta(days=d.weekday())


def scheduled_dish_id_for_calendar_date(db: Session, menu_date: date, *, store_id: int) -> int | None:
    """某日排期菜品 id：按日排期优先，否则周槽；无排期则 None。仅查 id，供库存/比对用。"""
    sid = int(store_id)
    sched_id = db.scalar(
        select(MenuSchedule.dish_id).where(
            MenuSchedule.menu_date == menu_date,
            MenuSchedule.store_id == sid,
        )
    )
    if sched_id is not None:
        return int(sched_id)
    anchor = _week_start(menu_date)
    slot = menu_date.weekday() + 1
    slot_dish = db.scalar(
        select(WeeklyMenuSlot.dish_id).where(
            WeeklyMenuSlot.store_id == sid,
            WeeklyMenuSlot.week_start == anchor,
            WeeklyMenuSlot.slot == slot,
        )
    )
    return int(slot_dish) if slot_dish is not None else None


def resolve_dish_for_calendar_date(db: Session, menu_date: date, *, store_id: int) -> MenuDish | None:
    """某日周槽位或按日排期上的菜品；无排期则 None。"""
    sid = int(store_id)
    anchor = _week_start(menu_date)
    slot = menu_date.weekday() + 1
    row = db.execute(
        select(WeeklyMenuSlot, MenuDish)
        .join(MenuDish, WeeklyMenuSlot.dish_id == MenuDish.id)
        .where(
            WeeklyMenuSlot.store_id == sid,
            WeeklyMenuSlot.week_start == anchor,
            WeeklyMenuSlot.slot == slot,
        )
    ).first()
    if row:
        return row[1]
    row2 = db.execute(
        select(MenuSchedule, MenuDish)
        .join(MenuDish, MenuSchedule.dish_id == MenuDish.id)
        .where(MenuSchedule.menu_date == menu_date, MenuSchedule.store_id == sid)
    ).first()
    if row2:
        return row2[1]
    return None


def subscription_total_meals_on_date(db: Session, menu_date: date, *, store_id: int) -> int:
    """当日应配送份数（到家+自提，含已送后不再应送仍在大表者；与 ``build_delivery_sheet`` 合计一致；非法定配送日则为 0）。

    菜单/库存读路径：未锁单走 SQL SUM；已锁单走冻结名单聚合，避免 ``total_meal_units_for_delivery_sheet`` 内重复全量推单探测。
    """
    from app.services.delivery_day_lock_service import is_delivery_day_sheet_locked

    sid = int(store_id)
    d = menu_date
    if not is_delivery_day_sheet_locked(db, store_id=sid, delivery_date=d):
        return total_meal_units_sql_sum_only(db, delivery_date=d, store_id=sid)
    return _total_meal_units_locked_date_sql(db, delivery_date=d, store_id=sid)


def subscription_total_meals_by_dates(
    db: Session, dates: Iterable[date], *, store_id: int
) -> dict[date, int]:
    """批量计算多日应配送份数；与配送大表 ``meal_units_totals_for_delivery_dates`` 同源。"""
    return meal_units_totals_for_delivery_dates(db, dates=dates, store_id=int(store_id))


def resolve_dishes_for_dates_batch(
    db: Session, dates: Iterable[date], *, store_id: int
) -> dict[date, MenuDish | None]:
    """批量解析日历日对应菜品：按日排期优先，否则取周槽位。"""
    unique_dates = sorted({d for d in dates})
    if not unique_dates:
        return {}
    sid = int(store_id)
    out: dict[date, MenuDish | None] = {d: None for d in unique_dates}

    sched_rows = db.execute(
        select(MenuSchedule.menu_date, MenuDish)
        .join(MenuDish, MenuSchedule.dish_id == MenuDish.id)
        .where(MenuSchedule.store_id == sid, MenuSchedule.menu_date.in_(unique_dates))
    ).all()
    for menu_date, dish in sched_rows:
        out[menu_date] = dish

    week_starts: set[date] = set()
    pending: list[tuple[date, date, int]] = []
    for d in unique_dates:
        if out[d] is not None:
            continue
        anchor = _week_start(d)
        slot = d.weekday() + 1
        week_starts.add(anchor)
        pending.append((d, anchor, slot))

    if week_starts:
        slot_rows = db.execute(
            select(WeeklyMenuSlot.week_start, WeeklyMenuSlot.slot, MenuDish)
            .join(MenuDish, WeeklyMenuSlot.dish_id == MenuDish.id)
            .where(WeeklyMenuSlot.store_id == sid, WeeklyMenuSlot.week_start.in_(week_starts))
        ).all()
        slot_map = {(ws, sl): dish for ws, sl, dish in slot_rows}
        for menu_date, anchor, slot in pending:
            out[menu_date] = slot_map.get((anchor, slot))
    return out


def weekly_menu_day_total_stock(db: Session, menu_date: date, *, store_id: int) -> int | None:
    """业务日对应周菜单槽位「日总份数」（与本周菜单配置同源）；未排菜或未填则 None。"""
    sid = int(store_id)
    anchor = _week_start(menu_date)
    slot = menu_date.weekday() + 1
    w = db.scalar(
        select(WeeklyMenuSlot).where(
            WeeklyMenuSlot.store_id == sid,
            WeeklyMenuSlot.week_start == anchor,
            WeeklyMenuSlot.slot == slot,
        )
    )
    if w is None or w.dish_id is None or w.total_stock is None:
        return None
    return max(0, int(w.total_stock))


def paid_single_portions_sum(db: Session, dish_id: int, menu_date: date, *, store_id: int) -> int:
    sid = int(store_id)
    v = db.scalar(
        select(func.coalesce(func.sum(SingleMealOrder.quantity), 0)).where(
            SingleMealOrder.delivery_date == menu_date,
            SingleMealOrder.dish_id == dish_id,
            SingleMealOrder.pay_status == "已支付",
            SingleMealOrder.store_id == sid,
        )
    )
    return int(v or 0)


def weekly_slot_row_for_dish_date(
    db: Session, dish_id: int, menu_date: date, *, store_id: int
) -> WeeklyMenuSlot | None:
    """与单次点餐同周槽+同一道菜的行；仅周排期有库存字段。"""
    sid = int(store_id)
    anchor = _week_start(menu_date)
    slot = menu_date.weekday() + 1
    return db.scalar(
        select(WeeklyMenuSlot).where(
            WeeklyMenuSlot.store_id == sid,
            WeeklyMenuSlot.week_start == anchor,
            WeeklyMenuSlot.slot == slot,
            WeeklyMenuSlot.dish_id == dish_id,
        )
    )


@dataclass(frozen=True)
class SingleOrderStockInfo:
    """周槽 total_stock 为 NULL 或纯按日排期无周槽时，单次卡剩余为 0（不可售）。"""

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


def single_order_stock_for_dish_date(
    db: Session, dish_id: int, menu_date: date, *, store_id: int
) -> SingleOrderStockInfo:
    sid = int(store_id)
    did = int(dish_id)
    w = weekly_slot_row_for_dish_date(db, did, menu_date, store_id=sid)
    scheduled_id = scheduled_dish_id_for_calendar_date(db, menu_date, store_id=sid)
    # 仅当该日为当前菜品供餐时才统计订阅占用（避免无关日触发配送大表级聚合）
    sub = (
        subscription_total_meals_on_date(db, menu_date, store_id=sid)
        if scheduled_id is not None and scheduled_id == did
        else 0
    )
    paid = paid_single_portions_sum(db, did, menu_date, store_id=sid)
    if w is None or w.total_stock is None:
        return SingleOrderStockInfo(
            limited=True, total_stock=None, subscription_meals=sub, paid_single_portions=paid, remaining=0
        )
    cap = int(w.total_stock or 0)
    single_cap = max(0, cap - sub)
    rem = max(0, single_cap - paid)
    return SingleOrderStockInfo(
        limited=True, total_stock=cap, subscription_meals=sub, paid_single_portions=paid, remaining=rem
    )


def single_order_stock_by_date_for_week(
    db: Session,
    *,
    week_start_anchor: date,
    dates: list[date],
    dishes_by_date: dict[date, MenuDish],
    weekly_slot_rows: Iterable[tuple[WeeklyMenuSlot, MenuDish]],
    store_id: int,
    subscription_floor_date: date | None,
) -> dict[date, SingleOrderStockInfo]:
    """与逐日调用 `single_order_stock_for_dish_date` 结果一致：预取订阅份数 / 已付单次，避免一周内重复查库与子查询。

    `dishes_by_date` 必须与 `GET /api/menu/weekly` 的周槽+按日补全合并结果一致；
    `weekly_slot_rows` 须为当周 `WeeklyMenuSlot` JOIN `MenuDish` 的原始行。

    ``subscription_floor_date``：早于该日历日的供餐日将 ``subscription_meals`` 视为 0（不跑会员履约统计），列表页加速用；当日及之后与全量计算一致。精确库存以下单/详情接口为准。
    """

    sid = int(store_id)
    if not dates:
        return {}

    # 早于 subscription_floor（通常为上海业务『今天』）的供餐日不再扫会员履约份数：已过日不可下单，省去最贵查询。
    subscription_floor = subscription_floor_date

    ws_by_day_dish: dict[tuple[date, int], WeeklyMenuSlot] = {}
    for ws, od in weekly_slot_rows:
        day = week_start_anchor + timedelta(days=int(ws.slot) - 1)
        ws_by_day_dish[(day, int(od.id))] = ws

    dates_needing_sub = [d for d in dates if subscription_floor is None or d >= subscription_floor]
    sub_by_date = subscription_total_meals_by_dates(db, dates_needing_sub, store_id=sid)
    for d in dates:
        if subscription_floor is not None and d < subscription_floor:
            sub_by_date[d] = 0
    dish_ids: set[int] = {int(dis.id) for dis in dishes_by_date.values() if dis is not None}
    paid = _paid_sums_for_dates_dishes(db, dates, dish_ids, store_id=sid)

    out: dict[date, SingleOrderStockInfo] = {}
    for d in dates:
        dish = dishes_by_date.get(d)
        if dish is None:
            continue
        did = int(dish.id)
        w = ws_by_day_dish.get((d, did))
        sub = int(sub_by_date.get(d, 0))
        paid_n = int(paid.get((d, did), 0))
        if w is None or w.total_stock is None:
            out[d] = SingleOrderStockInfo(
                limited=True, total_stock=None, subscription_meals=sub, paid_single_portions=paid_n, remaining=0
            )
        else:
            cap = int(w.total_stock or 0)
            single_cap = max(0, cap - sub)
            rem = max(0, single_cap - paid_n)
            out[d] = SingleOrderStockInfo(
                limited=True, total_stock=cap, subscription_meals=sub, paid_single_portions=paid_n, remaining=rem
            )
    return out


def assert_single_order_stock_available(
    db: Session, dish_id: int, menu_date: date, quantity: int, *, store_id: int
) -> None:
    info = single_order_stock_for_dish_date(db, dish_id, menu_date, store_id=int(store_id))
    rem = 0 if info.remaining is None else int(info.remaining)
    if rem <= 0:
        raise HTTPException(status_code=400, detail="该日单次卡已无库存，请改日再试")
    if quantity > rem:
        raise HTTPException(
            status_code=400,
            detail=f"该日单次卡剩余{rem}份，请减少份数或改日再试",
        )


def sync_kitchen_planned_to_menu_day_total_stock(
    db: Session,
    *,
    store_id: int,
    business_date: date,
    planned_total: int,
) -> bool:
    """后厨计划联动：写入营业日对应周槽「日总份数」；槽位无菜品则跳过。"""
    sid = int(store_id)
    anchor = _week_start(business_date)
    slot = business_date.weekday() + 1
    w = db.scalar(
        select(WeeklyMenuSlot).where(
            WeeklyMenuSlot.store_id == sid,
            WeeklyMenuSlot.week_start == anchor,
            WeeklyMenuSlot.slot == slot,
        )
    )
    if w is None or w.dish_id is None:
        return False
    w.total_stock = max(0, int(planned_total))
    return True


def set_weekly_slot_total_stock(
    db: Session, week_start: date, slot: int, total_stock: int | None, *, store_id: int
) -> None:
    """更新周槽日总份；NULL=未配置（单次卡不可售）。槽位须已有菜品行。"""
    if slot < 1 or slot > 7:
        raise HTTPException(status_code=400, detail="slot 须在 1～7 之间")
    sid = int(store_id)
    anchor = _week_start(week_start)
    w = db.scalar(
        select(WeeklyMenuSlot).where(
            WeeklyMenuSlot.store_id == sid,
            WeeklyMenuSlot.week_start == anchor,
            WeeklyMenuSlot.slot == slot,
        )
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
    db: Session, dates: list[date], dish_ids: set[int], *, store_id: int
) -> dict[tuple[date, int], int]:
    if not dates or not dish_ids:
        return {}
    sid = int(store_id)
    rows = db.execute(
        select(
            SingleMealOrder.delivery_date,
            SingleMealOrder.dish_id,
            func.coalesce(func.sum(SingleMealOrder.quantity), 0),
        )
        .where(
            SingleMealOrder.delivery_date.in_(dates),
            SingleMealOrder.dish_id.in_(dish_ids),
            SingleMealOrder.pay_status == "已支付",
            SingleMealOrder.store_id == sid,
        )
        .group_by(SingleMealOrder.delivery_date, SingleMealOrder.dish_id)
    ).all()
    return {(d, int(did)): int(s or 0) for d, did, s in rows}


def weekly_slot_stock_extras(
    db: Session,
    week_start_anchor: date,
    slot_payload: list[dict[str, Any]],
    *,
    store_id: int,
    sub_by_date: dict[date, int] | None = None,
    scheduled_by_date: dict[date, MenuDish | None] | None = None,
    paid: dict[tuple[date, int], int] | None = None,
    skip_subscription_stats: bool = False,
) -> list[dict[str, Any]]:
    """为每槽位附加 subscription_meals_for_day、single_retail_paid_portions、single_stock_remaining；total_stock 由调用方自 payload 已带明。

    ``skip_subscription_stats=True`` 时不查会员履约/已付单次（下周预告维护用，显著减库压）。
    """
    if not slot_payload:
        return []
    sid = int(store_id)
    dates = [week_start_anchor + timedelta(days=i) for i in range(7)]
    if skip_subscription_stats:
        sub_by_date = {}
        scheduled_by_date = {}
        paid = {}
    else:
        if sub_by_date is None:
            sub_by_date = subscription_total_meals_by_dates(db, dates, store_id=sid)
        if scheduled_by_date is None:
            scheduled_by_date = resolve_dishes_for_dates_batch(db, dates, store_id=sid)
        dish_ids: set[int] = set()
        for s in slot_payload:
            if s.get("dish_id") is not None:
                dish_ids.add(int(s["dish_id"]))
        if paid is None:
            paid = _paid_sums_for_dates_dishes(db, dates, dish_ids, store_id=sid)
    out: list[dict[str, Any]] = []
    for s in slot_payload:
        sl = int(s.get("slot", 0) or 0)
        menu_date = week_start_anchor + timedelta(days=sl - 1) if 1 <= sl <= 7 else week_start_anchor
        did = s.get("dish_id")
        base = {**s}
        if did is None:
            base["total_stock"] = None
            base["subscription_meals_for_day"] = None if skip_subscription_stats else 0
            base["single_retail_paid_portions"] = None
            base["single_stock_remaining"] = None
            out.append(base)
            continue
        if skip_subscription_stats:
            base["subscription_meals_for_day"] = None
            base["single_retail_paid_portions"] = None
            base["single_stock_remaining"] = None
            out.append(base)
            continue
        did_i = int(did)
        scheduled = scheduled_by_date.get(menu_date)
        sub = sub_by_date.get(menu_date, 0) if scheduled and int(scheduled.id) == did_i else 0
        paid_n = paid.get((menu_date, did_i), 0)
        base["subscription_meals_for_day"] = sub
        base["single_retail_paid_portions"] = paid_n
        cap_raw = s.get("total_stock")
        if cap_raw is None:
            base["total_stock"] = None
            base["single_stock_remaining"] = 0
        else:
            cap = int(cap_raw)
            base["total_stock"] = cap
            single_cap = max(0, cap - sub)
            base["single_stock_remaining"] = max(0, single_cap - paid_n)
        out.append(base)
    return out
