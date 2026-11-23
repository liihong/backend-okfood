"""商城零售行金额：与配送费解耦。"""

from decimal import Decimal
from unittest.mock import MagicMock

from app.services.retail.retail_order_amount import compute_retail_line_amount
from app.services.retail.store_retail_pickup_line_backfill_service import _item_needs_fixup
from types import SimpleNamespace


def test_line_amount_is_unit_times_qty_regardless_of_pickup() -> None:
    db = MagicMock()
    unit = Decimal("15.00")
    delivery = compute_retail_line_amount(
        db, unit_price=unit, quantity=2, store_pickup=False, store_id=1
    )
    pickup = compute_retail_line_amount(
        db, unit_price=unit, quantity=2, store_pickup=True, store_id=1
    )
    assert delivery == Decimal("30.00")
    assert pickup == Decimal("30.00")


def test_backfill_detects_understated_pickup_line() -> None:
    row = SimpleNamespace(unit_price_yuan=Decimal("15.00"), quantity=1, line_amount_yuan=Decimal("10.00"))
    assert _item_needs_fixup(row) == Decimal("15.00")


def test_backfill_skips_correct_line() -> None:
    row = SimpleNamespace(unit_price_yuan=Decimal("15.00"), quantity=2, line_amount_yuan=Decimal("30.00"))
    assert _item_needs_fixup(row) is None