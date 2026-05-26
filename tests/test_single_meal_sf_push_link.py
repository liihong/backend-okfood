"""单次订单与顺丰推单软关联。"""

from __future__ import annotations

from unittest.mock import MagicMock

from app.services.single_meal_order_service import (
    link_single_meal_orders_to_sf_push_no_commit,
    resolve_sf_push_for_single_meal_order,
)


def test_resolve_prefers_sf_same_city_push_id_on_order():
    db = MagicMock()
    o = MagicMock()
    o.store_id = 1
    o.sf_same_city_push_id = 4029
    pus = MagicMock()
    pus.id = 4029
    pus.error_code = 0
    pus.store_id = 1

    def _get(model, pk):
        if pk == 96:
            return o
        if pk == 4029:
            return pus
        return None

    db.get.side_effect = _get

    got = resolve_sf_push_for_single_meal_order(db, store_id=1, order_id=96)
    assert got is pus
    db.scalars.assert_not_called()


def test_link_single_meal_order_sets_push_id_and_sf_order_id():
    db = MagicMock()
    row = MagicMock()
    row.sf_same_city_push_id = None
    row.sf_order_id = None
    db.get.return_value = row
    pus = MagicMock()
    pus.id = 100
    pus.sf_order_id = "JS123"

    n = link_single_meal_orders_to_sf_push_no_commit(db, [96], pus)
    assert n == 1
    assert row.sf_same_city_push_id == 100
    assert row.sf_order_id == "JS123"
