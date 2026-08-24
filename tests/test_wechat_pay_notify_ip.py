"""微信支付回调 IP 白名单：官方网段与 .env 并集。"""

from __future__ import annotations

from unittest.mock import patch

from app.integrations.wechat_pay_v2 import notify_client_ip_allowed


def test_notify_ip_allows_official_shenzhen_even_if_env_omits_it():
    """现网 .env 曾漏配深圳段，导致已支付回调被拒、订单仍显示未支付。"""
    with patch(
        "app.integrations.wechat_pay_v2.settings"
    ) as mock_settings:
        mock_settings.WECHAT_PAY_IP_WHITELIST = (
            "182.254.48.0/24,140.207.54.0/24,101.226.103.0/24,121.51.58.0/24"
        )
        assert notify_client_ip_allowed("183.3.234.10") is True
        assert notify_client_ip_allowed("58.251.80.20") is True
        assert notify_client_ip_allowed("121.51.30.200") is True
        assert notify_client_ip_allowed("203.205.219.200") is True
        assert notify_client_ip_allowed("81.71.199.64") is True


def test_notify_ip_still_rejects_unrelated_when_whitelist_configured():
    with patch(
        "app.integrations.wechat_pay_v2.settings"
    ) as mock_settings:
        mock_settings.WECHAT_PAY_IP_WHITELIST = "182.254.48.0/24"
        assert notify_client_ip_allowed("8.8.8.8") is False


def test_notify_ip_skips_check_when_whitelist_empty():
    with patch(
        "app.integrations.wechat_pay_v2.settings"
    ) as mock_settings:
        mock_settings.WECHAT_PAY_IP_WHITELIST = ""
        assert notify_client_ip_allowed("8.8.8.8") is True
