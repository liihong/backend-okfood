"""顺丰推单后、当日全部送达前：小程序自助改地址/份数/请假锁定。"""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.models.member import Member
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


def test_lock_composition_all_fulfilled_unlocks():
    """当日全部推单已标记送达则不再锁定。"""
    from app.services.sf_order_fulfillment_service import member_sf_self_service_locked_on_delivery_date

    db = MagicMock()
    with patch(
        "app.services.sf_order_fulfillment_service.store_has_unfulfilled_sf_push_on_delivery_date",
        return_value=False,
    ):
        assert (
            member_sf_self_service_locked_on_delivery_date(
                db, member_id=1, store_id=1, delivery_date=date(2026, 5, 22)
            )
            is False
        )


def test_lock_composition_push_without_all_fulfilled():
    from app.services.sf_order_fulfillment_service import member_sf_self_service_locked_on_delivery_date

    db = MagicMock()
    with patch(
        "app.services.sf_order_fulfillment_service.store_has_unfulfilled_sf_push_on_delivery_date",
        return_value=True,
    ):
        assert (
            member_sf_self_service_locked_on_delivery_date(
                db, member_id=1, store_id=1, delivery_date=date(2026, 5, 22)
            )
            is True
        )


def test_lock_composition_no_push():
    from app.services.sf_order_fulfillment_service import member_sf_self_service_locked_on_delivery_date

    db = MagicMock()
    with patch(
        "app.services.sf_order_fulfillment_service.store_has_unfulfilled_sf_push_on_delivery_date",
        return_value=False,
    ):
        assert (
            member_sf_self_service_locked_on_delivery_date(
                db, member_id=1, store_id=1, delivery_date=date(2026, 5, 22)
            )
            is False
        )
