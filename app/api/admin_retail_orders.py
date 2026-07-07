"""管理端：商城零售订单 API。"""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.deps import SessionDep, admin_staff_subject, require_admin_tenant_store
from app.core.timeutil import today_shanghai
from app.schemas.store_retail_order import (
    StoreRetailAssignCourierIn,
    StoreRetailBatchAssignCourierIn,
    StoreRetailCancelIn,
    StoreRetailOrderIdsIn,
    StoreRetailOrderRemarkPatchIn,
)
from app.services.admin.store_retail_order_admin_service import (
    admin_assign_courier_store_retail_order,
    admin_cancel_store_retail_order,
    admin_mark_store_retail_order_delivered,
    admin_wechat_refund_store_retail_order,
    bulk_admin_assign_courier_store_retail_orders,
    bulk_admin_mark_store_retail_orders_delivered,
    bulk_push_store_retail_orders_to_sf,
    list_admin_store_retail_orders_by_order_day,
    push_store_retail_order_to_sf,
    update_admin_store_retail_order_remark,
)
from app.utils.response import dump_model, page_response, success

router = APIRouter(prefix="/admin", tags=["管理端-商城订单"])


@router.get("/orders/daily/retail-orders")
def admin_orders_daily_retail_orders(
    db: SessionDep,
    admin_username: str = Depends(admin_staff_subject),
    store_id: Annotated[int, Query(description="门店 id，默认 1")] = 1,
    order_date: Annotated[
        date | None,
        Query(description="下单业务日（上海日历日），默认当天"),
    ] = None,
    q: Annotated[str | None, Query(description="会员手机前缀或姓名模糊")] = None,
    fulfillment_phase: Annotated[
        str | None,
        Query(
            description=(
                "配送阶段：awaiting_accept 待接单 / pending_ship 待发货 / "
                "in_delivery 配送中 / delivered 已完成 / after_sale 退单售后"
            ),
        ),
    ] = None,
    page: int = 1,
    page_size: int = 20,
):
    """订单管理：当日商城零售订单（按下单日 + 配送阶段 Tab）。"""
    _, store_id = require_admin_tenant_store(db, admin_username=admin_username, store_id=store_id)
    day = order_date or today_shanghai()
    items, total = list_admin_store_retail_orders_by_order_day(
        db,
        store_id=store_id,
        order_day=day,
        q=q,
        fulfillment_phase=fulfillment_phase,
        page=max(1, page),
        page_size=min(max(1, page_size), 100),
    )
    return page_response(
        items=[dump_model(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
        msg="获取成功",
    )


@router.patch("/orders/retail-orders/{order_id}/remark")
def admin_retail_order_patch_remark(
    order_id: int,
    body: StoreRetailOrderRemarkPatchIn,
    db: SessionDep,
    admin_username: str = Depends(admin_staff_subject),
    store_id: Annotated[int, Query(description="门店 id，默认 1")] = 1,
):
    """商城零售：更新后台备注（不对会员端展示）。"""
    _, store_id = require_admin_tenant_store(db, admin_username=admin_username, store_id=store_id)
    try:
        out = update_admin_store_retail_order_remark(
            db,
            order_id=int(order_id),
            store_id=int(store_id),
            remark=body.remark,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return success(data=dump_model(out), msg="备注已更新")


@router.post("/orders/retail-orders/{order_id}/dispatch/sf-retail")
def admin_retail_order_dispatch_sf(
    order_id: int,
    db: SessionDep,
    admin_username: str = Depends(admin_staff_subject),
    store_id: Annotated[int, Query(description="门店 id，默认 1")] = 1,
):
    """商城零售：推送到顺丰。"""
    _, store_id = require_admin_tenant_store(db, admin_username=admin_username, store_id=store_id)
    try:
        out = push_store_retail_order_to_sf(db, order_id=int(order_id), store_id=int(store_id))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return success(data=out, msg=out.get("message", "已推送"))


@router.post("/orders/retail-orders/batch-dispatch/sf-retail")
def admin_retail_orders_batch_dispatch_sf(
    body: StoreRetailOrderIdsIn,
    db: SessionDep,
    admin_username: str = Depends(admin_staff_subject),
    store_id: Annotated[int, Query(description="门店 id，默认 1")] = 1,
):
    _, store_id = require_admin_tenant_store(db, admin_username=admin_username, store_id=store_id)
    out = bulk_push_store_retail_orders_to_sf(
        db, order_ids=[int(x) for x in body.order_ids], store_id=int(store_id)
    )
    return success(data=out, msg="批量推顺丰处理完成")


@router.post("/orders/retail-orders/batch-dispatch/store-courier")
def admin_retail_orders_batch_dispatch_courier(
    body: StoreRetailBatchAssignCourierIn,
    db: SessionDep,
    admin_username: str = Depends(admin_staff_subject),
    store_id: Annotated[int, Query(description="门店 id，默认 1")] = 1,
):
    tid, store_id = require_admin_tenant_store(db, admin_username=admin_username, store_id=store_id)
    out = bulk_admin_assign_courier_store_retail_orders(
        db,
        order_ids=[int(x) for x in body.order_ids],
        store_id=int(store_id),
        courier_id=body.courier_id,
        tenant_id=int(tid),
    )
    return success(data=out, msg="批量指派处理完成")


@router.post("/orders/retail-orders/{order_id}/dispatch/store-courier")
def admin_retail_order_dispatch_courier(
    order_id: int,
    body: StoreRetailAssignCourierIn,
    db: SessionDep,
    admin_username: str = Depends(admin_staff_subject),
    store_id: Annotated[int, Query(description="门店 id，默认 1")] = 1,
):
    tid, store_id = require_admin_tenant_store(db, admin_username=admin_username, store_id=store_id)
    try:
        out = admin_assign_courier_store_retail_order(
            db,
            order_id=int(order_id),
            store_id=int(store_id),
            courier_id=body.courier_id,
            tenant_id=int(tid),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return success(data=dump_model(out), msg="已指派配送员")


@router.post("/orders/retail-orders/{order_id}/mark-delivered")
def admin_retail_order_mark_delivered(
    order_id: int,
    db: SessionDep,
    admin_username: str = Depends(admin_staff_subject),
    store_id: Annotated[int, Query(description="门店 id，默认 1")] = 1,
):
    _, store_id = require_admin_tenant_store(db, admin_username=admin_username, store_id=store_id)
    try:
        msg = admin_mark_store_retail_order_delivered(db, order_id=int(order_id), store_id=int(store_id))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return success(data=None, msg=msg)


@router.post("/orders/retail-orders/batch-mark-delivered")
def admin_retail_orders_batch_mark_delivered(
    body: StoreRetailOrderIdsIn,
    db: SessionDep,
    admin_username: str = Depends(admin_staff_subject),
    store_id: Annotated[int, Query(description="门店 id，默认 1")] = 1,
):
    _, store_id = require_admin_tenant_store(db, admin_username=admin_username, store_id=store_id)
    out = bulk_admin_mark_store_retail_orders_delivered(
        db, order_ids=[int(x) for x in body.order_ids], store_id=int(store_id)
    )
    return success(data=out, msg="批量标记完成")


@router.post("/orders/retail-orders/{order_id}/cancel")
def admin_retail_order_cancel(
    order_id: int,
    body: StoreRetailCancelIn,
    db: SessionDep,
    admin_username: str = Depends(admin_staff_subject),
    store_id: Annotated[int, Query(description="门店 id，默认 1")] = 1,
):
    _, store_id = require_admin_tenant_store(db, admin_username=admin_username, store_id=store_id)
    try:
        msg = admin_cancel_store_retail_order(
            db,
            order_id=int(order_id),
            store_id=int(store_id),
            cancel_reason=body.cancel_reason,
            cancel_sf=body.cancel_sf,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return success(data=None, msg=msg)


@router.post("/orders/retail-orders/{order_id}/refund/wechat")
def admin_retail_order_refund_wechat(
    order_id: int,
    db: SessionDep,
    admin_username: str = Depends(admin_staff_subject),
    store_id: Annotated[int, Query(description="门店 id，默认 1")] = 1,
):
    """商城零售：微信已支付订单全额原路退款。"""
    _, store_id = require_admin_tenant_store(db, admin_username=admin_username, store_id=store_id)
    try:
        out = admin_wechat_refund_store_retail_order(db, order_id=int(order_id), store_id=int(store_id))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return success(data=out, msg=out.get("message", "已退款"))
