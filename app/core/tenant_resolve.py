"""租户/门店公开接口解析：兼容 OK饭（仅 X-Store-Id）与 SaaS 模板（X-Tenant-Id + X-Store-Id）。

设计原则
--------
1. **无 X-Tenant-Id**：行为与改造前完全一致，仅按 X-Store-Id（或 DEFAULT_STORE_ID）解析门店。
2. **有 X-Tenant-Id**：解析后与门店所属 tenant_id 交叉校验，防止跨租户串数据。
3. **TENANT_STRICT_MODE**：仅对非主租户生效；主租户（DEFAULT_TENANT_ID）永远兼容旧客户端。
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.store_scope import header_store_id_raw, parse_store_id_from_header_or_default
from app.core.tenant_scope import legacy_default_tenant_id
from app.models.store import Store
from app.models.tenant import Tenant
from app.models.tenant_integration_settings import TenantIntegrationSettings


def header_tenant_id_raw(request: Request | None) -> str | None:
    """读取 X-Tenant-Id 请求头（大小写兼容）。"""
    if request is None:
        return None
    return request.headers.get("X-Tenant-Id") or request.headers.get("x-tenant-id")


def resolve_tenant_id_from_header_value(db: Session, raw: str | None) -> int | None:
    """
    将 X-Tenant-Id 解析为内部 tenants.id。

    支持：
    - 数字字符串（如 ``"2"``）
    - 外部 code（如 ``"t_brand_a"``，对应 tenants.code）
    """
    if raw is None or str(raw).strip() == "":
        return None
    token = str(raw).strip()
    try:
        tid = int(token, 10)
        t = db.get(Tenant, tid)
        if t is not None and t.is_active:
            return int(t.id)
        return None
    except ValueError:
        pass
    row = db.scalar(select(Tenant).where(Tenant.code == token, Tenant.is_active.is_(True)))
    return int(row.id) if row is not None else None


def lookup_tenant_id_by_wx_appid(db: Session, appid: str) -> int | None:
    """
    按微信小程序 AppID 反查 tenant_id（SaaS 登录/AppID 映射）。

    主租户：若 AppID 与全局 .env WX_MINI_APPID 一致，回退 DEFAULT_TENANT_ID。
    """
    aid = (appid or "").strip()
    if not aid:
        return None
    row = db.scalar(
        select(TenantIntegrationSettings.tenant_id).where(
            TenantIntegrationSettings.wx_mini_appid == aid
        )
    )
    if row is not None:
        return int(row)
    base = get_settings()
    global_appid = (base.WX_MINI_APPID or "").strip()
    if global_appid and aid == global_appid:
        return legacy_default_tenant_id()
    return None


def tenant_external_code(db: Session, tenant_id: int) -> str:
    """对外 tenantId：优先 tenants.code，否则回退数字 id 字符串。"""
    t = db.get(Tenant, int(tenant_id))
    if t is None:
        return str(int(tenant_id))
    code = (getattr(t, "code", None) or "").strip()
    return code if code else str(int(t.id))


def _default_active_store_id_for_tenant(db: Session, tenant_id: int) -> int | None:
    """租户下 id 最小的启用门店（SaaS 仅带 X-Tenant-Id、未带门店时的回退）。"""
    sid = db.scalar(
        select(Store.id)
        .where(Store.tenant_id == int(tenant_id), Store.is_active.is_(True))
        .order_by(Store.id.asc())
        .limit(1)
    )
    return int(sid) if sid is not None else None


def assert_tenant_strict_header_if_required(
    *,
    tenant_id: int,
    header_tenant_resolved: int | None,
) -> None:
    """
    TENANT_STRICT_MODE 下，非主租户公开接口须显式携带且解析成功的 X-Tenant-Id。

    主租户与 OK饭 旧客户端（不传头）不受影响。
    """
    settings = get_settings()
    if not settings.TENANT_STRICT_MODE:
        return
    if int(tenant_id) == legacy_default_tenant_id():
        return
    if header_tenant_resolved is None:
        raise HTTPException(
            status_code=400,
            detail="当前租户须携带请求头 X-Tenant-Id",
        )


@dataclass(frozen=True)
class PublicTenantStoreContext:
    """公开接口租户+门店上下文（在 PublicStoreContext 基础上增加 tenant_code）。"""

    store_id: int
    tenant_id: int
    tenant_code: str | None = None


def resolve_public_tenant_store(db: Session, request: Request | None) -> PublicTenantStoreContext:
    """
    解析公开接口的 tenant_id + store_id。

    兼容路径（OK饭）::
        无 X-Tenant-Id → X-Store-Id 或 DEFAULT_STORE_ID → 门店 → tenant_id

    SaaS 路径::
        X-Tenant-Id + X-Store-Id → 交叉校验
        仅 X-Tenant-Id → 使用该租户默认启用门店
    """
    header_raw = header_tenant_id_raw(request)
    header_tid = resolve_tenant_id_from_header_value(db, header_raw)

    raw_store = header_store_id_raw(request) if request is not None else None
    has_store_header = raw_store is not None and str(raw_store).strip() != ""

    if header_tid is not None and not has_store_header:
        # SaaS：仅 tenant，回落到该租户默认店
        default_sid = _default_active_store_id_for_tenant(db, header_tid)
        if default_sid is None:
            raise HTTPException(status_code=404, detail="租户下无可用门店")
        store_id = default_sid
    else:
        store_id = parse_store_id_from_header_or_default(request)

    st = db.get(Store, int(store_id))
    if st is None or not st.is_active:
        raise HTTPException(status_code=404, detail="门店不存在或已停用")

    store_tenant_id = int(st.tenant_id)

    if header_tid is not None and header_tid != store_tenant_id:
        raise HTTPException(status_code=403, detail="X-Tenant-Id 与门店所属租户不一致")

    tenant = db.get(Tenant, store_tenant_id)
    if tenant is None or not tenant.is_active:
        raise HTTPException(status_code=404, detail="租户不存在或已停用")

    assert_tenant_strict_header_if_required(
        tenant_id=store_tenant_id,
        header_tenant_resolved=header_tid,
    )

    code = (getattr(tenant, "code", None) or "").strip() or None
    return PublicTenantStoreContext(
        store_id=int(st.id),
        tenant_id=store_tenant_id,
        tenant_code=code,
    )


def assert_header_tenant_matches_tenant_id(
    db: Session,
    request: Request,
    *,
    tenant_id: int,
) -> None:
    """登录等场景：若请求带 X-Tenant-Id，须与当前解析出的 tenant_id 一致。"""
    header_tid = resolve_tenant_id_from_header_value(db, header_tenant_id_raw(request))
    if header_tid is not None and int(header_tid) != int(tenant_id):
        raise HTTPException(status_code=403, detail="X-Tenant-Id 与当前小程序租户不一致")
