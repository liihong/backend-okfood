"""08:50 主租户零售单推接驳账号后，未取货也保持配送中。"""

import app.services.delivery.sf_same_city_service as sf_mod
from app.services.order.single_meal_order_service import (
    MORNING_AUTO_IN_DELIVERY_SNAPSHOT_KEY,
    keep_morning_auto_retail_in_delivery,
    push_morning_auto_retail_orders_to_relay_shop,
)


def test_morning_auto_stays_in_delivery_before_pickup() -> None:
    """任务打过标记的零售单，顺丰还没取货时不要改回待取货。"""
    snap = {MORNING_AUTO_IN_DELIVERY_SNAPSHOT_KEY: True}
    assert keep_morning_auto_retail_in_delivery("accepted", snap, None) is True
    assert keep_morning_auto_retail_in_delivery("accepted", snap, 1) is True


def test_morning_auto_does_not_block_pickup_or_later() -> None:
    """已取货（>=15）不再由这个判断拦住，妥投和取消仍走原回调。"""
    snap = {MORNING_AUTO_IN_DELIVERY_SNAPSHOT_KEY: True}
    assert keep_morning_auto_retail_in_delivery("accepted", snap, 15) is False
    assert keep_morning_auto_retail_in_delivery("accepted", snap, 17) is False


def test_morning_auto_retail_push_uses_relay_shop(monkeypatch) -> None:
    """08:50 零售单走接驳账号，不走门店及时单店铺。"""
    seen: dict[str, object] = {}

    def fake_item(*, order_id: int, store_id: int, dispatch_mode: str = "instant") -> dict:
        seen["order_id"] = order_id
        seen["store_id"] = store_id
        seen["dispatch_mode"] = dispatch_mode
        return {"order_id": order_id, "ok": False, "message": "测试不落库"}

    def fake_waves(oids: list[int], *, push_one) -> dict:
        return {"results": [push_one(oid) for oid in oids]}

    monkeypatch.setattr(sf_mod, "push_single_meal_retail_to_sf_bulk_item", fake_item)
    monkeypatch.setattr(sf_mod, "run_retail_sf_bulk_in_waves", fake_waves)

    out = push_morning_auto_retail_orders_to_relay_shop(order_ids=[11], store_id=3)
    assert seen == {"order_id": 11, "store_id": 3, "dispatch_mode": "relay"}
    assert out["results"][0]["ok"] is False


def test_manual_push_without_flag_is_not_kept() -> None:
    """订单管理手动推单没有标记，误标成配送中时仍允许改回待取货。"""
    assert keep_morning_auto_retail_in_delivery("accepted", {}, None) is False
    assert keep_morning_auto_retail_in_delivery("accepted", None, None) is False
    assert keep_morning_auto_retail_in_delivery("sf_awaiting_pickup", {MORNING_AUTO_IN_DELIVERY_SNAPSHOT_KEY: True}, None) is False
