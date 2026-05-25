"""顺丰回调：快速落库 + 异步履约、履约短路、扣次幂等。"""

from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from app.services.sf_order_fulfillment_service import (
    SfCallbackSideEffectJob,
    sf_push_fulfilled_quick_check,
)


def test_sf_push_fulfilled_quick_check_retail_delivered():
    pus = MagicMock()
    pus.push_kind = "single_meal_retail"
    pus.stop_id = "retail-smo-42"
    pus.request_snapshot = {}
    pus.delivery_date = date(2026, 5, 25)
    pus.error_code = 0
    pus.merchant_cancel_requested_at = None
    pus.sf_callback_order_status = 17

    db = MagicMock()
    order = MagicMock()
    order.fulfillment_status = "delivered"
    db.get.return_value = order

    assert sf_push_fulfilled_quick_check(db, pus) is True


def test_sf_push_fulfilled_quick_check_snapshot_all_delivered():
    pus = MagicMock()
    pus.push_kind = "delivery_sheet"
    pus.stop_id = "stop-1"
    pus.request_snapshot = {"fulfillment_member_ids": [1, 2], "fulfillment_single_meal_order_ids": [9]}
    pus.delivery_date = date(2026, 5, 25)
    pus.error_code = 0
    pus.merchant_cancel_requested_at = None
    pus.sf_callback_order_status = 17

    db = MagicMock()
    smo = MagicMock()
    smo.fulfillment_status = "delivered"
    db.get.return_value = smo

    with patch(
        "app.services.sf_order_fulfillment_service.member_subscription_delivered_on_delivery_date",
        return_value=True,
    ):
        assert sf_push_fulfilled_quick_check(db, pus) is True


def test_persist_schedules_side_effect_without_inline_fulfillment():
    from app.services.sf_callback_service import persist_sf_callback_and_sync_push

    pus = MagicMock()
    pus.id = 99
    pus.shop_order_id = "shop-1"
    pus.stop_id = "s1"
    pus.error_code = 0
    pus.merchant_cancel_requested_at = None
    pus.sf_callback_order_status = 17

    db = MagicMock()
    db.scalar.return_value = pus

    with patch(
        "app.services.sf_order_fulfillment_service.should_run_sf_auto_fulfillment",
        return_value=True,
    ), patch(
        "app.services.sf_order_fulfillment_service.should_apply_sf_cancel_sync",
        return_value=False,
    ):
        result = persist_sf_callback_and_sync_push(
            db,
            route_kind="order_complete",
            raw_body='{"shop_order_id":"shop-1"}',
            sign_ok=True,
            payload={"shop_order_id": "shop-1"},
            verify_error=None,
        )

    assert result.side_effect == SfCallbackSideEffectJob(
        push_id=99,
        route_kind="order_complete",
        operator_tag="sf:order_complete",
        action="fulfillment",
    )
    db.commit.assert_called_once()


def test_subscription_apply_idempotent_returns_none():
    from app.models.enums import DeliveryStatus
    from app.services.admin_delivery_fulfillment_service import _subscription_fulfilled_apply

    member = MagicMock()
    member.deleted_at = None
    member.store_pickup = False
    member.is_active = True
    member.balance = 5
    member.delivery_start_date = None

    log = MagicMock()
    log.status = DeliveryStatus.DELIVERED.value

    db = MagicMock()
    db.execute.return_value.scalar_one_or_none.side_effect = [member, log]

    with patch(
        "app.services.admin_delivery_fulfillment_service.is_absent_on_delivery_date",
        return_value=False,
    ), patch(
        "app.services.admin_delivery_fulfillment_service.is_subscription_delivery_day",
        return_value=True,
    ), patch(
        "app.services.admin_delivery_fulfillment_service.effective_daily_meal_units",
        return_value=1,
    ):
        out = _subscription_fulfilled_apply(
            db,
            member_id=1,
            delivery_date=date(2026, 5, 25),
            operator_tag="sf:test",
            kind="home",
            ok_ids={1},
        )
    assert out is None
