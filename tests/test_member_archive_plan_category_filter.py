"""会员档案库套餐筛选：按租户会员卡模版种类+餐段，而非写死周卡/月卡。"""

from __future__ import annotations

from datetime import date, time
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models.enums import CardOrderPayStatus, CardPayChannel, PlanType
from app.models.member import Member
from app.models.member_card_order import MemberCardOrder
from app.models.membership_card_template import MembershipCardTemplate
from app.models.store import Store
from app.models.tenant import Tenant
from app.services.admin.admin_service import _apply_member_list_filters
from app.services.admin.catalog_admin_service import resolve_membership_template_member_filter


@pytest.fixture()
def plan_filter_db() -> Session:
    engine = create_engine("sqlite:///:memory:")
    tables = [
        Tenant.__table__,
        Store.__table__,
        Member.__table__,
        MembershipCardTemplate.__table__,
        MemberCardOrder.__table__,
    ]
    Base.metadata.create_all(engine, tables=tables)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = SessionLocal()
    try:
        session.add_all(
            [
                Tenant(id=1, name="测试租户", is_active=True),
                Store(id=1, tenant_id=1, name="测试门店", leave_deadline_time=time(21, 0), is_active=True),
            ]
        )
        session.flush()
        yield session
    finally:
        session.close()
        engine.dispose()


def _member(db: Session, *, phone: str, plan_type: str) -> Member:
    m = Member(
        tenant_id=1,
        store_id=1,
        phone=phone,
        name=phone,
        balance=6,
        meal_quota_total=6,
        plan_type=plan_type,
        is_active=True,
        delivery_start_date=date(2026, 1, 1),
    )
    db.add(m)
    db.flush()
    return m


_tpl_id = 0


def _next_tpl_id() -> int:
    global _tpl_id
    _tpl_id += 1
    return _tpl_id


def _template(
    db: Session,
    *,
    kind_label: str,
    meal_periods: list[str],
    meals_grant: int = 6,
    sort_order: int = 0,
) -> MembershipCardTemplate:
    tpl = MembershipCardTemplate(
        id=_next_tpl_id(),
        tenant_id=1,
        store_id=1,
        kind_label=kind_label,
        name=kind_label,
        meals_grant=meals_grant,
        meal_periods=list(meal_periods),
        sale_price_yuan=Decimal("100.00"),
        is_active=True,
        sort_order=sort_order,
    )
    db.add(tpl)
    db.flush()
    return tpl


def _paid_order(db: Session, member: Member, tpl: MembershipCardTemplate | None, *, card_kind: str) -> None:
    db.add(
        MemberCardOrder(
            tenant_id=1,
            store_id=1,
            member_id=int(member.id),
            membership_template_id=int(tpl.id) if tpl is not None else None,
            card_kind=card_kind,
            pay_channel=CardPayChannel.OFFLINE.value,
            pay_status=CardOrderPayStatus.PAID.value,
            applied_to_member=True,
            meal_periods_snapshot=list(tpl.meal_periods) if tpl is not None else ["lunch"],
            created_by="test",
        )
    )
    db.flush()


def _filter_ids(
    db: Session,
    *,
    plan_type: str | None = None,
    membership_template_ids: list[int] | None = None,
    fallback_plan_type: str | None = None,
) -> set[int]:
    stmt = _apply_member_list_filters(
        select(Member.id).select_from(Member),
        q_phone=None,
        validity=None,
        store_id=1,
        plan_type=plan_type,
        membership_template_ids=membership_template_ids,
        membership_template_fallback_plan_type=fallback_plan_type,
    )
    return {int(x) for x in db.scalars(stmt).all()}


