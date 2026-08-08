"""管理后台：会员卡模版 + 门店普通商品（分类 / SPU / SKU）。"""



from typing import Annotated



from fastapi import APIRouter, Depends, Query



from app.core.deps import SessionDep, admin_staff_subject, require_admin_tenant_store

from app.schemas.catalog_admin import (

    MembershipCardTemplateCreateIn,

    MembershipCardTemplatePatchIn,

    StoreRetailCategoryCreateIn,

    StoreRetailCategoryPatchIn,

    StoreRetailSkuCreateIn,

    StoreRetailSkuPatchIn,

    StoreRetailSpuCreateIn,

    StoreRetailSpuPatchIn,

    StoreRetailSpuBundleSaveIn,

)

from app.services.admin.catalog_admin_service import (

    create_membership_template,

    delete_membership_template,

    list_membership_templates,

    membership_template_dump,

    patch_membership_template,

)

from app.services.admin.retail_category_admin_service import (

    create_retail_category,

    delete_retail_category,

    list_retail_categories,

    patch_retail_category,

)

from app.services.admin.retail_sku_admin_service import (

    create_retail_sku,

    delete_retail_sku,

    list_retail_skus,

    patch_retail_sku,

)

from app.services.admin.retail_spu_admin_service import (

    create_retail_spu,

    delete_retail_spu,

    get_retail_spu_detail,

    list_retail_spus,

    patch_retail_spu,

    save_retail_spu_bundle,

)

from app.utils.response import success



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

    return success(data=[membership_template_dump(r) for r in rows], msg="获取成功")





@router.post("/membership-templates")

def catalog_create_membership_template(

    db: SessionDep,

    admin_username: Annotated[str, Depends(admin_staff_subject)],

    body: MembershipCardTemplateCreateIn,

    store_id: Annotated[int, Query(description="门店 id，默认 1")] = 1,

):

    tid, sid = require_admin_tenant_store(db, admin_username=admin_username, store_id=store_id)

    row = create_membership_template(db, tenant_id=tid, store_id=sid, body=body)

    return success(data=membership_template_dump(row), msg="创建成功")





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

    return success(data=membership_template_dump(row), msg="已保存")





@router.delete("/membership-templates/{template_id}")

def catalog_delete_membership_template(

    template_id: int,

    db: SessionDep,

    admin_username: Annotated[str, Depends(admin_staff_subject)],

    store_id: Annotated[int, Query(description="门店 id，默认 1")] = 1,

):

    tid, sid = require_admin_tenant_store(db, admin_username=admin_username, store_id=store_id)

    delete_membership_template(db, template_id=int(template_id), tenant_id=tid, store_id=sid)

    return success(data=None, msg="已删除")





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

    return success(data=data, msg="获取成功")





@router.post("/retail-categories")

def catalog_create_retail_category(

    db: SessionDep,

    admin_username: Annotated[str, Depends(admin_staff_subject)],

    body: StoreRetailCategoryCreateIn,

    store_id: Annotated[int, Query(description="门店 id，默认 1")] = 1,

):

    _, sid = require_admin_tenant_store(db, admin_username=admin_username, store_id=store_id)

    row = create_retail_category(db, store_id=sid, body=body)

    return success(

        data={

            "id": int(row.id),

            "store_id": int(row.store_id),

            "name": row.name,

            "sort_order": int(row.sort_order),

            "is_active": bool(row.is_active),

        },

        msg="创建成功",

    )





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

    return success(

        data={

            "id": int(row.id),

            "store_id": int(row.store_id),

            "name": row.name,

            "sort_order": int(row.sort_order),

            "is_active": bool(row.is_active),

        },

        msg="已保存",

    )





@router.delete("/retail-categories/{category_id}")

def catalog_delete_retail_category(

    category_id: int,

    db: SessionDep,

    admin_username: Annotated[str, Depends(admin_staff_subject)],

    store_id: Annotated[int, Query(description="门店 id，默认 1")] = 1,

):

    _, sid = require_admin_tenant_store(db, admin_username=admin_username, store_id=store_id)

    delete_retail_category(db, category_id=int(category_id), store_id=sid)

    return success(data=None, msg="已删除")





# —— 商品 SPU ——





@router.get("/retail-spus")

def catalog_list_retail_spus(

    db: SessionDep,

    admin_username: Annotated[str, Depends(admin_staff_subject)],

    store_id: Annotated[int, Query(description="门店 id，默认 1")] = 1,

    category_id: Annotated[int | None, Query(description="可选：按分类筛选")] = None,

    shelf_only: Annotated[bool, Query()] = False,

):

    _, sid = require_admin_tenant_store(db, admin_username=admin_username, store_id=store_id)

    data = list_retail_spus(db, store_id=sid, category_id=category_id, shelf_only=shelf_only)

    return success(data=data, msg="获取成功")





@router.get("/retail-spus/{spu_id}")

def catalog_get_retail_spu(

    spu_id: int,

    db: SessionDep,

    admin_username: Annotated[str, Depends(admin_staff_subject)],

    store_id: Annotated[int, Query(description="门店 id，默认 1")] = 1,

):

    _, sid = require_admin_tenant_store(db, admin_username=admin_username, store_id=store_id)

    data = get_retail_spu_detail(db, spu_id=int(spu_id), store_id=sid)

    return success(data=data, msg="获取成功")





