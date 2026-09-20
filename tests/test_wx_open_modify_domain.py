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
    _apply_authorizer_server_domain,
    _domain_list_contains,
    _format_modify_domain_error,
    _snapshot_contains,
    _split_domain_csv,
    _to_wechat_bare_host,
    _to_wechat_https_origin,
    ensure_third_party_server_domain_pool,
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


def test_snapshot_contains_third_or_direct_domain() -> None:
    snap = {
        "requestdomain": [],
        "effective_domain": {"requestdomain": []},
        "third_domain": {"requestdomain": ["https://ok.sourcefire.cn"]},
        "direct_domain": {"requestdomain": []},
        "mp_domain": {"requestdomain": []},
    }
    assert _snapshot_contains(snap, "requestdomain", "https://ok.sourcefire.cn")
    snap["third_domain"] = {"requestdomain": []}
    snap["direct_domain"] = {"requestdomain": ["https://ok.sourcefire.cn"]}
    assert _snapshot_contains(snap, "requestdomain", "ok.sourcefire.cn")


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
    assert "全网发布" in msg


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
        "third_domain": {"requestdomain": ["https://ok.sourcefire.cn"]},
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
    assert out["third_domain"]["requestdomain"] == ["https://ok.sourcefire.cn"]


def test_split_domain_csv_semicolon_and_spaces() -> None:
    assert _split_domain_csv("ok.sourcefire.cn;okoss.sourcefire.cn") == {
        "ok.sourcefire.cn",
        "okoss.sourcefire.cn",
    }
    assert _split_domain_csv("ok.sourcefire.cn okoss.sourcefire.cn") == {
        "ok.sourcefire.cn",
        "okoss.sourcefire.cn",
    }


@patch("app.integrations.wechat_open_platform.get_component_access_token", return_value="comp")
@patch("app.services.shared.wx_open_code_service._post_modify_wxa_server_domain")
def test_domain_pool_adds_to_published_together(
    mock_post: MagicMock,
    _token: MagicMock,
) -> None:
    """已全网发布平台必须写入 published 池，只写测试版会 85301。"""
    mock_post.side_effect = [
        {"errcode": 0, "published_wxa_server_domain": "", "testing_wxa_server_domain": ""},
        {
            "errcode": 0,
            "published_wxa_server_domain": "ok.sourcefire.cn",
            "testing_wxa_server_domain": "ok.sourcefire.cn",
        },
    ]
    out = ensure_third_party_server_domain_pool(MagicMock(), ["ok.sourcefire.cn"])
    assert out["added"] == ["ok.sourcefire.cn"]
    add_body = mock_post.call_args_list[1][0][1]
    assert add_body["action"] == "add"
    assert add_body["wxa_server_domain"] == "ok.sourcefire.cn"
    assert add_body["is_modify_published_together"] is True


@patch("app.integrations.wechat_open_platform.get_component_access_token", return_value="comp")
@patch("app.services.shared.wx_open_code_service._post_modify_wxa_server_domain")
def test_domain_pool_61028_retries_testing_only(
    mock_post: MagicMock,
    _token: MagicMock,
) -> None:
    mock_post.side_effect = [
        {"errcode": 0, "published_wxa_server_domain": "", "testing_wxa_server_domain": ""},
        {"errcode": 61028, "errmsg": "第三方平台未发布"},
        {
            "errcode": 0,
            "testing_wxa_server_domain": "ok.sourcefire.cn",
        },
    ]
    out = ensure_third_party_server_domain_pool(MagicMock(), ["ok.sourcefire.cn"])
    assert out["added"] == ["ok.sourcefire.cn"]
    assert mock_post.call_args_list[1][0][1]["is_modify_published_together"] is True
    assert mock_post.call_args_list[2][0][1]["is_modify_published_together"] is False


@patch("app.integrations.wechat_open_platform.get_component_access_token", return_value="comp")
@patch("app.services.shared.wx_open_code_service._post_modify_wxa_server_domain")
def test_domain_pool_9410016_is_not_skipped(
    mock_post: MagicMock,
    _token: MagicMock,
) -> None:
    mock_post.side_effect = [
        {"errcode": 0, "published_wxa_server_domain": "", "testing_wxa_server_domain": ""},
        {"errcode": 9410016, "errmsg": "存在无效域名", "invalid_wxa_server_domain": "ok.sourcefire.cn"},
    ]
    with pytest.raises(HTTPException) as exc:
        ensure_third_party_server_domain_pool(MagicMock(), ["ok.sourcefire.cn"])
    assert exc.value.status_code == 400
    assert "9410016" in str(exc.value.detail)


@patch("app.services.shared.wx_open_code_service._post_modify_domain_directly")
@patch("app.services.shared.wx_open_code_service._post_modify_domain")
def test_apply_falls_back_to_directly_on_85301(
    mock_modify: MagicMock,
    mock_direct: MagicMock,
) -> None:
    mock_modify.return_value = {
        "errcode": 85301,
        "errmsg": "no domain to modify after filtered",
        "invalid_requestdomain": ["https://ok.sourcefire.cn"],
    }
    mock_direct.return_value = {"errcode": 0, "errmsg": "ok"}
    payload = {
        "action": "add",
        "requestdomain": ["https://ok.sourcefire.cn"],
        "wsrequestdomain": [],
        "uploaddomain": ["https://ok.sourcefire.cn"],
        "downloaddomain": ["https://ok.sourcefire.cn"],
        "udpdomain": [],
        "tcpdomain": [],
    }
    data, method = _apply_authorizer_server_domain("tok", payload)
    assert method == "modify_domain_directly"
    assert data.get("errcode") == 0
    mock_direct.assert_called_once_with("tok", payload)
