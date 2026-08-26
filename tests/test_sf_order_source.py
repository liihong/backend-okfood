"""顺丰 createorder.order_source（骑士端「来源」）优先用租户门店名。"""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from app.schemas.admin import SfSameCityRowBase
from app.services.delivery.sf_same_city_service import _create_order_payload, _sf_order_source


def _gset(**kwargs: object) -> SimpleNamespace:
    base: dict[str, object] = {
        "SF_OPEN_DEV_ID": 1,
        "SF_OPEN_SHOP_ID": "shop",
        "SF_OPEN_SHOP_TYPE": 1,
        "SF_ORDER_SOURCE": "OK饭健康餐",
        "SF_API_VERSION": 17,
        "SF_VEHICLE_TYPE_CODE": 1,
        "SF_DEFAULT_PRODUCT_TYPE": 1,
        "SF_PICKUP_PHONE": "13800000000",
        "SF_PICKUP_ADDRESS": "取件地址",
        "SF_CITY_NAME": "禹州市",
        "SF_PRODUCT_CATEGORY_LABEL": "餐品",
    }
    base.update(kwargs)
    return SimpleNamespace(**base)


def _row() -> SfSameCityRowBase:
    return SfSameCityRowBase(
        stop_id="stop-order-src-01",
        pickup_phone="13800000000",
        recv_name="高飞",
        recv_phone="15303996399",
        recv_lng=113.48,
        recv_lat=34.15,
        weight_kg=0.2,
        push_immediately=True,
        subscription_pending_units=1,
        single_meal_count=0,
    )


def test_order_source_uses_store_name_not_global_brand() -> None:
    store = SimpleNamespace(store_name="阆阆轻食", store_lng=113.48, store_lat=34.15)
    pld = _create_order_payload(
        _row(),
        shop_order_id="SOID1",
        gset=_gset(),
        store=store,
        now_ts=1710000000,
        delivery_date=date(2026, 8, 26),
    )
    assert pld["order_source"] == "阆阆轻食"
    assert pld["shop"]["shop_name"] == "阆阆轻食"


def test_order_source_falls_back_to_env_when_store_name_empty() -> None:
    store = SimpleNamespace(store_name="  ", store_lng=113.48, store_lat=34.15)
    assert _sf_order_source(store, _gset()) == "OK饭健康餐"


def test_order_source_truncated_to_12() -> None:
    store = SimpleNamespace(store_name="一二三四五六七八九十甲乙丙", store_lng=None, store_lat=None)
    assert _sf_order_source(store, _gset()) == "一二三四五六七八九十甲乙"
