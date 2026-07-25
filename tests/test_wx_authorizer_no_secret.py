"""方案 C：代授权租户无 Secret 时可登录/取号/订阅；失败不回退直连 Secret。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.integrations.wechat_mini import (
    WeChatMiniError,
    get_phone_pure_number,
    send_subscribe_message,
)
from app.integrations.wechat_open_platform import jscode2session_via_authorizer


@patch("app.integrations.wechat_mini.jscode2session")
@patch(
    "app.integrations.wechat_open_platform.tenant_uses_authorizer_mode",
    return_value=False,
)
def test_okfood_still_uses_direct_jscode2session(mock_auth_mode, mock_direct):
    """OK饭无 authorizer：仍走直连 Secret。"""
    mock_direct.return_value = {"openid": "oid_okfood"}
    db = MagicMock()
    out = jscode2session_via_authorizer("js_code", db=db, tenant_id=1)
    assert out["openid"] == "oid_okfood"
    mock_direct.assert_called_once_with("js_code", db=db, tenant_id=1)
    mock_auth_mode.assert_called_once_with(db, 1)


@patch("app.integrations.wechat_mini.jscode2session")
@patch("app.integrations.wechat_open_platform.get_component_access_token", return_value="comp_tok")
@patch(
    "app.services.shared.tenant_integration_service.get_merged_wx_credentials",
    return_value=("wx_saas_app", ""),
)
@patch(
    "app.integrations.wechat_open_platform.tenant_uses_authorizer_mode",
    return_value=True,
)
@patch("app.integrations.wechat_open_platform.httpx.Client")
def test_authorizer_login_no_secret_fallback_on_wx_error(
    mock_client_cls, _mode, _creds, _comp, mock_direct
):
    """代授权 jscode2session 业务失败：禁止回退直连 Secret。"""
    mock_client = MagicMock()
    mock_client_cls.return_value.__enter__.return_value = mock_client
    mock_client.get.return_value.json.return_value = {
        "errcode": 40029,
        "errmsg": "invalid code",
    }
    mock_client.get.return_value.raise_for_status = MagicMock()

    db = MagicMock()
    with pytest.raises(WeChatMiniError, match="代授权登录失败"):
        jscode2session_via_authorizer("bad_code", db=db, tenant_id=3)
    mock_direct.assert_not_called()


@patch("app.integrations.wechat_mini.jscode2session")
@patch(
    "app.services.shared.wx_open_authorizer_service.get_valid_authorizer_access_token",
    return_value="auth_at",
)
@patch("app.integrations.wechat_open_platform.get_component_access_token", return_value="comp_tok")
@patch(
    "app.services.shared.tenant_integration_service.get_merged_wx_credentials",
    return_value=("wx_saas_app", ""),
)
@patch(
    "app.integrations.wechat_open_platform.tenant_uses_authorizer_mode",
    return_value=True,
)
@patch("app.integrations.wechat_open_platform.httpx.Client")
def test_authorizer_login_success_without_secret(
    mock_client_cls, _mode, _creds, _comp, _auth_at, mock_direct
):
    mock_client = MagicMock()
    mock_client_cls.return_value.__enter__.return_value = mock_client
    mock_client.get.return_value.json.return_value = {"openid": "oid_saas", "session_key": "sk"}
    mock_client.get.return_value.raise_for_status = MagicMock()

    db = MagicMock()
    out = jscode2session_via_authorizer("js_ok", db=db, tenant_id=3)
    assert out["openid"] == "oid_saas"
    mock_direct.assert_not_called()


@patch("app.integrations.wechat_mini._credentials_for_call")
@patch(
    "app.integrations.wechat_mini._resolve_appid_and_access_token",
    return_value=("wx_saas", "authorizer_tok", True),
)
@patch("app.integrations.wechat_mini._request_getuserphonenumber")
def test_get_phone_authorizer_path_never_asks_secret(mock_request, _resolve, mock_creds):
    mock_request.return_value = {
        "phone_info": {"purePhoneNumber": "13800138000", "countryCode": "86"}
    }
    db = MagicMock()
    phone = get_phone_pure_number("phone_code", db=db, tenant_id=3)
    assert phone == "13800138000"
    mock_creds.assert_not_called()


@patch("app.integrations.wechat_mini._credentials_for_call")
@patch(
    "app.integrations.wechat_mini._resolve_appid_and_access_token",
    return_value=("wx_saas", "authorizer_tok", True),
)
@patch("app.integrations.wechat_mini.httpx.Client")
def test_subscribe_authorizer_path_never_asks_secret(mock_client_cls, _resolve, mock_creds):
    mock_client = MagicMock()
    mock_client_cls.return_value.__enter__.return_value = mock_client
    mock_client.post.return_value.json.return_value = {"errcode": 0}
    mock_client.post.return_value.raise_for_status = MagicMock()

    db = MagicMock()
    out = send_subscribe_message(
        "oid",
        "tmpl",
        page="pages/index",
        data={"thing1": {"value": "hi"}},
        db=db,
        tenant_id=3,
    )
    assert out.get("errcode") in (None, 0)
    mock_creds.assert_not_called()
