"""周菜单槽位库存扩展：性能路径与午/晚餐字段隔离。"""

from datetime import date

import pytest
from sqlalchemy.orm import Session

from app.models.enums import MealPeriod
from app.services.admin.day_stock_service import DayStockBreakdown
from app.services.admin.menu_day_stock_service import weekly_slot_stock_extras


def _mock_breakdown(*, kitchen: int, sub: int, paid: int, delta: int) -> DayStockBreakdown:
    """测试用拆解：remaining = kitchen - sub - paid + delta。"""
    rem = max(0, kitchen - sub - paid + delta)
    waste = max(0, -delta)
    return DayStockBreakdown(
        meal_period=MealPeriod.LUNCH.value,
        kitchen_output=kitchen,
        delivery_total=sub,
        pickup_total=0,
        single_retail_total=paid,
        waste_total=waste,
        adjustment_delta_sum=delta,
        remaining=rem,
    )


def test_weekly_slot_stock_extras_lunch_dinner_independent(db: Session, monkeypatch):
    """午餐/晚餐后厨出餐与剩余份数按餐段独立计算，互不串值。"""
    anchor = date(2026, 6, 16)  # 周一
    menu_date = anchor  # slot=1 → 周一

    def _batch(db, *, store_id, dates, meal_period, metrics_cache=None):
        period = meal_period
        if period == MealPeriod.LUNCH.value:
            return {menu_date: _mock_breakdown(kitchen=200, sub=40, paid=5, delta=-3)}
        return {menu_date: _mock_breakdown(kitchen=80, sub=15, paid=2, delta=-1)}

    monkeypatch.setattr(
        "app.services.admin.day_stock_service.get_day_stock_breakdown_by_dates",
        _batch,
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
    )
    dinner = weekly_slot_stock_extras(
        db,
        anchor,
        [{**payload[0], "total_stock": 80}],
        store_id=1,
        meal_period=MealPeriod.DINNER.value,
    )

    assert lunch[0]["total_stock"] == 200
    assert dinner[0]["total_stock"] == 80
    assert lunch[0]["single_stock_remaining"] == 200 - 40 - 5 + (-3)
    assert dinner[0]["single_stock_remaining"] == 80 - 15 - 2 + (-1)
    assert lunch[0]["waste_total"] == 3
    assert dinner[0]["waste_total"] == 1


def test_weekly_slot_stock_extras_uses_batch_breakdown_once(db: Session, monkeypatch):
    """本周菜单路径应批量调用 get_day_stock_breakdown_by_dates，禁止循环内逐槽位拆解。"""
    anchor = date(2026, 6, 16)
    batch_calls = {"n": 0}

    def _batch(db, *, store_id, dates, meal_period, metrics_cache=None):
        batch_calls["n"] += 1
        return {
            anchor + __import__("datetime").timedelta(days=i): _mock_breakdown(
                kitchen=100, sub=10, paid=1, delta=0
            )
            for i in range(7)
        }

    def _forbidden(*args, **kwargs):
        raise AssertionError("不应逐槽位调用 get_day_stock_breakdown")

    monkeypatch.setattr(
        "app.services.admin.day_stock_service.get_day_stock_breakdown_by_dates",
        _batch,
    )
    monkeypatch.setattr("app.services.admin.day_stock_service.get_day_stock_breakdown", _forbidden)

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
    )
    assert len(out) == 7
    assert batch_calls["n"] == 1
