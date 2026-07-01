"""会员端：商城零售订单 API。"""

from typing import Annotated

from fastapi import APIRouter, Query, Request

from app.core.deps import MemberIdScoped, SessionDep
from app.core.limiter import limiter
from app.integrations.wechat_pay_v2 import resolve_request_client_ip
from app.schemas.store_retail_order import StoreRetailOrderCreateIn
from app.services.client.store_retail_order_service import (
    create_store_retail_order,
    get_member_store_retail_order,
    list_member_store_retail_orders,
    member_cancel_store_retail_order,
    prepare_wechat_jsapi_for_retail_order,
    sync_store_retail_order_from_wechat_or_raise,
)
from app.utils.response import dump_model, page_response, success

router = APIRouter(prefix="/user", tags=["会员端-商城订单"])


@router.get("/retail-orders")
def list_retail_orders_me(
    db: SessionDep,
    member_id: MemberIdScoped,
    page: int = 1,
    page_size: int = 20,
    list_status: Annotated[
        str | None,
        Query(description="all | pending_pay | pending_delivery | completed"),
    ] = None,
):
    """商城零售订单列表（普通商品）。"""
    items, total = list_member_store_retail_orders(
        db, member_id, page=page, page_size=page_size, list_status=list_status
    )
    return page_response(
        items=[dump_model(x) for x in items],
        total=total,
        page=page,
        page_size=page_size,
        msg="获取成功",
    )


@router.get("/retail-orders/{order_id}")
def read_retail_order_me(
    order_id: int,
    db: SessionDep,
    member_id: MemberIdScoped,
):
    """商城零售订单详情。"""
    out = get_member_store_retail_order(db, member_id, order_id)
    return success(data=dump_model(out), msg="获取成功")


@router.post("/retail-orders")
@limiter.limit("30/minute")
def create_retail_order_me(
    request: Request,
    body: StoreRetailOrderCreateIn,
    db: SessionDep,
    member_id: MemberIdScoped,
):
    """创建商城零售未支付订单；随后调 pay/wechat-jsapi。"""
    _ = request
    out = create_store_retail_order(db, member_id, body)
    return success(data=dump_model(out), msg="订单已创建，请继续支付")


@router.post("/retail-orders/{order_id}/pay/wechat-jsapi")
@limiter.limit("30/minute")
def prepay_retail_order_wechat(
    request: Request,
    order_id: int,
    db: SessionDep,
    member_id: MemberIdScoped,
):
    """微信统一下单（JSAPI）。"""
    xf = request.headers.get("x-forwarded-for")
    ip = resolve_request_client_ip(xf, request.client.host if request.client else None)
    params = prepare_wechat_jsapi_for_retail_order(db, member_id, order_id, ip)
    return success(data=params, msg="获取支付参数成功")


@router.post("/retail-orders/{order_id}/sync-wechat-pay")
@limiter.limit("30/minute")
def sync_retail_order_after_pay(
    request: Request,
    order_id: int,
    db: SessionDep,
    member_id: MemberIdScoped,
):
    """支付成功后主动拉单同步入账。"""
    _ = request
    sync_store_retail_order_from_wechat_or_raise(db, member_id, order_id)
    out = get_member_store_retail_order(db, member_id, order_id)
    return success(data=dump_model(out), msg="支付结果已同步")


@router.post("/retail-orders/{order_id}/cancel")
@limiter.limit("30/minute")
def cancel_retail_order_me(
    request: Request,
    order_id: int,
    db: SessionDep,
    member_id: MemberIdScoped,
):
    """会员取消商城零售订单。"""
    _ = request
    msg = member_cancel_store_retail_order(db, member_id=member_id, order_id=order_id)
    out = get_member_store_retail_order(db, member_id, order_id)
    return success(data=dump_model(out), msg=msg)
