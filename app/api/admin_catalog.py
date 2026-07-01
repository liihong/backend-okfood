"""管理后台：会员卡模版 + 门店零售 SKU（仅配置层）。"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.deps import SessionDep, admin_staff_subject, require_admin_tenant_store
from app.schemas.catalog_admin import (
    MembershipCardTemplateCreateIn,
    MembershipCardTemplatePatchIn,
    StoreRetailCategoryCreateIn,
    StoreRetailCategoryPatchIn,
    StoreRetailProductCreateIn,
    StoreRetailProductPatchIn,
)
from app.services.admin.catalog_admin_service import (
    create_membership_template,
    create_retail_category,
    create_retail_product,
    delete_membership_template,
    delete_retail_category,
    delete_retail_product,
    list_membership_templates,
    list_retail_categories,
    list_retail_products,
    membership_template_dump,
    patch_membership_template,
    patch_retail_category,
    patch_retail_product,
    retail_product_dump,
)

router = APIRouter(prefix="/admin/catalog", tags=["管理端-商品与会员卡模版"])


@router.get("/membership-templates")
def catalog_list_membership_templates(
    db: SessionDep,
    admin_username: Annotated[str, Depends(admin_staff_subject)],
    store_id: Annotated[int, Query(description="门店 id，默认 1")] = 1,
    active_only: Annotated[bool, Query()] = False,
):
    tid, sid = require_admin_tenant_store(db, admin_username=admin_username, store_id=store_id)
    rows = list_membership_templates(db, tenant_id=tid, store_id=sid, active_only=active_only)
    return {"code": 200, "data": [membership_template_dump(r) for r in rows], "msg": "获取成功"}


@router.post("/membership-templates")
def catalog_create_membership_template(
    db: SessionDep,
    admin_username: Annotated[str, Depends(admin_staff_subject)],
    body: MembershipCardTemplateCreateIn,
    store_id: Annotated[int, Query(description="门店 id，默认 1")] = 1,
):
    tid, sid = require_admin_tenant_store(db, admin_username=admin_username, store_id=store_id)
    row = create_membership_template(db, tenant_id=tid, store_id=sid, body=body)
    return {"code": 200, "data": membership_template_dump(row), "msg": "创建成功"}


@router.patch("/membership-templates/{template_id}")
def catalog_patch_membership_template(
    template_id: int,
    db: SessionDep,
    admin_username: Annotated[str, Depends(admin_staff_subject)],
    body: MembershipCardTemplatePatchIn,
    store_id: Annotated[int, Query(description="门店 id，默认 1")] = 1,
):
    tid, sid = require_admin_tenant_store(db, admin_username=admin_username, store_id=store_id)
    row = patch_membership_template(
        db, template_id=int(template_id), tenant_id=tid, store_id=sid, body=body
    )
    return {"code": 200, "data": membership_template_dump(row), "msg": "已保存"}


@router.delete("/membership-templates/{template_id}")
def catalog_delete_membership_template(
    template_id: int,
    db: SessionDep,
    admin_username: Annotated[str, Depends(admin_staff_subject)],
    store_id: Annotated[int, Query(description="门店 id，默认 1")] = 1,
):
    tid, sid = require_admin_tenant_store(db, admin_username=admin_username, store_id=store_id)
    delete_membership_template(db, template_id=int(template_id), tenant_id=tid, store_id=sid)
    return {"code": 200, "data": None, "msg": "已删除"}


@router.get("/retail-categories")
def catalog_list_retail_categories(
    db: SessionDep,
    admin_username: Annotated[str, Depends(admin_staff_subject)],
    store_id: Annotated[int, Query(description="门店 id，默认 1")] = 1,
    active_only: Annotated[bool, Query()] = False,
):
    _, sid = require_admin_tenant_store(db, admin_username=admin_username, store_id=store_id)
    rows = list_retail_categories(db, store_id=sid, active_only=active_only)
    data = [
        {
            "id": int(r.id),
            "store_id": int(r.store_id),
            "name": r.name,
            "sort_order": int(r.sort_order),
            "is_active": bool(r.is_active),
        }
        for r in rows
    ]
    return {"code": 200, "data": data, "msg": "获取成功"}


@router.post("/retail-categories")
def catalog_create_retail_category(
    db: SessionDep,
    admin_username: Annotated[str, Depends(admin_staff_subject)],
    body: StoreRetailCategoryCreateIn,
    store_id: Annotated[int, Query(description="门店 id，默认 1")] = 1,
):
    _, sid = require_admin_tenant_store(db, admin_username=admin_username, store_id=store_id)
    row = create_retail_category(db, store_id=sid, body=body)
    return {
        "code": 200,
        "data": {
            "id": int(row.id),
            "store_id": int(row.store_id),
            "name": row.name,
            "sort_order": int(row.sort_order),
            "is_active": bool(row.is_active),
        },
        "msg": "创建成功",
    }


@router.patch("/retail-categories/{category_id}")
def catalog_patch_retail_category(
    category_id: int,
    db: SessionDep,
    admin_username: Annotated[str, Depends(admin_staff_subject)],
    body: StoreRetailCategoryPatchIn,
    store_id: Annotated[int, Query(description="门店 id，默认 1")] = 1,
):
    _, sid = require_admin_tenant_store(db, admin_username=admin_username, store_id=store_id)
    row = patch_retail_category(db, category_id=int(category_id), store_id=sid, body=body)
    return {
        "code": 200,
        "data": {
            "id": int(row.id),
            "store_id": int(row.store_id),
            "name": row.name,
            "sort_order": int(row.sort_order),
            "is_active": bool(row.is_active),
        },
        "msg": "已保存",
    }


@router.delete("/retail-categories/{category_id}")
def catalog_delete_retail_category(
    category_id: int,
    db: SessionDep,
    admin_username: Annotated[str, Depends(admin_staff_subject)],
    store_id: Annotated[int, Query(description="门店 id，默认 1")] = 1,
):
    _, sid = require_admin_tenant_store(db, admin_username=admin_username, store_id=store_id)
    delete_retail_category(db, category_id=int(category_id), store_id=sid)
    return {"code": 200, "data": None, "msg": "已删除"}


@router.get("/retail-products")
def catalog_list_retail_products(
    db: SessionDep,
    admin_username: Annotated[str, Depends(admin_staff_subject)],
    store_id: Annotated[int, Query(description="门店 id，默认 1")] = 1,
    category_id: Annotated[int | None, Query(description="可选：按分类筛选")] = None,
    shelf_only: Annotated[bool, Query()] = False,
):
    _, sid = require_admin_tenant_store(db, admin_username=admin_username, store_id=store_id)
    rows = list_retail_products(db, store_id=sid, category_id=category_id, shelf_only=shelf_only)
    return {"code": 200, "data": [retail_product_dump(r) for r in rows], "msg": "获取成功"}


@router.post("/retail-products")
def catalog_create_retail_product(
    db: SessionDep,
    admin_username: Annotated[str, Depends(admin_staff_subject)],
    body: StoreRetailProductCreateIn,
    store_id: Annotated[int, Query(description="门店 id，默认 1")] = 1,
):
    _, sid = require_admin_tenant_store(db, admin_username=admin_username, store_id=store_id)
    row = create_retail_product(db, store_id=sid, body=body)
    return {"code": 200, "data": retail_product_dump(row), "msg": "创建成功"}


@router.patch("/retail-products/{product_id}")
def catalog_patch_retail_product(
    product_id: int,
    db: SessionDep,
    admin_username: Annotated[str, Depends(admin_staff_subject)],
    body: StoreRetailProductPatchIn,
    store_id: Annotated[int, Query(description="门店 id，默认 1")] = 1,
):
    _, sid = require_admin_tenant_store(db, admin_username=admin_username, store_id=store_id)
    row = patch_retail_product(db, product_id=int(product_id), store_id=sid, body=body)
    return {"code": 200, "data": retail_product_dump(row), "msg": "已保存"}


@router.delete("/retail-products/{product_id}")
def catalog_delete_retail_product(
    product_id: int,
    db: SessionDep,
    admin_username: Annotated[str, Depends(admin_staff_subject)],
    store_id: Annotated[int, Query(description="门店 id，默认 1")] = 1,
):
    _, sid = require_admin_tenant_store(db, admin_username=admin_username, store_id=store_id)
    delete_retail_product(db, product_id=int(product_id), store_id=sid)
    return {"code": 200, "data": None, "msg": "已删除"}

