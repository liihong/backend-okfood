"""抖音撤销核销 OpenAPI 封装。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.integrations.douyin_life import certificate_cancel, DouyinLifeError


@patch("app.integrations.douyin_life.httpx.post")
def test_certificate_cancel_success(mock_post):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "data": {"error_code": 0, "description": "success"},
        "extra": {"error_code": 0, "description": "success"},
    }
    mock_post.return_value = mock_resp

    data = certificate_cancel(
        access_token="token",
        verify_id="123",
        certificate_id="456",
        cancel_token="cancel-tok",
    )
    assert data["error_code"] == 0
    mock_post.assert_called_once()
    call_kwargs = mock_post.call_args.kwargs
    assert call_kwargs["json"]["verify_id"] == "123"
    assert call_kwargs["json"]["certificate_id"] == "456"
    assert call_kwargs["json"]["cancel_token"] == "cancel-tok"


@patch("app.integrations.douyin_life.httpx.post")
def test_certificate_cancel_api_error(mock_post):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "data": {"error_code": 3000003, "description": "撤销核销超时"},
        "extra": {"error_code": 3000003, "description": "撤销核销超时"},
    }
    mock_post.return_value = mock_resp

    try:
        certificate_cancel(access_token="token", verify_id="1", certificate_id="2")
        assert False, "should raise"
    except DouyinLifeError as exc:
        assert "撤销核销超时" in str(exc)
