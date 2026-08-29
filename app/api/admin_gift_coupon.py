"""管理端：礼品券活动、圈人发放、当日大表求交核销。独立路由，不改配送接口。"""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.deps import SessionDep, admin_staff_subject, require_admin_tenant_store
from app.schemas.gift_coupon import (
    GiftCouponAudiencePreviewIn,
    GiftCouponCampaignCreateIn,
    GiftCouponCampaignPatchIn,
    GiftCouponManualGrantIn,
    GiftCouponRedeemIn,
)
from app.services.gift_coupon import service as svc
from app.utils.response import dump_model, page_response, success

router = APIRouter(prefix="/admin/gift-coupons", tags=["管理端-礼品券"])


@router.get("/campaigns")
def list_gift_coupon_campaigns(
    db: SessionDep,
    admin_username: Annotated[str, Depends(admin_staff_subject)],
    store_id: Annotated[int, Query(description="门店 id")] = 1,
    status: Annotated[str | None, Query(description="draft/active/closed")] = None,
):
    tid, sid = require_admin_tenant_store(db, admin_username=admin_username, store_id=store_id)
    items = svc.list_campaigns(db, tenant_id=tid, store_id=sid, status=status)
    return success(data=[dump_model(x) for x in items], msg="获取成功")


@router.post("/campaigns")
def create_gift_coupon_campaign(
    db: SessionDep,
    body: GiftCouponCampaignCreateIn,
    admin_username: Annotated[str, Depends(admin_staff_subject)],
    store_id: Annotated[int, Query(description="门店 id")] = 1,
):
    tid, sid = require_admin_tenant_store(db, admin_username=admin_username, store_id=store_id)
    data = svc.create_campaign(
        db, tenant_id=tid, store_id=sid, body=body, operator=admin_username
    )
    return success(data=dump_model(data), msg="已创建")


@router.patch("/campaigns/{campaign_id}")
def patch_gift_coupon_campaign(
    db: SessionDep,
    campaign_id: int,
    body: GiftCouponCampaignPatchIn,
    admin_username: Annotated[str, Depends(admin_staff_subject)],
    store_id: Annotated[int, Query(description="门店 id")] = 1,
):
    _, sid = require_admin_tenant_store(db, admin_username=admin_username, store_id=store_id)
    data = svc.patch_campaign(db, campaign_id=campaign_id, store_id=sid, body=body)
    return success(data=dump_model(data), msg="已保存")


@router.post("/campaigns/preview-audience")
def preview_gift_coupon_audience_by_rule(
    db: SessionDep,
    body: GiftCouponAudiencePreviewIn,
    admin_username: Annotated[str, Depends(admin_staff_subject)],
    store_id: Annotated[int, Query(description="门店 id")] = 1,
):
    """未保存活动时按表单规则预览圈人。"""
    tid, sid = require_admin_tenant_store(db, admin_username=admin_username, store_id=store_id)
    data = svc.preview_audience_by_rule(
        db,
        tenant_id=tid,
        store_id=sid,
        plan_kinds=list(body.plan_kinds),
        credited_from=body.credited_from,
        credited_to=body.credited_to,
        exclude_membership_refunded=bool(body.exclude_membership_refunded),
    )
    return success(data=dump_model(data), msg="预览成功")


@router.post("/campaigns/{campaign_id}/preview")
def preview_gift_coupon_campaign_audience(
    db: SessionDep,
    campaign_id: int,
    admin_username: Annotated[str, Depends(admin_staff_subject)],
    store_id: Annotated[int, Query(description="门店 id")] = 1,
):
    tid, sid = require_admin_tenant_store(db, admin_username=admin_username, store_id=store_id)
    data = svc.preview_campaign_audience(
        db, tenant_id=tid, store_id=sid, campaign_id=campaign_id
    )
    return success(data=dump_model(data), msg="预览成功")


@router.post("/campaigns/{campaign_id}/grant")
def grant_gift_coupon_campaign(
    db: SessionDep,
    campaign_id: int,
    admin_username: Annotated[str, Depends(admin_staff_subject)],
    store_id: Annotated[int, Query(description="门店 id")] = 1,
):
    tid, sid = require_admin_tenant_store(db, admin_username=admin_username, store_id=store_id)
    data = svc.grant_campaign(
        db, tenant_id=tid, store_id=sid, campaign_id=campaign_id, operator=admin_username
    )
    return success(data=dump_model(data), msg="发放成功")


@router.post("/campaigns/{campaign_id}/close")
def close_gift_coupon_campaign(
    db: SessionDep,
    campaign_id: int,
    admin_username: Annotated[str, Depends(admin_staff_subject)],
    store_id: Annotated[int, Query(description="门店 id")] = 1,
):
    _, sid = require_admin_tenant_store(db, admin_username=admin_username, store_id=store_id)
    data = svc.close_campaign(db, campaign_id=campaign_id, store_id=sid)
    return success(data=dump_model(data), msg="已结束")


