"""方案 B：改份数写入 pending，次日任务落库。"""

from datetime import time

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models.member import Member
from app.models.store import Store
from app.models.tenant import Tenant
from app.services.member_daily_meal_units_service import (
    apply_all_pending_daily_meal_units,
    pending_daily_meal_units,
    queue_daily_meal_units_change,
)
from app.services.member_service import effective_daily_meal_units


@pytest.fixture()
def pending_db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    tables = [Tenant.__table__, Store.__table__, Member.__table__]
    Base.metadata.create_all(engine, tables=tables)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = SessionLocal()
    try:
        session.add(Tenant(id=1, name="测试租户", is_active=True))
        session.add(
            Store(
                id=1,
                tenant_id=1,
                name="测试门店",
                leave_deadline_time=time(21, 0),
                is_active=True,
            )
        )
        session.commit()
        yield session
    finally:
        session.close()
        engine.dispose()


def _member(db: Session, *, units: int = 1) -> Member:
    m = Member(
        tenant_id=1,
        store_id=1,
        phone="13000001111",
        name="测试",
        balance=5,
        daily_meal_units=units,
        is_active=True,
    )
    db.add(m)
    db.flush()
    return m


def test_queue_does_not_change_today_units(pending_db: Session):
    m = _member(pending_db, units=1)
    queue_daily_meal_units_change(m, 2)
    pending_db.commit()
    assert effective_daily_meal_units(m) == 1
    assert pending_daily_meal_units(m) == 2


def test_apply_pending_on_midnight_job(pending_db: Session):
    m = _member(pending_db, units=1)
    queue_daily_meal_units_change(m, 2)
    pending_db.commit()
    n = apply_all_pending_daily_meal_units(pending_db)
    pending_db.commit()
    assert n == 1
    assert effective_daily_meal_units(m) == 2
    assert pending_daily_meal_units(m) is None


def test_queue_same_as_current_clears_pending(pending_db: Session):
    m = _member(pending_db, units=2)
    queue_daily_meal_units_change(m, 3)
    queue_daily_meal_units_change(m, 2)
    pending_db.commit()
    assert pending_daily_meal_units(m) is None
