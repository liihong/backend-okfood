"""微信开放平台 authorizer token 落库与刷新。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.services.shared.wx_open_authorizer_service import (
    build_tenant_authorize_redirect_uri,
    create_tenant_pre_auth_link,
    get_authorizer_admin_state,
    patch_authorizer_tokens_admin,
    pop_tenant_id_for_pre_auth,
    save_component_verify_ticket,
    tenant_has_authorizer_tokens,
)


@patch("app.services.shared.wx_open_authorizer_service.get_tenant_integration_row")
def test_tenant_has_authorizer_tokens(mock_get_row):
    row = MagicMock()
    row.wx_authorizer_refresh_token = "refresh_abc"
    mock_get_row.return_value = row
    db = MagicMock()
    assert tenant_has_authorizer_tokens(db, 2) is True

    row.wx_authorizer_refresh_token = ""
    assert tenant_has_authorizer_tokens(db, 2) is False


@patch("app.services.shared.wx_open_authorizer_service._ensure_component_state_row")
def test_save_component_verify_ticket(mock_ensure):
    row = MagicMock()
    mock_ensure.return_value = row
    db = MagicMock()
    save_component_verify_ticket(db, " ticket_xyz ")
    assert row.verify_ticket == "ticket_xyz"
    db.commit.assert_called_once()


@patch("app.services.shared.wx_open_authorizer_service.get_tenant_integration_row")
@patch("app.services.shared.wx_open_authorizer_service.get_component_verify_ticket", return_value="")
def test_patch_authorizer_clear(mock_ticket, mock_get_row):
    row = MagicMock()
    row.wx_mini_appid = "wx_test"
    row.wx_authorizer_access_token = "at"
    row.wx_authorizer_refresh_token = "rt"
    mock_get_row.return_value = row
    db = MagicMock()
    out = patch_authorizer_tokens_admin(db, 1, clear=True)
    assert out["has_authorizer_refresh_token"] is False
    assert row.wx_authorizer_refresh_token is None


@patch("app.services.shared.wx_open_authorizer_service.get_settings")
def test_build_tenant_authorize_redirect_uri(mock_settings):
    mock_settings.return_value.public_base_for_assets = "https://api.example.com"
    uri = build_tenant_authorize_redirect_uri(3)
    assert uri == "https://api.example.com/api/wx/open/authorize/callback?tenant_id=3"


@patch("app.services.shared.wx_open_authorizer_service.get_settings")
def test_build_tenant_authorize_redirect_uri_requires_base(mock_settings):
    mock_settings.return_value.public_base_for_assets = ""
    with pytest.raises(HTTPException) as exc:
        build_tenant_authorize_redirect_uri(3)
    assert exc.value.status_code == 503


def test_pop_tenant_id_for_pre_auth_roundtrip():
    from app.services.shared.wx_open_authorizer_service import _register_pending_pre_auth

    _register_pending_pre_auth("preabc", 3, 600)
    assert pop_tenant_id_for_pre_auth("preabc") == 3
    assert pop_tenant_id_for_pre_auth("preabc") is None


@patch("app.services.shared.wx_open_authorizer_service.get_component_verify_ticket", return_value="ticket")
@patch("app.integrations.wechat_open_platform.get_component_access_token", return_value="comp_token")
@patch("app.integrations.wechat_open_platform.wechat_open_platform_configured", return_value=True)
@patch("app.services.shared.wx_open_authorizer_service.get_settings")
@patch("app.services.shared.wx_open_authorizer_service.httpx.Client")
def test_create_tenant_pre_auth_link(mock_client_cls, mock_settings, _cfg, _token, _ticket):
    mock_settings.return_value.WX_OPEN_COMPONENT_APPID = "wx_component"
    mock_settings.return_value.public_base_for_assets = "https://api.example.com"

    tenant = MagicMock()
    tenant.name = "租户3"
    db = MagicMock()
    db.get.return_value = tenant

    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {"pre_auth_code": "pre123", "expires_in": 600}
    client = MagicMock()
    client.__enter__ = MagicMock(return_value=client)
    client.__exit__ = MagicMock(return_value=False)
    client.post.return_value = resp
    mock_client_cls.return_value = client

    out = create_tenant_pre_auth_link(db, 3)
    assert out["tenant_id"] == 3
    assert out["pre_auth_code"] == "pre123"
    assert "pre_auth_code=pre123" in out["authorization_url"]
    assert pop_tenant_id_for_pre_auth("pre123") == 3
