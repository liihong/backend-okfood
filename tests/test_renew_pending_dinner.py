"""待续费名单同时包含晚餐余次 1..阈值的会员；午餐口径保持不变。"""

from datetime import date
from types import SimpleNamespace

from sqlalchemy.dialects import mysql

from app.models.enums import MemberLifecycleCode
from app.services.admin.admin_service import (
    _member_delivering_scope,
    _member_renew_pending_scope,
)
from app.services.member.member_lifecycle_service import (
    _MemberLifecycleContext,
    _resolve_member_lifecycle_with_ctx,
)


def _sql(clause) -> str:
    return str(clause.compile(dialect=mysql.dialect(), compile_kwargs={"literal_binds": True}))


def _member(**kwargs):
    defaults = {
        "id": 1,
        "membership_refunded_at": None,
        "pause_effective_date": None,
        "delivery_deferred": False,
        "delivery_start_date": date(2026, 1, 1),
        "store_pickup": False,
        "is_active": True,
        "balance": 10,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def _dinner(balance: int):
    return SimpleNamespace(balance=balance)


def _ctx(dinner):
    return _MemberLifecycleContext(
        applied_card_order_ids=frozenset({1}),
        delivery_history_ids=frozenset({1}),
        latest_order_meta_by_id={},
        dinner_state_by_id={1: dinner},
        default_addr_by_id={1: object()},
    )


def _status(member, dinner):
    return _resolve_member_lifecycle_with_ctx(member, on_leave_today=False, ctx=_ctx(dinner))


def test_renew_pending_sql_includes_dinner_pool() -> None:
    """筛选 SQL 同时看午餐余次和晚餐池余次。"""
    sql = _sql(_member_renew_pending_scope(threshold=2))
    assert "member_meal_period_state" in sql
    assert "dinner" in sql
    assert "members.balance > 0" in sql
    assert "members.balance <= 2" in sql


def test_delivering_sql_drops_dinner_low_balance() -> None:
    """晚餐余次落在待续费区间时，不再留在正常配送中。"""
    sql = _sql(_member_delivering_scope(threshold=2))
    assert "member_meal_period_state" in sql
    assert "dinner" in sql


def test_dinner_only_low_balance_is_renew_pending() -> None:
    """纯晚餐、晚餐剩余 2 次：待续费。"""
    view = _status(_member(balance=0), _dinner(2))
    assert view.code == MemberLifecycleCode.RENEW_PENDING.value


def test_lunch_low_balance_still_renew_pending() -> None:
    """只有午餐剩余 1 次：仍是待续费。"""
    view = _status(_member(balance=1), None)
    assert view.code == MemberLifecycleCode.RENEW_PENDING.value


def test_combo_dinner_low_is_renew_pending() -> None:
    """午餐还很多、晚餐只剩 1 次：跟晚餐一起进待续费。"""
    view = _status(_member(balance=12), _dinner(1))
    assert view.code == MemberLifecycleCode.RENEW_PENDING.value


def test_dinner_with_plenty_stays_delivering() -> None:
    """晚餐剩余高于阈值时，仍是正常配送中。"""
    view = _status(_member(balance=0), _dinner(8))
    assert view.code == MemberLifecycleCode.DELIVERING.value
