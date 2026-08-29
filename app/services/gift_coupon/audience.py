"""按入账日 + 月卡/季卡圈人。只读开卡工单与次数流水，不改会员档案。"""

from __future__ import annotations

import re
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.timeutil import TZ_SHANGHAI
from app.models.balance_log import BalanceLog
from app.models.enums import BalanceReason, CardOrderPayStatus
from app.models.member import Member
from app.models.member_card_order import MemberCardOrder
from app.models.membership_card_template import MembershipCardTemplate
from app.schemas.gift_coupon import GiftCouponAudienceMemberOut
from app.services.gift_coupon.constants import CARD_ORDER_CREDIT_DETAIL_PREFIX
from app.services.gift_coupon.kinds import (
    classify_gift_plan_kind,
    normalize_plan_kinds,
    plan_kind_matches,
)

_ORDER_ID_IN_DETAIL_RE = re.compile(rf"{re.escape(CARD_ORDER_CREDIT_DETAIL_PREFIX)}(\d+)")


def _shanghai_calendar_day(dt: datetime | None) -> date | None:
    """库内 DATETIME 为北京 naive；按上海日历日取值。"""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.date()
    return dt.astimezone(TZ_SHANGHAI).date()


def _credit_at_by_order_id(db: Session, member_ids: list[int]) -> dict[int, datetime]:
    """一次查出这些会员的开卡入账流水，避免预览时对每张工单打一条 SQL（会卡死页面）。"""
    if not member_ids:
        return {}
    first: dict[int, datetime] = {}
    uniq = list(dict.fromkeys(int(i) for i in member_ids))
    chunk = 500
    for i in range(0, len(uniq), chunk):
        part = uniq[i : i + chunk]
        rows = db.scalars(
            select(BalanceLog).where(
                BalanceLog.member_id.in_(part),
                BalanceLog.change > 0,
                BalanceLog.reason == BalanceReason.RECHARGE.value,
                BalanceLog.detail.like(f"{CARD_ORDER_CREDIT_DETAIL_PREFIX}%"),
            )
        ).all()
        for row in rows:
            matched = _ORDER_ID_IN_DETAIL_RE.search(str(row.detail or ""))
            if not matched or row.created_at is None:
                continue
            oid = int(matched.group(1))
            prev = first.get(oid)
            if prev is None or row.created_at < prev:
                first[oid] = row.created_at
    return first


def first_credit_at_for_order(db: Session, order: MemberCardOrder) -> datetime | None:
    """该工单首次正向入账时间；无流水时回落 created_at（历史工单兼容）。"""
    by_id = _credit_at_by_order_id(db, [int(order.member_id)])
    return by_id.get(int(order.id)) or order.created_at


def preview_audience(
    db: Session,
    *,
    tenant_id: int,
    store_id: int,
    plan_kinds: list[str],
    credited_from: date,
    credited_to: date,
    exclude_membership_refunded: bool = True,
) -> list[GiftCouponAudienceMemberOut]:
    """
    区间内任意一次符合卡型的已入账工单即入围；同一会员只出现一次（取最早入账日）。

    不含：未入账、工单已退款、档案已退款（可选）、周卡/次卡。
    """
    selected = set(normalize_plan_kinds(plan_kinds))
    if not selected:
        return []
    if credited_to < credited_from:
        return []

    stmt = (
        select(MemberCardOrder, Member, MembershipCardTemplate)
        .join(Member, Member.id == MemberCardOrder.member_id)
        .outerjoin(
            MembershipCardTemplate,
            MembershipCardTemplate.id == MemberCardOrder.membership_template_id,
        )
        .where(
            MemberCardOrder.tenant_id == int(tenant_id),
            MemberCardOrder.store_id == int(store_id),
            MemberCardOrder.applied_to_member.is_(True),
            MemberCardOrder.pay_status != CardOrderPayStatus.REFUNDED.value,
            Member.deleted_at.is_(None),
            Member.store_id == int(store_id),
        )
    )
    if exclude_membership_refunded:
        stmt = stmt.where(Member.membership_refunded_at.is_(None))

    rows = db.execute(stmt).all()
    credit_at = _credit_at_by_order_id(db, [int(m.id) for _o, m, _t in rows])
    best: dict[int, GiftCouponAudienceMemberOut] = {}
    for order, member, tpl in rows:
        has_tpl = tpl is not None
        kind_label = (tpl.kind_label if tpl is not None else None) or None
        classified = classify_gift_plan_kind(
            kind_label=kind_label,
            card_kind=str(order.card_kind or ""),
            has_template=has_tpl,
        )
        if not plan_kind_matches(classified, selected):
            continue
        credited_at = credit_at.get(int(order.id)) or order.created_at
        credited_on = _shanghai_calendar_day(credited_at)
        if credited_on is None or credited_on < credited_from or credited_on > credited_to:
            continue
        display_kind = (kind_label or "").strip() or str(order.card_kind or "").strip() or "月卡"
        mid = int(member.id)
        item = GiftCouponAudienceMemberOut(
            member_id=mid,
            name=str(member.name or ""),
            phone=str(member.phone or ""),
            card_kind_label=display_kind,
            credited_on=credited_on.isoformat(),
        )
        prev = best.get(mid)
        if prev is None or item.credited_on < prev.credited_on:
            best[mid] = item

    return sorted(best.values(), key=lambda x: (x.credited_on, x.member_id))


def order_matches_active_campaign_rule(
    db: Session,
    *,
    order: MemberCardOrder,
    member: Member,
    tpl: MembershipCardTemplate | None,
    plan_kinds: list[str],
    credited_from: date,
    credited_to: date,
    exclude_membership_refunded: bool,
) -> bool:
    """入账钩子用：当前这张工单是否命中活动规则。"""
    if not bool(order.applied_to_member):
        return False
    if str(order.pay_status or "") == CardOrderPayStatus.REFUNDED.value:
        return False
    if member.deleted_at is not None:
        return False
    if exclude_membership_refunded and member.membership_refunded_at is not None:
        return False
    selected = set(normalize_plan_kinds(plan_kinds))
    classified = classify_gift_plan_kind(
        kind_label=(tpl.kind_label if tpl is not None else None),
        card_kind=str(order.card_kind or ""),
        has_template=tpl is not None,
    )
    if not plan_kind_matches(classified, selected):
        return False
    credited_on = _shanghai_calendar_day(first_credit_at_for_order(db, order))
    if credited_on is None:
        return False
    return credited_from <= credited_on <= credited_to
