"""顺丰推单后、送达前：小程序自助改地址/份数锁定。"""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.models.member import Member
from app.services.leave import (
    SF_SELF_SERVICE_LOCK_DURING_FULFILLMENT_MSG,
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


def test_lock_composition_delivered_unlocks():
    """已标记送达则不再锁定（推单存在时也如此）。"""
    from app.services.sf_order_fulfillment_service import member_sf_self_service_locked_on_delivery_date

    db = MagicMock()
    with patch(
        "app.services.sf_order_fulfillment_service.member_has_active_sf_push_on_delivery_date",
        return_value=True,
    ), patch(
        "app.services.sf_order_fulfillment_service.member_subscription_delivered_on_delivery_date",
        return_value=True,
    ):
        assert (
            member_sf_self_service_locked_on_delivery_date(
                db, member_id=1, store_id=1, delivery_date=date(2026, 5, 22)
            )
            is False
        )


def test_lock_composition_push_without_delivery():
    from app.services.sf_order_fulfillment_service import member_sf_self_service_locked_on_delivery_date

    db = MagicMock()
    with patch(
        "app.services.sf_order_fulfillment_service.member_has_active_sf_push_on_delivery_date",
        return_value=True,
    ), patch(
        "app.services.sf_order_fulfillment_service.member_subscription_delivered_on_delivery_date",
        return_value=False,
    ):
        assert (
            member_sf_self_service_locked_on_delivery_date(
                db, member_id=1, store_id=1, delivery_date=date(2026, 5, 22)
            )
            is True
        )
