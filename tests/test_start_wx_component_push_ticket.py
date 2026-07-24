"""start_wx_component_push_ticket 脚本 smoke test。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import scripts.start_wx_component_push_ticket as mod


@patch("scripts.start_wx_component_push_ticket.get_settings")
@patch("scripts.start_wx_component_push_ticket.httpx.Client")
def test_start_push_ticket_ok(mock_client_cls, mock_settings):
    mock_settings.return_value.WX_OPEN_COMPONENT_APPID = "wx_test"
    mock_settings.return_value.WX_OPEN_COMPONENT_SECRET = "secret"

    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {"errcode": 0, "errmsg": "ok"}
    client = MagicMock()
    client.__enter__ = MagicMock(return_value=client)
    client.__exit__ = MagicMock(return_value=False)
    client.post.return_value = resp
    mock_client_cls.return_value = client

    assert mod.main() == 0
    client.post.assert_called_once()


@patch("scripts.start_wx_component_push_ticket.get_settings")
def test_start_push_ticket_missing_env(mock_settings):
    mock_settings.return_value.WX_OPEN_COMPONENT_APPID = ""
    mock_settings.return_value.WX_OPEN_COMPONENT_SECRET = ""
    assert mod.main() == 1
