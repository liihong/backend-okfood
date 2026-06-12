"""管理后台：抖音团购（商品映射、核销记录）。"""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.deps import SessionDep, admin_staff_subject, require_admin_tenant_store
from app.schemas.douyin import DouyinProductMappingCreateIn, DouyinProductMappingPatchIn
from app.services.douyin import (
    create_douyin_product_mapping,
    list_douyin_product_mappings_paged,
    list_douyin_redemptions_paged,
    patch_douyin_product_mapping,
)
from app.utils.response import dump_model, page_response, success

router = APIRouter(prefix="/admin/marketing/douyin", tags=["管理端-抖音团购"])


@router.get("/product-mappings")
def admin_list_douyin_product_mappings(
    db: SessionDep,
    admin_username: Annotated[str, Depends(admin_staff_subject)],
    store_id: Annotated[int, Query(description="门店 id，默认 1")] = 1,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    keyword: Annotated[str | None, Query(max_length=64)] = None,
    active_only: Annotated[bool, Query()] = False,
):
    """抖音商品与本地权益映射列表。"""
    _ = admin_username
    tid, sid = require_admin_tenant_store(db, admin_username=admin_username, store_id=store_id)
    items, total = list_douyin_product_mappings_paged(
        db,
        store_id=sid,
        page=page,
        page_size=page_size,
        keyword=keyword,
        active_only=active_only,
    )
    _ = tid
    return page_response(
        items=[dump_model(x) for x in items],
        total=total,
        page=page,
        page_size=page_size,
        msg="获取成功",
    )


@router.post("/product-mappings")
def admin_create_douyin_product_mapping(
    db: SessionDep,
    admin_username: Annotated[str, Depends(admin_staff_subject)],
    body: DouyinProductMappingCreateIn,
    store_id: Annotated[int, Query(description="门店 id，默认 1")] = 1,
):
    """创建抖音商品映射。"""
    tid, sid = require_admin_tenant_store(db, admin_username=admin_username, store_id=store_id)
    out = create_douyin_product_mapping(
        db, tenant_id=tid, store_id=sid, body=body, operator=admin_username
    )
    return success(data=dump_model(out), msg="映射已创建")


@router.patch("/product-mappings/{mapping_id}")
def admin_patch_douyin_product_mapping(
    mapping_id: int,
    db: SessionDep,
    admin_username: Annotated[str, Depends(admin_staff_subject)],
    body: DouyinProductMappingPatchIn,
    store_id: Annotated[int, Query(description="门店 id，默认 1")] = 1,
):
    """编辑抖音商品映射。"""
    _ = admin_username
    _, sid = require_admin_tenant_store(db, admin_username=admin_username, store_id=store_id)
    out = patch_douyin_product_mapping(db, mapping_id=int(mapping_id), store_id=sid, body=body)
    return success(data=dump_model(out), msg="映射已更新")


@router.get("/redemptions")
def admin_list_douyin_redemptions(
    db: SessionDep,
    admin_username: Annotated[str, Depends(admin_staff_subject)],
    store_id: Annotated[int, Query(description="门店 id，默认 1")] = 1,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    member_phone: Annotated[str | None, Query(max_length=20)] = None,
    status: Annotated[str | None, Query(description="success/failed/verified/grant_failed/cancelled")] = None,
    date_from: Annotated[date | None, Query()] = None,
    date_to: Annotated[date | None, Query()] = None,
):
    """抖音验券核销记录。"""
    _ = admin_username
    _, sid = require_admin_tenant_store(db, admin_username=admin_username, store_id=store_id)
    items, total = list_douyin_redemptions_paged(
        db,
        store_id=sid,
        page=page,
        page_size=page_size,
        member_phone=member_phone,
        status=status,
        date_from=date_from,
        date_to=date_to,
    )
    return page_response(
        items=[dump_model(x) for x in items],
        total=total,
        page=page,
        page_size=page_size,
        msg="获取成功",
    )
