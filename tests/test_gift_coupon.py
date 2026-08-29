"""礼品券：圈人、发放、求交核销、入账钩子不得阻断开卡。"""

from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.db.base import Base
from app.models.balance_log import BalanceLog
from app.models.enums import BalanceReason, CardOrderKind, CardOrderPayStatus, CardPayChannel, PlanType
from app.models.gift_coupon_campaign import GiftCouponCampaign
from app.models.gift_coupon_entitlement import GiftCouponEntitlement
from app.models.member import Member
from app.models.member_card_order import MemberCardOrder
from app.models.membership_card_template import MembershipCardTemplate
from app.models.store import Store
from app.models.tenant import Tenant
from app.schemas.gift_coupon import GiftCouponCampaignCreateIn, GiftCouponTodayRowOut
from app.services.gift_coupon.audience import preview_audience
from app.services.gift_coupon.constants import (
    CAMPAIGN_ACTIVE,
    ENTITLEMENT_GRANTED,
    ENTITLEMENT_REDEEMED,
    PLAN_KIND_MONTH,
    PLAN_KIND_QUARTER,
)
from app.services.gift_coupon.hooks import try_auto_grant_after_card_credit
from app.services.gift_coupon.kinds import classify_gift_plan_kind, normalize_plan_kinds
from app.services.gift_coupon.service import (
    close_campaign,
    create_campaign,
    grant_campaign,
    list_entitlements,
    list_today_deliverable,
    list_today_redeemed,
    redeem_on_sheet,
)


@pytest.fixture()
def gdb() -> Session:
    engine = create_engine("sqlite:///:memory:")
    tables = [
        Tenant.__table__,
        Store.__table__,
        Member.__table__,
        MembershipCardTemplate.__table__,
        MemberCardOrder.__table__,
        BalanceLog.__table__,
        GiftCouponCampaign.__table__,
        GiftCouponEntitlement.__table__,
    ]
    Base.metadata.create_all(engine, tables=tables)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = SessionLocal()
    try:
        session.add_all(
            [
                Tenant(id=1, name="测试租户", is_active=True),
                Store(
                    id=1,
                    tenant_id=1,
                    name="测试门店",
                    leave_deadline_time=time(21, 0),
                    is_active=True,
                ),
            ]
        )
        session.flush()
        yield session
    finally:
        session.close()
        engine.dispose()


def _member(db: Session, *, phone: str, refunded: bool = False) -> Member:
    m = Member(
        tenant_id=1,
        store_id=1,
        phone=phone,
        name=phone,
        balance=24,
        meal_quota_total=24,
        plan_type=PlanType.MONTH.value,
        is_active=True,
        delivery_start_date=date(2026, 8, 1),
        membership_refunded_at=datetime(2026, 8, 20, 12, 0, 0) if refunded else None,
    )
    db.add(m)
    db.flush()
    return m


_tid = 0


def _tpl(db: Session, *, kind_label: str) -> MembershipCardTemplate:
    global _tid
    _tid += 1
    tpl = MembershipCardTemplate(
        id=_tid,
        tenant_id=1,
        store_id=1,
        kind_label=kind_label,
        name=kind_label,
        meals_grant=24,
        meal_periods=["lunch"],
        sale_price_yuan=Decimal("100.00"),
        is_active=True,
        sort_order=_tid,
    )
    db.add(tpl)
    db.flush()
    return tpl


def _order(
    db: Session,
    member: Member,
    *,
    tpl: MembershipCardTemplate | None,
    card_kind: str,
    credited_at: datetime,
    applied: bool = True,
    pay_status: str = CardOrderPayStatus.PAID.value,
) -> MemberCardOrder:
    order = MemberCardOrder(
        tenant_id=1,
        store_id=1,
        member_id=int(member.id),
        membership_template_id=int(tpl.id) if tpl is not None else None,
        card_kind=card_kind,
        pay_channel=CardPayChannel.OFFLINE.value,
        pay_status=pay_status,
        applied_to_member=applied,
        meal_periods_snapshot=["lunch"],
        created_by="test",
        created_at=credited_at,
    )
    db.add(order)
    db.flush()
    if applied:
        db.add(
            BalanceLog(
                member_id=int(member.id),
                meal_period="lunch",
                change=24,
                reason=BalanceReason.RECHARGE.value,
                operator="test",
                detail=f"开卡工单#{int(order.id)}；{card_kind}；同步入账+24次",
                created_at=credited_at,
            )
        )
        db.flush()
    return order


