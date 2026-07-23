"""微信开放平台 authorizer token 落库与刷新。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.services.shared.wx_open_authorizer_service import (
    get_authorizer_admin_state,
    patch_authorizer_tokens_admin,
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
