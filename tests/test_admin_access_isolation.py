"""管理端租户/门店隔离：会员 IDOR、顺丰推单归属校验。"""

from __future__ import annotations

from datetime import date, time

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.admin_access import require_member_in_admin_store, require_sf_push_in_admin_tenant
from app.db.base import Base
from app.models.admin_user import AdminUser
from app.models.member import Member
from app.models.sf_same_city_push import SfSameCityPush
from app.models.store import Store
from app.models.tenant import Tenant


@pytest.fixture()
def access_db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    tables = [
        Tenant.__table__,
        Store.__table__,
        AdminUser.__table__,
        Member.__table__,
        SfSameCityPush.__table__,
    ]
    Base.metadata.create_all(engine, tables=tables)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = SessionLocal()
    try:
        session.add(Tenant(id=1, name="租户A", is_active=True))
        session.add(Tenant(id=2, name="租户B", is_active=True))
        session.add(Store(id=1, tenant_id=1, name="A店", leave_deadline_time=time(21, 0), is_active=True))
        session.add(Store(id=2, tenant_id=2, name="B店", leave_deadline_time=time(21, 0), is_active=True))
        session.add(AdminUser(username="admin_a", password_hash="x", tenant_id=1, is_active=True))
        session.add(AdminUser(username="admin_b", password_hash="x", tenant_id=2, is_active=True))
        session.add(
            Member(
                id=101,
                tenant_id=1,
                store_id=1,
                phone="13000000101",
                name="A会员",
                balance=5,
                is_active=True,
                delivery_start_date=date(2026, 1, 1),
            )
        )
        session.add(
            Member(
                id=201,
                tenant_id=2,
                store_id=2,
                phone="13000000201",
                name="B会员",
                balance=5,
                is_active=True,
                delivery_start_date=date(2026, 1, 1),
            )
        )
        session.add(
            SfSameCityPush(
                id=1,
                store_id=2,
                delivery_date=date(2026, 7, 1),
                stop_id="s1",
                shop_order_id="ord-b-1",
            )
        )
        session.commit()
        yield session
    finally:
        session.close()
        engine.dispose()


def test_admin_cannot_access_other_tenant_member(access_db: Session) -> None:
    with pytest.raises(HTTPException) as exc:
        require_member_in_admin_store(
            access_db,
            admin_username="admin_a",
            member_id=201,
            store_id=1,
        )
    assert exc.value.status_code == 404


def test_admin_can_access_own_store_member(access_db: Session) -> None:
    m, tid, sid = require_member_in_admin_store(
        access_db,
        admin_username="admin_a",
        member_id=101,
        store_id=1,
    )
    assert int(m.id) == 101
    assert tid == 1
    assert sid == 1


def test_require_member_in_admin_store_must_unpack_three_values(access_db: Session) -> None:
    """退卡退款等接口须解包 (member, tenant_id, store_id)；只解包两个会 ValueError → 500。"""
    result = require_member_in_admin_store(
        access_db,
        admin_username="admin_a",
        member_id=101,
        store_id=1,
    )
    assert len(result) == 3
    with pytest.raises(ValueError, match="too many values to unpack"):
        _, sid = result  # type: ignore[misc]


def test_admin_cannot_operate_other_tenant_sf_push(access_db: Session) -> None:
    with pytest.raises(HTTPException) as exc:
        require_sf_push_in_admin_tenant(access_db, admin_username="admin_a", push_id=1)
    assert exc.value.status_code == 404
