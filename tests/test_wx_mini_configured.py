"""wx_mini_configured_for_tenant：直连 Secret 与 SaaS authorizer 双路径（不影响 OK饭）。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.integrations.wechat_mini import wx_mini_configured_for_tenant


@patch("app.services.shared.tenant_integration_service.get_merged_wx_credentials")
def test_configured_when_appid_and_secret(mock_creds):
    """主租户/直连：AppId+Secret 齐全即通过（OK饭路径）。"""
    mock_creds.return_value = ("wx_okfood", "secret_ok")
    db = MagicMock()
    assert wx_mini_configured_for_tenant(db, 1) is True
    mock_creds.assert_called_once_with(db, 1)


@patch(
    "app.services.shared.wx_open_authorizer_service.tenant_has_authorizer_tokens",
    return_value=True,
)
@patch(
    "app.integrations.wechat_open_platform.wechat_open_platform_configured",
    return_value=True,
)
@patch("app.services.shared.tenant_integration_service.get_merged_wx_credentials")
def test_configured_authorizer_without_secret(mock_creds, _plat, _auth):
    """SaaS：仅有 AppId + authorizer，无 Secret 亦可登录。"""
    mock_creds.return_value = ("wx6131d6d74a3edc6f", "")
    db = MagicMock()
    assert wx_mini_configured_for_tenant(db, 3) is True


@patch(
    "app.services.shared.wx_open_authorizer_service.tenant_has_authorizer_tokens",
    return_value=False,
)
@patch(
    "app.integrations.wechat_open_platform.wechat_open_platform_configured",
    return_value=True,
)
@patch("app.services.shared.tenant_integration_service.get_merged_wx_credentials")
def test_not_configured_without_secret_or_authorizer(mock_creds, _plat, _auth):
    """无 Secret 且无 authorizer：拒绝（非主租户禁止借全局密钥）。"""
    mock_creds.return_value = ("wx_other", "")
    db = MagicMock()
    assert wx_mini_configured_for_tenant(db, 3) is False


@patch("app.services.shared.tenant_integration_service.get_merged_wx_credentials")
def test_not_configured_without_appid(mock_creds):
    mock_creds.return_value = ("", "")
    db = MagicMock()
    assert wx_mini_configured_for_tenant(db, 3) is False
