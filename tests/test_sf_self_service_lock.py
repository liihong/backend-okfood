"""顺丰推单后、会员自身配送完成前：小程序自助改地址/份数/请假锁定。"""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.models.member import Member
from app.models.sf_same_city_push import SfSameCityPush
from app.services.leave import (
    SF_SELF_SERVICE_LOCK_DURING_FULFILLMENT_MSG,
    SF_SELF_SERVICE_LOCK_LEAVE_MSG,
    guard_member_self_leave_during_sf_fulfillment,
    guard_member_self_service_during_sf_fulfillment,
)


def test_guard_raises_when_sf_fulfillment_locked():
    db = MagicMock()
    m = Member(id=1, store_id=1, phone="13800000000")
    biz = date(2026, 5, 22)
    with patch(
        "app.services.sf_order_fulfillment_service.member_sf_self_service_locked_on_delivery_date",
        return_value=True,
    ):
        with pytest.raises(HTTPException) as exc:
            guard_member_self_service_during_sf_fulfillment(db, m, delivery_date=biz)
    assert exc.value.status_code == 400
    assert exc.value.detail == SF_SELF_SERVICE_LOCK_DURING_FULFILLMENT_MSG


def test_guard_passes_when_not_locked():
    db = MagicMock()
    m = Member(id=1, store_id=1, phone="13800000000")
    with patch(
        "app.services.sf_order_fulfillment_service.member_sf_self_service_locked_on_delivery_date",
        return_value=False,
    ):
        guard_member_self_service_during_sf_fulfillment(db, m, delivery_date=date(2026, 5, 22))


def test_leave_guard_raises_when_locked():
    db = MagicMock()
    m = Member(id=1, store_id=1, phone="13800000000")
    with patch(
        "app.services.sf_order_fulfillment_service.member_sf_self_service_locked_on_delivery_date",
        return_value=True,
    ):
        with pytest.raises(HTTPException) as exc:
            guard_member_self_leave_during_sf_fulfillment(db, m)
    assert exc.value.status_code == 400
    assert exc.value.detail == SF_SELF_SERVICE_LOCK_LEAVE_MSG


def test_member_unlocks_when_no_relevant_push():
    from app.services.sf_order_fulfillment_service import member_sf_self_service_locked_on_delivery_date

    db = MagicMock()
    with patch(
        "app.services.sf_order_fulfillment_service._member_active_sf_pushes_on_delivery_date",
        return_value=[],
    ):
        assert (
            member_sf_self_service_locked_on_delivery_date(
                db, member_id=1, store_id=1, delivery_date=date(2026, 5, 22)
            )
            is False
        )


def test_member_locked_when_own_push_in_transit():
    from app.services.sf_order_fulfillment_service import member_sf_self_service_locked_on_delivery_date

    db = MagicMock()
    pus = MagicMock(spec=SfSameCityPush)
    with patch(
        "app.services.sf_order_fulfillment_service._member_active_sf_pushes_on_delivery_date",
        return_value=[pus],
    ), patch(
        "app.services.sf_order_fulfillment_service._member_sf_push_fulfilled_for_lock",
        return_value=False,
    ):
        assert (
            member_sf_self_service_locked_on_delivery_date(
                db, member_id=1, store_id=1, delivery_date=date(2026, 5, 22)
            )
            is True
        )


def test_member_unlocks_when_own_push_fulfilled():
    from app.services.sf_order_fulfillment_service import member_sf_self_service_locked_on_delivery_date

    db = MagicMock()
    pus = MagicMock(spec=SfSameCityPush)
    with patch(
        "app.services.sf_order_fulfillment_service._member_active_sf_pushes_on_delivery_date",
        return_value=[pus],
    ), patch(
        "app.services.sf_order_fulfillment_service._member_sf_push_fulfilled_for_lock",
        return_value=True,
    ):
        assert (
            member_sf_self_service_locked_on_delivery_date(
                db, member_id=1, store_id=1, delivery_date=date(2026, 5, 22)
            )
            is False
        )


def test_member_unlocks_when_sf_callback_status_17():
    from app.services.sf_order_fulfillment_service import (
        _member_sf_push_fulfilled_for_lock,
        member_sf_self_service_locked_on_delivery_date,
    )

    db = MagicMock()
    pus = MagicMock(spec=SfSameCityPush)
    pus.error_code = 0
    pus.merchant_cancel_requested_at = None
    pus.sf_callback_order_status = 17
    pus.request_snapshot = {"fulfillment_member_ids": [1]}
    pus.delivery_date = date(2026, 5, 25)

    assert _member_sf_push_fulfilled_for_lock(db, pus, member_id=1) is True

    with patch(
        "app.services.sf_order_fulfillment_service._member_active_sf_pushes_on_delivery_date",
        return_value=[pus],
    ):
        assert (
            member_sf_self_service_locked_on_delivery_date(
                db, member_id=1, store_id=1, delivery_date=date(2026, 5, 25)
            )
            is False
        )


def test_store_unlocks_when_all_sf_callback_status_17():
    """门店级统计：顺丰已全部回调妥投(17)时视为全部履约。"""
    from app.services.sf_order_fulfillment_service import store_has_unfulfilled_sf_push_on_delivery_date

    db = MagicMock()
    pus = MagicMock(spec=SfSameCityPush)
    pus.sf_callback_order_status = 17
    pus.request_snapshot = {"fulfillment_member_ids": [1]}
    db.scalars.return_value.all.return_value = [pus]

    assert (
        store_has_unfulfilled_sf_push_on_delivery_date(
            db, store_id=1, delivery_date=date(2026, 5, 25)
        )
        is False
    )


def test_store_locked_when_sf_in_transit():
    from app.services.sf_order_fulfillment_service import store_has_unfulfilled_sf_push_on_delivery_date

    db = MagicMock()
    pus = MagicMock(spec=SfSameCityPush)
    pus.sf_callback_order_status = 10
    pus.request_snapshot = {}
    db.scalars.return_value.all.return_value = [pus]

    assert (
        store_has_unfulfilled_sf_push_on_delivery_date(
            db, store_id=1, delivery_date=date(2026, 5, 25)
        )
        is True
    )
