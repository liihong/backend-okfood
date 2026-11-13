"""08:50 主租户零售单推及时单后，未取货也保持配送中。"""

from app.services.order.single_meal_order_service import (
    MORNING_AUTO_IN_DELIVERY_SNAPSHOT_KEY,
    keep_morning_auto_retail_in_delivery,
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


def test_manual_push_without_flag_is_not_kept() -> None:
    """订单管理手动推单没有标记，误标成配送中时仍允许改回待取货。"""
    assert keep_morning_auto_retail_in_delivery("accepted", {}, None) is False
    assert keep_morning_auto_retail_in_delivery("accepted", None, None) is False
    assert keep_morning_auto_retail_in_delivery("sf_awaiting_pickup", {MORNING_AUTO_IN_DELIVERY_SNAPSHOT_KEY: True}, None) is False
