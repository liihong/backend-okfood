"""周槽日总份：午餐/晚餐写入隔离，改晚餐不得影响午餐读取。"""

from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models.enums import MealPeriod
from app.models.menu_dish import MenuDish
from app.models.store import Store
from app.models.tenant import Tenant
from app.models.weekly_menu_slot import WeeklyMenuSlot
from app.services.menu_day_stock_service import (
    set_weekly_slot_total_stock,
    weekly_menu_dinner_day_total_stock,
    weekly_menu_lunch_day_total_stock,
)


@pytest.fixture()
def menu_db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    tables = [
        Tenant.__table__,
        Store.__table__,
        MenuDish.__table__,
        WeeklyMenuSlot.__table__,
    ]
    Base.metadata.create_all(engine, tables=tables)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = SessionLocal()
    try:
        from datetime import time

        session.add(Tenant(id=1, name="t", is_active=True))
        session.add(
            Store(id=1, tenant_id=1, name="s", leave_deadline_time=time(21, 0), is_active=True)
        )
        session.add(MenuDish(id=1, store_id=1, name="测试菜", is_enabled=True))
        anchor = date(2026, 6, 15)
        for idx, (period, stock) in enumerate(
            ((MealPeriod.LUNCH.value, 100), (MealPeriod.DINNER.value, 50)), start=1
        ):
            session.add(
                WeeklyMenuSlot(
                    id=idx,
                    store_id=1,
                    week_start=anchor,
                    slot=1,
                    meal_period=period,
                    dish_id=1,
                    total_stock=stock,
                )
            )
        session.commit()
        yield session
    finally:
        session.close()
        engine.dispose()


def test_set_dinner_total_stock_does_not_change_lunch(menu_db: Session, monkeypatch):
    """改晚餐日总份后，午餐顶卡读取值保持不变。"""
    anchor = date(2026, 6, 15)
    menu_date = anchor  # slot=1 周一

    monkeypatch.setattr(
        "app.services.day_stock_service.sync_store_kitchen_plan_row",
        lambda *a, **k: None,
    )
    monkeypatch.setattr(
        "app.services.admin_service.invalidate_dashboard_live_summary_cache",
        lambda *a, **k: None,
    )

    assert weekly_menu_lunch_day_total_stock(menu_db, menu_date, store_id=1) == 100
    assert weekly_menu_dinner_day_total_stock(menu_db, menu_date, store_id=1) == 50

    set_weekly_slot_total_stock(
        menu_db,
        anchor,
        1,
        88,
        store_id=1,
        meal_period=MealPeriod.DINNER.value,
    )

    assert weekly_menu_lunch_day_total_stock(menu_db, menu_date, store_id=1) == 100
    assert weekly_menu_dinner_day_total_stock(menu_db, menu_date, store_id=1) == 88