def _sheet(*member_ids: int) -> dict[int, GiftCouponTodayRowOut]:
    out: dict[int, GiftCouponTodayRowOut] = {}
    for mid in member_ids:
        out[int(mid)] = GiftCouponTodayRowOut(
            entitlement_id=0,
            campaign_id=0,
            campaign_name="",
            sheet_label="",
            member_id=int(mid),
            name=str(mid),
            phone="",
            area="测试片区",
            address_line="测试地址",
        )
    return out


def test_classify_quarter_not_month() -> None:
    assert (
        classify_gift_plan_kind(kind_label="季卡", card_kind="月卡", has_template=True)
        == PLAN_KIND_QUARTER
    )
    assert (
        classify_gift_plan_kind(kind_label="月卡", card_kind="月卡", has_template=True)
        == PLAN_KIND_MONTH
    )
    assert (
        classify_gift_plan_kind(kind_label=None, card_kind="月卡", has_template=False)
        == PLAN_KIND_MONTH
    )
    assert (
        classify_gift_plan_kind(kind_label="午晚餐卡", card_kind="月卡", has_template=True)
        == PLAN_KIND_MONTH
    )
    assert classify_gift_plan_kind(kind_label="周卡", card_kind="周卡", has_template=True) is None


def test_normalize_plan_kinds_accepts_json_string() -> None:
    assert normalize_plan_kinds('["month"]') == [PLAN_KIND_MONTH]
    assert normalize_plan_kinds(["month", "quarter"]) == [PLAN_KIND_MONTH, PLAN_KIND_QUARTER]


def test_audience_month_excludes_quarter_and_refund(gdb: Session) -> None:
    month_tpl = _tpl(gdb, kind_label="月卡")
    quarter_tpl = _tpl(gdb, kind_label="季卡")
    m_month = _member(gdb, phone="13800000001")
    m_quarter = _member(gdb, phone="13800000002")
    m_refund = _member(gdb, phone="13800000003", refunded=True)
    m_classic = _member(gdb, phone="13800000004")
    m_combo = _member(gdb, phone="13800000005")
    combo_tpl = _tpl(gdb, kind_label="午晚餐卡")
    _order(
        gdb,
        m_combo,
        tpl=combo_tpl,
        card_kind=CardOrderKind.MONTH.value,
        credited_at=datetime(2026, 8, 9, 10, 0, 0),
    )
    _order(
        gdb,
        m_month,
        tpl=month_tpl,
        card_kind=CardOrderKind.MONTH.value,
        credited_at=datetime(2026, 8, 5, 10, 0, 0),
    )
    _order(
        gdb,
        m_quarter,
        tpl=quarter_tpl,
        card_kind=CardOrderKind.MONTH.value,
        credited_at=datetime(2026, 8, 6, 10, 0, 0),
    )
    _order(
        gdb,
        m_refund,
        tpl=month_tpl,
        card_kind=CardOrderKind.MONTH.value,
        credited_at=datetime(2026, 8, 7, 10, 0, 0),
    )
    _order(
        gdb,
        m_classic,
        tpl=None,
        card_kind=CardOrderKind.MONTH.value,
        credited_at=datetime(2026, 8, 8, 10, 0, 0),
    )
    gdb.commit()

    month_items = preview_audience(
        gdb,
        tenant_id=1,
        store_id=1,
        plan_kinds=[PLAN_KIND_MONTH],
        credited_from=date(2026, 8, 1),
        credited_to=date(2026, 8, 31),
        exclude_membership_refunded=True,
    )
    ids = {x.member_id for x in month_items}
    assert int(m_month.id) in ids
    assert int(m_classic.id) in ids
    assert int(m_combo.id) in ids
    assert int(m_quarter.id) not in ids
    assert int(m_refund.id) not in ids

    quarter_items = preview_audience(
        gdb,
        tenant_id=1,
        store_id=1,
        plan_kinds=[PLAN_KIND_QUARTER],
        credited_from=date(2026, 8, 1),
        credited_to=date(2026, 8, 31),
        exclude_membership_refunded=True,
    )
    assert {x.member_id for x in quarter_items} == {int(m_quarter.id)}


