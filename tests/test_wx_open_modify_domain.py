"""微信 modify_domain 域名规范化与 85301 错误文案。

查询生效域名（管理端，需平台管理员 Token）：
curl -sS "http://127.0.0.1:8000/api/admin/system/tenants/3/wx-code/effective-domains" \\
  -H "Authorization: Bearer $ADMIN_TOKEN"
"""

from unittest.mock import MagicMock, patch

from fastapi import HTTPException
import pytest

from app.services.shared.wx_open_code_service import (
    GET_EFFECTIVE_DOMAIN_URL,
    _domain_list_contains,
    _format_modify_domain_error,
    _to_wechat_bare_host,
    _to_wechat_https_origin,
    get_effective_domains_for_tenant,
)


def test_https_origin_strips_path() -> None:
    assert (
        _to_wechat_https_origin("https://ok.sourcefire.cn/api/v1", label="BASE_URL")
        == "https://ok.sourcefire.cn"
    )


def test_https_origin_adds_scheme() -> None:
    assert _to_wechat_https_origin("ok.sourcefire.cn", label="BASE_URL") == "https://ok.sourcefire.cn"


def test_https_origin_upgrades_http() -> None:
    assert (
        _to_wechat_https_origin("http://okoss.sourcefire.cn/okfood", label="OSS")
        == "https://okoss.sourcefire.cn"
    )


def test_https_origin_rejects_ip() -> None:
    with pytest.raises(HTTPException) as exc:
        _to_wechat_https_origin("https://127.0.0.1", label="BASE_URL")
    assert exc.value.status_code == 400
    assert "IP" in str(exc.value.detail)


def test_bare_host_keeps_non_default_port() -> None:
    origin = _to_wechat_https_origin("https://api.example.com:8443/x", label="BASE_URL")
    assert origin == "https://api.example.com:8443"
    assert _to_wechat_bare_host(origin) == "api.example.com:8443"


def test_domain_list_contains_ignores_scheme_and_path() -> None:
    assert _domain_list_contains(["https://ok.sourcefire.cn/"], "ok.sourcefire.cn")
    assert not _domain_list_contains(["https://other.example.com"], "ok.sourcefire.cn")


def test_format_85301_lists_invalid_domains() -> None:
    msg = _format_modify_domain_error(
        {
            "errcode": 85301,
            "errmsg": "no domain to modify after filtered",
            "invalid_requestdomain": ["https://ok.sourcefire.cn/api"],
            "invalid_downloaddomain": [],
            "no_icp_domain": [],
        },
        submitted={"requestdomain": ["https://ok.sourcefire.cn"], "downloaddomain": []},
    )
    assert "85301" in msg
    assert "https://ok.sourcefire.cn/api" in msg
    assert "小程序服务器域名" in msg


@patch("app.services.shared.wx_open_code_service._authorizer_access_token_or_http", return_value="tok")
@patch("app.services.shared.wx_open_code_service._ensure_authorizer_for_code_ops")
@patch("app.services.shared.wx_open_code_service.httpx.Client")
def test_get_effective_domains_uses_post_with_empty_json(
    mock_client_cls: MagicMock,
    _ensure: MagicMock,
    _token: MagicMock,
) -> None:
    """微信 get_effective_domain 必须 POST，空 GET 会返回 43002。"""
    resp = MagicMock()
    resp.json.return_value = {
        "errcode": 0,
        "effective_domain": {"requestdomain": ["https://ok.sourcefire.cn"]},
    }
    client = MagicMock()
    client.post.return_value = resp
    mock_client_cls.return_value.__enter__.return_value = client

    out = get_effective_domains_for_tenant(MagicMock(), 3)

    client.post.assert_called_once()
    args, kwargs = client.post.call_args
    assert args[0] == GET_EFFECTIVE_DOMAIN_URL
    assert kwargs["params"] == {"access_token": "tok"}
    assert kwargs["json"] == {}
    client.get.assert_not_called()
    assert out["requestdomain"] == ["https://ok.sourcefire.cn"]
