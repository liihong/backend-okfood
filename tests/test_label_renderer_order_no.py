"""标签渲染：配送备餐短号展示优先级。"""

from __future__ import annotations

from app.schemas.store_print import LabelItemIn
from app.services.print.label_renderer import _order_no_display


def test_delivery_prefers_prep_order_no_over_shop_order_id() -> None:
    """推单后 shop_order_id 存在时，面单订单号仍应为大表备餐短号。"""
    item = LabelItemIn(
        order_kind="delivery",
        order_no="ZX001",
        shop_order_id="OKF20260807stop001",
    )
    assert _order_no_display(item) == "ZX001"


def test_delivery_falls_back_to_shop_order_id_when_no_prep_no() -> None:
    item = LabelItemIn(
        order_kind="delivery",
        order_no="",
        shop_order_id="OKF20260807stop001",
    )
    assert _order_no_display(item) == "OKF20260807stop001"


def test_retail_uses_order_no() -> None:
    item = LabelItemIn(
        order_kind="retail",
        order_no="OKF12345",
        shop_order_id="OKF20260807stop001",
    )
    assert _order_no_display(item) == "OKF12345"
