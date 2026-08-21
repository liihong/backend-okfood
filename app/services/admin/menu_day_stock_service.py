"""日菜单总库存存于 weekly_menu_slot.total_stock。

单次可售剩余统一由 ``day_stock_service.get_day_stock_breakdown`` 计算，
本模块仅做组装与批量查询，禁止手写 cap-sub-paid 公式。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import TYPE_CHECKING, Any, Iterable

from fastapi import HTTPException
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.core.delivery_calendar import is_subscription_delivery_day
from app.core.timeutil import today_shanghai
from app.models.menu_dish import MenuDish
from app.models.menu_schedule import MenuSchedule
from app.models.single_meal_order import SingleMealOrder
from app.models.weekly_menu_slot import WeeklyMenuSlot
from app.models.enums import MealPeriod
from app.services.meal_period.constants import DEFAULT_MEAL_PERIOD
from app.services.meal_period.normalize import normalize_meal_period
from app.services.delivery.delivery_sheet_service import (
    DeliverySheetDayMetrics,
    _total_meal_units_locked_date_sql,
    delivery_sheet_metrics_for_date,
    delivery_sheet_metrics_for_period,
    delivery_sheet_metrics_pending_sql_for_future_date,
    delivery_sheet_metrics_via_sql_for_unlocked_date,
    meal_units_totals_for_delivery_dates,
    total_meal_units_sql_sum_only,
)


if TYPE_CHECKING:
    from app.services.admin.day_stock_service import DayStockBreakdown


def invalidate_menu_day_stock_read_caches(store_id: int | None = None) -> None:
    """库存写操作后占位失效（跨请求进程内缓存已移除，保留接口供调用方统一触发仪表盘缓存清理）。"""
    _ = store_id


def _week_start(d: date) -> date:
    return d - timedelta(days=d.weekday())


def scheduled_dish_id_for_calendar_date(
    db: Session, menu_date: date, *, store_id: int, meal_period: str = DEFAULT_MEAL_PERIOD
) -> int | None:
    """某日排期菜品 id：按日排期优先，否则周槽；无排期则 None。仅查 id，供库存/比对用。"""
    sid = int(store_id)
    period = normalize_meal_period(meal_period)
    sched_id = db.scalar(
        select(MenuSchedule.dish_id).where(
            MenuSchedule.menu_date == menu_date,
            MenuSchedule.store_id == sid,
            MenuSchedule.meal_period == period,
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
            WeeklyMenuSlot.meal_period == period,
        )
    )
    return int(slot_dish) if slot_dish is not None else None


def resolve_dish_for_calendar_date(
    db: Session, menu_date: date, *, store_id: int, meal_period: str = DEFAULT_MEAL_PERIOD
) -> MenuDish | None:
    """某日周槽位或按日排期上的菜品；无排期则 None。"""
    sid = int(store_id)
    period = normalize_meal_period(meal_period)
    anchor = _week_start(menu_date)
    slot = menu_date.weekday() + 1
    row = db.execute(
        select(WeeklyMenuSlot, MenuDish)
        .join(MenuDish, WeeklyMenuSlot.dish_id == MenuDish.id)
        .where(
            WeeklyMenuSlot.store_id == sid,
            WeeklyMenuSlot.week_start == anchor,
            WeeklyMenuSlot.slot == slot,
            WeeklyMenuSlot.meal_period == period,
        )
    ).first()
    if row:
        return row[1]
    row2 = db.execute(
        select(MenuSchedule, MenuDish)
        .join(MenuDish, MenuSchedule.dish_id == MenuDish.id)
        .where(
            MenuSchedule.menu_date == menu_date,
            MenuSchedule.store_id == sid,
            MenuSchedule.meal_period == period,
        )
    ).first()
    if row2:
        return row2[1]
    return None


def subscription_total_meals_on_date(db: Session, menu_date: date, *, store_id: int) -> int:
    """当日应配送份数（到家+自提，含已送后不再应送仍在大表者；与 ``build_delivery_sheet`` 合计一致；非法定配送日则为 0）。

    菜单/库存读路径：未锁单走 SQL SUM；已锁单走冻结名单聚合，避免 ``total_meal_units_for_delivery_sheet`` 内重复全量推单探测。
    """
    from app.services.delivery.delivery_day_lock_service import is_delivery_day_sheet_frozen_after_sf_push

    sid = int(store_id)
    d = menu_date
    if not is_delivery_day_sheet_frozen_after_sf_push(
        db, store_id=sid, delivery_date=d
    ):
        return total_meal_units_sql_sum_only(db, delivery_date=d, store_id=sid)
    return _total_meal_units_locked_date_sql(db, delivery_date=d, store_id=sid)


def subscription_total_meals_by_dates(
    db: Session, dates: Iterable[date], *, store_id: int
) -> dict[date, int]:
    """批量计算多日应配送份数；与配送大表 ``meal_units_totals_for_delivery_dates`` 同源。"""
    return meal_units_totals_for_delivery_dates(db, dates=dates, store_id=int(store_id))


def dashboard_meal_totals_by_dates(
    db: Session,
    dates: Iterable[date],
    *,
    store_id: int,
    meal_period: str = DEFAULT_MEAL_PERIOD,
    metrics_cache: dict | None = None,
) -> dict[date, int]:
    """与营业概览备餐份数（meal_total）同源，按餐段拆分。"""
    sid = int(store_id)
    period = normalize_meal_period(meal_period)
    uniq = list(dict.fromkeys(dates))
    if not uniq:
        return {}

    cache = metrics_cache if metrics_cache is not None else {}
    out: dict[date, int] = {}
    for d in uniq:
        m = delivery_sheet_metrics_for_period(
            db,
            delivery_date=d,
            store_id=sid,
            meal_period=period,
            metrics_cache=cache,
        )
        out[d] = int(m.meal_total)
    return out


# 单次零售库存占用：仅系统取消(cancelled)不计入；顺丰取消(sf_cancelled)仍占用
SINGLE_RETAIL_INVENTORY_EXCLUDED_FULFILLMENT = ("cancelled",)
_SINGLE_RETAIL_EXCLUDED_FULFILLMENT = SINGLE_RETAIL_INVENTORY_EXCLUDED_FULFILLMENT


def _single_retail_inventory_scope_filters(*, store_id: int) -> list:
    """单次零售占用库存口径：已支付未取消 + 未支付待支付；已取消/已退款不计入。"""
    sid = int(store_id)
    return [
        or_(
            and_(
                SingleMealOrder.store_id == sid,
                SingleMealOrder.pay_status == "已支付",
                SingleMealOrder.fulfillment_status.notin_(_SINGLE_RETAIL_EXCLUDED_FULFILLMENT),
            ),
            and_(
                SingleMealOrder.store_id == sid,
                SingleMealOrder.pay_status == "未支付",
                SingleMealOrder.fulfillment_status == "pending",
            ),
        )
    ]


def paid_single_retail_portions_by_dates(
    db: Session, dates: Iterable[date], *, store_id: int, meal_period: str = DEFAULT_MEAL_PERIOD
) -> dict[date, int]:
    """供餐日单次零售占用库存份数（按餐段）。"""
    uniq = list(dict.fromkeys(dates))
    if not uniq:
        return {}
    sid = int(store_id)
    period = normalize_meal_period(meal_period)

    rows = db.execute(
        select(
            SingleMealOrder.delivery_date,
            func.coalesce(func.sum(SingleMealOrder.quantity), 0),
        )
        .where(
            SingleMealOrder.delivery_date.in_(uniq),
            SingleMealOrder.meal_period == period,
            *_single_retail_inventory_scope_filters(store_id=sid),
        )
        .group_by(SingleMealOrder.delivery_date)
    ).all()
    out = {d: 0 for d in uniq}
    for d, qty in rows:
        if d is not None:
            out[d] = int(qty or 0)
    return out


def resolve_dishes_for_dates_batch(
    db: Session,
    dates: Iterable[date],
    *,
    store_id: int,
    meal_period: str = DEFAULT_MEAL_PERIOD,
) -> dict[date, MenuDish | None]:
    """批量解析日历日对应菜品：按日排期优先，否则取周槽位；须指定 meal_period 避免午/晚餐混读。"""
    unique_dates = sorted({d for d in dates})
    if not unique_dates:
        return {}
    sid = int(store_id)
    period = normalize_meal_period(meal_period)
    out: dict[date, MenuDish | None] = {d: None for d in unique_dates}

    sched_rows = db.execute(
        select(MenuSchedule.menu_date, MenuDish)
        .join(MenuDish, MenuSchedule.dish_id == MenuDish.id)
        .where(
            MenuSchedule.store_id == sid,
            MenuSchedule.menu_date.in_(unique_dates),
            MenuSchedule.meal_period == period,
        )
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
            .where(
                WeeklyMenuSlot.store_id == sid,
                WeeklyMenuSlot.week_start.in_(week_starts),
                WeeklyMenuSlot.meal_period == period,
            )
        ).all()
        slot_map = {(ws, sl): dish for ws, sl, dish in slot_rows}
        for menu_date, anchor, slot in pending:
            out[menu_date] = slot_map.get((anchor, slot))
    return out


def weekly_menu_lunch_day_total_stock(db: Session, menu_date: date, *, store_id: int) -> int | None:
    """营业概览午餐顶卡「后厨产出量」：仅读 weekly_menu_slot.meal_period=lunch。"""
    return weekly_menu_day_total_stock(
        db, menu_date, store_id=store_id, meal_period=MealPeriod.LUNCH.value
    )


def weekly_menu_dinner_day_total_stock(db: Session, menu_date: date, *, store_id: int) -> int | None:
    """营业概览晚餐顶卡「后厨产出量」：仅读 weekly_menu_slot.meal_period=dinner。"""
    return weekly_menu_day_total_stock(
        db, menu_date, store_id=store_id, meal_period=MealPeriod.DINNER.value
    )


def weekly_menu_day_total_stock(
    db: Session, menu_date: date, *, store_id: int, meal_period: str = DEFAULT_MEAL_PERIOD
) -> int | None:
    """业务日对应周菜单槽位「日总份数」（后厨出餐）；须显式传入 meal_period 区分午/晚餐。"""
    sid = int(store_id)
    period = normalize_meal_period(meal_period)
    anchor = _week_start(menu_date)
    slot = menu_date.weekday() + 1
    w = db.scalar(
        select(WeeklyMenuSlot).where(
            WeeklyMenuSlot.store_id == sid,
            WeeklyMenuSlot.week_start == anchor,
            WeeklyMenuSlot.slot == slot,
            WeeklyMenuSlot.meal_period == period,
        )
    )
    if w is None or w.dish_id is None or w.total_stock is None:
        return None
    return max(0, int(w.total_stock))


def paid_single_portions_sum(
    db: Session, dish_id: int, menu_date: date, *, store_id: int, meal_period: str = DEFAULT_MEAL_PERIOD
) -> int:
    """指定餐段、菜品、供餐日的已付单次零售份数（与 paid_single_retail_portions_by_dates 同源）。"""
    sid = int(store_id)
    period = normalize_meal_period(meal_period)
    v = db.scalar(
        select(func.coalesce(func.sum(SingleMealOrder.quantity), 0)).where(
            SingleMealOrder.delivery_date == menu_date,
            SingleMealOrder.dish_id == dish_id,
            SingleMealOrder.meal_period == period,
            *_single_retail_inventory_scope_filters(store_id=sid),
        )
    )
    return int(v or 0)


def weekly_slot_row_for_dish_date(
    db: Session, dish_id: int, menu_date: date, *, store_id: int, meal_period: str = DEFAULT_MEAL_PERIOD
) -> WeeklyMenuSlot | None:
    """与单次点餐同周槽+同一道菜的行；仅周排期有库存字段。"""
    sid = int(store_id)
    period = normalize_meal_period(meal_period)
    anchor = _week_start(menu_date)
    slot = menu_date.weekday() + 1
    return db.scalar(
        select(WeeklyMenuSlot).where(
            WeeklyMenuSlot.store_id == sid,
            WeeklyMenuSlot.week_start == anchor,
            WeeklyMenuSlot.slot == slot,
            WeeklyMenuSlot.dish_id == dish_id,
            WeeklyMenuSlot.meal_period == period,
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


def _single_order_stock_info_from_breakdown(
    breakdown,
    *,
    total_stock: int | None,
    business_date: date,
    subscription_floor: date | None = None,
) -> SingleOrderStockInfo:
    """由 ``get_day_stock_breakdown`` 构造单次可售信息，禁止在此处重复写剩余公式。"""
    from app.services.admin.day_stock_service import resolve_single_stock_remaining_display

    sub = int(breakdown.delivery_total) + int(breakdown.pickup_total)
    paid = int(breakdown.single_retail_total)
    rem = resolve_single_stock_remaining_display(
        breakdown,
        business_date=business_date,
        total_stock=total_stock,
        subscription_floor=subscription_floor,
    )
    return SingleOrderStockInfo(
        limited=True,
        total_stock=None if total_stock is None else int(total_stock),
        subscription_meals=sub,
        paid_single_portions=paid,
        remaining=rem,
    )


def single_order_stock_for_dish_date(
    db: Session,
    dish_id: int,
    menu_date: date,
    *,
    store_id: int,
    meal_period: str = DEFAULT_MEAL_PERIOD,
) -> SingleOrderStockInfo:
    from app.services.admin.day_stock_service import get_day_stock_breakdown

    sid = int(store_id)
    period = normalize_meal_period(meal_period)
    did = int(dish_id)
    w = weekly_slot_row_for_dish_date(db, did, menu_date, store_id=sid, meal_period=period)
    cap = None if w is None or w.total_stock is None else int(w.total_stock or 0)
    breakdown = get_day_stock_breakdown(db, store_id=sid, business_date=menu_date, meal_period=period)
    return _single_order_stock_info_from_breakdown(
        breakdown,
        total_stock=cap,
        business_date=menu_date,
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
    meal_period: str = DEFAULT_MEAL_PERIOD,
) -> dict[date, SingleOrderStockInfo]:
    """与逐日调用 `single_order_stock_for_dish_date` 结果一致：预取营业概览同源备餐份数 / 当日已付单次零售合计。

    `dishes_by_date` 必须与 `GET /api/menu/weekly` 的周槽+按日补全合并结果一致；
    `weekly_slot_rows` 须为当周 `WeeklyMenuSlot` JOIN `MenuDish` 的原始行（同一 meal_period）。

    ``subscription_floor_date``：早于该日历日的供餐日不扫会员履约份数，且 ``remaining`` 固定为 0（已过日不可下单；若仍按 sub=0 计算会虚高）。
    """

    sid = int(store_id)
    if not dates:
        return {}

    # 早于 subscription_floor（通常为上海业务『今天』）的供餐日不再扫会员履约份数：已过日不可下单，省去最贵查询。
    subscription_floor = subscription_floor_date
    # 须与调用方 get_weekly_menu(meal_period=…) 一致，禁止写死午餐导致晚餐库存串读
    period = normalize_meal_period(meal_period)

    ws_by_day_dish: dict[tuple[date, int], WeeklyMenuSlot] = {}
    for ws, od in weekly_slot_rows:
        day = week_start_anchor + timedelta(days=int(ws.slot) - 1)
        ws_by_day_dish[(day, int(od.id))] = ws

    from app.services.admin.day_stock_service import get_day_stock_breakdown_by_dates

    # 与营业概览 / 下单校验同源：批量拉拆解，禁止在此处手写 cap-sub-paid 公式
    breakdown_by_date = get_day_stock_breakdown_by_dates(
        db, store_id=sid, dates=dates, meal_period=period
    )

    out: dict[date, SingleOrderStockInfo] = {}
    for d in dates:
        dish = dishes_by_date.get(d)
        if dish is None:
            continue
        did = int(dish.id)
        w = ws_by_day_dish.get((d, did))
        cap = None if w is None or w.total_stock is None else int(w.total_stock or 0)
        breakdown = breakdown_by_date.get(d)
        if breakdown is None:
            continue
        out[d] = _single_order_stock_info_from_breakdown(
            breakdown,
            total_stock=cap,
            business_date=d,
            subscription_floor=subscription_floor,
        )
    return out


def assert_single_order_stock_available(
    db: Session,
    dish_id: int,
    menu_date: date,
    quantity: int,
    *,
    store_id: int,
    meal_period: str = DEFAULT_MEAL_PERIOD,
) -> None:
    info = single_order_stock_for_dish_date(
        db, dish_id, menu_date, store_id=int(store_id), meal_period=meal_period
    )
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
    meal_period: str = DEFAULT_MEAL_PERIOD,
) -> bool:
    """后厨计划联动：写入营业日对应周槽「日总份数」；槽位无菜品则跳过。"""
    sid = int(store_id)
    period = normalize_meal_period(meal_period)
    anchor = _week_start(business_date)
    slot = business_date.weekday() + 1
    w = db.scalar(
        select(WeeklyMenuSlot).where(
            WeeklyMenuSlot.store_id == sid,
            WeeklyMenuSlot.week_start == anchor,
            WeeklyMenuSlot.slot == slot,
            WeeklyMenuSlot.meal_period == period,
        )
    )
    if w is None or w.dish_id is None:
        return False
    w.total_stock = max(0, int(planned_total))
    return True


def set_weekly_slot_total_stock(
    db: Session,
    week_start: date,
    slot: int,
    total_stock: int | None,
    *,
    store_id: int,
    meal_period: str = DEFAULT_MEAL_PERIOD,
) -> DayStockBreakdown | None:
    """更新周槽日总份；NULL=未配置（单次卡不可售）。槽位须已有菜品行。返回最新日库存拆解。"""
    if slot < 1 or slot > 7:
        raise HTTPException(status_code=400, detail="slot 须在 1～7 之间")
    from app.services.meal_period.normalize import normalize_meal_period

    sid = int(store_id)
    # 写入路径严格校验餐段，避免 dinner 请求被静默当成 lunch 更新错槽位
    period = normalize_meal_period(meal_period)
    anchor = _week_start(week_start)
    w = db.scalar(
        select(WeeklyMenuSlot).where(
            WeeklyMenuSlot.store_id == sid,
            WeeklyMenuSlot.week_start == anchor,
            WeeklyMenuSlot.slot == slot,
            WeeklyMenuSlot.meal_period == period,
        )
    )
    if total_stock is None:
        if w is not None:
            w.total_stock = None
            db.commit()
            from app.services.admin.day_stock_service import invalidate_stock_read_caches

            invalidate_stock_read_caches(sid)
        return None
    if not w:
        raise HTTPException(status_code=400, detail="该日期槽位无菜品，请先选菜再设总库存")
    if total_stock < 0:
        raise HTTPException(status_code=400, detail="总库存不能为负数")
    w.total_stock = int(total_stock)
    menu_date = anchor + timedelta(days=slot - 1)
    from app.services.admin.day_stock_service import sync_store_kitchen_plan_row

    # 午/晚餐后厨出餐分字段存储：同步写入 store_kitchen_plans 对应餐段行
    sync_store_kitchen_plan_row(
        db,
        store_id=sid,
        business_date=menu_date,
        meal_period=period,
        planned_total=int(total_stock),
    )
    db.commit()
    from app.services.admin.day_stock_service import get_day_stock_breakdown, invalidate_stock_read_caches

    invalidate_stock_read_caches(sid)
    return get_day_stock_breakdown(
        db,
        store_id=sid,
        business_date=menu_date,
        meal_period=period,
    )


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
            *_single_retail_inventory_scope_filters(store_id=sid),
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
    meal_period: str = DEFAULT_MEAL_PERIOD,
    sub_by_date: dict[date, int] | None = None,
    scheduled_by_date: dict[date, MenuDish | None] | None = None,
    paid: dict[tuple[date, int], int] | None = None,
    paid_by_date: dict[date, int] | None = None,
    skip_subscription_stats: bool = False,
) -> list[dict[str, Any]]:
    """为每槽位附加 subscription_meals_for_day、single_retail_paid_portions、single_stock_remaining；total_stock 由调用方自 payload 已带。

    剩余份数统一由 ``resolve_single_stock_remaining_display`` 计算（与小程序 ``single_stock_remaining`` 同源）。

    ``skip_subscription_stats=True`` 时不查会员履约/已付单次（下周预告维护用，显著减库压）。
    """
    if not slot_payload:
        return []
    sid = int(store_id)
    period = normalize_meal_period(meal_period)
    dates = [week_start_anchor + timedelta(days=i) for i in range(7)]
    if skip_subscription_stats:
        breakdown_by_date: dict[date, Any] = {}
    else:
        from app.services.admin.day_stock_service import get_day_stock_breakdown_by_dates, resolve_single_stock_remaining_display

        # 与营业概览 / 小程序 / 下单校验同源：一次批量拉拆解，禁止在循环内逐槽位重算
        breakdown_by_date = get_day_stock_breakdown_by_dates(
            db, store_id=sid, dates=dates, meal_period=period
        )

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
        bd = breakdown_by_date.get(menu_date)
        if bd is None:
            base["subscription_meals_for_day"] = 0
            base["single_retail_paid_portions"] = 0
            base["single_stock_remaining"] = 0
            base["waste_total"] = 0
            out.append(base)
            continue
        base["subscription_meals_for_day"] = int(bd.delivery_total) + int(bd.pickup_total)
        base["single_retail_paid_portions"] = int(bd.single_retail_total)
        cap_raw = s.get("total_stock")
        if cap_raw is None:
            base["total_stock"] = None
            base["single_stock_remaining"] = 0
            base["waste_total"] = int(bd.waste_total)
        else:
            base["total_stock"] = int(cap_raw)
            base["single_stock_remaining"] = resolve_single_stock_remaining_display(
                bd,
                business_date=menu_date,
                total_stock=int(cap_raw),
            )
            base["waste_total"] = int(bd.waste_total)
        out.append(base)
    return out
