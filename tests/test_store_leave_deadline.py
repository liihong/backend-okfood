"""门店请假截止时刻会决定小程序能否请第二天的假。"""

from datetime import datetime, time
from zoneinfo import ZoneInfo

from app.services.member.leave import is_miniprogram_leave_prep_locked
from app.services.shared.platform_tenant_service import _parse_leave_deadline

TZ = ZoneInfo("Asia/Shanghai")
# 租户期望：每天下午 17:00 前可以请第二天的假
DEADLINE_17 = time(17, 0, 0)


def _at(hour: int, minute: int, *, day: int = 26) -> datetime:
    return datetime(2026, 10, day, hour, minute, tzinfo=TZ)


def test_parse_1700_is_seventeen() -> None:
    assert _parse_leave_deadline("17:00") == DEADLINE_17
    assert _parse_leave_deadline("17:00:00") == DEADLINE_17


def test_before_1700_can_request_tomorrow_leave() -> None:
    """09:00–16:59 不在备餐锁窗，小程序可以请第二天的假。"""
    assert not is_miniprogram_leave_prep_locked(deadline_time=DEADLINE_17, now=_at(9, 0))
    assert not is_miniprogram_leave_prep_locked(deadline_time=DEADLINE_17, now=_at(16, 59))


def test_from_1700_until_next_0900_leave_is_locked() -> None:
    """17:00 起锁到次日 09:00 前，与门店字段写入后的运行时口径一致。"""
    assert is_miniprogram_leave_prep_locked(deadline_time=DEADLINE_17, now=_at(17, 0))
    assert is_miniprogram_leave_prep_locked(deadline_time=DEADLINE_17, now=_at(23, 30))
    assert is_miniprogram_leave_prep_locked(deadline_time=DEADLINE_17, now=_at(8, 59, day=27))
    assert not is_miniprogram_leave_prep_locked(deadline_time=DEADLINE_17, now=_at(9, 0, day=27))