def test_audience_renew_once_and_outside_range(gdb: Session) -> None:
    tpl = _tpl(gdb, kind_label="月卡")
    m = _member(gdb, phone="13800000011")
    _order(
        gdb,
        m,
        tpl=tpl,
        card_kind=CardOrderKind.MONTH.value,
        credited_at=datetime(2026, 7, 1, 10, 0, 0),
    )
    _order(
        gdb,
        m,
        tpl=tpl,
        card_kind=CardOrderKind.MONTH.value,
        credited_at=datetime(2026, 8, 15, 10, 0, 0),
    )
    gdb.commit()
    items = preview_audience(
        gdb,
        tenant_id=1,
        store_id=1,
        plan_kinds=[PLAN_KIND_MONTH],
        credited_from=date(2026, 8, 1),
        credited_to=date(2026, 8, 31),
    )
    assert len(items) == 1
    assert items[0].member_id == int(m.id)
    assert items[0].credited_on == "2026-08-15"


def test_grant_redeem_skip_not_on_sheet_and_idempotent(gdb: Session) -> None:
    tpl = _tpl(gdb, kind_label="月卡")
    on_sheet = _member(gdb, phone="13800000021")
    off_sheet = _member(gdb, phone="13800000022")
    _order(
        gdb,
        on_sheet,
        tpl=tpl,
        card_kind=CardOrderKind.MONTH.value,
        credited_at=datetime(2026, 8, 3, 10, 0, 0),
    )
    _order(
        gdb,
        off_sheet,
        tpl=tpl,
        card_kind=CardOrderKind.MONTH.value,
        credited_at=datetime(2026, 8, 4, 10, 0, 0),
    )
    gdb.commit()
    camp = create_campaign(
        gdb,
        tenant_id=1,
        store_id=1,
        body=GiftCouponCampaignCreateIn(
            name="8月礼品券",
            sheet_label="礼品券",
            plan_kinds=["month"],
            credited_from=date(2026, 8, 1),
            credited_to=date(2026, 8, 31),
        ),
        operator="tester",
    )
    granted = grant_campaign(
        gdb, tenant_id=1, store_id=1, campaign_id=camp.id, operator="tester"
    )
    assert granted.status == CAMPAIGN_ACTIVE
    assert granted.granted_count == 2
    items, total = list_entitlements(
        gdb, tenant_id=1, store_id=1, campaign_id=camp.id, status="granted", page=1, page_size=20
    )
    assert total == 2
    assert len(items) == 2

    ents = gdb.scalars(select(GiftCouponEntitlement)).all()
    by_member = {int(e.member_id): e for e in ents}
    sheet = _sheet(int(on_sheet.id))
    today = list_today_deliverable(
        gdb,
        tenant_id=1,
        store_id=1,
        delivery_date=date(2026, 8, 28),
        sheet_view="lunch",
        sheet_members=sheet,
    )
    assert len(today.items) == 1
    assert today.items[0].member_id == int(on_sheet.id)

    both_ids = [int(by_member[int(on_sheet.id)].id), int(by_member[int(off_sheet.id)].id)]
    result = redeem_on_sheet(
        gdb,
        tenant_id=1,
        store_id=1,
        delivery_date=date(2026, 8, 28),
        sheet_view="lunch",
        entitlement_ids=both_ids,
        operator="tester",
        sheet_members=sheet,
    )
    assert result.redeemed_count == 1
    assert result.skipped_not_on_sheet == 1
    gdb.refresh(by_member[int(off_sheet.id)])
    assert by_member[int(off_sheet.id)].status == ENTITLEMENT_GRANTED
    gdb.refresh(by_member[int(on_sheet.id)])
    assert by_member[int(on_sheet.id)].status == ENTITLEMENT_REDEEMED

    again = redeem_on_sheet(
        gdb,
        tenant_id=1,
        store_id=1,
        delivery_date=date(2026, 8, 28),
        sheet_view="lunch",
        entitlement_ids=[int(by_member[int(on_sheet.id)].id)],
        operator="tester",
        sheet_members=sheet,
    )
    assert again.redeemed_count == 0
    assert again.already_redeemed_count == 1

    reprinted = list_today_redeemed(
        gdb,
        tenant_id=1,
        store_id=1,
        delivery_date=date(2026, 8, 28),
        sheet_view="lunch",
        sheet_members=sheet,
    )
    assert len(reprinted.items) == 1
    gdb.refresh(by_member[int(on_sheet.id)])
    assert by_member[int(on_sheet.id)].status == ENTITLEMENT_REDEEMED