def test_template_filter_matches_same_kind_and_period(plan_filter_db: Session) -> None:
    lunch_week = _template(plan_filter_db, kind_label="周卡", meal_periods=["lunch"], sort_order=1)
    lunch_month = _template(
        plan_filter_db, kind_label="月卡", meal_periods=["lunch"], meals_grant=24, sort_order=2
    )
    combo_month = _template(
        plan_filter_db,
        kind_label="月卡",
        meal_periods=["lunch", "dinner"],
        meals_grant=24,
        sort_order=3,
    )
    season = _template(
        plan_filter_db, kind_label="季卡", meal_periods=["lunch"], meals_grant=24, sort_order=4
    )

    m_week = _member(plan_filter_db, phone="13800001001", plan_type=PlanType.WEEK.value)
    m_month_lunch = _member(plan_filter_db, phone="13800001002", plan_type=PlanType.MONTH.value)
    m_month_combo = _member(plan_filter_db, phone="13800001003", plan_type=PlanType.MONTH.value)
    m_season = _member(plan_filter_db, phone="13800001004", plan_type=PlanType.MONTH.value)
    _paid_order(plan_filter_db, m_week, lunch_week, card_kind=PlanType.WEEK.value)
    _paid_order(plan_filter_db, m_month_lunch, lunch_month, card_kind=PlanType.MONTH.value)
    _paid_order(plan_filter_db, m_month_combo, combo_month, card_kind=PlanType.MONTH.value)
    _paid_order(plan_filter_db, m_season, season, card_kind=PlanType.MONTH.value)
    plan_filter_db.commit()

    week_ids, week_fb = resolve_membership_template_member_filter(
        plan_filter_db, template_id=int(lunch_week.id), tenant_id=1, store_id=1
    )
    assert week_fb == PlanType.WEEK.value
    assert _filter_ids(
        plan_filter_db, membership_template_ids=week_ids, fallback_plan_type=week_fb
    ) == {int(m_week.id)}

    month_lunch_ids, month_fb = resolve_membership_template_member_filter(
        plan_filter_db, template_id=int(lunch_month.id), tenant_id=1, store_id=1
    )
    assert month_fb == PlanType.MONTH.value
    assert _filter_ids(
        plan_filter_db, membership_template_ids=month_lunch_ids, fallback_plan_type=month_fb
    ) == {int(m_month_lunch.id)}

    combo_ids, combo_fb = resolve_membership_template_member_filter(
        plan_filter_db, template_id=int(combo_month.id), tenant_id=1, store_id=1
    )
    assert combo_fb is None
    assert _filter_ids(
        plan_filter_db, membership_template_ids=combo_ids, fallback_plan_type=combo_fb
    ) == {int(m_month_combo.id)}

    season_ids, season_fb = resolve_membership_template_member_filter(
        plan_filter_db, template_id=int(season.id), tenant_id=1, store_id=1
    )
    assert season_fb is None
    assert _filter_ids(
        plan_filter_db, membership_template_ids=season_ids, fallback_plan_type=season_fb
    ) == {int(m_season.id)}


def test_lunch_week_filter_includes_imported_member_without_card_order(plan_filter_db: Session) -> None:
    lunch_week = _template(plan_filter_db, kind_label="周卡", meal_periods=["lunch"])
    imported = _member(plan_filter_db, phone="13800001005", plan_type=PlanType.WEEK.value)
    other = _member(plan_filter_db, phone="13800001006", plan_type=PlanType.MONTH.value)
    plan_filter_db.commit()

    ids, fb = resolve_membership_template_member_filter(
        plan_filter_db, template_id=int(lunch_week.id), tenant_id=1, store_id=1
    )
    assert fb == PlanType.WEEK.value
    hit = _filter_ids(plan_filter_db, membership_template_ids=ids, fallback_plan_type=fb)
    assert int(imported.id) in hit
    assert int(other.id) not in hit


def test_legacy_plan_type_filter_still_matches_member_plan_type(plan_filter_db: Session) -> None:
    week = _member(plan_filter_db, phone="13800001007", plan_type=PlanType.WEEK.value)
    month = _member(plan_filter_db, phone="13800001008", plan_type=PlanType.MONTH.value)
    plan_filter_db.commit()
    assert _filter_ids(plan_filter_db, plan_type=PlanType.WEEK.value) == {int(week.id)}
    assert _filter_ids(plan_filter_db, plan_type=PlanType.MONTH.value) == {int(month.id)}


def test_same_kind_and_period_templates_share_filter(plan_filter_db: Session) -> None:
    """下拉按展示文案去重后，同类模版会员仍应一并查出。"""
    a = _template(plan_filter_db, kind_label="周卡", meal_periods=["lunch"], sort_order=1)
    b = _template(plan_filter_db, kind_label="周卡", meal_periods=["lunch"], sort_order=2)
    ma = _member(plan_filter_db, phone="13800001009", plan_type=PlanType.WEEK.value)
    mb = _member(plan_filter_db, phone="13800001010", plan_type=PlanType.WEEK.value)
    _paid_order(plan_filter_db, ma, a, card_kind=PlanType.WEEK.value)
    _paid_order(plan_filter_db, mb, b, card_kind=PlanType.WEEK.value)
    plan_filter_db.commit()

    ids, fb = resolve_membership_template_member_filter(
        plan_filter_db, template_id=int(a.id), tenant_id=1, store_id=1
    )
    assert int(a.id) in ids and int(b.id) in ids
    hit = _filter_ids(plan_filter_db, membership_template_ids=ids, fallback_plan_type=fb)
    assert hit == {int(ma.id), int(mb.id)}
