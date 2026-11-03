"""管理端开菜单：食材、配菜配方、按周估算。不改周菜单和菜品说明。"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.deps import SessionDep, admin_staff_subject, require_admin_tenant_store
from app.schemas.prep_menu import DishPrepSopPutIn, PrepEstimateIn, PrepIngredientIn, PrepIngredientPatchIn
from app.services.admin import prep_menu_service as svc
from app.utils.response import dump_model, success

router = APIRouter(prefix="/admin/prep-menu", tags=["管理端-开菜单"])


def _store_id(db: SessionDep, admin_username: str, store_id: int) -> int:
    _, sid = require_admin_tenant_store(db, admin_username=admin_username, store_id=store_id)
    return sid


@router.get("/ingredients")
def list_ingredients(
    db: SessionDep,
    admin_username: str = Depends(admin_staff_subject),
    store_id: Annotated[int, Query(description="门店 id")] = 1,
):
    """食材与出成率。"""
    sid = _store_id(db, admin_username, store_id)
    rows = svc.list_prep_ingredients(db, store_id=sid)
    return success(data=[dump_model(row) for row in rows], msg="获取成功")


@router.post("/ingredients")
def create_ingredient(
    body: PrepIngredientIn,
    db: SessionDep,
    admin_username: str = Depends(admin_staff_subject),
    store_id: Annotated[int, Query(description="门店 id")] = 1,
):
    """新增食材。"""
    sid = _store_id(db, admin_username, store_id)
    row = svc.create_prep_ingredient(db, body, store_id=sid)
    return success(data=dump_model(row), msg="食材已保存")


@router.patch("/ingredients/{ingredient_id}")
def patch_ingredient(
    ingredient_id: int,
    body: PrepIngredientPatchIn,
    db: SessionDep,
    admin_username: str = Depends(admin_staff_subject),
    store_id: Annotated[int, Query(description="门店 id")] = 1,
):
    """修改食材名称、单位或出成率。"""
    sid = _store_id(db, admin_username, store_id)
    row = svc.patch_prep_ingredient(db, ingredient_id, body, store_id=sid)
    return success(data=dump_model(row), msg="食材已保存")


@router.delete("/ingredients/{ingredient_id}")
def remove_ingredient(
    ingredient_id: int,
    db: SessionDep,
    admin_username: str = Depends(admin_staff_subject),
    store_id: Annotated[int, Query(description="门店 id")] = 1,
):
    """删除未被配方引用的食材。"""
    sid = _store_id(db, admin_username, store_id)
    svc.delete_prep_ingredient(db, ingredient_id, store_id=sid)
    return success(msg="食材已删除")


@router.get("/sops/{dish_id}")
def get_sop(
    dish_id: int,
    db: SessionDep,
    admin_username: str = Depends(admin_staff_subject),
    store_id: Annotated[int, Query(description="门店 id")] = 1,
):
    """读取某菜品的单份毛菜配方。"""
    sid = _store_id(db, admin_username, store_id)
    row = svc.get_dish_prep_sop(db, dish_id, store_id=sid)
    return success(data=dump_model(row), msg="获取成功")


@router.put("/sops/{dish_id}")
def put_sop(
    dish_id: int,
    body: DishPrepSopPutIn,
    db: SessionDep,
    admin_username: str = Depends(admin_staff_subject),
    store_id: Annotated[int, Query(description="门店 id")] = 1,
):
    """整单覆盖某菜品的配菜。空列表表示清空。"""
    sid = _store_id(db, admin_username, store_id)
    row = svc.replace_dish_prep_sop(db, dish_id, body, store_id=sid)
    return success(data=dump_model(row), msg="配菜已保存")


@router.post("/estimate")
def estimate(
    body: PrepEstimateIn,
    db: SessionDep,
    admin_username: str = Depends(admin_staff_subject),
    store_id: Annotated[int, Query(description="门店 id")] = 1,
):
    """按本周排菜估算毛菜、净菜。份数覆盖只影响本次结果。"""
    sid = _store_id(db, admin_username, store_id)
    row = svc.estimate_prep_menu(db, body, store_id=sid)
    return success(data=dump_model(row), msg="获取成功")
