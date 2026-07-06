"""多租户作用域：主租户兼容、跨租户回落禁令、会员/门店 SQL 范围的单一入口。

设计原则
--------
1. **历史主租户**（``DEFAULT_TENANT_ID``，多为 id=1）：未填对接字段时仍可回退全局 ``.env``，保证现网单店不受影响。
2. **其它租户**：禁止回退主租户或全局密钥/门店，配置不全时明确提示去「平台管理 → 租户对接设置」补全。
3. **Service 层**：禁止在 ``tenant_id``/``store_id`` 双空时静默落到主租户默认店。
"""

from __future__ import annotations

from fastapi import HTTPException

from app.core.config import get_settings


# 非主租户对接不全时，统一引导平台管理员补配置（勿暴露主租户 .env 内容）
TENANT_INTEGRATION_INCOMPLETE_HINT = (
    "租户第三方对接配置不完整，请联系平台管理员在「平台管理 → 租户对接设置」中补全后再试"
)


def legacy_default_tenant_id() -> int:
    """历史单店主租户 id（与 ``Settings.DEFAULT_TENANT_ID`` 一致）。"""
    return int(get_settings().DEFAULT_TENANT_ID)


def legacy_default_store_id() -> int:
    """历史单店默认门店 id（公开接口未传 ``X-Store-Id`` 时使用）。"""
    return int(get_settings().DEFAULT_STORE_ID)


def allows_global_env_fallback(tenant_id: int) -> bool:
    """仅主租户允许未填对接字段时回退全局 ``.env``。"""
    return int(tenant_id) == legacy_default_tenant_id()


def merge_tenant_field_or_global(
    tenant_value: str | None,
    global_value: str | None,
    *,
    tenant_id: int,
) -> str:
    """合并租户字段：主租户可回退全局；其它租户缺省则返回空串（由上层校验并提示补配置）。"""
    tv = (tenant_value or "").strip()
    if tv:
        return tv
    if allows_global_env_fallback(tenant_id):
        return (global_value or "").strip()
    return ""


def merge_tenant_int_or_global(
    tenant_value: int | None,
    global_value: int | None,
    *,
    tenant_id: int,
) -> int:
    """整型合并：主租户可回退全局默认值。"""
    if tenant_value is not None:
        return int(tenant_value)
    if allows_global_env_fallback(tenant_id):
        return int(global_value or 0)
    return 0


def require_store_id_for_service(store_id: int | None, *, operation: str) -> int:
    """服务层入口：必须显式传入 ``store_id``，禁止回落主租户默认门店。"""
    if store_id is None:
        raise HTTPException(
            status_code=400,
            detail=f"{operation}须指定 store_id，禁止回落默认主门店",
        )
    return int(store_id)


def sql_member_scope_clause(*, tenant_id: int | None, store_id: int | None):
    """
    会员名单 SQL 范围子句：优先按门店；否则按租户。

    **禁止** ``tenant_id`` 与 ``store_id`` 同时为空时回落主租户，避免多租户环境下误扫租户 1 数据。
    调用方须从已校验的门店/租户上下文传入至少其一。
    """
    from sqlalchemy import false

    from app.models.member import Member

    if store_id is not None:
        return Member.store_id == int(store_id)
    if tenant_id is not None:
        return Member.tenant_id == int(tenant_id)
    # 双空：返回恒假条件，查询结果为空（比抛异常更稳妥，避免遗漏调用点导致 500）
    return false()
