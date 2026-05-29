"""零售单次推顺丰：使用按订单锁，不占门店级推单锁。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.services.sf_same_city_service import push_single_meal_retail_to_sf


def test_retail_push_uses_per_order_lock_not_store_serial_lock():
    db = MagicMock()
    order = MagicMock()
    order.id = 129
    order.store_id = 1
    order.pay_status = "已支付"
    order.store_pickup = False
    order.member_address_id = 1
    order.fulfillment_status = "pending"
    order.delivery_date = __import__("datetime").date(2026, 5, 29)
    order.quantity = 1
    order.dish_id = 1

    store = MagicMock()
    store.tenant_id = 1
    store.sf_retail_push_shop_id = "shop-retail"
    store.sf_retail_push_shop_type = None

    addr = MagicMock()
    addr.lng = 113.92
    addr.lat = 35.29
    addr.delivery_region_id = None
    addr.map_location_text = "河南省新乡市"
    addr.door_detail = "1号"
    addr.contact_phone = "13800000000"
    addr.contact_name = "张三"

    dish = MagicMock()
    dish.name = "餐品"

    gset = MagicMock()
    gset.SF_OPEN_DEV_ID = 1
    gset.SF_OPEN_SECRET = "secret"
    gset.SF_PICKUP_PHONE = "13800000000"
    gset.SF_PICKUP_ADDRESS = "取件地址"
    gset.SF_DEFAULT_VEHICLE_TYPE = "小轿车"

    def _get(model, pk):
        if pk == 129:
            return order
        if pk == 1 and model.__name__ == "Store":
            return store
        if pk == 1 and "Address" in getattr(model, "__name__", ""):
            return addr
        return dish

    db.get.side_effect = _get
    db.scalar.return_value = None

    with patch(
        "app.services.single_meal_order_service.single_meal_fulfillment_allows_dispatch",
        return_value=True,
    ), patch("app.services.sf_same_city_service.merged_sf_integration_namespace", return_value=gset), patch(
        "app.services.sf_same_city_service.get_store_config",
        return_value=MagicMock(store_name="门店", store_lng=113.88, store_lat=35.30),
    ), patch("app.services.sf_same_city_service.SfOpenClient") as client_cls, patch(
        "app.services.sf_same_city_service._sf_retail_order_push_lock"
    ) as retail_lock, patch("app.services.sf_same_city_service._sf_push_serial_lock") as store_lock, patch(
        "app.services.single_meal_order_service.link_single_meal_orders_to_sf_push_no_commit"
    ):
        retail_lock.return_value.__enter__ = MagicMock(return_value=None)
        retail_lock.return_value.__exit__ = MagicMock(return_value=None)
        store_lock.return_value.__enter__ = MagicMock(return_value=None)
        store_lock.return_value.__exit__ = MagicMock(return_value=None)
        http = MagicMock()
        http.create_order.return_value = {"result": {"sf_order_id": "SF123", "sf_bill_id": "B1"}}
        client_cls.return_value.__enter__.return_value = http

        out = push_single_meal_retail_to_sf(db, order_id=129, store_id=1)

    assert out.ok is True
    assert out.sf_order_id == "SF123"
    retail_lock.assert_called_once()
    store_lock.assert_not_called()