def test_closed_campaign_not_in_today_list(gdb: Session) -> None:
    tpl = _tpl(gdb, kind_label="月卡")
    m = _member(gdb, phone="13800000031")
    _order(
        gdb,
        m,
        tpl=tpl,
        card_kind=CardOrderKind.MONTH.value,
        credited_at=datetime(2026, 8, 1, 10, 0, 0),
    )
    gdb.commit()
    camp = create_campaign(
        gdb,
        tenant_id=1,
        store_id=1,
        body=GiftCouponCampaignCreateIn(
            name="关闭测试",
            sheet_label="礼品券",
            plan_kinds=["month"],
            credited_from=date(2026, 8, 1),
            credited_to=date(2026, 8, 31),
        ),
        operator="tester",
    )
    grant_campaign(gdb, tenant_id=1, store_id=1, campaign_id=camp.id, operator="tester")
    close_campaign(gdb, campaign_id=camp.id, store_id=1)
    today = list_today_deliverable(
        gdb,
        tenant_id=1,
        store_id=1,
        delivery_date=date(2026, 8, 28),
        sheet_view="lunch",
        sheet_members=_sheet(int(m.id)),
    )
    assert today.items == []


def test_auto_grant_hook_and_does_not_raise(gdb: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    tpl = _tpl(gdb, kind_label="月卡")
    m = _member(gdb, phone="13800000041")
    camp = create_campaign(
        gdb,
        tenant_id=1,
        store_id=1,
        body=GiftCouponCampaignCreateIn(
            name="自动补发",
            sheet_label="礼品券",
            plan_kinds=["month"],
            credited_from=date(2026, 8, 1),
            credited_to=date(2026, 8, 31),
        ),
        operator="tester",
    )
    grant_campaign(gdb, tenant_id=1, store_id=1, campaign_id=camp.id, operator="tester")
    order = _order(
        gdb,
        m,
        tpl=tpl,
        card_kind=CardOrderKind.MONTH.value,
        credited_at=datetime(2026, 8, 29, 10, 0, 0),
    )
    gdb.commit()
    try_auto_grant_after_card_credit(gdb, order)
    gdb.commit()
    n = gdb.scalar(
        select(GiftCouponEntitlement).where(
            GiftCouponEntitlement.member_id == int(m.id),
            GiftCouponEntitlement.campaign_id == camp.id,
        )
    )
    assert n is not None
    assert n.status == ENTITLEMENT_GRANTED

    def _boom(*_a, **_k):
        raise RuntimeError("boom")

    monkeypatch.setattr(
        "app.services.gift_coupon.hooks._auto_grant_after_card_credit", _boom
    )
    try_auto_grant_after_card_credit(gdb, order)
