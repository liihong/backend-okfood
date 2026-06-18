"""周菜单槽位库存扩展：性能路径与午/晚餐字段隔离。"""

from datetime import date

import pytest
from sqlalchemy.orm import Session

from app.models.enums import MealPeriod
from app.services.menu_day_stock_service import weekly_slot_stock_extras


def test_weekly_slot_stock_extras_lunch_dinner_independent(db: Session, monkeypatch):
    """午餐/晚餐后厨出餐与剩余份数按餐段独立计算，互不串值。"""
    anchor = date(2026, 6, 16)  # 周一
    menu_date = anchor  # slot=1 → 周一

    monkeypatch.setattr(
        "app.services.menu_day_stock_service.dashboard_meal_totals_by_dates",
        lambda *a, **k: {menu_date: 40 if k.get("meal_period") == MealPeriod.LUNCH.value else 15},
    )
    monkeypatch.setattr(
        "app.services.menu_day_stock_service.paid_single_retail_portions_by_dates",
        lambda *a, **k: {menu_date: 5 if k.get("meal_period") == MealPeriod.LUNCH.value else 2},
    )
    monkeypatch.setattr(
        "app.services.day_stock_service.sum_adjustment_deltas_by_dates",
        lambda *a, **k: {menu_date: -3 if k.get("meal_period") == MealPeriod.LUNCH.value else -1},
    )

    payload = [
        {
            "slot": 1,
            "dish_id": 1,
            "name": "测试菜",
            "total_stock": 200,
        }
    ]

    lunch = weekly_slot_stock_extras(
        db,
        anchor,
        payload,
        store_id=1,
        meal_period=MealPeriod.LUNCH.value,
        sub_by_date={menu_date: 40},
        paid_by_date={menu_date: 5},
    )
    dinner = weekly_slot_stock_extras(
        db,
        anchor,
        [{**payload[0], "total_stock": 80}],
        store_id=1,
        meal_period=MealPeriod.DINNER.value,
        sub_by_date={menu_date: 15},
        paid_by_date={menu_date: 2},
    )

    assert lunch[0]["total_stock"] == 200
    assert dinner[0]["total_stock"] == 80
    assert lunch[0]["single_stock_remaining"] == 200 - 40 - 5 + (-3)
    assert dinner[0]["single_stock_remaining"] == 80 - 15 - 2 + (-1)
    assert lunch[0]["waste_total"] == 3
    assert dinner[0]["waste_total"] == 1


def test_weekly_slot_stock_extras_skips_breakdown_per_slot(db: Session, monkeypatch):
    """本周菜单路径不应逐槽位调用 get_day_stock_breakdown。"""
    anchor = date(2026, 6, 16)
    calls = {"n": 0}

    def _forbidden(*args, **kwargs):
        calls["n"] += 1
        raise AssertionError("不应逐槽位调用 get_day_stock_breakdown")

    monkeypatch.setattr("app.services.day_stock_service.get_day_stock_breakdown", _forbidden)
    monkeypatch.setattr(
        "app.services.day_stock_service.sum_adjustment_deltas_by_dates",
        lambda *a, **k: {anchor + __import__("datetime").timedelta(days=i): 0 for i in range(7)},
    )

    slots = [
        {"slot": i, "dish_id": i, "name": f"d{i}", "total_stock": 100}
        for i in range(1, 8)
    ]
    out = weekly_slot_stock_extras(
        db,
        anchor,
        slots,
        store_id=1,
        meal_period=MealPeriod.LUNCH.value,
        sub_by_date={anchor + __import__("datetime").timedelta(days=i): 10 for i in range(7)},
        paid_by_date={anchor + __import__("datetime").timedelta(days=i): 1 for i in range(7)},
    )
    assert len(out) == 7
    assert calls["n"] == 0
