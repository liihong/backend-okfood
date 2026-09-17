"""微信 modify_domain 域名规范化与 85301 错误文案。"""

from fastapi import HTTPException
import pytest

from app.services.shared.wx_open_code_service import (
    _domain_list_contains,
    _format_modify_domain_error,
    _to_wechat_bare_host,
    _to_wechat_https_origin,
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
