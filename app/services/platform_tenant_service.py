"""平台管理员：租户 CRUD、租户维度后台账号维护。"""

from __future__ import annotations

from datetime import time as dt_time

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.core.security import hash_password
from app.models.admin_user import AdminUser
from app.models.store import Store
from app.models.tenant import Tenant
from app.schemas.admin import (
    PlatformStoreCreateIn,
    PlatformStoreOut,
    PlatformSystemOverviewOut,
    PlatformTenantAdminCreateIn,
    PlatformTenantAdminOut,
    PlatformTenantAdminPatchIn,
    PlatformTenantCreateIn,
    PlatformTenantOut,
    PlatformTenantPatchIn,
)

_MANAGED_ROLES = frozenset({"full", "delivery", "support"})
_SYSTEM_ROLE = "system"


def _tenant_or_404(db: Session, tenant_id: int) -> Tenant:
    t = db.get(Tenant, tenant_id)
    if not t:
        raise HTTPException(status_code=404, detail="租户不存在")
    return t


def _fmt_dt(v) -> str:
    if v is None:
        return ""
    try:
        return v.isoformat()
    except (TypeError, AttributeError):
        return str(v)


def _parse_leave_deadline(raw: str) -> dt_time:
    s = (raw or "").strip()
    if not s:
        return dt_time(21, 0, 0)
    parts = s.replace(".", ":").split(":")
    try:
        if len(parts) == 2:
            h, m = int(parts[0]), int(parts[1])
            if not (0 <= h <= 23 and 0 <= m <= 59):
                raise ValueError
            return dt_time(h, m, 0)
        if len(parts) == 3:
            h, m, sec = int(parts[0]), int(parts[1]), int(parts[2])
            if not (0 <= h <= 23 and 0 <= m <= 59 and 0 <= sec <= 59):
                raise ValueError
            return dt_time(h, m, sec)
    except ValueError:
        pass
    raise HTTPException(status_code=400, detail="leave_deadline_time 须为 HH:MM 或 HH:MM:SS")


def _fmt_leave_time(v: dt_time | None) -> str:
    if v is None:
        return ""
    return v.strftime("%H:%M:%S")


def _store_to_out(st: Store) -> PlatformStoreOut:
    return PlatformStoreOut(
        id=int(st.id),
        tenant_id=int(st.tenant_id),
        name=st.name,
        is_active=st.is_active,
        leave_deadline_time=_fmt_leave_time(st.leave_deadline_time),
        created_at=_fmt_dt(st.created_at),
    )


def get_platform_overview(db: Session) -> PlatformSystemOverviewOut:
    tt = int(db.scalar(select(func.count()).select_from(Tenant)) or 0)
    ta = int(
        db.scalar(select(func.count()).select_from(Tenant).where(Tenant.is_active.is_(True))) or 0
    )
    st = int(db.scalar(select(func.count()).select_from(Store)) or 0)
    sa = int(
        db.scalar(select(func.count()).select_from(Store).where(Store.is_active.is_(True))) or 0
    )
    au = int(
        db.scalar(
            select(func.count()).select_from(AdminUser).where(AdminUser.is_active.is_(True))
        )
        or 0
    )
    return PlatformSystemOverviewOut(
        tenants_total=tt,
        tenants_active=ta,
        stores_total=st,
        stores_active=sa,
        admin_users_active=au,
    )


def list_tenant_stores_for_platform(db: Session, tenant_id: int) -> list[PlatformStoreOut]:
    _tenant_or_404(db, tenant_id)
    rows = db.scalars(select(Store).where(Store.tenant_id == tenant_id).order_by(Store.id)).all()
    return [_store_to_out(r) for r in rows]


def create_store_for_platform(db: Session, tenant_id: int, body: PlatformStoreCreateIn) -> PlatformStoreOut:
    _tenant_or_404(db, tenant_id)
    name = (body.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="门店名称不能为空")
    ld = _parse_leave_deadline(body.leave_deadline_time)
    st = Store(tenant_id=tenant_id, name=name, leave_deadline_time=ld, is_active=body.is_active)
    db.add(st)
    db.commit()
    db.refresh(st)
    return _store_to_out(st)


def list_platform_tenants(db: Session) -> list[PlatformTenantOut]:
    tenants = list(db.scalars(select(Tenant).order_by(Tenant.id)).all())
    if not tenants:
        return []
    ids = [t.id for t in tenants]
    store_rows = db.execute(
        select(Store.tenant_id, func.count())
        .where(Store.tenant_id.in_(ids))
        .group_by(Store.tenant_id)
    ).all()
    store_map = {int(r[0]): int(r[1]) for r in store_rows}
    admin_rows = db.execute(
        select(AdminUser.tenant_id, func.count())
        .where(AdminUser.tenant_id.in_(ids), AdminUser.is_active.is_(True))
        .group_by(AdminUser.tenant_id)
    ).all()
    admin_map = {int(r[0]): int(r[1]) for r in admin_rows}
    return [
        PlatformTenantOut(
            id=t.id,
            name=t.name,
            is_active=t.is_active,
            created_at=_fmt_dt(t.created_at),
            store_count=int(store_map.get(t.id, 0)),
            admin_count=int(admin_map.get(t.id, 0)),
        )
        for t in tenants
    ]


