"""晚餐暂停与开卡赠送：只断言日程规则，不连午餐暂停。"""

from datetime import date

from app.services.meal_period.dinner_pause import (
    dinner_pause_value_for_card_credit,
    dinner_schedule_allows_delivery,
)


def test_formal_dinner_credit_does_not_force_pause() -> None:
    """正式晚餐、全餐入账写成不暂停，即使同时填了赠送次数。"""
    assert dinner_pause_value_for_card_credit(paid_dinner=True, gift_dinner=0) is False
    assert dinner_pause_value_for_card_credit(paid_dinner=True, gift_dinner=5) is False


def test_gift_dinner_defaults_to_paused() -> None:
    """只有赠送晚餐时默认暂停。纯午餐卡不改标记。"""
    assert dinner_pause_value_for_card_credit(paid_dinner=False, gift_dinner=5) is True
    assert dinner_pause_value_for_card_credit(paid_dinner=False, gift_dinner=0) is None


def test_paused_dinner_only_on_chosen_date() -> None:
    """暂停后只有指定日进晚餐单；未暂停的正式晚餐仍然每天可进。"""
    day = date(2026, 10, 21)
    other = date(2026, 10, 22)
    assert dinner_schedule_allows_delivery(
        entitled=False,
        dinner_delivery_paused=True,
        dinner_deliver_on=day,
        delivery_date=day,
    )
    assert not dinner_schedule_allows_delivery(
        entitled=False,
        dinner_delivery_paused=True,
        dinner_deliver_on=day,
        delivery_date=other,
    )
    assert not dinner_schedule_allows_delivery(
        entitled=True,
        dinner_delivery_paused=True,
        dinner_deliver_on=None,
        delivery_date=day,
    )
    assert dinner_schedule_allows_delivery(
        entitled=True,
        dinner_delivery_paused=False,
        dinner_deliver_on=None,
        delivery_date=day,
    )
    # 指定日期不会把未暂停的正式晚餐收成只送这一天
    assert dinner_schedule_allows_delivery(
        entitled=True,
        dinner_delivery_paused=False,
        dinner_deliver_on=other,
        delivery_date=day,
    )
