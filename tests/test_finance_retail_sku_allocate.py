"""商城 SKU 营业额：券前行金额按订单实收分摊，合计必须等于实收。"""

from decimal import Decimal

from app.services.admin.finance_received_service import allocate_order_amount_to_lines


def test_allocate_matches_payable_when_coupon_applied() -> None:
    shares = allocate_order_amount_to_lines(
        Decimal("120.00"),
        [Decimal("100.00"), Decimal("50.00")],
    )
    assert shares == [Decimal("80.00"), Decimal("40.00")]
    assert sum(shares, Decimal("0")) == Decimal("120.00")


def test_allocate_puts_remainder_on_last_line() -> None:
    shares = allocate_order_amount_to_lines(
        Decimal("10.00"),
        [Decimal("1.00"), Decimal("1.00"), Decimal("1.00")],
    )
    assert sum(shares, Decimal("0")) == Decimal("10.00")
    assert shares[0] == Decimal("3.33")
    assert shares[1] == Decimal("3.33")
    assert shares[2] == Decimal("3.34")


def test_allocate_single_line_takes_full_payable() -> None:
    shares = allocate_order_amount_to_lines(Decimal("9.90"), [Decimal("12.00")])
    assert shares == [Decimal("9.90")]


def test_allocate_zero_line_amounts_keeps_payable_on_first() -> None:
    shares = allocate_order_amount_to_lines(
        Decimal("8.00"),
        [Decimal("0"), Decimal("0")],
    )
    assert shares == [Decimal("8.00"), Decimal("0.00")]