def create_platform_tenant(db: Session, body: PlatformTenantCreateIn) -> PlatformTenantOut:
    name = (body.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="租户名称不能为空")
    t = Tenant(name=name, is_active=body.is_active)
    db.add(t)
    db.commit()
    db.refresh(t)
    return PlatformTenantOut(
        id=t.id,
        name=t.name,
        is_active=t.is_active,
        created_at=_fmt_dt(t.created_at),
        store_count=0,
        admin_count=0,
    )


def patch_platform_tenant(db: Session, tenant_id: int, body: PlatformTenantPatchIn) -> PlatformTenantOut:
    t = _tenant_or_404(db, tenant_id)
    if body.name is not None:
        n = body.name.strip()
        if not n:
            raise HTTPException(status_code=400, detail="租户名称不能为空")
        t.name = n
    if body.is_active is not None:
        t.is_active = body.is_active
    db.commit()
    db.refresh(t)
    store_n = int(
        db.scalar(select(func.count()).select_from(Store).where(Store.tenant_id == t.id)) or 0
    )
    admin_n = int(
        db.scalar(
            select(func.count())
            .select_from(AdminUser)
            .where(AdminUser.tenant_id == t.id, AdminUser.is_active.is_(True))
        )
        or 0
    )
    return PlatformTenantOut(
        id=t.id,
        name=t.name,
        is_active=t.is_active,
        created_at=_fmt_dt(t.created_at),
        store_count=store_n,
        admin_count=admin_n,
    )


def soft_delete_platform_tenant(db: Session, tenant_id: int) -> None:
    t = _tenant_or_404(db, tenant_id)
    t.is_active = False
    db.commit()


def list_tenant_admins_for_platform(db: Session, tenant_id: int) -> list[PlatformTenantAdminOut]:
    _tenant_or_404(db, tenant_id)
    rows = db.scalars(
        select(AdminUser).where(AdminUser.tenant_id == tenant_id).order_by(AdminUser.id)
    ).all()
    return [
        PlatformTenantAdminOut(
            id=r.id,
            tenant_id=r.tenant_id,
            username=r.username,
            role=r.role,
            is_active=r.is_active,
            created_at=_fmt_dt(r.created_at),
        )
        for r in rows
    ]


def create_tenant_admin_for_platform(
    db: Session, tenant_id: int, body: PlatformTenantAdminCreateIn
) -> PlatformTenantAdminOut:
    _tenant_or_404(db, tenant_id)
    role = (body.role or "").strip().lower()
    if role not in _MANAGED_ROLES:
        raise HTTPException(status_code=400, detail="角色仅支持 full / delivery / support")
    uname = (body.username or "").strip()
    if not uname:
        raise HTTPException(status_code=400, detail="用户名不能为空")
    if db.scalar(select(AdminUser.id).where(AdminUser.username == uname)):
        raise HTTPException(status_code=400, detail="用户名已存在")
    u = AdminUser(
        tenant_id=tenant_id,
        username=uname,
        password_hash=hash_password(body.password),
        role=role,
        is_active=True,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return PlatformTenantAdminOut(
        id=u.id,
        tenant_id=u.tenant_id,
        username=u.username,
        role=u.role,
        is_active=u.is_active,
        created_at=_fmt_dt(u.created_at),
    )


def _managed_admin_or_404(db: Session, *, tenant_id: int, admin_id: int) -> AdminUser:
    u = db.get(AdminUser, admin_id)
    if not u or int(u.tenant_id) != int(tenant_id):
        raise HTTPException(status_code=404, detail="管理员不存在")
    if (u.role or "").strip().lower() == _SYSTEM_ROLE:
        raise HTTPException(status_code=400, detail="不能通过该接口修改平台管理员账号")
    return u


def patch_tenant_admin_for_platform(
    db: Session,
    tenant_id: int,
    admin_id: int,
    body: PlatformTenantAdminPatchIn,
    *,
    operator_username: str,
) -> PlatformTenantAdminOut:
    u = _managed_admin_or_404(db, tenant_id=tenant_id, admin_id=admin_id)
    if body.password is not None:
        u.password_hash = hash_password(body.password)
    if body.role is not None:
        role = body.role.strip().lower()
        if role not in _MANAGED_ROLES:
            raise HTTPException(status_code=400, detail="角色仅支持 full / delivery / support")
        u.role = role
    if body.is_active is not None:
        if not body.is_active and u.username == operator_username:
            raise HTTPException(status_code=400, detail="不能停用自己的账号")
        u.is_active = body.is_active
    db.commit()
    db.refresh(u)
    return PlatformTenantAdminOut(
        id=u.id,
        tenant_id=u.tenant_id,
        username=u.username,
        role=u.role,
        is_active=u.is_active,
        created_at=_fmt_dt(u.created_at),
    )


def deactivate_tenant_admin_for_platform(
    db: Session, tenant_id: int, admin_id: int, *, operator_username: str
) -> None:
    u = _managed_admin_or_404(db, tenant_id=tenant_id, admin_id=admin_id)
    if u.username == operator_username:
        raise HTTPException(status_code=400, detail="不能停用自己的账号")
    u.is_active = False
    db.commit()
