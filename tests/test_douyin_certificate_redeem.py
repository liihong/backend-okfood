"""抖音验券兑换：撤销核销与发奖失败处理。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.models.enums import DouyinRedemptionStatus
from app.services.douyin.certificate_service import (
    _grant_error_message,
    _handle_grant_failure,
    _try_cancel_douyin_verify,
)


def test_grant_error_message_from_http_exception():
    exc = HTTPException(status_code=400, detail="周卡配置异常")
    assert _grant_error_message(exc) == "周卡配置异常"


def test_grant_error_message_from_generic_exception():
    assert _grant_error_message(RuntimeError("db down")) == "db down"


def test_try_cancel_douyin_verify_missing_ids():
    ok, err = _try_cancel_douyin_verify(access_token="tok", verify_id="", certificate_id="cid")
    assert ok is False
    assert err is not None


@patch("app.services.douyin.certificate_service.certificate_cancel")
def test_try_cancel_douyin_verify_success(mock_cancel):
    mock_cancel.return_value = {"error_code": 0}
    ok, err = _try_cancel_douyin_verify(
        access_token="tok",
        verify_id="vid",
        certificate_id="cid",
    )
    assert ok is True
    assert err is None
    mock_cancel.assert_called_once()


@patch("app.services.douyin.certificate_service._try_cancel_douyin_verify")
def test_handle_grant_failure_cancel_ok_marks_cancelled(mock_cancel):
    mock_cancel.return_value = (True, None)
    db = MagicMock()
    row = MagicMock()
    row.status = DouyinRedemptionStatus.VERIFIED.value
    db.get.return_value = row

    with pytest.raises(HTTPException) as ei:
        _handle_grant_failure(
            db,
            access_token="tok",
            redemption_id=1,
            certificate_id="cert-1",
            douyin_verify_id="verify-1",
            grant_error="Data truncated for column pay_channel",
        )

    assert ei.value.status_code == 400
    assert row.status == DouyinRedemptionStatus.CANCELLED.value
    assert "撤销核销" in (row.error_msg or "")
    db.commit.assert_called_once()


@patch("app.services.douyin.certificate_service._try_cancel_douyin_verify")
def test_handle_grant_failure_cancel_fail_marks_grant_failed(mock_cancel):
    mock_cancel.return_value = (False, "超过可撤销时间")
    db = MagicMock()
    row = MagicMock()
    db.get.return_value = row

    with pytest.raises(HTTPException) as ei:
        _handle_grant_failure(
            db,
            access_token="tok",
            redemption_id=2,
            certificate_id="cert-2",
            douyin_verify_id="verify-2",
            grant_error="Data truncated for column pay_channel",
        )

    assert ei.value.status_code == 500
    assert row.status == DouyinRedemptionStatus.GRANT_FAILED.value
    assert "撤销核销失败" in (row.error_msg or "")
