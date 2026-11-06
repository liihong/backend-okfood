"""供餐日前的推单快照不能提前锁住当天名单。"""

from datetime import date, datetime, timedelta

import pytest

from app.services.delivery.delivery_day_lock_service import (
    delivery_date_is_future,
    delivery_day_push_window,
    reject_future_delivery_sheet_push,
    snapshot_recorded_before_delivery_day,
)


def test_push_window_is_delivery_calendar_day() -> None:
    start, end = delivery_day_push_window(date(2026, 10, 13))
    assert start == datetime(2026, 10, 13, 0, 0, 0)
    assert end == datetime(2026, 10, 14, 0, 0, 0)
    assert datetime(2026, 10, 12, 9, 42, 23) < start
    assert start <= datetime(2026, 10, 13, 8, 50, 0) < end


def test_future_delivery_date_is_rejected_and_not_snapshotted() -> None:
    today = date(2026, 10, 13)
    assert delivery_date_is_future(date(2026, 10, 14), today=today)
    assert not delivery_date_is_future(today, today=today)
    # 历史补推仍允许，避免挡住已过去业务日的重推
    assert not delivery_date_is_future(date(2026, 10, 12), today=today)
    with pytest.raises(ValueError, match="不能提前推送"):
        reject_future_delivery_sheet_push(date(2099, 1, 1))


def test_instant_push_allows_only_the_next_shanghai_day() -> None:
    """及时单可推上海次日；预约推单仍拒绝次日；后天及以后两边都拒绝。"""
    from app.core.timeutil import today_shanghai

    today = today_shanghai()
    tomorrow = today + timedelta(days=1)
    day_after = today + timedelta(days=2)

    # 预约推单默认仍拒绝次日
    with pytest.raises(ValueError, match="只能推送上海当天"):
        reject_future_delivery_sheet_push(tomorrow)

    # 及时单：次日、当天、历史补推都放行
    reject_future_delivery_sheet_push(tomorrow, allow_next_day=True)
    reject_future_delivery_sheet_push(today, allow_next_day=True)
    reject_future_delivery_sheet_push(today - timedelta(days=1), allow_next_day=True)

    # 及时单：后天及以后仍拒绝，且文案与预约推单区分
    with pytest.raises(ValueError, match="及时单只能推送上海当天及次日"):
        reject_future_delivery_sheet_push(day_after, allow_next_day=True)


def test_snapshot_before_delivery_day_does_not_lock() -> None:
    day = date(2026, 10, 13)
    assert snapshot_recorded_before_delivery_day(datetime(2026, 10, 12, 9, 42, 23), day)
    assert not snapshot_recorded_before_delivery_day(datetime(2026, 10, 13, 8, 50, 1), day)
    assert not snapshot_recorded_before_delivery_day(None, day)
