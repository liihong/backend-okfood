"""抖音验券兑换：撤销核销与发奖失败处理。"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.integrations.douyin_life import DouyinPrepareCertificate, DouyinPrepareResult
from app.models.enums import DouyinRedemptionStatus
from app.models.douyin.certificate_redemption import DouyinCertificateRedemption
from app.models.member import Member
from app.schemas.douyin import DouyinCertificateRedeemIn
from app.services.douyin.certificate_service import (
    _grant_error_message,
    _handle_grant_failure,
    _try_cancel_douyin_verify,
    redeem_douyin_certificate,
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
    db.scalar.return_value = row

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
    row.status = DouyinRedemptionStatus.VERIFIED.value
    db.scalar.return_value = row

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


@patch("app.services.douyin.certificate_service._try_cancel_douyin_verify")
def test_handle_grant_failure_skips_cancel_when_already_success(mock_cancel):
    """并发续发奖已成功时，不得撤销抖音核销（否则本地 success + 抖音未核销）。"""
    db = MagicMock()
    row = MagicMock()
    row.status = DouyinRedemptionStatus.SUCCESS.value
    db.scalar.return_value = row

    _handle_grant_failure(
        db,
        access_token="tok",
        redemption_id=3,
        certificate_id="cert-3",
        douyin_verify_id="verify-3",
        grant_error="late failure",
    )

    mock_cancel.assert_not_called()
    db.commit.assert_not_called()


@patch("app.services.douyin.certificate_service._complete_local_grant")
@patch("app.services.douyin.certificate_service.certificate_verify")
@patch("app.services.douyin.certificate_service.certificate_prepare")
@patch("app.services.douyin.certificate_service.find_active_mapping_for_certificate")
@patch("app.services.douyin.certificate_service.get_douyin_access_token")
@patch("app.services.douyin.certificate_service.get_douyin_store_config")
def test_redeem_prepare_ok_with_verified_row_still_calls_verify(
    mock_store_cfg,
    mock_access_token,
    mock_find_mapping,
    mock_prepare,
    mock_verify,
    mock_complete_grant,
):
    """prepare 成功时即使本地流水为 verified，也必须调用抖音 verify，不可仅续发本地权益。"""
    mock_store_cfg.return_value = MagicMock(poi_id="poi-1", account_id="acc-1")
    mock_access_token.return_value = "tok"
    mock_find_mapping.return_value = MagicMock(
        id=1,
        grant_type="week_card",
        target_id=None,
        display_name="周卡",
        is_active=True,
    )
    cert = DouyinPrepareCertificate(
        certificate_id="cert-99",
        encrypted_code="enc-code",
        code="121349085360194",
        product_id="p1",
        sku_id="s1",
        product_out_id=None,
        sku_out_id=None,
        third_sku_id=None,
        title="周卡",
        pay_amount_fen=9900,
    )
    mock_prepare.return_value = DouyinPrepareResult(
        verify_token="vt-new",
        order_id="121349085360194",
        certificates=[cert],
    )
    mock_verify.return_value = {
        "verify_results": [{"result": 0, "verify_id": "dy-verify-new", "msg": "验券成功"}]
    }
    mock_complete_grant.return_value = MagicMock(message="ok")

    db = MagicMock()
    member = Member(id=1, tenant_id=1, store_id=1, deleted_at=None)
    db.get.return_value = member

    existing = DouyinCertificateRedemption(
        id=10,
        tenant_id=1,
        store_id=1,
        member_id=1,
        certificate_id="cert-99",
        status=DouyinRedemptionStatus.VERIFIED.value,
        douyin_verify_id="old-verify",
        verify_token="vt-old",
        douyin_order_id="121349085360194",
        mapping_id=1,
        amount_yuan=Decimal("99.00"),
    )
    db.scalar.return_value = existing

    redeem_douyin_certificate(
        db,
        member_id=1,
        body=DouyinCertificateRedeemIn(code="121349085360194"),
    )

    mock_verify.assert_called_once()
    call_kw = mock_verify.call_args.kwargs
    assert call_kw["verify_token"] == "vt-new"
    assert call_kw["encrypted_codes"] == ["enc-code"]
    assert call_kw["order_id"] == "121349085360194"
    mock_complete_grant.assert_called_once()
