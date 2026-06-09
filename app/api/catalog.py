from fastapi import APIRouter, Depends

from app.core.deps import SessionDep, public_store_dep, PublicStoreContext
from app.services.catalog_admin_service import list_retail_menu_public
from app.utils.response import success

router = APIRouter(prefix="/catalog", tags=["商品目录"])


@router.get("/retail-menu")
def catalog_retail_menu(db: SessionDep, store_ctx: PublicStoreContext = Depends(public_store_dep)):
    """小程序菜单页：门店零售分类及上架商品（无需登录）。"""
    items = list_retail_menu_public(db, store_id=int(store_ctx.store_id))
    return success(data=items, msg="获取成功")
