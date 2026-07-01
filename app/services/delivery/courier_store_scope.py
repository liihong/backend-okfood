"""骑手任务门店范围：单店自动收窄，多店仍按租户+片区（共享配送网络）。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.store import Store


def resolve_courier_task_store_id(db: Session, *, tenant_id: int | None) -> int | None:
    """
    解析骑手订阅任务 store 过滤。
    - 租户仅一家启用门店：返回该 store_id（避免同租户误用 DEFAULT_STORE_ID 混单）
    - 多店或未指定租户：返回 None，沿用 tenant_id 级过滤
    """
    if tenant_id is None:
        return None
    ids = list(
        db.scalars(
            select(Store.id)
            .where(Store.tenant_id == int(tenant_id), Store.is_active.is_(True))
            .order_by(Store.id.asc())
        ).all()
    )
    if len(ids) == 1:
        return int(ids[0])
    return None
