"""后厨快捷设定：仅写入本周菜单对应营业日的「日总份数」。"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.delivery_calendar import is_subscription_delivery_day
from app.services.admin.menu_day_stock_service import sync_kitchen_planned_to_menu_day_total_stock

if TYPE_CHECKING:
    from app.services.admin.day_stock_service import DayStockBreakdown


def set_menu_day_total_stock_by_business_date(
    db: Session,
    *,
    store_id: int,
    business_date: date,
    total_stock: int,
    meal_period: str = "lunch",
    updated_by: str | None = None,
) -> tuple[int, DayStockBreakdown | None]:
    """与「本周菜单配置」日总份数同源；槽位无菜品时拒绝保存。返回 (日总份数, 最新拆解)。"""
    from app.services.meal_period.normalize import normalize_meal_period
    from app.services.admin.day_stock_service import (
        get_day_stock_breakdown,
        invalidate_stock_read_caches,
        sync_store_kitchen_plan_row,
    )

    total = max(0, int(total_stock))
    period = normalize_meal_period(meal_period)
    sid = int(store_id)
    if not is_subscription_delivery_day(business_date):
        bd = get_day_stock_breakdown(
            db, store_id=sid, business_date=business_date, meal_period=period
        )
        return total, bd
    synced = sync_kitchen_planned_to_menu_day_total_stock(
        db,
        store_id=sid,
        business_date=business_date,
        planned_total=total,
        meal_period=period,
    )
    if not synced:
        raise HTTPException(
            status_code=400,
            detail="该日菜单未排菜，请先在「本周菜单」选择菜品后再设日总份数",
        )
    sync_store_kitchen_plan_row(
        db,
        store_id=sid,
        business_date=business_date,
        meal_period=period,
        planned_total=total,
        updated_by=updated_by,
    )
    db.commit()
    # 写后统一失效读缓存，并返回与小程序 / 顶卡同源的拆解
    invalidate_stock_read_caches(sid)
    bd = get_day_stock_breakdown(
        db, store_id=sid, business_date=business_date, meal_period=period
    )
    return total, bd
