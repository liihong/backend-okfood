"""SaaS 租户公开配置 API（模板库联调）。"""

from fastapi import APIRouter, Depends, HTTPException

from app.core.deps import SessionDep, public_store_dep, PublicStoreContext
from app.services.client.tenant_saas_service import build_tenant_config_public
from app.utils.response import success

router = APIRouter(prefix="/tenant", tags=["SaaS-租户"])


@router.get("/config")
def get_tenant_config(
    db: SessionDep,
    store_ctx: PublicStoreContext = Depends(public_store_dep),
):
    """
    启动时合并 ext 配置，减少仅改 ext 就要 re-commit 的频率。

    404：租户不存在或未启用（模板库 fallback 到 ext）。
    OK饭 旧小程序不传 X-Tenant-Id 亦可正常访问（按 X-Store-Id 解析主租户）。
    """
    payload = build_tenant_config_public(db, store_ctx)
    if payload is None:
        raise HTTPException(status_code=404, detail="租户配置不存在")
    return success(data=payload, msg="获取成功")
