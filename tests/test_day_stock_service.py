"""日库存：公式、损耗流水、分餐段隔离。"""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy.orm import Session

from app.models.enums import DayStockAdjustmentReason, MealPeriod
from app.services.day_stock_service import create_day_stock_adjustment, get_day_stock_breakdown


@pytest.fixture(autouse=True)
def _day_stock_log_table(db: Session):
    from app.db.base import Base
    from app.models.day_stock_adjustment_log import DayStockAdjustmentLog

    Base.metadata.create_all(db.get_bind(), tables=[DayStockAdjustmentLog.__table__])
    yield


def _fake_metrics(*, home: int = 0, pickup: int = 0):
    return type("M", (), {
        "home_pending_meal_total": home,
        "home_delivered_meal_total": 0,
        "pickup_meal_total": pickup,
    })()


def _patch_stock_deps(monkeypatch, *, d: date, kitchen: int | None, home: int, pickup: int = 0, retail: int = 0):
    monkeypatch.setattr(
        "app.services.day_stock_service.weekly_menu_day_total_stock",
        lambda db, menu_date, store_id, meal_period=MealPeriod.LUNCH.value: kitchen,
    )
    monkeypatch.setattr(
        "app.services.day_stock_service._prep_metrics_for_period",
        lambda *a, **k: _fake_metrics(home=home, pickup=pickup),
    )
    monkeypatch.setattr(
        "app.services.day_stock_service.paid_single_retail_portions_by_dates",
        lambda db, dates, store_id, meal_period=MealPeriod.LUNCH.value: {d: retail},
    )


def test_day_stock_breakdown_no_kitchen_returns_none_remaining(db: Session, monkeypatch):
    d = date(2026, 6, 17)
    _patch_stock_deps(monkeypatch, d=d, kitchen=None, home=0)
    bd = get_day_stock_breakdown(db, store_id=1, business_date=d, meal_period=MealPeriod.LUNCH.value)
    assert bd.kitchen_output is None
    assert bd.remaining is None


def test_waste_adjustment_reduces_remaining(db: Session, monkeypatch):
    d = date(2026, 6, 18)
    _patch_stock_deps(monkeypatch, d=d, kitchen=100, home=10, retail=5)

    before = get_day_stock_breakdown(db, store_id=1, business_date=d, meal_period=MealPeriod.LUNCH.value)
    assert before.remaining == 85

    after = create_day_stock_adjustment(
        db,
        store_id=1,
        business_date=d,
        meal_period=MealPeriod.LUNCH.value,
        delta=-2,
        reason_code=DayStockAdjustmentReason.SPILL.value,
        remark="小哥撒漏",
        operator="test_admin",
    )
    assert after.remaining == 83
    assert after.waste_total == 2


def test_lunch_dinner_kitchen_independent(db: Session, monkeypatch):
    d = date(2026, 6, 19)

    def _kitchen(db, menu_date, store_id, meal_period=MealPeriod.LUNCH.value):
        return 200 if meal_period == MealPeriod.LUNCH.value else 80

    monkeypatch.setattr("app.services.day_stock_service.weekly_menu_day_total_stock", _kitchen)

    def _metrics(db, store_id, business_date, meal_period):
        home = 50 if meal_period == MealPeriod.LUNCH.value else 30
        return _fake_metrics(home=home)

    monkeypatch.setattr("app.services.day_stock_service._prep_metrics_for_period", _metrics)
    monkeypatch.setattr(
        "app.services.day_stock_service.paid_single_retail_portions_by_dates",
        lambda *a, **k: {d: 0},
    )

    lunch = get_day_stock_breakdown(db, store_id=1, business_date=d, meal_period=MealPeriod.LUNCH.value)
    dinner = get_day_stock_breakdown(db, store_id=1, business_date=d, meal_period=MealPeriod.DINNER.value)
    assert lunch.kitchen_output == 200
    assert dinner.kitchen_output == 80
    assert lunch.remaining == 150
    assert dinner.remaining == 50
