"""请假餐段：工单含该餐，或该餐剩余次数大于 0，就可以请。"""

from app.services.meal_period.leave_scope import leave_periods_open_for_request


def test_lunch_card_with_dinner_counts_can_leave_dinner() -> None:
    """午餐工单、另外加上晚餐次数：可以只请晚餐，全天两餐都请。"""
    opened = leave_periods_open_for_request(
        frozenset({"lunch"}),
        lunch_balance=6,
        dinner_balance=2,
    )
    assert opened == frozenset({"lunch", "dinner"})


def test_zero_dinner_counts_and_no_dinner_card_cannot_leave_dinner() -> None:
    """没有晚餐工单、晚餐次数也是 0：全天只含午餐。"""
    opened = leave_periods_open_for_request(
        frozenset({"lunch"}),
        lunch_balance=0,
        dinner_balance=0,
    )
    assert opened == frozenset({"lunch"})


def test_dinner_counts_only_open_dinner_leave() -> None:
    """工单不含任何餐、只剩晚餐次数：只能请晚餐。"""
    opened = leave_periods_open_for_request(
        frozenset(),
        lunch_balance=0,
        dinner_balance=3,
    )
    assert opened == frozenset({"dinner"})
