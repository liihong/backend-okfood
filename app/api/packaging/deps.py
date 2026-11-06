"""包装接口的门店范围。与开菜单相同，只允许操作本租户门店。"""

from typing import Annotated

from fastapi import Depends, Query

from app.core.deps import SessionDep, admin_staff_subject, require_admin_tenant_store


def packaging_store_id(
    db: SessionDep,
    admin_username: Annotated[str, Depends(admin_staff_subject)],
    store_id: Annotated[int, Query(description="门店 id")] = 1,
) -> int:
    _tenant_id, sid = require_admin_tenant_store(db, admin_username=admin_username, store_id=store_id)
    return sid