@router.get("/entitlements")
def list_gift_coupon_entitlements(
    db: SessionDep,
    admin_username: Annotated[str, Depends(admin_staff_subject)],
    store_id: Annotated[int, Query(description="门店 id")] = 1,
    campaign_id: Annotated[int | None, Query()] = None,
    status: Annotated[str | None, Query(description="granted/redeemed/revoked")] = None,
    member_phone: Annotated[str | None, Query(max_length=20)] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 20,
):
    tid, sid = require_admin_tenant_store(db, admin_username=admin_username, store_id=store_id)
    items, total = svc.list_entitlements(
        db,
        tenant_id=tid,
        store_id=sid,
        campaign_id=campaign_id,
        status=status,
        member_phone=member_phone,
        page=page,
        page_size=page_size,
    )
    return page_response(
        items=[dump_model(x) for x in items],
        total=total,
        page=page,
        page_size=page_size,
        msg="获取成功",
    )


@router.post("/entitlements/manual-grant")
def manual_grant_gift_coupon(
    db: SessionDep,
    body: GiftCouponManualGrantIn,
    admin_username: Annotated[str, Depends(admin_staff_subject)],
    store_id: Annotated[int, Query(description="门店 id")] = 1,
):
    tid, sid = require_admin_tenant_store(db, admin_username=admin_username, store_id=store_id)
    data = svc.manual_grant(
        db,
        tenant_id=tid,
        store_id=sid,
        campaign_id=int(body.campaign_id),
        phones=list(body.member_phones),
        operator=admin_username,
    )
    return success(data=dump_model(data), msg="补发完成")


@router.post("/entitlements/{entitlement_id}/revoke")
def revoke_gift_coupon_entitlement(
    db: SessionDep,
    entitlement_id: int,
    admin_username: Annotated[str, Depends(admin_staff_subject)],
    store_id: Annotated[int, Query(description="门店 id")] = 1,
):
    _, sid = require_admin_tenant_store(db, admin_username=admin_username, store_id=store_id)
    data = svc.revoke_entitlement(
        db, entitlement_id=entitlement_id, store_id=sid, operator=admin_username
    )
    return success(data=dump_model(data), msg="已作废")


@router.get("/today-deliverable")
def list_today_deliverable_gift_coupons(
    db: SessionDep,
    admin_username: Annotated[str, Depends(admin_staff_subject)],
    store_id: Annotated[int, Query(description="门店 id")] = 1,
    delivery_date: Annotated[date | None, Query(description="业务日")] = None,
    sheet_view: Annotated[str, Query(description="lunch/dinner/lunch_dinner")] = "lunch",
):
    """当日大表 ∩ 未核销资格。不改配送大表本身。"""
    tid, sid = require_admin_tenant_store(db, admin_username=admin_username, store_id=store_id)
    data = svc.list_today_deliverable(
        db,
        tenant_id=tid,
        store_id=sid,
        delivery_date=delivery_date,
        sheet_view=sheet_view,
    )
    return success(data=dump_model(data), msg="获取成功")


@router.get("/today-redeemed")
def list_today_redeemed_gift_coupons(
    db: SessionDep,
    admin_username: Annotated[str, Depends(admin_staff_subject)],
    store_id: Annotated[int, Query(description="门店 id")] = 1,
    delivery_date: Annotated[date | None, Query(description="业务日")] = None,
    sheet_view: Annotated[str, Query()] = "lunch",
):
    """当日已核销，供补打标签。"""
    tid, sid = require_admin_tenant_store(db, admin_username=admin_username, store_id=store_id)
    data = svc.list_today_redeemed(
        db,
        tenant_id=tid,
        store_id=sid,
        delivery_date=delivery_date,
        sheet_view=sheet_view,
    )
    return success(data=dump_model(data), msg="获取成功")


@router.post("/redeem")
def redeem_gift_coupons_on_sheet(
    db: SessionDep,
    body: GiftCouponRedeemIn,
    admin_username: Annotated[str, Depends(admin_staff_subject)],
    store_id: Annotated[int, Query(description="门店 id")] = 1,
):
    """勾选且在当日大表上的人核销；未上表的人资格保留。"""
    tid, sid = require_admin_tenant_store(db, admin_username=admin_username, store_id=store_id)
    data = svc.redeem_on_sheet(
        db,
        tenant_id=tid,
        store_id=sid,
        delivery_date=body.delivery_date,
        sheet_view=body.sheet_view,
        entitlement_ids=list(body.entitlement_ids),
        operator=admin_username,
    )
    return success(data=dump_model(data), msg="核销成功")
