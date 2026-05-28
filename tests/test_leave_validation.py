"""请假日期校验（纯函数，不连库）。"""

from __future__ import annotations

from datetime import datetime

from zoneinfo import ZoneInfo

from app.core.timeutil import min_leave_start_shanghai


def test_min_leave_start_is_day_after_shanghai_today():
    # 2026-05-21 04:37 上海：最早请假日从 22 号起
    now = datetime(2026, 5, 21, 4, 37, 36, tzinfo=ZoneInfo("Asia/Shanghai"))
    assert min_leave_start_shanghai(now).isoformat() == "2026-05-22"

    # 2026-05-21 20:00 上海：最早请假日仍为次日（与具体时刻无关）
    now_late = datetime(2026, 5, 21, 20, 0, 0, tzinfo=ZoneInfo("Asia/Shanghai"))
    assert min_leave_start_shanghai(now_late).isoformat() == "2026-05-22"

def test_leave_cancel_guard_skips_when_not_absent_today():
    from datetime import date

    from app.models.enums import LeaveType
    from app.models.member import Member
    from app.services.leave import is_absent_on_delivery_date

    m = Member(
        id=1,
        store_id=1,
        phone="13800000000",
        leave_range_start=date(2026, 5, 22),
        leave_range_end=date(2026, 5, 31),
    )
    biz_today = date(2026, 5, 21)
    assert is_absent_on_delivery_date(m, biz_today, today=biz_today) is False
    assert LeaveType.CANCEL.value == "cancel"
