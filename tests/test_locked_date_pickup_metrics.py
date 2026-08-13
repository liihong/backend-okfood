"""锁单日后厨顶卡自提份数：纯自提会员不在顺丰快照里，仍须计入。"""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import event, literal, select
from sqlalchemy.orm import Session

from app.models.member import Member
from app.services.delivery.delivery_sheet_service import _pickup_meal_units_split_for_locked_date


def _sqlite_least(*args):
    vals = [a for a in args if a is not None]
    return min(vals) if vals else None


def _sqlite_greatest(*args):
    vals = [a for a in args if a is not None]
    return max(vals) if vals else None


@pytest.fixture()
def pickup_db(db: Session) -> Session:
    """为 SQLite 注册 least/greatest，以跑 MySQL 口径的资格 SQL。"""
    engine = db.get_bind()

    def _register(dbapi_conn, _connection_record) -> None:
        dbapi_conn.create_function("least", -1, _sqlite_least)
        dbapi_conn.create_function("greatest", -1, _sqlite_greatest)

    event.listen(engine, "connect", _register)
    raw = db.connection().connection
    if hasattr(raw, "dbapi_connection"):
        raw = raw.dbapi_connection
    raw.create_function("least", -1, _sqlite_least)
    raw.create_function("greatest", -1, _sqlite_greatest)
    yield db
    event.remove(engine, "connect", _register)


def _eligible_pickup_member(db, *, phone: str, name: str, units: int = 1) -> Member:
    """当日应门店自提的订阅会员。"""
    d = date(2026, 8, 13)
    m = Member(
        tenant_id=1,
        store_id=1,
        phone=phone,
        name=name,
        balance=6,
        meal_quota_total=6,
        daily_meal_units=units,
        plan_type="周卡",
        is_active=True,
        delivery_deferred=False,
        store_pickup=True,
        delivery_start_date=d,
    )
    db.add(m)
    db.flush()
    return m


def test_locked_date_pickup_counts_eligible_member_missing_from_sf_snapshot(pickup_db: Session):
    """推单快照只有到家会员时，当前应自提份数仍计入待自提。"""
    db = pickup_db
    d = date(2026, 8, 13)
    home = Member(
        tenant_id=1,
        store_id=1,
        phone="13800000001",
        name="到家",
        balance=6,
        meal_quota_total=6,
        daily_meal_units=1,
        plan_type="周卡",
        is_active=True,
        delivery_deferred=False,
        store_pickup=False,
        delivery_start_date=d,
    )
    pickup = _eligible_pickup_member(db, phone="13800000002", name="自提")
    db.add(home)
    db.commit()
    db.refresh(home)
    db.refresh(pickup)

    snapshot = {int(home.id): 1}
    empty_delivered = select(literal(0)).where(literal(False))
    pu_delivered, pu_pending = _pickup_meal_units_split_for_locked_date(
        db,
        delivery_date=d,
        store_id=1,
        snapshot=snapshot,
        members_by_id={int(home.id): home},
        delivered_subq=empty_delivered,
    )
    assert pu_delivered == 0
    assert pu_pending == 1


def test_locked_date_pickup_uses_snapshot_units_for_switched_pickup(pickup_db: Session):
    """锁单后改自提：快照份数计入自提，不因资格 SQL 漏计。"""
    db = pickup_db
    d = date(2026, 8, 13)
    switched = Member(
        tenant_id=1,
        store_id=1,
        phone="13800000003",
        name="改自提",
        balance=0,
        meal_quota_total=6,
        daily_meal_units=2,
        plan_type="周卡",
        is_active=True,
        delivery_deferred=False,
        store_pickup=True,
        delivery_start_date=d,
    )
    db.add(switched)
    db.commit()
    db.refresh(switched)

    snapshot = {int(switched.id): 2}
    empty_delivered = select(literal(0)).where(literal(False))
    pu_delivered, pu_pending = _pickup_meal_units_split_for_locked_date(
        db,
        delivery_date=d,
        store_id=1,
        snapshot=snapshot,
        members_by_id={int(switched.id): switched},
        delivered_subq=empty_delivered,
    )
    assert pu_delivered == 0
    assert pu_pending == 2
