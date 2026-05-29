"""大表合并推顺丰成功后，合并停靠点内的单次卡应进入「顺丰待取货」。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.services.single_meal_order_service import mark_single_meals_sf_awaiting_pickup_on_push_no_commit


def test_mark_single_meals_sf_awaiting_pickup_on_push_from_pending():
    db = MagicMock()
    row = MagicMock()
    row.pay_status = "已支付"
    row.store_pickup = False
    row.fulfillment_status = "pending"
    db.get.return_value = row

    n = mark_single_meals_sf_awaiting_pickup_on_push_no_commit(db, [42])

    assert n == 1
    assert row.fulfillment_status == "sf_awaiting_pickup"


def test_mark_single_meals_sf_awaiting_pickup_idempotent_when_already_in_delivery():
    db = MagicMock()
    row = MagicMock()
    row.pay_status = "已支付"
    row.store_pickup = False
    row.fulfillment_status = "accepted"
    db.get.return_value = row

    n = mark_single_meals_sf_awaiting_pickup_on_push_no_commit(db, [42])

    assert n == 0
    assert row.fulfillment_status == "accepted"


def test_persist_sf_push_success_marks_merged_single_meals_accepted():
    from app.services.sf_same_city_service import _persist_sf_push_success

    db = MagicMock()
    prep = MagicMock()
    prep.stop_id = "stop-abc"
    prep.snap_db = {"fulfillment_single_meal_order_ids": [7, 8]}
    with patch(
        "app.services.single_meal_order_service.mark_single_meals_accepted_on_sf_push_no_commit",
        return_value=2,
    ) as mark_fn, patch(
        "app.services.sf_same_city_service._upsert_sf_push_row",
        return_value=MagicMock(),
    ):
        out = _persist_sf_push_success(
            db,
            sid=1,
            d=__import__("datetime").date(2026, 5, 26),
            prep=prep,
            res={"result": {"sf_order_id": "SF123", "sf_bill_id": "B1"}},
        )

    mark_fn.assert_called_once_with(db, [7, 8])
    assert out.ok is True
