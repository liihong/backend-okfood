"""管理端资源访问校验：会员 / 推单等须归属当前管理员租户与操作门店。"""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.deps import require_admin_tenant_store
from app.models.member import Member
from app.models.sf_same_city_push import SfSameCityPush
from app.models.store import Store


def require_member_in_admin_store(
    db: Session,
    *,
    admin_username: str,
    member_id: int,
    store_id: int,
) -> tuple[Member, int, int]:
    """
    校验会员存在且属于管理员可操作门店；返回 (member, tenant_id, store_id)。
    跨租户/跨店统一 404，避免 IDOR 探测。
    """
    tid, sid = require_admin_tenant_store(
        db, admin_username=admin_username, store_id=int(store_id)
    )
    m = db.get(Member, int(member_id))
    if not m or m.deleted_at is not None:
        raise HTTPException(status_code=404, detail="会员不存在")
    if int(m.tenant_id) != tid or int(m.store_id) != sid:
        raise HTTPException(status_code=404, detail="会员不存在")
    return m, tid, sid


def require_sf_push_in_admin_tenant(
    db: Session,
    *,
    admin_username: str,
    push_id: int,
) -> tuple[SfSameCityPush, int, int]:
    """校验顺丰推单记录存在且门店属于管理员租户；返回 (push_row, tenant_id, store_id)。"""
    from app.core.deps import require_admin_tenant_id

    tid = require_admin_tenant_id(db, admin_username=admin_username)
    push_row = db.get(SfSameCityPush, int(push_id))
    if push_row is None:
        raise HTTPException(status_code=404, detail="推单记录不存在")
    st = db.get(Store, int(push_row.store_id))
    if st is None or not st.is_active or int(st.tenant_id) != tid:
        raise HTTPException(status_code=404, detail="推单记录不存在")
    return push_row, tid, int(st.id)
