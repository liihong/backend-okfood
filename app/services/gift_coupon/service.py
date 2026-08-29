"""礼品券主服务：活动、发放、资格、与当日大表求交核销。

不写入 members.remarks，不改配送应送 SQL。
今日名单只读调用 build_delivery_sheet，取其会员 id 后在本模块求交。
"""

from __future__ import annotations

import logging
from datetime import date

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.timeutil import beijing_now_naive, today_shanghai
from app.models.enums import DeliverySheetView
from app.models.gift_coupon_campaign import GiftCouponCampaign
from app.models.gift_coupon_entitlement import GiftCouponEntitlement
from app.models.member import Member
from app.models.member_address import MemberAddress
from app.schemas.admin import DeliverySheetOut
from app.schemas.gift_coupon import (
    GiftCouponAudiencePreviewOut,
    GiftCouponCampaignCreateIn,
    GiftCouponCampaignOut,
    GiftCouponCampaignPatchIn,
    GiftCouponEntitlementOut,
    GiftCouponManualGrantFailedItem,
    GiftCouponManualGrantOut,
    GiftCouponRedeemOut,
    GiftCouponTodayListOut,
    GiftCouponTodayRowOut,
)
from app.services.gift_coupon.audience import preview_audience
from app.services.gift_coupon.kinds import normalize_plan_kinds
from app.services.gift_coupon.constants import (
    CAMPAIGN_ACTIVE,
    CAMPAIGN_CLOSED,
    CAMPAIGN_DRAFT,
    ENTITLEMENT_GRANTED,
    ENTITLEMENT_REDEEMED,
    ENTITLEMENT_REVOKED,
    GRANT_SOURCE_MANUAL,
    GRANT_SOURCE_RULE,
    MATCH_ANY_IN_RANGE,
)

logger = logging.getLogger(__name__)

_PHONE_SEPS = (" ", "-")


def _normalize_phone(phone: str) -> str:
    s = (phone or "").strip()
    for ch in _PHONE_SEPS:
        s = s.replace(ch, "")
    return s


