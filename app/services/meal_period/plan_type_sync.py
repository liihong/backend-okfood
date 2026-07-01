"""会员 plan_type 与开卡工单对齐：多卡并存时以最近一笔已入账工单为准。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import CardOrderPayStatus, PlanType
from app.models.member import Member
from app.models.member_card_order import MemberCardOrder
from app.models.membership_card_template import MembershipCardTemplate


def meal_scope_label_from_periods(periods: frozenset[str] | set[str]) -> str:
    """根据餐段资格生成管理端展示标签：午餐 / 晚餐 / 全餐。"""
    normalized = {(x or "").strip().lower() for x in periods if x}
    has_lunch = "lunch" in normalized
    has_dinner = "dinner" in normalized
    if has_lunch and has_dinner:
        return "全餐"
    if has_dinner:
        return "晚餐"
    if has_lunch:
        return "午餐"
    return "午餐"


def format_plan_type_display(plan_type: str | None, periods: frozenset[str] | set[str]) -> str:
    """管理端方案 A：「周卡 · 全餐」；plan_type 仍为计费周期，餐段来自 entitled_meal_periods。"""
    pt = (plan_type or PlanType.TIMES.value).strip() or PlanType.TIMES.value
    return f"{pt} · {meal_scope_label_from_periods(periods)}"


def _latest_applied_paid_card_order(db: Session, member_id: int) -> MemberCardOrder | None:
    """最近一笔已缴且已入账的开卡工单（按 id 倒序，id 越大越新）。"""
    return db.scalars(
        select(MemberCardOrder)
        .where(
            MemberCardOrder.member_id == int(member_id),
            MemberCardOrder.pay_status == CardOrderPayStatus.PAID.value,
            MemberCardOrder.applied_to_member.is_(True),
        )
        .order_by(MemberCardOrder.id.desc())
    ).first()


def plan_type_from_card_order(db: Session, order: MemberCardOrder) -> PlanType:
    """从开卡工单解析计费周期（周/月/次），与入账逻辑一致。"""
    from app.services.member.member_card_order_service import _plan_for_membership_template, _quota_for_card_kind

    tpl_id = getattr(order, "membership_template_id", None)
    if tpl_id is not None:
        tpl = db.get(MembershipCardTemplate, int(tpl_id))
        if tpl is not None:
            return _plan_for_membership_template(tpl)
    return _quota_for_card_kind(order.card_kind)[0]


def sync_member_plan_type_from_latest_card_order(db: Session, member: Member) -> None:
    """
    多卡并存：以最近一笔已入账工单更新 members.plan_type。
    plan_type 为会员级计费周期（周/月/次），与餐段资格正交；展示请用 format_plan_type_display。
    无已入账工单时不改动（保留手工 patch 或历史档案）。
    """
    db.flush()
    order = _latest_applied_paid_card_order(db, int(member.id))
    if order is None:
        return
    plan = plan_type_from_card_order(db, order)
    member.plan_type = plan.value
    db.add(member)
