"""微信小程序手机号换取：access_token 失效重试。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.integrations import wechat_mini
from app.integrations.wechat_mini import WeChatMiniError, get_phone_pure_number


@pytest.fixture(autouse=True)
def _clear_token_cache():
    wechat_mini._access_token_by_appid.clear()
    yield
    wechat_mini._access_token_by_appid.clear()


@patch("app.integrations.wechat_mini._credentials_for_call", return_value=("wx_test_app", "secret"))
@patch("app.integrations.wechat_mini.get_stable_access_token_for_app")
@patch("app.integrations.wechat_mini._request_getuserphonenumber")
def test_get_phone_retries_once_on_invalid_access_token(mock_request, mock_get_token, _mock_creds):
    mock_get_token.side_effect = ["stale_token", "fresh_token"]
    mock_request.side_effect = [
        {"errcode": 40001, "errmsg": "invalid credential, access_token is invalid or not latest"},
        {"phone_info": {"purePhoneNumber": "15716680808", "countryCode": "86"}},
    ]

    phone = get_phone_pure_number("phone-code-abc")

    assert phone == "15716680808"
    assert mock_get_token.call_count == 2
    assert mock_request.call_count == 2
    mock_request.assert_any_call("phone-code-abc", "stale_token")
    mock_request.assert_any_call("phone-code-abc", "fresh_token")
    assert "wx_test_app" not in wechat_mini._access_token_by_appid or mock_get_token.call_count == 2


@patch("app.integrations.wechat_mini._credentials_for_call", return_value=("wx_test_app", "secret"))
@patch("app.integrations.wechat_mini.get_stable_access_token_for_app", return_value="token")
@patch("app.integrations.wechat_mini._request_getuserphonenumber")
def test_get_phone_still_fails_after_retry(mock_request, _mock_get_token, _mock_creds):
    mock_request.return_value = {
        "errcode": 40001,
        "errmsg": "invalid credential, access_token is invalid or not latest",
    }

    with pytest.raises(WeChatMiniError, match="手机号授权无效或已过期"):
        get_phone_pure_number("phone-code-abc")

    assert mock_request.call_count == 2


@patch("app.integrations.wechat_mini._credentials_for_call", return_value=("wx_test_app", "secret"))
@patch("app.integrations.wechat_mini.get_stable_access_token_for_app", return_value="token")
@patch("app.integrations.wechat_mini._request_getuserphonenumber")
def test_get_phone_does_not_retry_on_invalid_phone_code(mock_request, _mock_get_token, _mock_creds):
    mock_request.return_value = {"errcode": 40029, "errmsg": "invalid code"}

    with pytest.raises(WeChatMiniError, match="手机号授权无效或已过期"):
        get_phone_pure_number("expired-phone-code")

    assert mock_request.call_count == 1
