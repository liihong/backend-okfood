"""管理后台：小程序营销（优惠券等）。"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.deps import SessionDep, admin_staff_subject, require_admin_tenant_store
from app.schemas.marketing.coupon import (
    CouponTemplateActiveIn,
    CouponTemplateCreateIn,
    CouponTemplatePatchIn,
    MemberCouponBatchGrantIn,
    MemberCouponGrantIn,
)
from app.services.marketing.coupon_template_service import (
    create_coupon_template,
    list_coupon_templates_paged,
    patch_coupon_template,
    set_coupon_template_active,
)
from app.services.marketing.member_coupon_service import (
    grant_member_coupon,
    grant_member_coupons_batch,
    list_member_coupons_paged,
    revoke_member_coupon,
)
from app.schemas.marketing.home_banner import (
    HomeBannerActiveIn,
    HomeBannerCreateIn,
    HomeBannerPatchIn,
)
from app.services.home_banner_service import (
    create_home_banner,
    delete_home_banner,
    list_home_banners_admin,
    patch_home_banner,
    set_home_banner_active,
)
from app.schemas.marketing.home_entry_poster import HomeEntryPosterUpsertIn
from app.services.home_entry_poster_service import get_entry_poster_admin, upsert_entry_poster
from app.utils.response import dump_model, page_response, success

router = APIRouter(prefix="/admin/marketing", tags=["管理端-小程序营销"])


@router.get("/coupon-templates")
def marketing_list_coupon_templates(
    db: SessionDep,
    admin_username: Annotated[str, Depends(admin_staff_subject)],
    store_id: Annotated[int, Query(description="门店 id，默认 1")] = 1,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    biz_type: Annotated[str | None, Query(description="member_card/single_meal/store_retail/all")] = None,
    active_only: Annotated[bool, Query()] = False,
    keyword: Annotated[str | None, Query(max_length=64)] = None,
):
    """券种模板分页列表。"""
    tid, sid = require_admin_tenant_store(db, admin_username=admin_username, store_id=store_id)
    items, total = list_coupon_templates_paged(
        db,
        tenant_id=tid,
        store_id=sid,
        page=page,
        page_size=page_size,
        biz_type=biz_type,
        active_only=active_only,
        keyword=keyword,
    )
    return page_response(
        items=[dump_model(x) for x in items],
        total=total,
        page=page,
        page_size=page_size,
        msg="获取成功",
    )


@router.post("/coupon-templates")
def marketing_create_coupon_template(
    db: SessionDep,
    admin_username: Annotated[str, Depends(admin_staff_subject)],
    body: CouponTemplateCreateIn,
    store_id: Annotated[int, Query(description="门店 id，默认 1")] = 1,
):
    """创建优惠券券种。"""
    tid, sid = require_admin_tenant_store(db, admin_username=admin_username, store_id=store_id)
    out = create_coupon_template(db, tenant_id=tid, store_id=sid, body=body, operator=admin_username)
    return success(data=dump_model(out), msg="券种已创建")


@router.patch("/coupon-templates/{template_id}")
def marketing_patch_coupon_template(
    template_id: int,
    db: SessionDep,
    admin_username: Annotated[str, Depends(admin_staff_subject)],
    body: CouponTemplatePatchIn,
    store_id: Annotated[int, Query(description="门店 id，默认 1")] = 1,
):
    """编辑券种（已发放实例不受影响）。"""
    _ = admin_username
    _, sid = require_admin_tenant_store(db, admin_username=admin_username, store_id=store_id)
    out = patch_coupon_template(db, template_id=int(template_id), store_id=sid, body=body)
    return success(data=dump_model(out), msg="券种已更新")


@router.patch("/coupon-templates/{template_id}/active")
def marketing_set_coupon_template_active(
    template_id: int,
    db: SessionDep,
    admin_username: Annotated[str, Depends(admin_staff_subject)],
    body: CouponTemplateActiveIn,
    store_id: Annotated[int, Query(description="门店 id，默认 1")] = 1,
):
    """券种上下架。"""
    _ = admin_username
    _, sid = require_admin_tenant_store(db, admin_username=admin_username, store_id=store_id)
    out = set_coupon_template_active(
        db, template_id=int(template_id), store_id=sid, is_active=bool(body.is_active)
    )
    return success(data=dump_model(out), msg="状态已更新")


@router.get("/member-coupons")
def marketing_list_member_coupons(
    db: SessionDep,
    admin_username: Annotated[str, Depends(admin_staff_subject)],
    store_id: Annotated[int, Query(description="门店 id，默认 1")] = 1,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    member_id: Annotated[int | None, Query()] = None,
    member_phone: Annotated[str | None, Query(description="会员手机号，模糊匹配")] = None,
    template_id: Annotated[int | None, Query()] = None,
    status: Annotated[str | None, Query()] = None,
    biz_type: Annotated[str | None, Query()] = None,
):
    """用户持券发放记录。"""
    _ = admin_username
    _, sid = require_admin_tenant_store(db, admin_username=admin_username, store_id=store_id)
    items, total = list_member_coupons_paged(
        db,
        store_id=sid,
        page=page,
        page_size=page_size,
        member_id=member_id,
        member_phone=member_phone,
        template_id=template_id,
        status=status,
        biz_type=biz_type,
    )
    return page_response(
        items=[dump_model(x) for x in items],
        total=total,
        page=page,
        page_size=page_size,
        msg="获取成功",
    )


@router.post("/member-coupons/grant")
def marketing_grant_member_coupon(
    db: SessionDep,
    admin_username: Annotated[str, Depends(admin_staff_subject)],
    body: MemberCouponGrantIn,
    store_id: Annotated[int, Query(description="门店 id，默认 1")] = 1,
):
    """向指定会员（手机号）发放优惠券。"""
    tid, sid = require_admin_tenant_store(db, admin_username=admin_username, store_id=store_id)
    out = grant_member_coupon(db, tenant_id=tid, store_id=sid, body=body, operator=admin_username)
    return success(data=dump_model(out), msg="优惠券已发放")


@router.post("/member-coupons/grant-batch")
def marketing_grant_member_coupons_batch(
    db: SessionDep,
    admin_username: Annotated[str, Depends(admin_staff_subject)],
    body: MemberCouponBatchGrantIn,
    store_id: Annotated[int, Query(description="门店 id，默认 1")] = 1,
):
    """批量向会员发放优惠券（按手机号）。"""
    tid, sid = require_admin_tenant_store(db, admin_username=admin_username, store_id=store_id)
    out = grant_member_coupons_batch(db, tenant_id=tid, store_id=sid, body=body, operator=admin_username)
    msg = f"成功发放 {out.success_count} 张"
    if out.failed:
        msg += f"，失败 {len(out.failed)} 个"
    return success(data=dump_model(out), msg=msg)


@router.post("/member-coupons/{coupon_id}/revoke")
def marketing_revoke_member_coupon(
    coupon_id: int,
    db: SessionDep,
    admin_username: Annotated[str, Depends(admin_staff_subject)],
    store_id: Annotated[int, Query(description="门店 id，默认 1")] = 1,
):
    """作废未使用的用户券。"""
    _ = admin_username
    _, sid = require_admin_tenant_store(db, admin_username=admin_username, store_id=store_id)
    out = revoke_member_coupon(db, coupon_id=int(coupon_id), store_id=sid)
    return success(data=dump_model(out), msg="优惠券已作废")


@router.get("/home-banners")
def marketing_list_home_banners(
    db: SessionDep,
    admin_username: Annotated[str, Depends(admin_staff_subject)],
    store_id: Annotated[int, Query(description="门店 id，默认 1")] = 1,
):
    """首页 Banner 列表（含未启用）。"""
    _ = admin_username
    _, sid = require_admin_tenant_store(db, admin_username=admin_username, store_id=store_id)
    items = list_home_banners_admin(db, store_id=sid)
    return success(data=[dump_model(x) for x in items], msg="获取成功")


@router.post("/home-banners")
def marketing_create_home_banner(
    db: SessionDep,
    admin_username: Annotated[str, Depends(admin_staff_subject)],
    body: HomeBannerCreateIn,
    store_id: Annotated[int, Query(description="门店 id，默认 1")] = 1,
):
    """创建首页 Banner。"""
    _ = admin_username
    _, sid = require_admin_tenant_store(db, admin_username=admin_username, store_id=store_id)
    out = create_home_banner(db, store_id=sid, body=body)
    return success(data=dump_model(out), msg="Banner 已创建")


@router.patch("/home-banners/{banner_id}")
def marketing_patch_home_banner(
    banner_id: int,
    db: SessionDep,
    admin_username: Annotated[str, Depends(admin_staff_subject)],
    body: HomeBannerPatchIn,
    store_id: Annotated[int, Query(description="门店 id，默认 1")] = 1,
):
    """编辑首页 Banner。"""
    _ = admin_username
    _, sid = require_admin_tenant_store(db, admin_username=admin_username, store_id=store_id)
    out = patch_home_banner(db, banner_id=int(banner_id), store_id=sid, body=body)
    return success(data=dump_model(out), msg="Banner 已更新")


@router.delete("/home-banners/{banner_id}")
def marketing_delete_home_banner(
    banner_id: int,
    db: SessionDep,
    admin_username: Annotated[str, Depends(admin_staff_subject)],
    store_id: Annotated[int, Query(description="门店 id，默认 1")] = 1,
):
    """删除首页 Banner。"""
    _ = admin_username
    _, sid = require_admin_tenant_store(db, admin_username=admin_username, store_id=store_id)
    delete_home_banner(db, banner_id=int(banner_id), store_id=sid)
    return success(msg="Banner 已删除")


@router.patch("/home-banners/{banner_id}/active")
def marketing_set_home_banner_active(
    banner_id: int,
    db: SessionDep,
    admin_username: Annotated[str, Depends(admin_staff_subject)],
    body: HomeBannerActiveIn,
    store_id: Annotated[int, Query(description="门店 id，默认 1")] = 1,
):
    """首页 Banner 上下架。"""
    _ = admin_username
    _, sid = require_admin_tenant_store(db, admin_username=admin_username, store_id=store_id)
    out = set_home_banner_active(db, banner_id=int(banner_id), store_id=sid, is_active=bool(body.is_active))
    return success(data=dump_model(out), msg="状态已更新")


@router.get("/entry-poster")
def marketing_get_entry_poster(
    db: SessionDep,
    admin_username: Annotated[str, Depends(admin_staff_subject)],
    store_id: Annotated[int, Query(description="门店 id，默认 1")] = 1,
):
    """进入弹窗海报配置（每门店一条）。"""
    _ = admin_username
    _, sid = require_admin_tenant_store(db, admin_username=admin_username, store_id=store_id)
    out = get_entry_poster_admin(db, store_id=sid)
    return success(data=dump_model(out) if out else None, msg="获取成功")


@router.put("/entry-poster")
def marketing_upsert_entry_poster(
    db: SessionDep,
    admin_username: Annotated[str, Depends(admin_staff_subject)],
    body: HomeEntryPosterUpsertIn,
    store_id: Annotated[int, Query(description="门店 id，默认 1")] = 1,
):
    """保存进入弹窗海报配置。"""
    _ = admin_username
    _, sid = require_admin_tenant_store(db, admin_username=admin_username, store_id=store_id)
    out = upsert_entry_poster(db, store_id=sid, body=body)
    return success(data=dump_model(out), msg="保存成功")
