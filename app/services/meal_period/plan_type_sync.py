"""会员 plan_type 与开卡工单对齐：多卡并存时以最近一笔已入账工单为准。"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.models.enums import CardOrderPayStatus, CardPayChannel, PlanType
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


def card_kind_label_from_periods(periods: frozenset[str] | set[str]) -> str:
    """无模版种类时的兜底：午餐卡 / 晚餐卡 / 午晚餐卡。"""
    scope = meal_scope_label_from_periods(periods)
    if scope == "全餐":
        return "午晚餐卡"
    return f"{scope}卡"


def load_member_card_kind_label_map(
    db: Session,
    member_ids: list[int],
    *,
    periods_by_member: dict[int, frozenset[str]] | None = None,
) -> dict[int, str]:
    """各会员最近一笔已入账工单的卡种类（kind_label）；无模版时按餐段资格兜底。"""
    ids = sorted({int(x) for x in member_ids if x is not None})
    out: dict[int, str] = {}
    if not ids:
        return out
    latest_sq = (
        select(
            MemberCardOrder.member_id.label("mid"),
            func.max(MemberCardOrder.id).label("max_id"),
        )
        .where(
            MemberCardOrder.member_id.in_(ids),
            MemberCardOrder.pay_status == CardOrderPayStatus.PAID.value,
            MemberCardOrder.applied_to_member.is_(True),
        )
        .group_by(MemberCardOrder.member_id)
    ).subquery("latest_card_tpl")
    rows = db.execute(
        select(
            MemberCardOrder.member_id,
            MembershipCardTemplate.kind_label,
        )
        .select_from(MemberCardOrder)
        .join(
            latest_sq,
            and_(
                MemberCardOrder.member_id == latest_sq.c.mid,
                MemberCardOrder.id == latest_sq.c.max_id,
            ),
        )
        .outerjoin(
            MembershipCardTemplate,
            MemberCardOrder.membership_template_id == MembershipCardTemplate.id,
        )
    ).all()
    tpl_by_mid: dict[int, str] = {}
    for mid, kind_label in rows:
        tpl_by_mid[int(mid)] = (kind_label or "").strip()
    periods_map = periods_by_member or {}
    for mid in ids:
        label = tpl_by_mid.get(mid, "")
        if label:
            out[mid] = label
        else:
            out[mid] = card_kind_label_from_periods(periods_map.get(mid, frozenset()))
    return out


def _normalized_period_set(periods: frozenset[str] | set[str] | list[str] | None) -> frozenset[str]:
    """空餐段视为经典午餐，与工单快照缺省口径一致。"""
    normalized = {(x or "").strip().lower() for x in (periods or []) if x}
    return normalized if normalized else frozenset({"lunch"})


def catalog_template_plan_label_for_member(
    plan_type: str | None,
    periods: frozenset[str] | set[str] | list[str] | None,
    templates: list[MembershipCardTemplate] | list[object],
) -> str | None:
    """
    无工单卡包时，按计费周期 + 餐段匹配本店卡包展示名。
    只读展示，不写会员/工单。
    """
    if not templates:
        return None
    from app.services.meal_period.template_periods import catalog_periods_from_template
    from app.services.member.member_card_order_service import _plan_for_membership_template

    want_plan = (plan_type or "").strip()
    want_periods = _normalized_period_set(periods)
    hits: list[object] = []
    for tpl in templates:
        if _plan_for_membership_template(tpl).value != want_plan:
            continue
        tpl_periods = _normalized_period_set(catalog_periods_from_template(tpl))
        if tpl_periods == want_periods:
            hits.append(tpl)
    if not hits:
        return None

    def _rank(t: object) -> tuple[int, int, int]:
        active = 0 if bool(getattr(t, "is_active", True)) else 1
        order = int(getattr(t, "sort_order", 0) or 0)
        tid = int(getattr(t, "id", 0) or 0)
        return (active, order, tid)

    hits.sort(key=_rank)
    return membership_template_plan_label(hits[0])


def load_member_plan_type_display_map(
    db: Session,
    member_ids: list[int],
    *,
    plan_type_by_member: dict[int, str | None] | None = None,
    periods_by_member: dict[int, frozenset[str]] | None = None,
    catalog_templates: list[MembershipCardTemplate] | list[object] | None = None,
) -> dict[int, str]:
    """
    档案库套餐列：优先最近已入账工单的卡包文案（与筛选下拉一致）；
    无模版时按周期+餐段匹配本店卡包名，再回退「月卡 · 全餐」。不写库。
    """
    ids = sorted({int(x) for x in member_ids if x is not None})
    pt_map = plan_type_by_member or {}
    periods_map = periods_by_member or {}
    templates = list(catalog_templates or [])
    out: dict[int, str] = {}
    if not ids:
        return out
    latest_sq = (
        select(
            MemberCardOrder.member_id.label("mid"),
            func.max(MemberCardOrder.id).label("max_id"),
        )
        .where(
            MemberCardOrder.member_id.in_(ids),
            MemberCardOrder.pay_status == CardOrderPayStatus.PAID.value,
            MemberCardOrder.applied_to_member.is_(True),
        )
        .group_by(MemberCardOrder.member_id)
    ).subquery("latest_plan_display")
    rows = db.execute(
        select(MemberCardOrder.member_id, MembershipCardTemplate)
        .select_from(MemberCardOrder)
        .join(
            latest_sq,
            and_(
                MemberCardOrder.member_id == latest_sq.c.mid,
                MemberCardOrder.id == latest_sq.c.max_id,
            ),
        )
        .outerjoin(
            MembershipCardTemplate,
            MemberCardOrder.membership_template_id == MembershipCardTemplate.id,
        )
    ).all()
    tpl_label_by_mid: dict[int, str] = {}
    for mid, tpl in rows:
        if tpl is not None:
            tpl_label_by_mid[int(mid)] = membership_template_plan_label(tpl)
    for mid in ids:
        label = tpl_label_by_mid.get(mid, "").strip()
        if label:
            out[mid] = label
            continue
        catalog_label = catalog_template_plan_label_for_member(
            pt_map.get(mid), periods_map.get(mid, frozenset()), templates
        )
        if catalog_label:
            out[mid] = catalog_label
        else:
            out[mid] = format_plan_type_display(
                pt_map.get(mid), periods_map.get(mid, frozenset())
            )
    return out


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


def membership_template_plan_label(template: MembershipCardTemplate) -> str:
    """与管理端下拉 ``membershipTemplatePlanLabel`` 对齐：种类 + 餐段。"""
    from app.services.meal_period.template_periods import meal_periods_from_template

    kind = (template.kind_label or "").strip() or (template.name or "").strip() or "会员卡"
    if "·" in kind or "午餐" in kind or "晚餐" in kind or "全餐" in kind:
        return kind
    periods = meal_periods_from_template(template)
    return f"{kind} · {meal_scope_label_from_periods(set(periods))}"


def apply_admin_membership_template(
    db: Session,
    member: Member,
    template: MembershipCardTemplate,
    *,
    operator: str | None = None,
) -> dict[str, object]:
    """
    后台改套餐：写入 members.plan_type，并把最近一笔已入账工单对齐到该模版
    （模版 id / card_kind / 餐段快照）。不改余额、不重写历史工单金额。
    其余已入账工单只对齐餐段快照，避免并集资格仍停留在旧的「全餐」。
    台账导入等无已入账工单的会员：补一条 0 元已缴工单只绑定卡包与餐段，不入账次数。
    返回是否改动了工单及展示文案，供操作记录使用。
    """
    from app.services.member.member_card_order_service import (
        _plan_for_membership_template,
        enum_card_kind_for_template,
    )
    from app.services.meal_period.combo_with_lunch import snapshot_deliver_dinner_with_lunch_from_template
    from app.services.meal_period.template_periods import meal_periods_from_template

    plan = _plan_for_membership_template(template)
    member.plan_type = plan.value
    db.add(member)

    periods = meal_periods_from_template(template)
    combo = snapshot_deliver_dinner_with_lunch_from_template(template, periods)
    card_kind = enum_card_kind_for_template(template)
    new_label = membership_template_plan_label(template)
    latest = _latest_applied_paid_card_order(db, int(member.id))
    if latest is None:
        created_by = (operator or "admin").strip()[:64] or "admin"
        db.add(
            MemberCardOrder(
                member_id=int(member.id),
                tenant_id=int(member.tenant_id),
                store_id=int(member.store_id),
                membership_template_id=int(template.id),
                meal_periods_snapshot=periods,
                deliver_dinner_with_lunch_snapshot=combo,
                card_kind=card_kind,
                pay_channel=CardPayChannel.OFFLINE.value,
                pay_status=CardOrderPayStatus.PAID.value,
                amount_yuan=Decimal("0.00"),
                remark="档案修改套餐类型（不入账次数）",
                applied_to_member=True,
                created_by=created_by,
            )
        )
        return {
            "order_changed": True,
            "prev_template_id": None,
            "new_template_id": int(template.id),
            "new_label": new_label,
        }

    prev_tid = (
        int(latest.membership_template_id) if latest.membership_template_id is not None else None
    )
    card_kind = enum_card_kind_for_template(template)
    order_changed = (
        prev_tid != int(template.id)
        or (latest.card_kind or "") != card_kind
        or list(latest.meal_periods_snapshot or []) != list(periods)
        or bool(latest.deliver_dinner_with_lunch_snapshot) != bool(combo)
    )
    latest.membership_template_id = int(template.id)
    latest.card_kind = card_kind
    latest.meal_periods_snapshot = periods
    latest.deliver_dinner_with_lunch_snapshot = combo
    db.add(latest)

    older_orders = db.scalars(
        select(MemberCardOrder).where(
            MemberCardOrder.member_id == int(member.id),
            MemberCardOrder.pay_status == CardOrderPayStatus.PAID.value,
            MemberCardOrder.applied_to_member.is_(True),
            MemberCardOrder.id != int(latest.id),
        )
    ).all()
    for row in older_orders:
        if list(row.meal_periods_snapshot or []) != list(periods) or bool(
            row.deliver_dinner_with_lunch_snapshot
        ) != bool(combo):
            row.meal_periods_snapshot = periods
            row.deliver_dinner_with_lunch_snapshot = combo
            db.add(row)
            order_changed = True

    return {
        "order_changed": order_changed,
        "prev_template_id": prev_tid,
        "new_template_id": int(template.id),
        "new_label": new_label,
    }


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
