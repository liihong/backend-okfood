"""取出某一餐要扣的包装份数。

只读后厨出餐。日总份已经含订阅和单次，卖出的和包好没卖出的都在里面，
所以这里不能再加到家、自提、单次，否则同一份餐会扣两次耗材。
日总份为空时才退回实发份数，并让调用方在消息里说明少计了未售出的包装。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from app.services.admin.day_stock_service import get_day_stock_breakdown
from app.services.admin.menu_day_stock_service import weekly_menu_day_total_stock
from app.services.packaging.constants import PORTION_SOURCE_DELIVERED, PORTION_SOURCE_KITCHEN


@dataclass(frozen=True)
class MealPortions:
    portions: int
    source: str
    kitchen_output: int | None


def resolve_portion_basis(kitchen_output: int | None, delivered_portions: int) -> tuple[int, str]:
    """后厨出餐优先。0 也是有效值，表示这餐确定没包，不再改用实发份数。"""
    if kitchen_output is not None:
        return max(0, int(kitchen_output)), PORTION_SOURCE_KITCHEN
    return max(0, int(delivered_portions)), PORTION_SOURCE_DELIVERED


def delivered_portions_from_breakdown(breakdown) -> int:
    """实发 = 到家待送 + 到家已送 + 自提 + 已付单次。待送和已送是同一批人的两半。"""
    return (
        int(breakdown.delivery_total)
        + int(breakdown.pickup_total)
        + int(breakdown.single_retail_total)
    )


def meal_portions(db: Session, *, store_id: int, biz_date: date, meal_period: str) -> MealPortions:
    """读取这一餐的扣库份数。不写任何库存。"""
    kitchen = weekly_menu_day_total_stock(
        db, biz_date, store_id=int(store_id), meal_period=meal_period
    )
    if kitchen is not None:
        portions, source = resolve_portion_basis(int(kitchen), 0)
        return MealPortions(portions=portions, source=source, kitchen_output=int(kitchen))
    breakdown = get_day_stock_breakdown(
        db, store_id=int(store_id), business_date=biz_date, meal_period=meal_period
    )
    delivered = delivered_portions_from_breakdown(breakdown)
    portions, source = resolve_portion_basis(None, delivered)
    return MealPortions(portions=portions, source=source, kitchen_output=None)
