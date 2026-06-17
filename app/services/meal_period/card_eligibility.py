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


def meal_periods_from_order_snapshot(order: MemberCardOrder) -> frozenset[str]:
    """单笔已入账工单的餐段快照。"""
    snap = getattr(order, "meal_periods_snapshot", None)
    periods = _normalize_periods(snap)
    if periods:
        return periods
    # 无 snapshot 的历史工单：与经典周/月/次一致，视为午餐
    return frozenset(DEFAULT_MEAL_PERIODS_SNAPSHOT)


def _fallback_periods_for_legacy_member(member: Member) -> frozenset[str]:
    """
    无任何已入账工单快照时：若仍有 balance，按现网视为午餐订阅（兼容极老数据）。
    """
    if int(member.balance or 0) > 0:
        return frozenset(DEFAULT_MEAL_PERIODS_SNAPSHOT)
    return frozenset()


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
    return _fallback_periods_for_legacy_member(m)


def members_entitled_meal_periods_map(
    db: Session, member_ids: list[int]
) -> dict[int, frozenset[str]]:
    """批量解析餐段资格，避免大表逐会员查库。"""
    ids = sorted({int(x) for x in member_ids if x is not None})
    if not ids:
        return {}
    rows = db.scalars(
        select(MemberCardOrder).where(
            MemberCardOrder.member_id.in_(ids),
            MemberCardOrder.pay_status == CardOrderPayStatus.PAID.value,
            MemberCardOrder.applied_to_member.is_(True),
        )
    ).all()
    by_member: dict[int, set[str]] = defaultdict(set)
    for row in rows:
        by_member[int(row.member_id)] |= set(meal_periods_from_order_snapshot(row))
    out: dict[int, frozenset[str]] = {}
    for mid in ids:
        if by_member[mid]:
            out[mid] = frozenset(by_member[mid])
        else:
            m = db.get(Member, mid)
            out[mid] = _fallback_periods_for_legacy_member(m) if m else frozenset()
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


def filter_members_for_sheet_view(db: Session, members: list[Member], sheet_view: str) -> list[Member]:
    """大表名单最后一道过滤：纯晚餐会员不会出现在 lunch 视图。"""
    if not members:
        return []
    id_map = members_entitled_meal_periods_map(db, [int(m.id) for m in members])
    return [m for m in members if _periods_match_sheet(id_map.get(int(m.id), frozenset()), sheet_view)]
