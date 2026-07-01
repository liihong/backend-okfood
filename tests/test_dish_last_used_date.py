"""菜品列表 last_used_date：按日排期与周槽位取最近供餐日。"""

from datetime import date, datetime, time

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.timeutil import beijing_now_naive
from app.db.base import Base
from app.models.menu_dish import MenuDish
from app.models.menu_schedule import MenuSchedule
from app.models.store import Store
from app.models.tenant import Tenant
from app.models.weekly_menu_slot import WeeklyMenuSlot
from app.services.admin.admin_service import list_dishes_admin


@pytest.fixture()
def dish_db(monkeypatch) -> Session:
    engine = create_engine("sqlite:///:memory:")
    tables = [
        Tenant.__table__,
        Store.__table__,
        MenuDish.__table__,
        MenuSchedule.__table__,
        WeeklyMenuSlot.__table__,
    ]
    Base.metadata.create_all(engine, tables=tables)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = SessionLocal()
    try:
        now = beijing_now_naive()
        session.add(Tenant(id=1, name="t", is_active=True))
        session.add(
            Store(id=1, tenant_id=1, name="s", leave_deadline_time=time(21, 0), is_active=True)
        )
        session.add_all(
            [
                MenuDish(id=1, store_id=1, name="周槽菜", is_enabled=True, created_at=now),
                MenuDish(id=2, store_id=1, name="排期菜", is_enabled=True, created_at=now),
                MenuDish(id=3, store_id=1, name="从未排期", is_enabled=True, created_at=now),
            ]
        )
        session.add(
            WeeklyMenuSlot(
                id=1,
                store_id=1,
                week_start=date(2026, 6, 16),
                slot=2,
                meal_period="lunch",
                dish_id=1,
            )
        )
        session.add(
            MenuSchedule(
                id=1,
                store_id=1,
                menu_date=date(2026, 6, 20),
                meal_period="lunch",
                dish_id=2,
            )
        )
        session.commit()
        monkeypatch.setattr("app.services.admin.admin_service.today_shanghai", lambda: date(2026, 6, 23))
        yield session
    finally:
        session.close()
        engine.dispose()


def test_list_dishes_includes_last_used_date(dish_db: Session):
    items = list_dishes_admin(dish_db, enabled_only=False, store_id=1, lite=False)
    by_id = {item.id: item for item in items}

    assert by_id[1].last_used_date == "2026-06-17"
    assert by_id[2].last_used_date == "2026-06-20"
    assert by_id[3].last_used_date is None


def test_list_dishes_lite_omits_last_used_date(dish_db: Session):
    items = list_dishes_admin(dish_db, enabled_only=False, store_id=1, lite=True)
    assert all(item.last_used_date is None for item in items)
