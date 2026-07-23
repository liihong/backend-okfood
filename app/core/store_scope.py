"""门店 / 租户解析：公开接口读请求头，会员接口与 JWT 档案对齐。"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.member import Member
from app.models.store import Store
from app.models.tenant import Tenant


def header_store_id_raw(request: Request) -> str | None:
    return request.headers.get("X-Store-Id") or request.headers.get("x-store-id")


def parse_store_id_from_header_or_default(request: Request | None) -> int:
    """未传头时使用 DEFAULT_STORE_ID，保证旧客户端不变。"""
    if request is None:
        return int(settings.DEFAULT_STORE_ID)
    raw = header_store_id_raw(request)
    if raw is None or str(raw).strip() == "":
        return int(settings.DEFAULT_STORE_ID)
    try:
        return int(str(raw).strip(), 10)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="请求头 X-Store-Id 无效") from e


@dataclass(frozen=True)
class PublicStoreContext:
    store_id: int
    tenant_id: int
    tenant_code: str | None = None


def resolve_public_store(db: Session, store_id: int) -> PublicStoreContext:
    st = db.get(Store, int(store_id))
    if not st or not st.is_active:
        raise HTTPException(status_code=404, detail="门店不存在或已停用")
    tenant = db.get(Tenant, int(st.tenant_id))
    code = None
    if tenant is not None:
        code = (getattr(tenant, "code", None) or "").strip() or None
    return PublicStoreContext(
        store_id=int(st.id),
        tenant_id=int(st.tenant_id),
        tenant_code=code,
    )


def assert_member_belongs_to_header_store(request: Request, member: Member) -> int:
    """已登录会员：若带 X-Store-Id 则须与档案一致；否则以档案门店为准。"""
    raw = header_store_id_raw(request)
    if raw is None or str(raw).strip() == "":
        return int(member.store_id)
    try:
        hid = int(str(raw).strip(), 10)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="请求头 X-Store-Id 无效") from e
    if hid != int(member.store_id):
        raise HTTPException(
            status_code=403,
            detail="当前登录账号不属于该门店，请使用正确门店入口或重新登录",
        )
    return hid


def admin_resolve_store_or_403(db: Session, *, admin_tenant_id: int, store_id: int) -> Store:
    """后台：门店须属于管理员所在租户。"""
    st = db.get(Store, int(store_id))
    if not st or not st.is_active:
        raise HTTPException(status_code=404, detail="门店不存在或已停用")
    if int(st.tenant_id) != int(admin_tenant_id):
        raise HTTPException(status_code=403, detail="无权操作该门店")
    return st
