"""零售单推顺丰：及时单走零售店铺，接驳单走配送大表店铺。"""

from datetime import date
from types import SimpleNamespace

import pytest

from app.schemas.admin import SfSameCityRowBase
from app.services.delivery.sf_same_city_service import (
    _create_order_payload,
    apply_single_meal_sf_dispatch_account,
    normalize_single_meal_sf_dispatch_mode,
)


def _gset(*, shop_id: str = "sheet-shop") -> SimpleNamespace:
    return SimpleNamespace(
        SF_OPEN_DEV_ID=1,
        SF_OPEN_SHOP_ID=shop_id,
        SF_OPEN_SHOP_TYPE=1,
        SF_PICKUP_PHONE="13800000000",
        SF_PICKUP_ADDRESS="新乡市门店",
        SF_CITY_NAME="新乡市",
        SF_API_VERSION=17,
        SF_VEHICLE_TYPE_CODE=1,
        SF_DEFAULT_PRODUCT_TYPE=1,
        SF_ORDER_SOURCE="OKFOOD",
        SF_PRODUCT_CATEGORY_LABEL="餐品",
        SF_DEFAULT_VEHICLE_TYPE="小轿车",
    )


def _store() -> SimpleNamespace:
    return SimpleNamespace(
        sf_retail_push_shop_id="instant-shop",
        sf_retail_push_shop_type=2,
        store_name="OK饭",
        store_lng=113.88,
        store_lat=35.30,
    )


def _row() -> SfSameCityRowBase:
    return SfSameCityRowBase(
        stop_id="retail-smo-1",
        pickup_phone="13800000000",
        weight_kg=0.5,
        recv_name="张三",
        recv_phone="13900000000",
        push_immediately=True,
    )


def test_blank_mode_is_instant() -> None:
    assert normalize_single_meal_sf_dispatch_mode(None) == "instant"
    assert normalize_single_meal_sf_dispatch_mode("  RELAY ") == "relay"


def test_unknown_mode_rejected() -> None:
    with pytest.raises(ValueError, match="及时单"):
        normalize_single_meal_sf_dispatch_mode("appoint")


def test_instant_uses_retail_shop_and_is_immediate() -> None:
    gset = _gset()
    mode = apply_single_meal_sf_dispatch_account(gset, _store(), dispatch_mode="instant")
    assert mode == "instant"
    assert gset.SF_OPEN_SHOP_ID == "instant-shop"
    assert gset.SF_OPEN_SHOP_TYPE == 2
    pld = _create_order_payload(
        _row(),
        shop_order_id="OKFSMO1",
        gset=gset,
        store=_store(),
        now_ts=1_700_000_000,
        delivery_date=date(2026, 11, 16),
    )
    assert pld["shop_id"] == "instant-shop"
    assert pld["shop_type"] == 2
    assert pld["is_appoint"] == 0


def test_relay_keeps_sheet_shop() -> None:
    gset = _gset(shop_id="sheet-shop")
    mode = apply_single_meal_sf_dispatch_account(gset, _store(), dispatch_mode="relay")
    assert mode == "relay"
    assert gset.SF_OPEN_SHOP_ID == "sheet-shop"
    assert gset.SF_OPEN_SHOP_TYPE == 1
    pld = _create_order_payload(
        _row(),
        shop_order_id="OKFSMO1",
        gset=gset,
        store=_store(),
        now_ts=1_700_000_000,
        delivery_date=date(2026, 11, 16),
    )
    assert pld["shop_id"] == "sheet-shop"
    assert pld["is_appoint"] == 0
    assert pld["shop_id"] != "instant-shop"


def test_instant_requires_retail_shop() -> None:
    store = _store()
    store.sf_retail_push_shop_id = "  "
    with pytest.raises(ValueError, match="零售推顺丰店铺ID"):
        apply_single_meal_sf_dispatch_account(_gset(), store, dispatch_mode="instant")


def test_relay_requires_sheet_shop() -> None:
    with pytest.raises(ValueError, match="租户对接"):
        apply_single_meal_sf_dispatch_account(_gset(shop_id=""), _store(), dispatch_mode="relay")
