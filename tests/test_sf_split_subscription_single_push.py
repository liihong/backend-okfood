"""月卡大表推单与单次卡拆分：各创一单顺丰。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.schemas.admin import SfSameCityPreviewRow
from app.services.sf_same_city_service import (
    _delivery_sheet_push_row,
    _fulfillment_ids_for_delivery_sheet_push,
)


def test_delivery_sheet_push_row_excludes_single_meal_count():
    row = SfSameCityPreviewRow(
        stop_id="abcd1234",
        group_area="A区",
        address_line="1号",
        pickup_phone="13800000000",
        recv_name="张三",
        recv_phone="13800000000",
        product_category="餐品",
        weight_kg=1.0,
        subscription_pending_units=1,
        single_meal_count=1,
    )
    out = _delivery_sheet_push_row(row)
    assert out.subscription_pending_units == 1
    assert out.single_meal_count == 0


def test_fulfillment_ids_for_delivery_sheet_push_omits_singles():
    agg = MagicMock()
    agg.sub_lines = [{"member_id": 940, "units": 1, "is_delivered": False}]
    agg.singles = [{"id": 96, "qty": 1}]
    db = MagicMock()
    mids, oids, member_ids = _fulfillment_ids_for_delivery_sheet_push(db, agg)
    assert mids == [940]
    assert oids == []
    assert member_ids == {940}


def test_push_delivery_sheet_does_not_auto_push_single_meals():
    from app.services.sf_same_city_service import push_sf_same_city

    db = MagicMock()
    body = MagicMock()
    body.delivery_date = __import__("datetime").date(2026, 5, 26)
    body.rows = []
    with patch("app.services.sf_same_city_service.get_settings") as gs, patch(
        "app.services.sf_same_city_service.get_store_config", return_value=MagicMock()
    ), patch("app.services.sf_same_city_service.merged_sf_integration_namespace") as gset, patch(
        "app.services.sf_same_city_service._sf_push_serial_lock"
    ) as lock:
        gs.return_value.DEFAULT_STORE_ID = 1
        gs.return_value.SF_PUSH_HTTP_CONCURRENCY = 1
        gset.return_value.SF_OPEN_DEV_ID = 1
        gset.return_value.SF_OPEN_SHOP_ID = "shop"
        gset.return_value.SF_OPEN_SECRET = "secret"
        gset.return_value.SF_PICKUP_PHONE = "13800000000"
        gset.return_value.SF_PICKUP_ADDRESS = "addr"
        lock.return_value.__enter__ = MagicMock(return_value=None)
        lock.return_value.__exit__ = MagicMock(return_value=None)
        db.get.return_value = MagicMock(is_active=True, tenant_id=1)
        out = push_sf_same_city(db, body, store_id=1, ags_hint={})
        assert out.results == []
