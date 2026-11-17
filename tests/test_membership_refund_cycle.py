"""退卡：已消费只看最近一次开卡之后；应退按该工单实付。"""

from datetime import date, datetime
from decimal import Decimal

from app.services.admin.member_membership_refund_service import (
    card_paid_yuan_for_refund,
    refund_yuan_from_latest_card,
    select_deliveries_after_card_credit,
)


def test_consumption_before_latest_card_is_excluded() -> None:
    """更早周期的配送不算进这次退卡。"""
    credit_at = datetime(2026, 7, 22, 11, 35, 40)
    total, by_date = select_deliveries_after_card_credit(
        credit_at,
        [(datetime(2026, 5, 6, 8, 51, 40), date(2026, 5, 6), 1)],
    )
    assert total == 0
    assert by_date == {}


def test_consumption_after_latest_card_is_kept() -> None:
    """开卡之后的配送计入，开卡之前的同一次核对里丢掉。"""
    credit_at = datetime(2026, 7, 22, 11, 35, 40)
    total, by_date = select_deliveries_after_card_credit(
        credit_at,
        [
            (datetime(2026, 5, 6, 8, 51, 40), date(2026, 5, 6), 1),
            (datetime(2026, 8, 3, 9, 0, 0), date(2026, 8, 3), 1),
        ],
    )
    assert total == 1
    assert by_date == {date(2026, 8, 3): 1}


def test_no_card_anchor_does_not_fall_back_to_full_history() -> None:
    """没有仍有效的开卡入账时，不把历史配送整段算进来。"""
    total, by_date = select_deliveries_after_card_credit(
        None,
        [(datetime(2026, 5, 6, 8, 51, 40), date(2026, 5, 6), 1)],
    )
    assert total == 0
    assert by_date == {}


def test_deduction_at_the_same_moment_as_credit_is_previous_cycle() -> None:
    """扣次时刻不晚于入账，仍算上一档。"""
    credit_at = datetime(2026, 7, 22, 11, 35, 40)
    total, by_date = select_deliveries_after_card_credit(
        credit_at,
        [(credit_at, date(2026, 7, 22), 1)],
    )
    assert total == 0
    assert by_date == {}


def test_douyin_paid_rounds_to_card_order_list_amount() -> None:
    """工单实收列把 169.80 显示成 170，退卡用这个整数。"""
    assert card_paid_yuan_for_refund(Decimal("169.80")) == Decimal("170")
    assert card_paid_yuan_for_refund(Decimal("169.40")) == Decimal("169")
    assert card_paid_yuan_for_refund(Decimal("168")) == Decimal("168")


def test_no_consumption_refunds_full_rounded_paid() -> None:
    """没吃：退实收全额。"""
    refund = refund_yuan_from_latest_card(
        card_paid_yuan=Decimal("170"),
        consumed_original_yuan=Decimal("0"),
    )
    assert refund == Decimal("170.00")


def test_refund_subtracts_consumed_dish_original_price() -> None:
    """实收 178，吃过一餐原价 36：应退 142，不按 178×5/6。"""
    refund = refund_yuan_from_latest_card(
        card_paid_yuan=Decimal("178"),
        consumed_original_yuan=Decimal("36"),
    )
    assert refund == Decimal("142.00")


def test_consumed_original_above_paid_refunds_zero() -> None:
    refund = refund_yuan_from_latest_card(
        card_paid_yuan=Decimal("178"),
        consumed_original_yuan=Decimal("200"),
    )
    assert refund == Decimal("0.00")


def test_same_day_units_after_credit_are_summed() -> None:
    total, by_date = select_deliveries_after_card_credit(
        datetime(2026, 7, 22, 11, 35, 40),
        [
            (datetime(2026, 8, 3, 9, 0, 0), date(2026, 8, 3), 1),
            (datetime(2026, 8, 3, 18, 0, 0), date(2026, 8, 3), 2),
        ],
    )
    assert total == 3
    assert by_date == {date(2026, 8, 3): 3}
