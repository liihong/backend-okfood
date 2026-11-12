"""管理端随餐饮饮品。路径挂在 /api/admin/drink，和菜品接口分开注册。"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.deps import SessionDep, admin_staff_subject, require_admin_tenant_store
from app.schemas.menu_drink import DrinkUpsertIn
from app.services.admin import menu_drink_service as svc
from app.utils.response import dump_model, success

router = APIRouter(prefix="/admin", tags=["管理端-随餐饮"])


def _store_id(db: SessionDep, admin_username: str, store_id: int) -> int:
    _, sid = require_admin_tenant_store(db, admin_username=admin_username, store_id=store_id)
    return sid


@router.get("/drinks")
def list_drinks(
    db: SessionDep,
    admin_username: str = Depends(admin_staff_subject),
    store_id: Annotated[int, Query(description="门店 id，默认 1")] = 1,
    enabled_only: bool = False,
):
    """饮品列表。菜品的配餐饮下拉用这份数据，不读零售果蔬汁。"""
    sid = _store_id(db, admin_username, store_id)
    rows = svc.list_drinks_admin(db, store_id=sid, enabled_only=enabled_only)
    return success(data=[dump_model(row) for row in rows], msg="获取成功")


@router.get("/drink/{drink_id}")
def drink_detail(
    drink_id: int,
    db: SessionDep,
    admin_username: str = Depends(admin_staff_subject),
    store_id: Annotated[int, Query(description="门店 id，默认 1")] = 1,
):
    """单条饮品。"""
    sid = _store_id(db, admin_username, store_id)
    row = svc.get_drink_admin(db, drink_id, store_id=sid)
    return success(data=dump_model(row), msg="获取成功")


@router.post("/drink")
def save_drink(
    body: DrinkUpsertIn,
    db: SessionDep,
    admin_username: str = Depends(admin_staff_subject),
    store_id: Annotated[int, Query(description="门店 id，默认 1")] = 1,
):
    """新建或更新饮品。带 id 为更新。"""
    sid = _store_id(db, admin_username, store_id)
    row = svc.upsert_drink(db, body, store_id=sid)
    return success(data=dump_model(row), msg="饮品已保存")


@router.delete("/drink/{drink_id}")
def remove_drink(
    drink_id: int,
    db: SessionDep,
    admin_username: str = Depends(admin_staff_subject),
    store_id: Annotated[int, Query(description="门店 id，默认 1")] = 1,
):
    """删除饮品。仍被本周菜单或菜品引用时拒绝删除。"""
    sid = _store_id(db, admin_username, store_id)
    svc.delete_drink(db, drink_id, store_id=sid)
    return success(msg="饮品已删除")