@router.post("/retail-spus")

def catalog_create_retail_spu(

    db: SessionDep,

    admin_username: Annotated[str, Depends(admin_staff_subject)],

    body: StoreRetailSpuCreateIn,

    store_id: Annotated[int, Query(description="门店 id，默认 1")] = 1,

):

    _, sid = require_admin_tenant_store(db, admin_username=admin_username, store_id=store_id)

    data = create_retail_spu(db, store_id=sid, body=body)

    return success(data=data, msg="创建成功")





@router.post("/retail-spus/bundle")

def catalog_create_retail_spu_bundle(

    db: SessionDep,

    admin_username: Annotated[str, Depends(admin_staff_subject)],

    body: StoreRetailSpuBundleSaveIn,

    store_id: Annotated[int, Query(description="门店 id，默认 1")] = 1,

):

    """原子创建：SPU + 至少一个 SKU。"""

    _, sid = require_admin_tenant_store(db, admin_username=admin_username, store_id=store_id)

    data = save_retail_spu_bundle(db, store_id=sid, body=body, spu_id=None)

    return success(data=data, msg="创建成功")





@router.put("/retail-spus/{spu_id}/bundle")

def catalog_update_retail_spu_bundle(

    spu_id: int,

    db: SessionDep,

    admin_username: Annotated[str, Depends(admin_staff_subject)],

    body: StoreRetailSpuBundleSaveIn,

    store_id: Annotated[int, Query(description="门店 id，默认 1")] = 1,

):

    """原子更新：SPU + 全部 SKU。"""

    _, sid = require_admin_tenant_store(db, admin_username=admin_username, store_id=store_id)

    data = save_retail_spu_bundle(db, store_id=sid, body=body, spu_id=int(spu_id))

    return success(data=data, msg="已保存")





@router.patch("/retail-spus/{spu_id}")

def catalog_patch_retail_spu(

    spu_id: int,

    db: SessionDep,

    admin_username: Annotated[str, Depends(admin_staff_subject)],

    body: StoreRetailSpuPatchIn,

    store_id: Annotated[int, Query(description="门店 id，默认 1")] = 1,

):

    _, sid = require_admin_tenant_store(db, admin_username=admin_username, store_id=store_id)

    data = patch_retail_spu(db, spu_id=int(spu_id), store_id=sid, body=body)

    return success(data=data, msg="已保存")





@router.delete("/retail-spus/{spu_id}")

def catalog_delete_retail_spu(

    spu_id: int,

    db: SessionDep,

    admin_username: Annotated[str, Depends(admin_staff_subject)],

    store_id: Annotated[int, Query(description="门店 id，默认 1")] = 1,

):

    _, sid = require_admin_tenant_store(db, admin_username=admin_username, store_id=store_id)

    delete_retail_spu(db, spu_id=int(spu_id), store_id=sid)

    return success(data=None, msg="已删除")





# —— SKU（路径 retail-products 保持 retail_product_id 语义）——





@router.get("/retail-products")

def catalog_list_retail_products(

    db: SessionDep,

    admin_username: Annotated[str, Depends(admin_staff_subject)],

    store_id: Annotated[int, Query(description="门店 id，默认 1")] = 1,

    spu_id: Annotated[int | None, Query(description="可选：按商品 SPU 筛选")] = None,

    shelf_only: Annotated[bool, Query()] = False,

):

    _, sid = require_admin_tenant_store(db, admin_username=admin_username, store_id=store_id)

    data = list_retail_skus(db, store_id=sid, spu_id=spu_id, shelf_only=shelf_only)

    return success(data=data, msg="获取成功")





@router.post("/retail-products")

def catalog_create_retail_product(

    db: SessionDep,

    admin_username: Annotated[str, Depends(admin_staff_subject)],

    body: StoreRetailSkuCreateIn,

    store_id: Annotated[int, Query(description="门店 id，默认 1")] = 1,

):

    _, sid = require_admin_tenant_store(db, admin_username=admin_username, store_id=store_id)

    data = create_retail_sku(db, store_id=sid, body=body)

    return success(data=data, msg="创建成功")





@router.patch("/retail-products/{product_id}")

def catalog_patch_retail_product(

    product_id: int,

    db: SessionDep,

    admin_username: Annotated[str, Depends(admin_staff_subject)],

    body: StoreRetailSkuPatchIn,

    store_id: Annotated[int, Query(description="门店 id，默认 1")] = 1,

):

    _, sid = require_admin_tenant_store(db, admin_username=admin_username, store_id=store_id)

    data = patch_retail_sku(db, sku_id=int(product_id), store_id=sid, body=body)

    return success(data=data, msg="已保存")





@router.delete("/retail-products/{product_id}")

def catalog_delete_retail_product(

    product_id: int,

    db: SessionDep,

    admin_username: Annotated[str, Depends(admin_staff_subject)],

    store_id: Annotated[int, Query(description="门店 id，默认 1")] = 1,

):

    _, sid = require_admin_tenant_store(db, admin_username=admin_username, store_id=store_id)

    delete_retail_sku(db, sku_id=int(product_id), store_id=sid)

    return success(data=None, msg="已删除")


