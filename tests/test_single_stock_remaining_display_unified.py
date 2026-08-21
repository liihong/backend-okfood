"""单次可售剩余展示：管理端周菜单与小程序详情须同源。"""

from datetime import date

import pytest
from sqlalchemy.orm import Session

from app.models.enums import MealPeriod
from app.services.admin.day_stock_service import DayStockBreakdown, resolve_single_stock_remaining_display
from app.services.admin.menu_day_stock_service import (
    single_order_stock_for_dish_date,
    weekly_slot_stock_extras,
)


def _mock_breakdown(*, kitchen: int, sub: int, paid: int, delta: int) -> DayStockBreakdown:
    rem = max(0, kitchen - sub - paid + delta)
    return DayStockBreakdown(
        meal_period=MealPeriod.LUNCH.value,
        kitchen_output=kitchen,
        delivery_total=sub,
        pickup_total=0,
        single_retail_total=paid,
        waste_total=max(0, -delta),
        adjustment_delta_sum=delta,
        remaining=rem,
    )


def test_resolve_single_stock_remaining_display_unconfigured_cap_is_zero():
    bd = _mock_breakdown(kitchen=100, sub=10, paid=2, delta=0)
    assert (
        resolve_single_stock_remaining_display(
            bd,
            business_date=date(2026, 6, 16),
            total_stock=None,
        )
        == 0
    )


def test_weekly_slot_and_detail_share_resolve_display(db: Session, monkeypatch):
    """管理端 weekly-slots 与小程序 detail 须走同一展示出口。"""
    anchor = date(2026, 6, 16)
    menu_date = anchor
    bd = _mock_breakdown(kitchen=50, sub=20, paid=5, delta=-2)

    monkeypatch.setattr(
        "app.services.admin.day_stock_service.get_day_stock_breakdown",
        lambda *a, **k: bd,
    )
    monkeypatch.setattr(
        "app.services.admin.day_stock_service.get_day_stock_breakdown_by_dates",
        lambda *a, **k: {menu_date: bd},
    )
    monkeypatch.setattr(
        "app.services.admin.menu_day_stock_service.weekly_slot_row_for_dish_date",
        lambda *a, **k: type("W", (), {"total_stock": 50})(),
    )

    expected = resolve_single_stock_remaining_display(
        bd,
        business_date=menu_date,
        total_stock=50,
    )

    slots = weekly_slot_stock_extras(
        db,
        anchor,
        [{"slot": 1, "dish_id": 1, "total_stock": 50}],
        store_id=1,
        meal_period=MealPeriod.LUNCH.value,
    )
    detail = single_order_stock_for_dish_date(
        db, 1, menu_date, store_id=1, meal_period=MealPeriod.LUNCH.value
    )

    assert slots[0]["single_stock_remaining"] == expected
    assert detail.remaining == expected
    assert expected == 50 - 20 - 5 + (-2)
