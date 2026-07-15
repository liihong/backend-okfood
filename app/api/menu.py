from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.deps import SessionDep, public_store_dep, PublicStoreContext
from app.services.member.member_service import get_menu_detail_by_dish_id, get_today_menu, get_tomorrow_menu, get_weekly_menu
from app.utils.response import success

router = APIRouter(prefix="/menu", tags=["菜单"])


def _parse_stock_dates(raw: str | None) -> list[date] | None:
    """解析 stock_dates 查询参数（逗号分隔 YYYY-MM-DD）；空串视为未指定。"""
    if raw is None:
        return None
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    if not parts:
        return None
    return [date.fromisoformat(p) for p in parts]


@router.get("/today")
def today_menu(
    db: SessionDep,
    store_ctx: PublicStoreContext = Depends(public_store_dep),
    meal_period: Annotated[str, Query(description="lunch/dinner，默认 lunch")] = "lunch",
):
    """查询今日餐谱（上海业务日）；不含库存字段，详情页或下单接口另行查询。"""
    return success(
        data=get_today_menu(db, store_id=int(store_ctx.store_id), meal_period=meal_period),
        msg="获取成功",
    )


@router.get("/tomorrow")
def tomorrow_menu(
    db: SessionDep,
    store_ctx: PublicStoreContext = Depends(public_store_dep),
    meal_period: Annotated[str, Query(description="lunch/dinner，默认 lunch")] = "lunch",
):
    """查询明日餐谱（上海业务日）。"""
    return success(
        data=get_tomorrow_menu(db, store_id=int(store_ctx.store_id), meal_period=meal_period),
        msg="获取成功",
    )


@router.get("/weekly")
def weekly_menu(
    db: SessionDep,
    store_ctx: PublicStoreContext = Depends(public_store_dep),
    week_start: Annotated[
        date | None,
        Query(description="该周任意一天；将归一化为当周周一。不传则按上海当前日期取本周"),
    ] = None,
    as_of_date: Annotated[
        date | None,
        Query(
            description=(
                "业务参考日（上海日历日 YYYY-MM-DD），通常为客户端『今天』。"
                "仅 ``include_stock=true`` 时用于加速订阅份数统计；不传则服务端取当前上海日期。"
            )
        ),
    ] = None,
    include_stock: Annotated[
        bool,
        Query(
            description=(
                "是否返回单次卡库存字段。列表页建议 false（仅查排餐与菜品，显著更快）；"
                "精确库存请用 ``/menu/detail/{dish_id}?service_date=`` 或下单接口校验。"
            )
        ),
    ] = False,
    stock_dates: Annotated[
        str | None,
        Query(
            description=(
                "include_stock=true 时生效：仅计算这些供餐日的库存，逗号分隔 YYYY-MM-DD。"
                "不传则计算整周（兼容旧客户端）。"
            )
        ),
    ] = None,
    meal_period: Annotated[str, Query(description="lunch/dinner，默认 lunch")] = "lunch",
):
    """一周菜单（周一至周日）：每日 `date`、`dish_id`（可空）、`title`/`desc`/`pic`。详情用 `dish_id` 调 `/menu/detail/{dish_id}`。无需登录。"""
    return success(
        data=get_weekly_menu(
            db,
            week_start,
            store_id=int(store_ctx.store_id),
            as_of_date=as_of_date,
            include_stock=include_stock,
            stock_dates=_parse_stock_dates(stock_dates),
            meal_period=meal_period,
        ),
        msg="获取成功",
    )


@router.get("/detail/{dish_id}")
def menu_detail(
    dish_id: int,
    db: SessionDep,
    store_ctx: PublicStoreContext = Depends(public_store_dep),
    service_date: Annotated[
        date | None,
        Query(description="供餐日 YYYY-MM-DD；传则返回该日单次卡剩余库存等字段"),
    ] = None,
    meal_period: Annotated[str, Query(description="lunch/dinner，默认 lunch")] = "lunch",
):
    """餐品详情，dish_id 为菜品库主键，与周列表项中 `dish_id` 一致。无需登录。"""
    return success(
        data=get_menu_detail_by_dish_id(
            db,
            dish_id,
            service_date=service_date,
            store_id=int(store_ctx.store_id),
            meal_period=meal_period,
        ),
        msg="获取成功",
    )
