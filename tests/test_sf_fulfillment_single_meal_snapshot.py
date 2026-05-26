"""顺丰大表推单妥投：不得误标推单后新下的单次卡。"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

from app.services.sf_order_fulfillment_service import _single_meal_order_ids_for_push


def test_delivery_sheet_tuotou_skips_single_placed_after_push():
    pus = MagicMock()
    pus.request_snapshot = {
        "fulfillment_member_ids": [940],
        "preview_row": {"single_meal_count": 0, "subscription_pending_units": 1},
    }
    pus.created_at = datetime(2026, 5, 26, 7, 0, 30)

    agg = MagicMock()
    agg.singles = [{"id": 96, "qty": 1}]

    db = MagicMock()
    late_order = MagicMock()
    late_order.created_at = datetime(2026, 5, 26, 10, 11, 41)
    db.get.return_value = late_order

    oids = _single_meal_order_ids_for_push(db, pus, agg)
    assert oids == []


def test_delivery_sheet_tuotou_uses_snapshot_single_meal_ids():
    pus = MagicMock()
    pus.request_snapshot = {
        "fulfillment_member_ids": [940],
        "fulfillment_single_meal_order_ids": [96],
        "preview_row": {"single_meal_count": 1, "subscription_pending_units": 1},
    }
    pus.created_at = datetime(2026, 5, 26, 7, 0, 30)

    oids = _single_meal_order_ids_for_push(MagicMock(), pus, None)
    assert oids == [96]


def test_empty_snapshot_single_meal_ids_means_no_singles():
    pus = MagicMock()
    pus.request_snapshot = {
        "fulfillment_member_ids": [940],
        "fulfillment_single_meal_order_ids": [],
        "preview_row": {"single_meal_count": 0, "subscription_pending_units": 1},
    }
    pus.created_at = datetime(2026, 5, 26, 7, 0, 30)

    agg = MagicMock()
    agg.singles = [{"id": 96, "qty": 1}]

    oids = _single_meal_order_ids_for_push(MagicMock(), pus, agg)
    assert oids == []
