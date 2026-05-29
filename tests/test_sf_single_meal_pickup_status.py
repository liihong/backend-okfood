"""顺丰已取货回调：单次订单由待取货进入配送中。"""

from __future__ import annotations

from unittest.mock import MagicMock

from app.services.single_meal_order_service import (
    mark_single_meals_in_delivery_on_sf_pickup_no_commit,
    sync_single_meal_pickup_status_from_sf_push_no_commit,
)


def test_mark_in_delivery_from_sf_awaiting_pickup():
    db = MagicMock()
    row = MagicMock()
    row.pay_status = "已支付"
    row.store_pickup = False
    row.fulfillment_status = "sf_awaiting_pickup"
    db.get.return_value = row

    n = mark_single_meals_in_delivery_on_sf_pickup_no_commit(db, [7])

    assert n == 1
    assert row.fulfillment_status == "accepted"


def test_sync_pickup_from_sf_push_when_status_15():
    db = MagicMock()
    pus = MagicMock()
    pus.error_code = 0
    pus.sf_callback_order_status = 15
    pus.stop_id = "retail-smo-9"
    pus.id = 100
    pus.request_snapshot = {"fulfillment_single_meal_order_ids": [9]}
    row = MagicMock()
    row.pay_status = "已支付"
    row.store_pickup = False
    row.fulfillment_status = "sf_awaiting_pickup"
    db.get.return_value = row
    db.scalars.return_value.all.return_value = []

    n = sync_single_meal_pickup_status_from_sf_push_no_commit(db, pus)

    assert n == 1
    assert row.fulfillment_status == "accepted"
