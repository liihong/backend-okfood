"""多租户隔离：对接配置合并、支付验签、会员范围、自动划区。"""

from __future__ import annotations

from datetime import date, time

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.core.tenant_scope import (
    allows_global_env_fallback,
    merge_tenant_field_or_global,
    sql_member_scope_clause,
)
from app.db.base import Base
from app.models.delivery_region import DeliveryRegion
from app.models.member import Member
from app.models.member_address import MemberAddress
from app.models.member_card_order import MemberCardOrder
from app.models.single_meal_order import SingleMealOrder
from app.models.store import Store
from app.models.tenant import Tenant
from app.models.tenant_integration_settings import TenantIntegrationSettings
from app.services.member.member_address_service import apply_auto_area_from_coords_or_geocode
from app.services.shared.region_assignment import assign_region_for_coords
from app.services.shared.tenant_integration_service import (
    get_merged_pay_config,
    get_merged_wx_credentials,
    resolve_tenant_id_for_wechat_out_trade_no,
    resolve_wechat_pay_notify_api_key_candidates,
)


@pytest.fixture()
def scope_db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    tables = [
        Tenant.__table__,
        Store.__table__,
        TenantIntegrationSettings.__table__,
        Member.__table__,
        MemberAddress.__table__,
        MemberCardOrder.__table__,
        SingleMealOrder.__table__,
        DeliveryRegion.__table__,
    ]
    Base.metadata.create_all(engine, tables=tables)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = SessionLocal()
    try:
        session.add(Tenant(id=1, name="主租户", is_active=True))
        session.add(Tenant(id=2, name="租户B", is_active=True))
        session.add(
            Store(id=1, tenant_id=1, name="主店", leave_deadline_time=time(21, 0), is_active=True)
        )
        session.add(
            Store(id=2, tenant_id=2, name="B店", leave_deadline_time=time(21, 0), is_active=True)
        )
        session.add(
            TenantIntegrationSettings(
                tenant_id=2,
                wechat_pay_mch_id="1900000109",
                wechat_pay_api_key="b" * 32,
                wx_mini_appid="wx_b_app",
                wx_mini_secret="secret_b",
            )
        )
        session.add(
            Member(
                id=10,
                tenant_id=2,
                store_id=2,
                phone="13000000010",
                name="B会员",
                balance=1,
                is_active=True,
                delivery_start_date=date(2026, 1, 1),
            )
        )
        session.add(
            MemberAddress(
                id=1,
                member_id=10,
                contact_name="B",
                contact_phone="13000000010",
                is_default=True,
                lng=121.5,
                lat=31.2,
            )
        )
        session.add(
            DeliveryRegion(
                id=1,
                tenant_id=1,
                name="主租户片区",
                polygon_json=[[121, 31], [122, 31], [122, 32], [121, 32], [121, 31]],
                priority=1,
                is_active=True,
            )
        )
        session.add(
            DeliveryRegion(
                id=2,
                tenant_id=2,
                name="B租户片区",
                polygon_json=[[121, 31], [122, 31], [122, 32], [121, 32], [121, 31]],
                priority=1,
                is_active=True,
            )
        )
        session.commit()
        yield session
    finally:
        session.close()
        engine.dispose()


def test_non_legacy_tenant_does_not_fallback_global_wx(scope_db: Session) -> None:
    appid, secret = get_merged_wx_credentials(scope_db, 2)
    assert appid == "wx_b_app"
    assert secret == "secret_b"


def test_legacy_tenant_can_fallback_global_wx(scope_db: Session, monkeypatch) -> None:
    monkeypatch.setenv("WX_MINI_APPID", "wx_legacy")
    monkeypatch.setenv("WX_MINI_SECRET", "sec_legacy")
    get_settings.cache_clear()
    appid, secret = get_merged_wx_credentials(scope_db, 1)
    assert appid == "wx_legacy"
    assert secret == "sec_legacy"
    get_settings.cache_clear()


def test_non_legacy_pay_config_does_not_use_global_mch(scope_db: Session, monkeypatch) -> None:
    monkeypatch.setenv("WECHAT_PAY_MCH_ID", "global_mch")
    monkeypatch.setenv("WECHAT_PAY_API_KEY", "a" * 32)
    get_settings.cache_clear()
    cfg = get_merged_pay_config(scope_db, 2)
    assert cfg.wechat_pay_mch_id == "1900000109"
    assert cfg.wechat_pay_api_key == "b" * 32
    get_settings.cache_clear()


def test_resolve_out_trade_no_no_legacy_fallback(scope_db: Session) -> None:
    assert (
        resolve_tenant_id_for_wechat_out_trade_no(scope_db, "missing_no", allow_legacy_default_fallback=False)
        is None
    )
    assert (
        resolve_tenant_id_for_wechat_out_trade_no(scope_db, "missing_no", allow_legacy_default_fallback=True)
        == 1
    )


def test_wechat_notify_keys_include_tenant_b(scope_db: Session, monkeypatch) -> None:
    monkeypatch.setenv("WECHAT_PAY_API_KEY", "a" * 32)
    get_settings.cache_clear()
    data = {"mch_id": "1900000109", "out_trade_no": "not_in_db_yet"}
    keys = resolve_wechat_pay_notify_api_key_candidates(scope_db, data)
    assert "b" * 32 in keys
    get_settings.cache_clear()


def test_assign_region_respects_tenant_id(scope_db: Session) -> None:
    r1 = assign_region_for_coords(scope_db, 121.5, 31.5, tenant_id=1)
    r2 = assign_region_for_coords(scope_db, 121.5, 31.5, tenant_id=2)
    assert r1 is not None and int(r1.id) == 1
    assert r2 is not None and int(r2.id) == 2


def test_auto_area_uses_member_tenant(scope_db: Session) -> None:
    addr = scope_db.get(MemberAddress, 1)
    assert addr is not None
    apply_auto_area_from_coords_or_geocode(scope_db, addr)
    assert int(addr.delivery_region_id) == 2


def test_sql_member_scope_both_none_is_false_clause() -> None:
    from sqlalchemy import false as sa_false

    clause = sql_member_scope_clause(tenant_id=None, store_id=None)
    assert str(clause) == str(sa_false())


def test_allows_global_only_for_default_tenant() -> None:
    default_tid = int(get_settings().DEFAULT_TENANT_ID)
    assert allows_global_env_fallback(default_tid) is True
    assert allows_global_env_fallback(default_tid + 999) is False


def test_merge_field_non_legacy_empty() -> None:
    assert merge_tenant_field_or_global(None, "global_val", tenant_id=2) == ""
    assert (
        merge_tenant_field_or_global(None, "global_val", tenant_id=int(get_settings().DEFAULT_TENANT_ID))
        == "global_val"
    )
