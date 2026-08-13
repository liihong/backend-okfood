"""主租户 OK饭 直连；加盟租户服务商模式（特约商户号 + WECHAT_PAY_SP_*）。"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.integrations.wechat_pay_v2 import partner_base_params, pay_trade_base_params
from app.models.tenant import Tenant
from app.models.tenant_integration_settings import TenantIntegrationSettings
from app.schemas.admin import TenantPayConfigPatchIn
from app.services.shared.tenant_integration_service import (
    MergedPayConfig,
    get_merged_pay_config,
    get_tenant_pay_config_out,
    is_partner_pay_config,
    list_tenant_ids_by_wechat_mch_id,
    patch_tenant_pay_config,
    wechat_pay_misconfiguration_detail_merged,
)


def _settings(**kwargs):
    base = dict(
        DEFAULT_TENANT_ID=1,
        WECHAT_PAY_MCH_ID="1744316470",
        WECHAT_PAY_API_KEY="D" * 32,
        WECHAT_PAY_NOTIFY_URL="https://example.com/api/pay/wechat/notify",
        WECHAT_PAY_SSL_CERT_PATH="",
        WECHAT_PAY_SSL_KEY_PATH="",
        WECHAT_PAY_SP_APPID="wx_sp_app",
        WECHAT_PAY_SP_MCH_ID="1900008001",
        WECHAT_PAY_SP_API_KEY="B" * 32,
        WECHAT_PAY_SP_SSL_CERT_PATH="",
        WECHAT_PAY_SP_SSL_KEY_PATH="",
        WX_MINI_APPID="wx_okfood",
    )
    base.update(kwargs)
    return SimpleNamespace(**base)


@pytest.fixture()
def db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(
        engine,
        tables=[Tenant.__table__, TenantIntegrationSettings.__table__],
    )
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = SessionLocal()
    try:
        session.add(Tenant(id=1, name="OK饭", is_active=True))
        session.add(Tenant(id=2, name="加盟租户", is_active=True))
        session.commit()
        yield session
    finally:
        session.close()
        engine.dispose()


def test_patch_tenant_pay_config_only_needs_sub_mch_id(db: Session) -> None:
    """加盟店主只需填写特约商户号。"""
    empty = get_tenant_pay_config_out(db, 2)
    assert empty.wechat_pay_mch_id is None

    out = patch_tenant_pay_config(
        db,
        2,
        TenantPayConfigPatchIn(wechat_pay_mch_id="1116333132"),
    )
    assert out.tenant_id == 2
    assert out.wechat_pay_mch_id == "1116333132"


@patch("app.services.shared.tenant_integration_service.get_settings", return_value=_settings())
@patch("app.core.tenant_scope.get_settings", return_value=_settings())
def test_okfood_primary_tenant_stays_direct(_s1, _s2, db: Session) -> None:
    """主租户不带服务商字段，下单仍用 appid + mch_id + openid。"""
    cfg = get_merged_pay_config(db, 1)
    assert is_partner_pay_config(cfg) is False
    assert cfg.wechat_pay_mch_id == "1744316470"
    assert cfg.wechat_pay_api_key == "D" * 32
    assert cfg.wechat_pay_sp_mch_id == ""
    assert wechat_pay_misconfiguration_detail_merged(cfg, tenant_id=1) is None

    fields = pay_trade_base_params(cfg, openid="user_openid")
    assert fields == {
        "appid": "wx_okfood",
        "mch_id": "1744316470",
        "openid": "user_openid",
    }
    assert "sub_mch_id" not in fields
    assert "sub_openid" not in fields


@patch("app.services.shared.tenant_integration_service.get_settings", return_value=_settings())
@patch("app.core.tenant_scope.get_settings", return_value=_settings())
def test_franchise_tenant_uses_partner(_s1, _s2, db: Session) -> None:
    """加盟租户：mch_id 为特约商户号，服务商号来自 WECHAT_PAY_SP_*。"""
    patch_tenant_pay_config(db, 2, TenantPayConfigPatchIn(wechat_pay_mch_id="1116333132"))
    row = db.get(TenantIntegrationSettings, 2)
    assert row is not None
    row.wx_mini_appid = "wx_tenant_mini"
    db.commit()

    cfg = get_merged_pay_config(db, 2)
    assert is_partner_pay_config(cfg) is True
    assert cfg.wechat_pay_mch_id == "1116333132"
    assert cfg.wechat_pay_sp_mch_id == "1900008001"
    assert cfg.wechat_pay_sp_appid == "wx_sp_app"
    assert cfg.wechat_pay_api_key == "B" * 32
    assert cfg.wx_mini_appid == "wx_tenant_mini"
    assert wechat_pay_misconfiguration_detail_merged(cfg, tenant_id=2) is None

    fields = pay_trade_base_params(cfg, openid="sub_user")
    assert fields["appid"] == "wx_sp_app"
    assert fields["mch_id"] == "1900008001"
    assert fields["sub_mch_id"] == "1116333132"
    assert fields["sub_appid"] == "wx_tenant_mini"
    assert fields["sub_openid"] == "sub_user"
    assert "openid" not in fields


@patch("app.services.shared.tenant_integration_service.get_settings", return_value=_settings())
@patch("app.core.tenant_scope.get_settings", return_value=_settings())
def test_notify_matches_sub_mch_not_okfood_direct_mch(_s1, _s2, db: Session) -> None:
    """服务商号不能误判给主租户；直连商户号才能归 OK饭。"""
    patch_tenant_pay_config(db, 2, TenantPayConfigPatchIn(wechat_pay_mch_id="1116333132"))
    assert list_tenant_ids_by_wechat_mch_id(db, "1116333132") == [2]
    assert list_tenant_ids_by_wechat_mch_id(db, "1900008001") == []
    assert list_tenant_ids_by_wechat_mch_id(db, "1744316470") == [1]


def test_partner_base_params_shape() -> None:
    cfg = MergedPayConfig(
        wx_mini_appid="wx_mini",
        wechat_pay_mch_id="1116333132",
        wechat_pay_api_key="C" * 32,
        wechat_pay_notify_url="https://example.com/n",
        wechat_pay_sp_appid="wx_sp",
        wechat_pay_sp_mch_id="1900008001",
    )
    assert partner_base_params(cfg) == {
        "appid": "wx_sp",
        "mch_id": "1900008001",
        "sub_mch_id": "1116333132",
        "sub_appid": "wx_mini",
    }
