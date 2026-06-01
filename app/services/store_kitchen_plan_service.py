"""后厨快捷设定：仅写入本周菜单对应营业日的「日总份数」。"""

from __future__ import annotations

from datetime import date

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.services.menu_day_stock_service import sync_kitchen_planned_to_menu_day_total_stock


def set_menu_day_total_stock_by_business_date(
    db: Session,
    *,
    store_id: int,
    business_date: date,
    total_stock: int,
) -> int:
    """与「本周菜单配置」日总份数同源；槽位无菜品时拒绝保存。"""
    total = max(0, int(total_stock))
    synced = sync_kitchen_planned_to_menu_day_total_stock(
        db,
        store_id=int(store_id),
        business_date=business_date,
        planned_total=total,
    )
    if not synced:
        raise HTTPException(
            status_code=400,
            detail="该日菜单未排菜，请先在「本周菜单」选择菜品后再设日总份数",
        )
    db.commit()
    # 顶卡 dashboard-summary 有 90s 锚点缓存，保存后需失效以免仍展示旧「日总份数」
    from app.services.admin_service import invalidate_dashboard_live_summary_cache

    invalidate_dashboard_live_summary_cache(int(store_id))
    return total
