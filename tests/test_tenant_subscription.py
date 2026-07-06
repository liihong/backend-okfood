"""租户按年订阅：到期拦截与续费提醒口径。"""

from __future__ import annotations

from datetime import date, time

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.tenant_subscription import (
    TENANT_EXPIRY_REMIND_DAYS,
    assert_admin_tenant_subscription_active,
    build_tenant_subscription_out,
    is_tenant_subscription_expired,
    tenant_subscription_status,
)
from app.db.base import Base
from app.models.admin_user import AdminUser
from app.models.store import Store
from app.models.tenant import Tenant


@pytest.fixture()
def tenant_db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    tables = [Tenant.__table__, Store.__table__, AdminUser.__table__]
    Base.metadata.create_all(engine, tables=tables)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def _seed_tenant(
    db: Session,
    *,
    expires_at: date | None,
    is_active: bool = True,
) -> tuple[Tenant, AdminUser]:
    t = Tenant(id=1, name="测试租户", is_active=is_active, expires_at=expires_at)
    st = Store(id=1, tenant_id=1, name="店", leave_deadline_time=time(21, 0), is_active=True)
    u = AdminUser(
        id=1,
        tenant_id=1,
        username="owner_a",
        password_hash="x",
        role="full",
        is_active=True,
    )
    db.add_all([t, st, u])
    db.commit()
    return t, u


def test_subscription_status_unset_when_no_expires_at():
    t = Tenant(name="x", is_active=True, expires_at=None)
    assert tenant_subscription_status(t) == "unset"
    assert not is_tenant_subscription_expired(t, today=date(2026, 7, 6))


def test_subscription_expired_after_end_date():
    t = Tenant(name="x", is_active=True, expires_at=date(2026, 7, 6))
    assert not is_tenant_subscription_expired(t, today=date(2026, 7, 6))
    assert is_tenant_subscription_expired(t, today=date(2026, 7, 7))
    assert tenant_subscription_status(t, today=date(2026, 7, 7)) == "expired"


def test_subscription_expiring_soon_within_remind_window():
    t = Tenant(name="x", is_active=True, expires_at=date(2026, 7, 20))
    anchor = date(2026, 7, 6)
    out = build_tenant_subscription_out(t, today=anchor)
    assert out["status"] == "expiring_soon"
    assert out["days_until_expiry"] == 14
    assert out["remind_days"] == TENANT_EXPIRY_REMIND_DAYS


def test_login_blocked_when_tenant_expired(tenant_db: Session):
    _, u = _seed_tenant(tenant_db, expires_at=date(2026, 1, 1))
    with pytest.raises(HTTPException) as exc:
        assert_admin_tenant_subscription_active(
            tenant_db, u, today=date(2026, 7, 6)
        )
    assert exc.value.status_code == 403
    assert "到期" in str(exc.value.detail)


def test_system_admin_skips_expiry_check(tenant_db: Session):
    t = Tenant(id=2, name="平台", is_active=True, expires_at=date(2020, 1, 1))
    u = AdminUser(
        id=2,
        tenant_id=2,
        username="sys",
        password_hash="x",
        role="system",
        is_active=True,
    )
    tenant_db.add_all([t, u])
    tenant_db.commit()
    assert_admin_tenant_subscription_active(
        tenant_db, u, jwt_role="admin_system", today=date(2026, 7, 6)
    )


def test_create_platform_tenant_requires_expires_at(tenant_db: Session):
    from app.schemas.admin import PlatformTenantCreateIn
    from app.services.shared.platform_tenant_service import create_platform_tenant

    row = create_platform_tenant(
        tenant_db,
        PlatformTenantCreateIn(name="新租户", is_active=True, expires_at=date(2027, 7, 6)),
    )
    assert row.expires_at == "2027-07-06"
    assert row.subscription_status == "ok"
