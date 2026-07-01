"""会员餐段资格：仅依据已入账开卡工单的 meal_periods_snapshot 并集，不在 members 表打标记。"""

from __future__ import annotations

import json
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import CardOrderPayStatus, DeliverySheetView
from app.models.member import Member
from app.models.member_card_order import MemberCardOrder
from app.services.meal_period.constants import DEFAULT_MEAL_PERIODS_SNAPSHOT


def _normalize_periods(raw: object) -> frozenset[str]:
    """解析 JSON/list 餐段列表，非法值丢弃。"""
    if raw is None:
        return frozenset()
    items: list[object]
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            items = parsed if isinstance(parsed, list) else []
        except json.JSONDecodeError:
            return frozenset()
    elif isinstance(raw, list):
        items = raw
    else:
        return frozenset()
    out: set[str] = set()
    for x in items:
        s = str(x).strip().lower()
        if s in ("lunch", "dinner"):
            out.add(s)
    return frozenset(out)


def meal_periods_from_snapshot_value(meal_periods_snapshot: object) -> frozenset[str]:
    """解析工单 meal_periods_snapshot 字段；无有效值时视为经典午餐卡。"""
    periods = _normalize_periods(meal_periods_snapshot)
    if periods:
        return periods
    return frozenset(DEFAULT_MEAL_PERIODS_SNAPSHOT)


def meal_periods_from_order_snapshot(order: MemberCardOrder) -> frozenset[str]:
    """单笔已入账工单的餐段快照。"""
    return meal_periods_from_snapshot_value(getattr(order, "meal_periods_snapshot", None))


def _fallback_periods_batch(
    db: Session, members_by_id: dict[int, Member]
) -> dict[int, frozenset[str]]:
    """
    无任何已入账工单快照时：按各餐段剩余次数批量推断资格（兼容极老数据）。
    午餐读 members.balance；晚餐读 member_meal_period_state。
    """
    from app.models.enums import MealPeriod
    from app.models.member_meal_period_state import MemberMealPeriodState

    if not members_by_id:
        return {}
    ids = list(members_by_id.keys())
    dinner_bal: dict[int, int] = {}
    if ids:
        for mid, bal in db.execute(
            select(MemberMealPeriodState.member_id, MemberMealPeriodState.balance).where(
                MemberMealPeriodState.member_id.in_(ids),
                MemberMealPeriodState.meal_period == MealPeriod.DINNER.value,
            )
        ).all():
            dinner_bal[int(mid)] = int(bal or 0)
    out: dict[int, frozenset[str]] = {}
    for mid, member in members_by_id.items():
        periods: set[str] = set()
        if int(member.balance or 0) > 0:
            periods.add(MealPeriod.LUNCH.value)
        if dinner_bal.get(mid, 0) > 0:
            periods.add(MealPeriod.DINNER.value)
        out[mid] = frozenset(periods)
    return out


def _fallback_periods_for_legacy_member(db: Session, member: Member) -> frozenset[str]:
    """单会员 legacy 推断（member_entitled_meal_periods 等单查路径）。"""
    return _fallback_periods_batch(db, {int(member.id): member}).get(int(member.id), frozenset())


def member_entitled_meal_periods(db: Session, member_id: int) -> frozenset[str]:
    """会员当前餐段资格 = 所有「已缴且已入账」工单 meal_periods_snapshot 的并集。"""
    mid = int(member_id)
    rows = db.scalars(
        select(MemberCardOrder).where(
            MemberCardOrder.member_id == mid,
            MemberCardOrder.pay_status == CardOrderPayStatus.PAID.value,
            MemberCardOrder.applied_to_member.is_(True),
        )
    ).all()
    merged: set[str] = set()
    for row in rows:
        merged |= meal_periods_from_order_snapshot(row)
    if merged:
        return frozenset(merged)
    m = db.get(Member, mid)
    if m is None:
        return frozenset()
    return _fallback_periods_for_legacy_member(db, m)


def members_entitled_meal_periods_map(
    db: Session,
    member_ids: list[int],
    *,
    members_by_id: dict[int, Member] | None = None,
) -> dict[int, frozenset[str]]:
    """批量解析餐段资格，避免大表逐会员查库。"""
    ids = sorted({int(x) for x in member_ids if x is not None})
    if not ids:
        return {}
    # 仅拉 member_id + snapshot 两列，避免 ORM 全行 hydration 拖慢大表
    rows = db.execute(
        select(MemberCardOrder.member_id, MemberCardOrder.meal_periods_snapshot).where(
            MemberCardOrder.member_id.in_(ids),
            MemberCardOrder.pay_status == CardOrderPayStatus.PAID.value,
            MemberCardOrder.applied_to_member.is_(True),
        )
    ).all()
    by_member: dict[int, set[str]] = defaultdict(set)
    for member_id, snap in rows:
        by_member[int(member_id)] |= set(meal_periods_from_snapshot_value(snap))
    missing = [mid for mid in ids if not by_member[mid]]
    fallback_map: dict[int, frozenset[str]] = {}
    if missing:
        known = members_by_id or {}
        fb_members = {mid: known[mid] for mid in missing if mid in known}
        need_load = [mid for mid in missing if mid not in fb_members]
        if need_load:
            for m in db.scalars(select(Member).where(Member.id.in_(need_load))).all():
                fb_members[int(m.id)] = m
        fallback_map = _fallback_periods_batch(db, fb_members)
    out: dict[int, frozenset[str]] = {}
    for mid in ids:
        if by_member[mid]:
            out[mid] = frozenset(by_member[mid])
        else:
            out[mid] = fallback_map.get(mid, frozenset())
    return out


def member_entitled_for_sheet(db: Session, member_id: int, sheet_view: str) -> bool:
    """判断会员是否应出现在指定大表视图。"""
    periods = member_entitled_meal_periods(db, member_id)
    return _periods_match_sheet(periods, sheet_view)


def _periods_match_sheet(periods: frozenset[str], sheet_view: str) -> bool:
    view = (sheet_view or DeliverySheetView.LUNCH.value).strip().lower()
    if view == DeliverySheetView.LUNCH.value:
        return "lunch" in periods
    if view == DeliverySheetView.DINNER.value:
        return "dinner" in periods
    if view == DeliverySheetView.LUNCH_DINNER.value:
        return "lunch" in periods and "dinner" in periods
    return "lunch" in periods


def filter_member_groups_for_sheet_view(
    db: Session,
    sheet_view: str,
    *member_groups: list[Member],
) -> tuple[list[Member], ...]:
    """多组会员名单共用一次餐段资格查库（到家 + 自提）。"""
    combined: list[Member] = []
    for group in member_groups:
        combined.extend(group)
    if not combined:
        return tuple([] for _ in member_groups)
    members_by_id = {int(m.id): m for m in combined}
    id_map = members_entitled_meal_periods_map(
        db, list(members_by_id.keys()), members_by_id=members_by_id
    )

    def _keep(member: Member) -> bool:
        return _periods_match_sheet(id_map.get(int(member.id), frozenset()), sheet_view)

    return tuple([m for m in group if _keep(m)] for group in member_groups)


def filter_members_for_sheet_view(db: Session, members: list[Member], sheet_view: str) -> list[Member]:
    """大表名单最后一道过滤：纯晚餐会员不会出现在 lunch 视图。"""
    if not members:
        return []
    return filter_member_groups_for_sheet_view(db, sheet_view, members)[0]