def _parse_phones(raw: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in raw:
        for part in str(item or "").replace("，", ",").replace("；", ";").replace("\n", ",").split(","):
            for bit in part.replace(";", " ").split():
                ph = _normalize_phone(bit)
                if not ph or ph in seen:
                    continue
                seen.add(ph)
                out.append(ph)
    return out


def _campaign_or_404(db: Session, *, campaign_id: int, store_id: int) -> GiftCouponCampaign:
    row = db.get(GiftCouponCampaign, int(campaign_id))
    if not row or int(row.store_id) != int(store_id):
        raise HTTPException(status_code=404, detail="礼品券活动不存在")
    return row


def _dt_iso(v) -> str | None:
    if v is None:
        return None
    if hasattr(v, "isoformat"):
        return v.isoformat()
    return str(v)


def _date_iso(v) -> str | None:
    if v is None:
        return None
    if hasattr(v, "isoformat"):
        return v.isoformat()
    return str(v)


def _entitlement_counts(db: Session, campaign_id: int) -> tuple[int, int, int]:
    rows = db.execute(
        select(GiftCouponEntitlement.status, func.count(GiftCouponEntitlement.id)).where(
            GiftCouponEntitlement.campaign_id == int(campaign_id)
        ).group_by(GiftCouponEntitlement.status)
    ).all()
    by = {str(s): int(c) for s, c in rows}
    return (
        by.get(ENTITLEMENT_GRANTED, 0),
        by.get(ENTITLEMENT_REDEEMED, 0),
        by.get(ENTITLEMENT_REVOKED, 0),
    )


def campaign_to_out(db: Session, row: GiftCouponCampaign) -> GiftCouponCampaignOut:
    g, r, v = _entitlement_counts(db, int(row.id))
    kinds = normalize_plan_kinds(row.plan_kinds)
    return GiftCouponCampaignOut(
        id=int(row.id),
        name=str(row.name),
        sheet_label=str(row.sheet_label),
        status=str(row.status),  # type: ignore[arg-type]
        plan_kinds=kinds,  # type: ignore[arg-type]
        credited_from=row.credited_from.isoformat(),
        credited_to=row.credited_to.isoformat(),
        exclude_membership_refunded=bool(row.exclude_membership_refunded),
        match_mode=str(row.match_mode),  # type: ignore[arg-type]
        created_by=str(row.created_by),
        granted_at=_dt_iso(row.granted_at),
        closed_at=_dt_iso(row.closed_at),
        created_at=_dt_iso(row.created_at) or "",
        granted_count=g,
        redeemed_count=r,
        revoked_count=v,
    )


def _member_for_entitlement(db: Session, member_id: int) -> Member | None:
    m = db.get(Member, int(member_id))
    if not m or m.deleted_at is not None:
        return None
    return m


def entitlement_to_out(db: Session, row: GiftCouponEntitlement) -> GiftCouponEntitlementOut:
    camp = db.get(GiftCouponCampaign, int(row.campaign_id))
    mem = _member_for_entitlement(db, int(row.member_id))
    return GiftCouponEntitlementOut(
        id=int(row.id),
        campaign_id=int(row.campaign_id),
        campaign_name=str(camp.name) if camp else "",
        sheet_label=str(camp.sheet_label) if camp else "",
        member_id=int(row.member_id),
        member_name=str(mem.name or "") if mem else "",
        member_phone=str(mem.phone or "") if mem else "",
        status=str(row.status),  # type: ignore[arg-type]
        grant_source=str(row.grant_source),  # type: ignore[arg-type]
        granted_at=_dt_iso(row.granted_at) or "",
        granted_by=str(row.granted_by),
        redeemed_at=_dt_iso(row.redeemed_at),
        redeemed_delivery_date=_date_iso(row.redeemed_delivery_date),
        redeemed_by=(row.redeemed_by or None),
        revoked_at=_dt_iso(row.revoked_at),
        revoked_by=(row.revoked_by or None),
    )


def list_campaigns(
    db: Session,
    *,
    tenant_id: int,
    store_id: int,
    status: str | None = None,
) -> list[GiftCouponCampaignOut]:
    stmt = select(GiftCouponCampaign).where(
        GiftCouponCampaign.tenant_id == int(tenant_id),
        GiftCouponCampaign.store_id == int(store_id),
    )
    if status:
        stmt = stmt.where(GiftCouponCampaign.status == status)
    stmt = stmt.order_by(GiftCouponCampaign.id.desc())
    rows = db.scalars(stmt).all()
    return [campaign_to_out(db, r) for r in rows]


def create_campaign(
    db: Session,
    *,
    tenant_id: int,
    store_id: int,
    body: GiftCouponCampaignCreateIn,
    operator: str,
) -> GiftCouponCampaignOut:
    row = GiftCouponCampaign(
        tenant_id=int(tenant_id),
        store_id=int(store_id),
        name=body.name.strip(),
        sheet_label=body.sheet_label.strip(),
        status=CAMPAIGN_DRAFT,
        plan_kinds=list(body.plan_kinds),
        credited_from=body.credited_from,
        credited_to=body.credited_to,
        exclude_membership_refunded=bool(body.exclude_membership_refunded),
        match_mode=MATCH_ANY_IN_RANGE,
        created_by=(operator or "").strip() or "admin",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return campaign_to_out(db, row)


def patch_campaign(
    db: Session,
    *,
    campaign_id: int,
    store_id: int,
    body: GiftCouponCampaignPatchIn,
) -> GiftCouponCampaignOut:
    row = _campaign_or_404(db, campaign_id=campaign_id, store_id=store_id)
    if str(row.status) != CAMPAIGN_DRAFT:
        raise HTTPException(status_code=400, detail="仅草稿活动可修改规则")
    if body.name is not None:
        row.name = body.name.strip()
    if body.sheet_label is not None:
        row.sheet_label = body.sheet_label.strip()
    if body.plan_kinds is not None:
        row.plan_kinds = list(body.plan_kinds)
    if body.credited_from is not None:
        row.credited_from = body.credited_from
    if body.credited_to is not None:
        row.credited_to = body.credited_to
    if body.exclude_membership_refunded is not None:
        row.exclude_membership_refunded = bool(body.exclude_membership_refunded)
    if row.credited_to < row.credited_from:
        raise HTTPException(status_code=400, detail="入账日结束不能早于开始")
    db.add(row)
    db.commit()
    db.refresh(row)
    return campaign_to_out(db, row)


def preview_campaign_audience(
    db: Session,
    *,
    tenant_id: int,
    store_id: int,
    campaign_id: int,
) -> GiftCouponAudiencePreviewOut:
    row = _campaign_or_404(db, campaign_id=campaign_id, store_id=store_id)
    items = preview_audience(
        db,
        tenant_id=int(tenant_id),
        store_id=int(store_id),
        plan_kinds=normalize_plan_kinds(row.plan_kinds),
        credited_from=row.credited_from,
        credited_to=row.credited_to,
        exclude_membership_refunded=bool(row.exclude_membership_refunded),
    )
    return GiftCouponAudiencePreviewOut(total=len(items), items=items)


def preview_audience_by_rule(
    db: Session,
    *,
    tenant_id: int,
    store_id: int,
    plan_kinds: list[str],
    credited_from: date,
    credited_to: date,
    exclude_membership_refunded: bool = True,
) -> GiftCouponAudiencePreviewOut:
    items = preview_audience(
        db,
        tenant_id=int(tenant_id),
        store_id=int(store_id),
        plan_kinds=plan_kinds,
        credited_from=credited_from,
        credited_to=credited_to,
        exclude_membership_refunded=exclude_membership_refunded,
    )
    return GiftCouponAudiencePreviewOut(total=len(items), items=items)


def _insert_entitlement_if_absent(
    db: Session,
    *,
    campaign: GiftCouponCampaign,
    member_id: int,
    operator: str,
    source: str,
) -> GiftCouponEntitlement | None:
    exists = db.scalar(
        select(GiftCouponEntitlement.id).where(
            GiftCouponEntitlement.campaign_id == int(campaign.id),
            GiftCouponEntitlement.member_id == int(member_id),
        )
    )
    if exists is not None:
        return None
    row = GiftCouponEntitlement(
        campaign_id=int(campaign.id),
        member_id=int(member_id),
        tenant_id=int(campaign.tenant_id),
        store_id=int(campaign.store_id),
        status=ENTITLEMENT_GRANTED,
        grant_source=source,
        granted_at=beijing_now_naive(),
        granted_by=(operator or "").strip() or "admin",
    )
    db.add(row)
    db.flush()
    return row


def grant_campaign(
    db: Session,
    *,
    tenant_id: int,
    store_id: int,
    campaign_id: int,
    operator: str,
) -> GiftCouponCampaignOut:
    """按当前规则发放资格；草稿→active。已有资格幂等跳过。"""
    row = _campaign_or_404(db, campaign_id=campaign_id, store_id=store_id)
    if str(row.status) == CAMPAIGN_CLOSED:
        raise HTTPException(status_code=400, detail="活动已结束，无法发放")
    audience = preview_audience(
        db,
        tenant_id=int(tenant_id),
        store_id=int(store_id),
        plan_kinds=normalize_plan_kinds(row.plan_kinds),
        credited_from=row.credited_from,
        credited_to=row.credited_to,
        exclude_membership_refunded=bool(row.exclude_membership_refunded),
    )
    op = (operator or "").strip() or "admin"
    for item in audience:
        _insert_entitlement_if_absent(
            db, campaign=row, member_id=int(item.member_id), operator=op, source=GRANT_SOURCE_RULE
        )
    if str(row.status) == CAMPAIGN_DRAFT:
        row.status = CAMPAIGN_ACTIVE
        row.granted_at = beijing_now_naive()
        db.add(row)
    db.commit()
    db.refresh(row)
    return campaign_to_out(db, row)


def close_campaign(db: Session, *, campaign_id: int, store_id: int) -> GiftCouponCampaignOut:
    row = _campaign_or_404(db, campaign_id=campaign_id, store_id=store_id)
    if str(row.status) == CAMPAIGN_CLOSED:
        return campaign_to_out(db, row)
    row.status = CAMPAIGN_CLOSED
    row.closed_at = beijing_now_naive()
    db.add(row)
    db.commit()
    db.refresh(row)
    return campaign_to_out(db, row)


def list_entitlements(
    db: Session,
    *,
    tenant_id: int,
    store_id: int,
    campaign_id: int | None = None,
    status: str | None = None,
    member_phone: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[GiftCouponEntitlementOut], int]:
    stmt = select(GiftCouponEntitlement).where(
        GiftCouponEntitlement.tenant_id == int(tenant_id),
        GiftCouponEntitlement.store_id == int(store_id),
    )
    if campaign_id is not None:
        stmt = stmt.where(GiftCouponEntitlement.campaign_id == int(campaign_id))
    if status:
        stmt = stmt.where(GiftCouponEntitlement.status == status)
    phone = _normalize_phone(member_phone or "")
    if phone:
        stmt = stmt.join(Member, Member.id == GiftCouponEntitlement.member_id).where(
            Member.phone.contains(phone)
        )
    total = int(db.scalar(select(func.count()).select_from(stmt.subquery())) or 0)
    stmt = stmt.order_by(GiftCouponEntitlement.id.desc())
    stmt = stmt.offset((max(1, page) - 1) * page_size).limit(page_size)
    rows = db.scalars(stmt).all()
    return [entitlement_to_out(db, r) for r in rows], total


def manual_grant(
    db: Session,
    *,
    tenant_id: int,
    store_id: int,
    campaign_id: int,
    phones: list[str],
    operator: str,
) -> GiftCouponManualGrantOut:
    camp = _campaign_or_404(db, campaign_id=campaign_id, store_id=store_id)
    if str(camp.status) != CAMPAIGN_ACTIVE:
        raise HTTPException(status_code=400, detail="仅进行中的活动可手工补发")
    parsed = _parse_phones(phones)
    if not parsed:
        raise HTTPException(status_code=400, detail="请至少填写一个有效手机号")
    op = (operator or "").strip() or "admin"
    items: list[GiftCouponEntitlementOut] = []
    failed: list[GiftCouponManualGrantFailedItem] = []
    for ph in parsed:
        mem = db.scalar(
            select(Member).where(
                Member.store_id == int(store_id),
                Member.tenant_id == int(tenant_id),
                Member.phone == ph,
                Member.deleted_at.is_(None),
            )
        )
        if mem is None:
            failed.append(GiftCouponManualGrantFailedItem(member_phone=ph, reason="会员不存在"))
            continue
        created = _insert_entitlement_if_absent(
            db, campaign=camp, member_id=int(mem.id), operator=op, source=GRANT_SOURCE_MANUAL
        )
        if created is None:
            failed.append(GiftCouponManualGrantFailedItem(member_phone=ph, reason="已持有该活动礼品券"))
            continue
        items.append(entitlement_to_out(db, created))
    if items:
        db.commit()
    else:
        db.rollback()
    return GiftCouponManualGrantOut(success_count=len(items), failed=failed, items=items)


def revoke_entitlement(
    db: Session,
    *,
    entitlement_id: int,
    store_id: int,
    operator: str,
) -> GiftCouponEntitlementOut:
    row = db.get(GiftCouponEntitlement, int(entitlement_id))
    if not row or int(row.store_id) != int(store_id):
        raise HTTPException(status_code=404, detail="礼品券资格不存在")
    if str(row.status) == ENTITLEMENT_REDEEMED:
        raise HTTPException(status_code=400, detail="已核销的礼品券不能作废")
    if str(row.status) == ENTITLEMENT_REVOKED:
        return entitlement_to_out(db, row)
    row.status = ENTITLEMENT_REVOKED
    row.revoked_at = beijing_now_naive()
    row.revoked_by = (operator or "").strip() or "admin"
    db.add(row)
    db.commit()
    db.refresh(row)
    return entitlement_to_out(db, row)


def member_ids_from_delivery_sheet(sheet: DeliverySheetOut) -> dict[int, GiftCouponTodayRowOut]:
    """
    只读拆大表停靠点：会员 id → 地址/片区。

    不改 remarks_combined。后厨地址仅用于礼品券独立标签。
    """
    by_id: dict[int, GiftCouponTodayRowOut] = {}
    pickup_area = "门店自提"
    for group in sheet.groups or []:
        area = str(group.area or "")
        is_pickup = area == pickup_area
        for stop in group.stops or []:
            addr = str(stop.address_line or "")
            stop_area = str(stop.area or area)
            for mem in stop.members or []:
                mid = int(mem.member_id)
                by_id[mid] = GiftCouponTodayRowOut(
                    entitlement_id=0,
                    campaign_id=0,
                    campaign_name="",
                    sheet_label="",
                    member_id=mid,
                    name=str(mem.name or ""),
                    phone=str(mem.phone or ""),
                    area=stop_area,
                    address_line=addr,
                    store_pickup=is_pickup or bool(getattr(mem, "store_pickup", False)),
                )
    return by_id


def _load_today_sheet_members(
    db: Session,
    *,
    store_id: int,
    delivery_date: date,
    sheet_view: str,
) -> dict[int, GiftCouponTodayRowOut]:
    """只读调用配送大表；include_member_stats=false 避免额外统计。"""
    from app.services.delivery.delivery_sheet_service import build_delivery_sheet

    view = (sheet_view or DeliverySheetView.LUNCH.value).strip().lower()
    if view not in (
        DeliverySheetView.LUNCH.value,
        DeliverySheetView.DINNER.value,
        DeliverySheetView.LUNCH_DINNER.value,
    ):
        view = DeliverySheetView.LUNCH.value
    sheet = build_delivery_sheet(
        db,
        delivery_date=delivery_date,
        store_id=int(store_id),
        sheet_view=view,
        include_member_stats=False,
    )
    return member_ids_from_delivery_sheet(sheet)


def _fill_row_from_entitlement(
    base: GiftCouponTodayRowOut,
    ent: GiftCouponEntitlement,
    camp: GiftCouponCampaign,
) -> GiftCouponTodayRowOut:
    return GiftCouponTodayRowOut(
        entitlement_id=int(ent.id),
        campaign_id=int(camp.id),
        campaign_name=str(camp.name),
        sheet_label=str(camp.sheet_label),
        member_id=int(ent.member_id),
        name=base.name,
        phone=base.phone,
        area=base.area,
        address_line=base.address_line,
        store_pickup=base.store_pickup,
    )


def list_today_deliverable(
    db: Session,
    *,
    tenant_id: int,
    store_id: int,
    delivery_date: date | None,
    sheet_view: str,
    sheet_members: dict[int, GiftCouponTodayRowOut] | None = None,
) -> GiftCouponTodayListOut:
    """
    进行中活动的 granted ∩ 当日大表。

    测试可注入 sheet_members，避免拉起完整配送依赖。
    """
    d = delivery_date or today_shanghai()
    view = (sheet_view or DeliverySheetView.LUNCH.value).strip().lower()
    if sheet_members is None:
        sheet_members = _load_today_sheet_members(
            db, store_id=store_id, delivery_date=d, sheet_view=view
        )
    on_sheet = set(sheet_members.keys())
    ents = db.scalars(
        select(GiftCouponEntitlement)
        .join(GiftCouponCampaign, GiftCouponCampaign.id == GiftCouponEntitlement.campaign_id)
        .where(
            GiftCouponEntitlement.tenant_id == int(tenant_id),
            GiftCouponEntitlement.store_id == int(store_id),
            GiftCouponEntitlement.status == ENTITLEMENT_GRANTED,
            GiftCouponCampaign.status == CAMPAIGN_ACTIVE,
        )
        .order_by(GiftCouponEntitlement.id.asc())
    ).all()
    items: list[GiftCouponTodayRowOut] = []
    for ent in ents:
        if int(ent.member_id) not in on_sheet:
            continue
        camp = db.get(GiftCouponCampaign, int(ent.campaign_id))
        if camp is None:
            continue
        base = sheet_members[int(ent.member_id)]
        items.append(_fill_row_from_entitlement(base, ent, camp))
    return GiftCouponTodayListOut(delivery_date=d.isoformat(), sheet_view=view, items=items)


def list_today_redeemed(
    db: Session,
    *,
    tenant_id: int,
    store_id: int,
    delivery_date: date | None,
    sheet_view: str = "lunch",
    sheet_members: dict[int, GiftCouponTodayRowOut] | None = None,
) -> GiftCouponTodayListOut:
    """当日已核销名单，供补打标签（不改状态）。"""
    d = delivery_date or today_shanghai()
    view = (sheet_view or DeliverySheetView.LUNCH.value).strip().lower()
    if sheet_members is None:
        sheet_members = _load_today_sheet_members(
            db, store_id=store_id, delivery_date=d, sheet_view=view
        )
    ents = db.scalars(
        select(GiftCouponEntitlement).where(
            GiftCouponEntitlement.tenant_id == int(tenant_id),
            GiftCouponEntitlement.store_id == int(store_id),
            GiftCouponEntitlement.status == ENTITLEMENT_REDEEMED,
            GiftCouponEntitlement.redeemed_delivery_date == d,
        ).order_by(GiftCouponEntitlement.id.asc())
    ).all()
    items: list[GiftCouponTodayRowOut] = []
    for ent in ents:
        camp = db.get(GiftCouponCampaign, int(ent.campaign_id))
        if camp is None:
            continue
        base = sheet_members.get(int(ent.member_id))
        if base is None:
            mem = _member_for_entitlement(db, int(ent.member_id))
            addr = db.scalar(
                select(MemberAddress).where(
                    MemberAddress.member_id == int(ent.member_id),
                    MemberAddress.is_default.is_(True),
                )
            )
            from app.services.member.member_address_service import full_address_line

            addr_line = ""
            if addr is not None:
                addr_line = full_address_line(addr.map_location_text, addr.door_detail)
            base = GiftCouponTodayRowOut(
                entitlement_id=0,
                campaign_id=0,
                campaign_name="",
                sheet_label="",
                member_id=int(ent.member_id),
                name=str(mem.name or "") if mem else "",
                phone=str(mem.phone or "") if mem else "",
                area="",
                address_line=addr_line,
                store_pickup=bool(mem.store_pickup) if mem else False,
            )
        items.append(_fill_row_from_entitlement(base, ent, camp))
    return GiftCouponTodayListOut(delivery_date=d.isoformat(), sheet_view=view, items=items)


def redeem_on_sheet(
    db: Session,
    *,
    tenant_id: int,
    store_id: int,
    delivery_date: date,
    sheet_view: str,
    entitlement_ids: list[int],
    operator: str,
    sheet_members: dict[int, GiftCouponTodayRowOut] | None = None,
) -> GiftCouponRedeemOut:
    """
    仅核销：进行中活动 + granted + 勾选 + 当日大表上的人。

    不在大表的勾选计入 skipped_not_on_sheet，资格保持 granted。
    已核销的勾选幂等计入 already_redeemed_count，便于打印失败后重试。
    """
    if not entitlement_ids:
        raise HTTPException(status_code=400, detail="请勾选要配送礼品券的会员")
    view = (sheet_view or DeliverySheetView.LUNCH.value).strip().lower()
    if sheet_members is None:
        sheet_members = _load_today_sheet_members(
            db, store_id=store_id, delivery_date=delivery_date, sheet_view=view
        )
    on_sheet = set(sheet_members.keys())
    ids = []
    seen: set[int] = set()
    for i in entitlement_ids:
        n = int(i)
        if n in seen:
            continue
        seen.add(n)
        ids.append(n)

    op = (operator or "").strip() or "admin"
    now = beijing_now_naive()
    redeemed_count = 0
    already = 0
    skipped = 0
    out_items: list[GiftCouponTodayRowOut] = []

    for eid in ids:
        ent = db.get(GiftCouponEntitlement, eid)
        if not ent or int(ent.store_id) != int(store_id) or int(ent.tenant_id) != int(tenant_id):
            raise HTTPException(status_code=404, detail=f"礼品券资格不存在: {eid}")
        camp = db.get(GiftCouponCampaign, int(ent.campaign_id))
        if camp is None or str(camp.status) != CAMPAIGN_ACTIVE:
            raise HTTPException(status_code=400, detail="活动未在进行中，无法核销")
        mid = int(ent.member_id)
        if str(ent.status) == ENTITLEMENT_REDEEMED:
            already += 1
            base = sheet_members.get(mid) or GiftCouponTodayRowOut(
                entitlement_id=int(ent.id),
                campaign_id=int(camp.id),
                campaign_name=str(camp.name),
                sheet_label=str(camp.sheet_label),
                member_id=mid,
                name="",
                phone="",
            )
            out_items.append(_fill_row_from_entitlement(base, ent, camp))
            continue
        if str(ent.status) != ENTITLEMENT_GRANTED:
            raise HTTPException(status_code=400, detail="该礼品券已作废，无法核销")
        if mid not in on_sheet:
            skipped += 1
            continue
        ent.status = ENTITLEMENT_REDEEMED
        ent.redeemed_at = now
        ent.redeemed_delivery_date = delivery_date
        ent.redeemed_by = op
        ent.redeemed_sheet_view = view
        db.add(ent)
        redeemed_count += 1
        out_items.append(_fill_row_from_entitlement(sheet_members[mid], ent, camp))

    db.commit()
    return GiftCouponRedeemOut(
        redeemed_count=redeemed_count,
        already_redeemed_count=already,
        skipped_not_on_sheet=skipped,
        items=out_items,
    )
