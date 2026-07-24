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
from app.schemas.tenant_saas import TenantSaasConfigPatchIn, WxAuthorizerPatchIn, WxComponentTicketIn
from app.services.client.tenant_saas_service import (
    build_tenant_saas_admin_out,
    patch_tenant_saas_admin,
)
from app.services.shared.wx_open_authorizer_service import (
    create_tenant_pre_auth_link,
    exchange_authorization_code,
    get_authorizer_admin_state,
    patch_authorizer_tokens_admin,
    refresh_authorizer_access_token,
    save_component_verify_ticket,
)
from app.services.shared.tenant_integration_service import (
    get_tenant_integration_admin_out,
    patch_tenant_integration_admin,
)
from app.services.shared.platform_tenant_service import (
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


@router.get("/tenants/{tenant_id}/saas-config")
def platform_get_tenant_saas_config(
    tenant_id: int,
    db: SessionDep,
    _admin: Annotated[str, Depends(admin_system_subject)],
):
    """平台管理：读取租户 SaaS 展示配置（theme/features/share/homeLayout 等）。"""
    row = build_tenant_saas_admin_out(db, tenant_id)
    return success(data=row, msg="获取成功")


@router.patch("/tenants/{tenant_id}/saas-config")
def platform_patch_tenant_saas_config(
    tenant_id: int,
    body: TenantSaasConfigPatchIn,
    db: SessionDep,
    _admin: Annotated[str, Depends(admin_system_subject)],
):
    """平台管理：更新租户 SaaS 展示配置（写入 extra_json.saas）。"""
    row = patch_tenant_saas_admin(db, tenant_id, body)
    return success(data=row, msg="已保存")


@router.get("/wx-open/component-state")
def platform_wx_component_state(
    db: SessionDep,
    _admin: Annotated[str, Depends(admin_system_subject)],
):
    """平台：component verify_ticket 是否已落库（不回显 ticket 明文）。"""
    from app.services.shared.wx_open_authorizer_service import get_component_verify_ticket

    ticket = get_component_verify_ticket(db)
    from app.core.config import get_settings

    s = get_settings()
    return success(
        data={
            "component_platform_configured": bool(
                (s.WX_OPEN_COMPONENT_APPID or "").strip() and (s.WX_OPEN_COMPONENT_SECRET or "").strip()
            ),
            "component_ticket_present": bool(ticket),
            "ticket_updated_hint": "ticket 由微信回调或下方手动写入接口更新",
        },
        msg="获取成功",
    )


@router.post("/wx-open/component-ticket")
def platform_wx_component_ticket_manual(
    body: WxComponentTicketIn,
    db: SessionDep,
    _admin: Annotated[str, Depends(admin_system_subject)],
):
    """平台：手动写入 component_verify_ticket（回调未接通时的运维入口）。"""
    save_component_verify_ticket(db, body.verify_ticket)
    return success(msg="verify_ticket 已保存")


@router.get("/tenants/{tenant_id}/wx-authorizer")
def platform_get_wx_authorizer(
    tenant_id: int,
    db: SessionDep,
    _admin: Annotated[str, Depends(admin_system_subject)],
):
    """平台：租户代授权小程序 token 状态（不回显明文）。"""
    row = get_authorizer_admin_state(db, tenant_id)
    return success(data=row, msg="获取成功")


@router.patch("/tenants/{tenant_id}/wx-authorizer")
def platform_patch_wx_authorizer(
    tenant_id: int,
    body: WxAuthorizerPatchIn,
    db: SessionDep,
    _admin: Annotated[str, Depends(admin_system_subject)],
):
    """平台：手动写入/清除 authorizer refresh_token。"""
    row = patch_authorizer_tokens_admin(
        db,
        tenant_id,
        authorizer_refresh_token=body.authorizer_refresh_token,
        authorizer_access_token=body.authorizer_access_token,
        clear=bool(body.clear),
    )
    return success(data=row, msg="已保存")


@router.post("/tenants/{tenant_id}/wx-authorizer/pre-auth-link")
def platform_create_wx_pre_auth_link(
    tenant_id: int,
    db: SessionDep,
    _admin: Annotated[str, Depends(admin_system_subject)],
):
    """平台：传统模式为租户生成小程序授权链接（含 pre_auth_code，约 10 分钟有效）。"""
    row = create_tenant_pre_auth_link(db, tenant_id)
    return success(data=row, msg="授权链接已生成")


@router.post("/tenants/{tenant_id}/wx-authorizer/exchange-code")
def platform_exchange_wx_authorizer_code(
    tenant_id: int,
    body: WxAuthorizerPatchIn,
    db: SessionDep,
    _admin: Annotated[str, Depends(admin_system_subject)],
):
    """平台：用授权码 authorization_code 换取 token 并落库。"""
    code = (body.authorization_code or "").strip()
    if not code:
        from fastapi import HTTPException

        raise HTTPException(status_code=400, detail="authorization_code 不能为空")
    row = exchange_authorization_code(db, authorization_code=code, tenant_id=tenant_id)
    return success(data=row, msg="授权 token 已落库")


@router.post("/tenants/{tenant_id}/wx-authorizer/refresh")
def platform_refresh_wx_authorizer(
    tenant_id: int,
    db: SessionDep,
    _admin: Annotated[str, Depends(admin_system_subject)],
):
    """平台：强制刷新 authorizer_access_token。"""
    from app.integrations.wechat_mini import WeChatMiniError

    try:
        refresh_authorizer_access_token(db, tenant_id)
    except WeChatMiniError as e:
        from fastapi import HTTPException

        raise HTTPException(status_code=e.status_code, detail=str(e)) from e
    row = get_authorizer_admin_state(db, tenant_id)
    return success(data=row, msg="已刷新")


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
