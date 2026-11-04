"""包装结存、入库、校对、流水和预警。"""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.packaging.deps import packaging_store_id
from app.core.deps import SessionDep, admin_staff_subject
from app.schemas.packaging.stock import PackagingPurchaseIn, PackagingStocktakeIn
from app.services.packaging import stock_command_service as stock_svc
from app.utils.response import success

router = APIRouter(tags=["管理端-包装库存"])


@router.get("/stocks")
def list_packaging_stocks(
    db: SessionDep,
    admin_username: str = Depends(admin_staff_subject),
    store_id: int = Depends(packaging_store_id),
):
    _ = admin_username
    rows = stock_svc.list_stocks(db, store_id=store_id)
    return success(data=rows, msg="获取成功")


@router.get("/alerts")
def list_packaging_alerts(
    db: SessionDep,
    admin_username: str = Depends(admin_staff_subject),
    store_id: int = Depends(packaging_store_id),
):
    """结存页用的完整预警名单。系统消息正文超长时以这里为准。"""
    _ = admin_username
    rows = [row for row in stock_svc.list_stocks(db, store_id=store_id) if row["low"]]
    return success(data=rows, msg="获取成功")


@router.post("/purchase")
def purchase_packaging(
    body: PackagingPurchaseIn,
    db: SessionDep,
    admin_username: str = Depends(admin_staff_subject),
    store_id: int = Depends(packaging_store_id),
):
    row = stock_svc.purchase_in(
        db,
        store_id=store_id,
        sku_id=body.sku_id,
        qty=body.qty,
        operator=admin_username,
        remark=body.remark,
        biz_date=body.biz_date,
    )
    return success(data=row, msg="已入库")


@router.post("/stocktake")
def stocktake_packaging(
    body: PackagingStocktakeIn,
    db: SessionDep,
    admin_username: str = Depends(admin_staff_subject),
    store_id: int = Depends(packaging_store_id),
):
    """每周实盘。22 点之后改过的日总份不会回写，差额在这里收口。"""
    rows = stock_svc.stocktake(
        db,
        store_id=store_id,
        lines=[(line.sku_id, line.actual_qty) for line in body.lines],
        operator=admin_username,
        biz_date=body.biz_date,
    )
    return success(data=rows, msg="校对已保存")


@router.get("/txns")
def list_packaging_txns(
    db: SessionDep,
    admin_username: str = Depends(admin_staff_subject),
    store_id: int = Depends(packaging_store_id),
    sku_id: Annotated[int | None, Query()] = None,
    biz_date_from: Annotated[date | None, Query()] = None,
    biz_date_to: Annotated[date | None, Query()] = None,
):
    _ = admin_username
    rows = stock_svc.list_txns(
        db,
        store_id=store_id,
        sku_id=sku_id,
        biz_date_from=biz_date_from,
        biz_date_to=biz_date_to,
    )
    return success(data=rows, msg="获取成功")
