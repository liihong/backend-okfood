from fastapi import APIRouter, Depends

from app.core.deps import SessionDep, public_store_dep, PublicStoreContext
from app.services.home_banner_service import list_active_home_banners
from app.utils.response import dump_model, success

router = APIRouter(prefix="/home", tags=["首页"])


@router.get("/banners")
def home_banners(db: SessionDep, store_ctx: PublicStoreContext = Depends(public_store_dep)):
    """小程序首页 Banner 列表（仅启用项）。"""
    items = list_active_home_banners(db, store_id=int(store_ctx.store_id))
    return success(data=[dump_model(x) for x in items], msg="获取成功")
