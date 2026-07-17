"""小程序周菜单库存：与 day_stock 损耗流水口径一致。"""

from datetime import date, timedelta

import pytest
from sqlalchemy.orm import Session

from app.models.enums import MealPeriod
from app.services.admin.menu_day_stock_service import single_order_stock_by_date_for_week


class _FakeSlot:
    def __init__(self, slot: int, total_stock: int):
        self.slot = slot
        self.total_stock = total_stock


class _FakeDish:
    def __init__(self, dish_id: int):
        self.id = dish_id


def test_single_order_stock_by_date_for_week_deducts_waste(db: Session, monkeypatch):
    """周菜单批量库存路径应扣减损耗流水（与 weekly_slot_stock_extras 一致）。"""
    anchor = date(2026, 6, 16)  # 周一
    menu_date = anchor

    dish = _FakeDish(1)
    ws = _FakeSlot(1, 200)

    monkeypatch.setattr(
        "app.services.admin.menu_day_stock_service.dashboard_meal_totals_by_dates",
        lambda *a, **k: {menu_date: 40},
    )
    monkeypatch.setattr(
        "app.services.admin.menu_day_stock_service.paid_single_retail_portions_by_dates",
        lambda *a, **k: {menu_date: 5},
    )
    monkeypatch.setattr(
        "app.services.admin.day_stock_service.sum_adjustment_deltas_by_dates",
        lambda *a, **k: {menu_date: -3},
    )

    out = single_order_stock_by_date_for_week(
        db,
        week_start_anchor=anchor,
        dates=[menu_date],
        dishes_by_date={menu_date: dish},
        weekly_slot_rows=[(ws, dish)],
        store_id=1,
        subscription_floor_date=menu_date,
        meal_period=MealPeriod.LUNCH.value,
    )

    info = out[menu_date]
    assert info.remaining == 200 - 40 - 5 + (-3)
    assert info.subscription_meals == 40
    assert info.paid_single_portions == 5


def test_single_order_stock_by_date_for_week_past_date_zero_remaining(db: Session, monkeypatch):
    """早于 subscription_floor 的供餐日 remaining 固定为 0（即使 cap-sub-paid 仍有余量）。"""
    anchor = date(2026, 6, 16)  # 周一
    menu_date = anchor

    dish = _FakeDish(1)
    ws = _FakeSlot(1, 100)

    monkeypatch.setattr(
        "app.services.admin.menu_day_stock_service.dashboard_meal_totals_by_dates",
        lambda *a, **k: {menu_date: 0},
    )
    monkeypatch.setattr(
        "app.services.admin.menu_day_stock_service.paid_single_retail_portions_by_dates",
        lambda *a, **k: {menu_date: 0},
    )
    monkeypatch.setattr(
        "app.services.admin.day_stock_service.sum_adjustment_deltas_by_dates",
        lambda *a, **k: {menu_date: 0},
    )

    out = single_order_stock_by_date_for_week(
        db,
        week_start_anchor=anchor,
        dates=[menu_date],
        dishes_by_date={menu_date: dish},
        weekly_slot_rows=[(ws, dish)],
        store_id=1,
        subscription_floor_date=anchor + timedelta(days=1),  # 周二为 floor，周一已过
        meal_period=MealPeriod.LUNCH.value,
    )

    assert out[menu_date].remaining == 0
