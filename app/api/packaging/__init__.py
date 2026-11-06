"""包装库存路由汇总。main 只挂这一处。"""

from fastapi import APIRouter

from app.api.packaging.recipe import router as recipe_router
from app.api.packaging.sku import router as sku_router
from app.api.packaging.stock import router as stock_router

router = APIRouter(prefix="/admin/packaging")
router.include_router(sku_router)
router.include_router(stock_router)
router.include_router(recipe_router)
