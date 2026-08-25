"""顺丰开发者 ID/密钥：各租户未填时共用全局 .env；店铺编号仍按租户。"""

from __future__ import annotations

from datetime import date, time
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.tenant_scope import merge_shared_sf_developer_int, merge_shared_sf_developer_secret
from app.db.base import Base
from app.models.sf_same_city_push import SfSameCityPush
from app.models.store import Store
from app.models.tenant import Tenant
from app.models.tenant_integration_settings import TenantIntegrationSettings
from app.services.delivery.sf_same_city_service import _instant_sf_shop_configured
from app.services.shared.tenant_integration_service import (
    merged_sf_integration_namespace,
    resolve_sf_notify_app_key_candidates,
)


def _global_sf() -> SimpleNamespace:
    return SimpleNamespace(
        SF_OPEN_DEV_ID=999001,
        SF_OPEN_SECRET="global-sf-secret",
        SF_OPEN_SHOP_ID="GLOBAL-SHOP",
        SF_OPEN_SHOP_TYPE=1,
        SF_PICKUP_PHONE="10000000000",
        SF_PICKUP_ADDRESS="全局取件地址",
        SF_CITY_NAME="郑州",
        SF_ORDER_SOURCE="OKFOOD",
        SF_API_VERSION=17,
        SF_VEHICLE_TYPE_CODE=1,
        SF_DEFAULT_PRODUCT_TYPE=1,
        SF_KG_PER_MEAL_UNIT=0.5,
        SF_PRODUCT_CATEGORY_LABEL="餐品",
        SF_DEFAULT_VEHICLE_TYPE="小轿车",
        DEFAULT_STORE_ID=1,
        DEFAULT_TENANT_ID=1,
    )


@pytest.fixture()
def sf_db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    tables = [
        Tenant.__table__,
        Store.__table__,
        TenantIntegrationSettings.__table__,
        SfSameCityPush.__table__,
    ]
    Base.metadata.create_all(engine, tables=tables)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = SessionLocal()
    try:
        session.add(Tenant(id=1, name="主租户", is_active=True))
        session.add(Tenant(id=3, name="Hello轻厨", is_active=True))
        session.add(
            Store(
                id=3,
                tenant_id=3,
                name="Hello轻厨",
                leave_deadline_time=time(21, 0),
                is_active=True,
                sf_retail_push_shop_id="6282826746497",
                sf_retail_push_shop_type=1,
            )
        )
        session.add(
            TenantIntegrationSettings(
                tenant_id=3,
                sf_open_shop_id="6282826746497",
                sf_open_shop_type=1,
                sf_pickup_phone="13700893378",
                sf_pickup_address="禹州市颍川街道商贸大世界南外13号街",
            )
        )
        session.flush()
        yield session
    finally:
        session.close()
        engine.dispose()


def test_merge_shared_sf_developer_prefers_tenant_then_global() -> None:
    assert merge_shared_sf_developer_int(12, 99) == 12
    assert merge_shared_sf_developer_int(None, 99) == 99
    assert merge_shared_sf_developer_secret(" tenant-sec ", "g") == "tenant-sec"
    assert merge_shared_sf_developer_secret("  ", "g-sec") == "g-sec"
    assert merge_shared_sf_developer_secret(None, "g-sec") == "g-sec"


def test_non_primary_tenant_uses_global_sf_developer_keeps_own_shop(
    sf_db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "app.services.shared.tenant_integration_service.get_settings",
        _global_sf,
    )
    gset = merged_sf_integration_namespace(sf_db, 3)
    assert gset.SF_OPEN_DEV_ID == 999001
    assert gset.SF_OPEN_SECRET == "global-sf-secret"
    assert gset.SF_OPEN_SHOP_ID == "6282826746497"
    assert gset.SF_PICKUP_PHONE == "13700893378"
    assert _instant_sf_shop_configured(sf_db, store_id=3, tenant_id=3) is True


def test_located_callback_uses_global_secret_when_tenant_secret_empty(
    sf_db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "app.services.shared.tenant_integration_service.get_settings",
        _global_sf,
    )
    sf_db.add(
        SfSameCityPush(
            store_id=3,
            delivery_date=date(2026, 8, 25),
            stop_id="stop-1",
            shop_order_id="OKF-T3-001",
            error_code=0,
        )
    )
    sf_db.commit()
    keys = resolve_sf_notify_app_key_candidates(sf_db, {"shop_order_id": "OKF-T3-001"})
    assert keys == ["global-sf-secret"]
