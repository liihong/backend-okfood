"""菜品用盒、本周槽位用盒和每份标配。"""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.packaging.deps import packaging_store_id
from app.core.deps import SessionDep, admin_staff_subject
from app.schemas.packaging.recipe import PackagingRecipeReplaceIn, PackagingSlotRecipeIn
from app.services.packaging import recipe_service
from app.services.packaging.recipe_service import RecipeLineIn
from app.utils.response import success

router = APIRouter(prefix="/recipe", tags=["管理端-包装用盒"])


def _lines(body: PackagingRecipeReplaceIn | PackagingSlotRecipeIn) -> list[RecipeLineIn]:
    return [RecipeLineIn(sku_id=line.sku_id, qty_per_portion=line.qty_per_portion) for line in body.lines]


@router.get("/dishes")
def list_dish_packaging(
    db: SessionDep,
    admin_username: str = Depends(admin_staff_subject),
    store_id: int = Depends(packaging_store_id),
):
    _ = admin_username
    return success(data=recipe_service.list_dish_recipes(db, store_id=store_id), msg="获取成功")


@router.put("/dishes/{dish_id}")
def replace_dish_packaging(
    dish_id: int,
    body: PackagingRecipeReplaceIn,
    db: SessionDep,
    admin_username: str = Depends(admin_staff_subject),
    store_id: int = Depends(packaging_store_id),
):
    """只改菜品默认。已经排到本周槽位上的用盒不会被这只接口回写。"""
    _ = admin_username
    rows = recipe_service.replace_dish_lines(db, dish_id, _lines(body), store_id=store_id)
    return success(data=rows[0] if rows else None, msg="菜品用盒已保存")


@router.get("/standard")
def list_standard_packaging(
    db: SessionDep,
    admin_username: str = Depends(admin_staff_subject),
    store_id: int = Depends(packaging_store_id),
):
    _ = admin_username
    return success(data=recipe_service.list_standard_lines(db, store_id=store_id), msg="获取成功")


@router.put("/standard")
def replace_standard_packaging(
    body: PackagingRecipeReplaceIn,
    db: SessionDep,
    admin_username: str = Depends(admin_staff_subject),
    store_id: int = Depends(packaging_store_id),
):
    _ = admin_username
    rows = recipe_service.replace_standard_lines(db, _lines(body), store_id=store_id)
    return success(data=rows, msg="每份标配已保存")


@router.get("/slot")
def get_slot_packaging(
    db: SessionDep,
    week_start: Annotated[date, Query()],
    admin_username: str = Depends(admin_staff_subject),
    store_id: int = Depends(packaging_store_id),
    slot: Annotated[int, Query(ge=1, le=7)] = 1,
    meal_period: Annotated[str, Query()] = "lunch",
):
    _ = admin_username
    row = recipe_service.get_slot_lines(
        db, store_id=store_id, week_start=week_start, slot=slot, meal_period=meal_period
    )
    return success(data=row, msg="获取成功")


@router.put("/slot")
def replace_slot_packaging(
    body: PackagingSlotRecipeIn,
    db: SessionDep,
    admin_username: str = Depends(admin_staff_subject),
    store_id: int = Depends(packaging_store_id),
):
    """保存这一天这一餐的用盒，并记成该菜品的默认。"""
    _ = admin_username
    row = recipe_service.replace_slot_lines(
        db,
        store_id=store_id,
        week_start=body.week_start,
        slot=body.slot,
        meal_period=body.meal_period,
        lines=_lines(body),
    )
    return success(data=row, msg="用盒已保存")


@router.get("/slot-usage")
def list_slot_packaging_usage(
    db: SessionDep,
    week_start: Annotated[date, Query()],
    admin_username: str = Depends(admin_staff_subject),
    store_id: int = Depends(packaging_store_id),
):
    _ = admin_username
    rows = recipe_service.slot_usage(db, store_id=store_id, week_start=week_start)
    return success(data=rows, msg="获取成功")
