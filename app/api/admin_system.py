"""平台管理员接口：租户维护、租户下后台账号分配。"""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.deps import SessionDep, admin_system_subject
from app.schemas.admin import (
    PlatformStoreCreateIn,
    PlatformStorePatchIn,
    PlatformTenantAdminCreateIn,
    PlatformTenantAdminPatchIn,
    PlatformTenantCreateIn,
    PlatformTenantPatchIn,
    TenantIntegrationSettingsPatchIn,
)
from app.services.tenant_integration_service import (
    get_tenant_integration_admin_out,
    patch_tenant_integration_admin,
)
from app.services.platform_tenant_service import (
    create_platform_tenant,
    create_store_for_platform,
    create_tenant_admin_for_platform,
    deactivate_tenant_admin_for_platform,
    get_platform_overview,
    list_platform_tenants,
    list_tenant_admins_for_platform,
    list_tenant_stores_for_platform,
    patch_platform_tenant,
    patch_store_for_platform,
    patch_tenant_admin_for_platform,
    soft_delete_platform_tenant,
)
from app.utils.response import dump_model, success

router = APIRouter(prefix="/admin/system", tags=["管理端-平台"])


@router.get("/overview")
def platform_overview(
    db: SessionDep,
    _admin: Annotated[str, Depends(admin_system_subject)],
):
    row = get_platform_overview(db)
    return success(data=dump_model(row), msg="获取成功")


@router.get("/tenants")
def platform_list_tenants(
    db: SessionDep,
    _admin: Annotated[str, Depends(admin_system_subject)],
):
    items = list_platform_tenants(db)
    return success(data=[dump_model(x) for x in items], msg="获取成功")


@router.post("/tenants")
def platform_create_tenant(
    body: PlatformTenantCreateIn,
    db: SessionDep,
    _admin: Annotated[str, Depends(admin_system_subject)],
):
    row = create_platform_tenant(db, body)
    return success(data=dump_model(row), msg="创建成功")


@router.patch("/tenants/{tenant_id}")
def platform_patch_tenant(
    tenant_id: int,
    body: PlatformTenantPatchIn,
    db: SessionDep,
    _admin: Annotated[str, Depends(admin_system_subject)],
):
    row = patch_platform_tenant(db, tenant_id, body)
    return success(data=dump_model(row), msg="更新成功")


@router.delete("/tenants/{tenant_id}")
def platform_delete_tenant(
    tenant_id: int,
    db: SessionDep,
    _admin: Annotated[str, Depends(admin_system_subject)],
):
    soft_delete_platform_tenant(db, tenant_id)
    return success(data=None, msg="已停用租户")


@router.get("/tenants/{tenant_id}/integration-settings")
def platform_get_tenant_integration(
    tenant_id: int,
    db: SessionDep,
    _admin: Annotated[str, Depends(admin_system_subject)],
):
    row = get_tenant_integration_admin_out(db, tenant_id)
    return success(data=dump_model(row), msg="获取成功")


@router.patch("/tenants/{tenant_id}/integration-settings")
def platform_patch_tenant_integration(
    tenant_id: int,
    body: TenantIntegrationSettingsPatchIn,
    db: SessionDep,
    _admin: Annotated[str, Depends(admin_system_subject)],
):
    row = patch_tenant_integration_admin(db, tenant_id, body)
    return success(data=dump_model(row), msg="已保存")


@router.get("/tenants/{tenant_id}/stores")
def platform_list_tenant_stores(
    tenant_id: int,
    db: SessionDep,
    _admin: Annotated[str, Depends(admin_system_subject)],
):
    items = list_tenant_stores_for_platform(db, tenant_id)
    return success(data=[dump_model(x) for x in items], msg="获取成功")


@router.post("/tenants/{tenant_id}/stores")
def platform_create_tenant_store(
    tenant_id: int,
    body: PlatformStoreCreateIn,
    db: SessionDep,
    _admin: Annotated[str, Depends(admin_system_subject)],
):
    row = create_store_for_platform(db, tenant_id, body)
    return success(data=dump_model(row), msg="门店已创建")


@router.patch("/tenants/{tenant_id}/stores/{store_id}")
def platform_patch_tenant_store(
    tenant_id: int,
    store_id: int,
    body: PlatformStorePatchIn,
    db: SessionDep,
    _admin: Annotated[str, Depends(admin_system_subject)],
):
    row = patch_store_for_platform(db, tenant_id, store_id, body)
    return success(data=dump_model(row), msg="已保存")


@router.get("/tenants/{tenant_id}/admins")
def platform_list_tenant_admins(
    tenant_id: int,
    db: SessionDep,
    _admin: Annotated[str, Depends(admin_system_subject)],
):
    items = list_tenant_admins_for_platform(db, tenant_id)
    return success(data=[dump_model(x) for x in items], msg="获取成功")


@router.post("/tenants/{tenant_id}/admins")
def platform_create_tenant_admin(
    tenant_id: int,
    body: PlatformTenantAdminCreateIn,
    db: SessionDep,
    _admin: Annotated[str, Depends(admin_system_subject)],
):
    row = create_tenant_admin_for_platform(db, tenant_id, body)
    return success(data=dump_model(row), msg="创建成功")


@router.patch("/tenants/{tenant_id}/admins/{admin_id}")
def platform_patch_tenant_admin(
    tenant_id: int,
    admin_id: int,
    body: PlatformTenantAdminPatchIn,
    db: SessionDep,
    operator_username: Annotated[str, Depends(admin_system_subject)],
):
    row = patch_tenant_admin_for_platform(
        db, tenant_id, admin_id, body, operator_username=operator_username
    )
    return success(data=dump_model(row), msg="更新成功")


@router.delete("/tenants/{tenant_id}/admins/{admin_id}")
def platform_delete_tenant_admin(
    tenant_id: int,
    admin_id: int,
    db: SessionDep,
    operator_username: Annotated[str, Depends(admin_system_subject)],
):
    deactivate_tenant_admin_for_platform(
        db, tenant_id, admin_id, operator_username=operator_username
    )
    return success(data=None, msg="已停用账号")
