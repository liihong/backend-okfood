"""供餐日前的推单快照不能提前锁住当天名单。"""

from datetime import date, datetime

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


def test_snapshot_before_delivery_day_does_not_lock() -> None:
    day = date(2026, 10, 13)
    assert snapshot_recorded_before_delivery_day(datetime(2026, 10, 12, 9, 42, 23), day)
    assert not snapshot_recorded_before_delivery_day(datetime(2026, 10, 13, 8, 50, 1), day)
    assert not snapshot_recorded_before_delivery_day(None, day)
