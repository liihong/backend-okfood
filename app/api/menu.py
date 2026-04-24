from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query

from app.core.deps import SessionDep
from app.services.member_service import get_menu_detail_by_dish_id, get_tomorrow_menu, get_weekly_menu
from app.utils.response import success

router = APIRouter(prefix="/menu", tags=["菜单"])


@router.get("/tomorrow")
def tomorrow_menu(db: SessionDep):
    """查询明日餐谱（上海业务日）。"""
    return success(data=get_tomorrow_menu(db), msg="获取成功")


@router.get("/weekly")
def weekly_menu(
    db: SessionDep,
    week_start: Annotated[
        date | None,
        Query(description="该周任意一天；将归一化为当周周一。不传则按上海当前日期取本周"),
    ] = None,
):
    """一周菜单（周一至周日）：每日 `date`、`dish_id`（可空）、`title`/`desc`/`pic`。详情用 `dish_id` 调 `/menu/detail/{dish_id}`。无需登录。"""
    return success(data=get_weekly_menu(db, week_start), msg="获取成功")


@router.get("/detail/{dish_id}")
def menu_detail(
    db: SessionDep,
    dish_id: int,
    service_date: Annotated[
        date | None,
        Query(description="供餐日 YYYY-MM-DD；传则返回该日单次卡剩余库存等字段"),
    ] = None,
):
    """餐品详情，dish_id 为菜品库主键，与周列表项中 `dish_id` 一致。无需登录。"""
    return success(data=get_menu_detail_by_dish_id(db, dish_id, service_date=service_date), msg="获取成功")
