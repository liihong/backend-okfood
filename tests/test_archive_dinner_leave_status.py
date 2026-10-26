"""会员档案：纯晚餐请假计入「请假中」，午/全餐仍只看午餐主档。"""

from datetime import date
from types import SimpleNamespace

from sqlalchemy.dialects import mysql

from app.services.admin.admin_service import (
    _archive_member_on_leave_today,
    _member_archive_on_leave_scope,
    _member_on_leave_today,
)

TODAY = date(2026, 10, 26)


def _member(**kwargs):
    defaults = {
        "leave_range_start": None,
        "leave_range_end": None,
        "is_leaved_tomorrow": False,
        "tomorrow_leave_target_date": None,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def _dinner(**kwargs):
    defaults = {
        "leave_range_start": None,
        "leave_range_end": None,
        "is_leaved_tomorrow": False,
        "tomorrow_leave_target_date": None,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_lunch_leave_status_unchanged() -> None:
    """午餐区间含今日仍算请假；没有午餐请假时不算，与改前一致。"""
    on_leave = _member(leave_range_start=date(2026, 10, 26), leave_range_end=date(2026, 10, 28))
    assert _member_on_leave_today(on_leave, TODAY) is True
    idle = _member()
    assert _member_on_leave_today(idle, TODAY) is False
    # 全餐即使晚餐在请假，午餐主档函数本身也不看晚餐池
    assert _archive_member_on_leave_today(idle, _dinner(leave_range_start=TODAY, leave_range_end=TODAY), frozenset({"lunch", "dinner"}), TODAY) is False


def test_dinner_only_range_leave_counts_as_archive_leave() -> None:
    """单独晚餐会员：晚餐区间含今日则档案为请假中。"""
    member = _member()
    dinner = _dinner(leave_range_start=date(2026, 10, 25), leave_range_end=date(2026, 10, 27))
    assert _archive_member_on_leave_today(member, dinner, frozenset({"dinner"}), TODAY) is True


def test_dinner_only_tomorrow_leave_counts_until_target_day() -> None:
    """单独晚餐「仅明日」：提交当日至目标日都算请假中，过期后恢复。"""
    member = _member()
    dinner = _dinner(is_leaved_tomorrow=True, tomorrow_leave_target_date=date(2026, 10, 27))
    assert _archive_member_on_leave_today(member, dinner, frozenset({"dinner"}), TODAY) is True
    assert _archive_member_on_leave_today(member, dinner, frozenset({"dinner"}), date(2026, 10, 28)) is False


def test_dinner_only_leave_outside_today_does_not_flip_status() -> None:
    """晚餐区间尚未开始时，状态不提前改成请假中（与午餐区间口径相同）。"""
    member = _member()
    dinner = _dinner(leave_range_start=date(2026, 10, 28), leave_range_end=date(2026, 10, 30))
    assert _archive_member_on_leave_today(member, dinner, frozenset({"dinner"}), TODAY) is False


def test_lunch_member_dinner_leave_does_not_change_status() -> None:
    """只有午餐资格时，晚餐池请假不影响档案状态。"""
    member = _member()
    dinner = _dinner(leave_range_start=TODAY, leave_range_end=TODAY)
    assert _archive_member_on_leave_today(member, dinner, frozenset({"lunch"}), TODAY) is False


def test_archive_leave_filter_includes_dinner_pool() -> None:
    """请假中筛选 SQL 带上晚餐池，便于纯晚餐会员离开「正常配送中」。"""
    clause = _member_archive_on_leave_scope(today=TODAY)
    sql = str(clause.compile(dialect=mysql.dialect(), compile_kwargs={"literal_binds": True}))
    assert "member_meal_period_state" in sql
    assert "dinner" in sql
    assert "leave_range_start" in sql
