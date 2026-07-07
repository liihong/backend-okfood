"""商城零售订单金额：销售价为配送价，自提减固定配送费（与单次点餐一致）。"""

from decimal import Decimal
from unittest.mock import MagicMock, patch

from app.services.client.store_retail_order_service import _compute_retail_order_amount


@patch("app.services.client.store_retail_order_service.get_store_base_delivery_fee_yuan")
def test_retail_delivery_uses_list_price(mock_fee):
    mock_fee.return_value = Decimal("5.00")
    db = MagicMock()
    amt = _compute_retail_order_amount(
        db,
        unit_price=Decimal("108.00"),
        quantity=1,
        store_pickup=False,
        store_id=1,
    )
    assert amt == Decimal("108.00")
    mock_fee.assert_not_called()


@patch("app.services.client.store_retail_order_service.get_store_base_delivery_fee_yuan")
def test_retail_pickup_subtracts_delivery_fee(mock_fee):
    mock_fee.return_value = Decimal("5.00")
    db = MagicMock()
    amt = _compute_retail_order_amount(
        db,
        unit_price=Decimal("108.00"),
        quantity=1,
        store_pickup=True,
        store_id=1,
    )
    assert amt == Decimal("103.00")


@patch("app.services.client.store_retail_order_service.get_store_base_delivery_fee_yuan")
def test_retail_pickup_never_below_one_cent(mock_fee):
    mock_fee.return_value = Decimal("200.00")
    db = MagicMock()
    amt = _compute_retail_order_amount(
        db,
        unit_price=Decimal("108.00"),
        quantity=2,
        store_pickup=True,
        store_id=1,
    )
    assert amt == Decimal("0.02")
