"""商城零售订单（普通商品）：创建、支付、列表与后台履约。"""

from __future__ import annotations

import logging
import secrets
from datetime import date, timedelta
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session

from app.core.timeutil import beijing_now_naive, today_shanghai
from app.integrations.wechat_pay_v2 import (
    WeChatPayV2Error,
    WechatPayNotifyParsed,
    build_miniprogram_pay_params,
    query_order_by_out_trade_no,
    unified_order_jsapi,
    yuan_decimal_to_fen,
)
from app.models.enums import CouponLockedOrderBiz
from app.models.member import Member
from app.models.member_address import MemberAddress
from app.models.store_retail_category import StoreRetailCategory
from app.models.store_retail_order import StoreRetailOrder
from app.models.store_retail_product import StoreRetailProduct
from app.schemas.store_retail_order import (
    AdminStoreRetailOrderListOut,
    StoreRetailOrderCreateIn,
    StoreRetailOrderOut,
)
from app.services.marketing.coupon_checkout_service import (
    CouponCheckoutContext,
    lock_member_coupon_for_order,
    mark_member_coupon_used_for_order,
    release_member_coupon_for_order,
)
from app.services.member.member_address_service import (
    delivery_region_name_map,
    full_address_line,
    routing_area_label,
)
from app.services.order.single_meal_order_service import primary_courier_for_region_id
from app.services.shared.store_config_service import get_store_base_delivery_fee_yuan, get_store_config
from app.services.shared.tenant_integration_service import (
    assert_tenant_pay_config_ready,
    get_merged_pay_config,
)
logger = logging.getLogger(__name__)

UNPAID_STORE_RETAIL_ORDER_EXPIRE_MINUTES = 30
_FULFILLMENT_SF_AWAITING_PICKUP = "sf_awaiting_pickup"
_RETAIL_STOP_PREFIX = "retail-sro-"


def _format_amount_yuan(v: Decimal) -> str:
    return f"{v.quantize(Decimal('0.01')):.2f}"


def _new_temp_out_trade_no() -> str:
    return f"T{secrets.token_hex(14)}"[:32]


def _final_out_trade_no(order_id: int) -> str:
    s = f"OKR{order_id}"
    if len(s) > 32:
        raise HTTPException(status_code=500, detail="订单号超长")
    return s


def _unpaid_expire_cutoff():
    return beijing_now_naive() - timedelta(minutes=UNPAID_STORE_RETAIL_ORDER_EXPIRE_MINUTES)


def _assert_retail_product_orderable(db: Session, *, product: StoreRetailProduct, store_id: int) -> None:
    if int(product.store_id) != int(store_id):
        raise HTTPException(status_code=404, detail="商品不存在或已下架")
    if not bool(product.is_on_shelf):
        raise HTTPException(status_code=400, detail="商品已下架")
    if product.category_id is not None:
        cat = db.get(StoreRetailCategory, int(product.category_id))
        if not cat or not bool(cat.is_active) or int(cat.store_id) != int(store_id):
            raise HTTPException(status_code=400, detail="商品分类已停用")


def _compute_retail_order_amount(
    db: Session, *, unit_price: Decimal, quantity: int, store_pickup: bool, store_id: int
) -> Decimal:
    """与单次点餐一致：销售价为配送价；自提时减门店固定配送费。"""
    unit_dec = Decimal(unit_price).quantize(Decimal("0.01"))
    if store_pickup:
        fee = get_store_base_delivery_fee_yuan(db, store_id=int(store_id))
        unit_dec = max(Decimal("0.01"), (unit_dec - fee).quantize(Decimal("0.01")))
    return (unit_dec * Decimal(quantity)).quantize(Decimal("0.01"))


def _row_address_summary(db: Session, row: StoreRetailOrder) -> str:
    if bool(row.store_pickup):
        return "门店自提"
    addr = db.get(MemberAddress, row.member_address_id) if row.member_address_id else None
    if addr:
        nm = delivery_region_name_map(
            db, {int(addr.delivery_region_id)} if addr.delivery_region_id else set()
        )
        ar = routing_area_label(addr, nm)
        detail_line = full_address_line(addr.map_location_text, addr.door_detail)
        return f"{ar} {detail_line}".strip()
    return (row.routing_area or "").strip() or "—"


def _row_to_out(db: Session, row: StoreRetailOrder, *, address_summary: str | None = None) -> StoreRetailOrderOut:
    cfg = get_store_config(db, store_id=int(row.store_id))
    return StoreRetailOrderOut(
        id=int(row.id),
        out_trade_no=str(row.out_trade_no or ""),
        retail_product_id=int(row.retail_product_id),
        product_title=str(row.product_title or ""),
        member_address_id=int(row.member_address_id) if row.member_address_id is not None else None,
        store_pickup=bool(row.store_pickup),
        quantity=int(row.quantity or 1),
        fulfillment_date=row.fulfillment_date,
        routing_area=str(row.routing_area or ""),
        amount_yuan=_format_amount_yuan(Decimal(row.amount_yuan)),
        original_amount_yuan=(
            _format_amount_yuan(Decimal(row.original_amount_yuan))
            if row.original_amount_yuan is not None
            else None
        ),
        coupon_discount_yuan=(
            _format_amount_yuan(Decimal(row.coupon_discount_yuan))
            if row.coupon_discount_yuan is not None
            else None
        ),
        member_coupon_id=int(row.member_coupon_id) if row.member_coupon_id is not None else None,
        pay_status=str(row.pay_status or ""),
        pay_channel=row.pay_channel,
        fulfillment_status=str(row.fulfillment_status or ""),
        courier_id=row.courier_id,
        sf_same_city_push_id=int(row.sf_same_city_push_id) if row.sf_same_city_push_id is not None else None,
        sf_order_id=(row.sf_order_id or "").strip() or None,
        address_summary=address_summary if address_summary is not None else _row_address_summary(db, row),
        store_contact_phone=cfg.store_contact_phone,
        created_at=row.created_at,
    )


def expire_stale_unpaid_store_retail_orders(db: Session, *, member_id: int | None = None) -> int:
    cutoff = _unpaid_expire_cutoff()
    filters = [
        StoreRetailOrder.pay_status == "未支付",
        StoreRetailOrder.fulfillment_status == "pending",
        StoreRetailOrder.created_at < cutoff,
    ]
    if member_id is not None:
        filters.append(StoreRetailOrder.member_id == int(member_id))
    stale_ids = list(db.scalars(select(StoreRetailOrder.id).where(*filters)).all())
    if not stale_ids:
        return 0
    for oid in stale_ids:
        release_member_coupon_for_order(
            db, order_biz=CouponLockedOrderBiz.STORE_RETAIL, order_id=int(oid)
        )
    db.execute(
        update(StoreRetailOrder)
        .where(StoreRetailOrder.id.in_(stale_ids))
        .values(fulfillment_status="cancelled", courier_id=None)
    )
    db.commit()
    return len(stale_ids)


def _assert_no_pending_unpaid_retail_order(db: Session, member_id: int) -> None:
    oid = db.scalars(
        select(StoreRetailOrder.id)
        .where(
            StoreRetailOrder.member_id == int(member_id),
            StoreRetailOrder.pay_status == "未支付",
            StoreRetailOrder.fulfillment_status != "cancelled",
        )
        .order_by(StoreRetailOrder.id.desc())
        .limit(1)
    ).first()
    if oid is not None:
        raise HTTPException(
            status_code=409,
            detail=f"您有未支付的商城订单（#{int(oid)}），请先完成支付或取消后再下单",
        )


def create_store_retail_order(
    db: Session, member_id: int, body: StoreRetailOrderCreateIn
) -> StoreRetailOrderOut:
    expire_stale_unpaid_store_retail_orders(db, member_id=member_id)
    _assert_no_pending_unpaid_retail_order(db, member_id)

    prod = db.get(StoreRetailProduct, int(body.retail_product_id))
    if not prod:
        raise HTTPException(status_code=404, detail="商品不存在或已下架")

    mem = db.get(Member, member_id)
    if not mem or mem.deleted_at is not None:
        raise HTTPException(status_code=404, detail="用户不存在")

    _assert_retail_product_orderable(db, product=prod, store_id=int(mem.store_id))

    qty = int(body.quantity)
    if qty < 1 or qty > 50:
        raise HTTPException(status_code=400, detail="数量须在 1～50 之间")

    if body.store_pickup:
        address_summary = "门店自提"
        area = "门店自提"
        addr_id = None
    else:
        addr = db.get(MemberAddress, body.member_address_id)
        if not addr or int(addr.member_id) != int(member_id):
            raise HTTPException(status_code=404, detail="配送地址不存在")
        nm = delivery_region_name_map(db, {int(addr.delivery_region_id)} if addr.delivery_region_id else set())
        area = routing_area_label(addr, nm)
        detail_line = full_address_line(addr.map_location_text, addr.door_detail)
        address_summary = f"{area} {detail_line}".strip()
        addr_id = int(addr.id)

    amt = _compute_retail_order_amount(
        db,
        unit_price=Decimal(prod.unit_price_yuan),
        quantity=qty,
        store_pickup=bool(body.store_pickup),
        store_id=int(mem.store_id),
    )

    row = StoreRetailOrder(
        tenant_id=int(mem.tenant_id),
        store_id=int(mem.store_id),
        out_trade_no=_new_temp_out_trade_no(),
        member_id=member_id,
        retail_product_id=int(prod.id),
        product_title=(prod.title or "").strip() or "商品",
        member_address_id=addr_id,
        store_pickup=bool(body.store_pickup),
        quantity=qty,
        fulfillment_date=today_shanghai(),
        routing_area=area,
        amount_yuan=amt,
        pay_status="未支付",
        pay_channel=None,
        fulfillment_status="pending",
        courier_id=None,
    )
    db.add(row)
    db.flush()
    row.out_trade_no = _final_out_trade_no(int(row.id))

    if body.member_coupon_id is not None:
        ctx = CouponCheckoutContext(
            checkout_biz=CouponLockedOrderBiz.STORE_RETAIL,
            original_amount_yuan=amt,
            retail_product_id=int(prod.id),
            retail_category_id=int(prod.category_id) if prod.category_id is not None else None,
        )
        orig, disc, payable = lock_member_coupon_for_order(
            db,
            member_coupon_id=int(body.member_coupon_id),
            member_id=int(member_id),
            store_id=int(mem.store_id),
            ctx=ctx,
            order_id=int(row.id),
        )
        row.original_amount_yuan = orig
        row.coupon_discount_yuan = disc
        row.amount_yuan = payable
        row.member_coupon_id = int(body.member_coupon_id)

    db.commit()
    db.refresh(row)
    return _row_to_out(db, row, address_summary=address_summary)


def get_member_store_retail_order(db: Session, member_id: int, order_id: int) -> StoreRetailOrderOut:
    expire_stale_unpaid_store_retail_orders(db, member_id=member_id)
    row = db.get(StoreRetailOrder, int(order_id))
    if not row or int(row.member_id) != int(member_id):
        raise HTTPException(status_code=404, detail="订单不存在")
    return _row_to_out(db, row)


def list_member_store_retail_orders(
    db: Session,
    member_id: int,
    *,
    page: int = 1,
    page_size: int = 20,
    list_status: str | None = None,
) -> tuple[list[StoreRetailOrderOut], int]:
    expire_stale_unpaid_store_retail_orders(db, member_id=member_id)
    page = max(1, page)
    page_size = min(50, max(1, page_size))
    ls = (list_status or "all").strip().lower()
    filters: list = [StoreRetailOrder.member_id == int(member_id)]
    if ls == "pending_pay":
        filters.append(StoreRetailOrder.pay_status == "未支付")
        filters.append(StoreRetailOrder.fulfillment_status == "pending")
    elif ls == "pending_delivery":
        filters.append(StoreRetailOrder.pay_status == "已支付")
        filters.append(
            StoreRetailOrder.fulfillment_status.in_(("pending", _FULFILLMENT_SF_AWAITING_PICKUP, "accepted"))
        )
    elif ls == "completed":
        filters.append(StoreRetailOrder.pay_status == "已支付")
        filters.append(StoreRetailOrder.fulfillment_status == "delivered")
    elif ls != "all":
        pass

    total = int(db.scalar(select(func.count()).select_from(StoreRetailOrder).where(*filters)) or 0)
    rows = db.scalars(
        select(StoreRetailOrder)
        .where(*filters)
        .order_by(StoreRetailOrder.created_at.desc(), StoreRetailOrder.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return [_row_to_out(db, r) for r in rows], total


def _revalidate_product_before_pay(db: Session, row: StoreRetailOrder) -> None:
    prod = db.get(StoreRetailProduct, int(row.retail_product_id))
    if not prod:
        raise HTTPException(status_code=400, detail="商品已下架，请重新下单")
    _assert_retail_product_orderable(db, product=prod, store_id=int(row.store_id))


def prepare_wechat_jsapi_for_retail_order(
    db: Session, member_id: int, order_id: int, client_ip: str
) -> dict[str, str]:
    expire_stale_unpaid_store_retail_orders(db, member_id=member_id)
    order = db.get(StoreRetailOrder, order_id)
    if not order or int(order.member_id) != int(member_id):
        raise HTTPException(status_code=404, detail="订单不存在")
    if order.pay_status == "已支付":
        raise HTTPException(status_code=400, detail="订单已支付")
    if order.pay_status == "已退款":
        raise HTTPException(status_code=400, detail="订单已退款")
    if str(order.fulfillment_status or "").strip().lower() == "cancelled":
        raise HTTPException(status_code=400, detail="订单已超时关闭，请重新下单")

    _revalidate_product_before_pay(db, order)

    pay_cfg = assert_tenant_pay_config_ready(db, int(order.tenant_id), store_id=int(order.store_id))

    member = db.get(Member, member_id)
    if not member or member.deleted_at is not None:
        raise HTTPException(status_code=404, detail="用户不存在")
    openid = (member.wx_mini_openid or "").strip()
    if not openid:
        raise HTTPException(status_code=400, detail="请使用微信小程序授权登录后再支付")

    body_desc = (order.product_title or "商城商品")[:40]
    out_no = (order.out_trade_no or "").strip()
    if not out_no:
        raise HTTPException(status_code=500, detail="订单缺少商户单号")

    try:
        prepay_id = unified_order_jsapi(
            out_trade_no=out_no,
            body=body_desc,
            total_fee_fen=yuan_decimal_to_fen(order.amount_yuan),
            openid=openid,
            spbill_create_ip=client_ip,
            pay=pay_cfg,
        )
    except WeChatPayV2Error as e:
        raise HTTPException(status_code=e.status_code, detail=str(e)) from e

    return build_miniprogram_pay_params(
        prepay_id, appid=pay_cfg.wx_mini_appid, api_key=pay_cfg.wechat_pay_api_key
    )


def _notify_store_retail_order_paid(db: Session, order: StoreRetailOrder) -> None:
    from app.services.admin.admin_system_notification_service import create_store_retail_order_paid_notification

    member = db.get(Member, int(order.member_id))
    try:
        with db.begin_nested():
            create_store_retail_order_paid_notification(
                db,
                store_id=int(order.store_id),
                order_id=int(order.id),
                product_title=order.product_title,
                quantity=int(order.quantity or 1),
                amount_yuan=_format_amount_yuan(Decimal(order.amount_yuan)),
                store_pickup=bool(order.store_pickup),
                member_id=int(order.member_id),
                member_phone=(member.phone if member else None),
                member_name=(member.name if member else None),
                order_created_at=order.created_at,
                out_trade_no=str(order.out_trade_no or ""),
                pay_channel=str(order.pay_channel or ""),
            )
    except Exception:
        logger.exception("商城订单支付成功但系统消息写入失败 order_id=%s", int(order.id))


def finalize_store_retail_order_wechat_pay(
    db: Session, parsed: WechatPayNotifyParsed
) -> tuple[bool, str]:
    order = db.scalar(
        select(StoreRetailOrder)
        .where(StoreRetailOrder.out_trade_no == parsed.out_trade_no)
        .with_for_update()
    )
    if not order:
        return False, "order_not_found"
    if order.pay_status == "已退款":
        return False, "order_refunded"
    if order.pay_status == "已支付":
        mark_member_coupon_used_for_order(
            db, order_biz=CouponLockedOrderBiz.STORE_RETAIL, order_id=int(order.id)
        )
        db.commit()
        return True, "already_paid"

    expect_fen = yuan_decimal_to_fen(order.amount_yuan)
    if parsed.total_fee != expect_fen:
        logger.error(
            "商城订单微信回调金额不一致 out=%s expect=%s got=%s",
            parsed.out_trade_no,
            expect_fen,
            parsed.total_fee,
        )
        return False, "amount_mismatch"

    order.pay_status = "已支付"
    order.pay_channel = "微信"
    tid = (parsed.transaction_id or "").strip()
    order.wx_transaction_id = tid or order.wx_transaction_id
    if str(order.fulfillment_status or "").strip().lower() == "cancelled":
        order.fulfillment_status = "pending"
    if bool(order.store_pickup):
        order.courier_id = None
    else:
        pay_addr = db.get(MemberAddress, order.member_address_id)
        order.courier_id = primary_courier_for_region_id(
            db, int(pay_addr.delivery_region_id) if pay_addr and pay_addr.delivery_region_id else None
        )
    _notify_store_retail_order_paid(db, order)
    mark_member_coupon_used_for_order(
        db, order_biz=CouponLockedOrderBiz.STORE_RETAIL, order_id=int(order.id)
    )
    db.commit()
    return True, "paid"


def sync_store_retail_order_from_wechat_or_raise(db: Session, member_id: int, order_id: int) -> None:
    ok, reason = sync_store_retail_order_from_wechat_query(db, member_id, order_id)
    if ok:
        return
    if reason == "order_not_found":
        raise HTTPException(status_code=404, detail="订单不存在")
    if reason == "missing_out_trade_no":
        raise HTTPException(status_code=500, detail="订单缺少商户单号")
    if reason == "order_refunded":
        raise HTTPException(status_code=400, detail="订单已退款")
    if reason == "not_paid":
        raise HTTPException(status_code=400, detail="微信侧尚未支付成功，请稍候再试")
    raise HTTPException(status_code=400, detail=f"支付同步失败：{reason}")


def sync_store_retail_order_from_wechat_query(
    db: Session, member_id: int, order_id: int
) -> tuple[bool, str]:
    order = db.get(StoreRetailOrder, order_id)
    if not order or int(order.member_id) != int(member_id):
        return False, "order_not_found"
    out_no = (order.out_trade_no or "").strip()
    if not out_no:
        return False, "missing_out_trade_no"
    if (order.pay_status or "").strip() == "已退款":
        return False, "order_refunded"
    if (order.pay_status or "").strip() == "已支付":
        return True, "already_synced"

    pay_cfg = get_merged_pay_config(db, int(order.tenant_id), store_id=int(order.store_id))
    data = query_order_by_out_trade_no(out_no, pay=pay_cfg)
    trade_state = (data.get("trade_state") or "").strip().upper()
    if trade_state not in ("SUCCESS", "REFUND"):
        return False, "not_paid"

    parsed = WechatPayNotifyParsed(
        out_trade_no=out_no,
        transaction_id=(data.get("transaction_id") or "").strip(),
        total_fee=int(data.get("total_fee") or 0),
    )
    ok, reason = finalize_store_retail_order_wechat_pay(db, parsed)
    if ok:
        return True, "synced"
    return False, reason


def member_cancel_store_retail_order(db: Session, *, member_id: int, order_id: int) -> str:
    row = db.get(StoreRetailOrder, int(order_id))
    if not row or int(row.member_id) != int(member_id):
        raise HTTPException(status_code=404, detail="订单不存在")
    pay = (row.pay_status or "").strip()
    fs = str(row.fulfillment_status or "").strip().lower()
    if fs in ("delivered", "cancelled"):
        raise HTTPException(status_code=400, detail="订单当前状态不可取消")
    if pay == "已支付":
        if row.store_pickup:
            raise HTTPException(status_code=400, detail="订单已进入待取货阶段，请联系客服处理")
        if fs != "pending":
            raise HTTPException(status_code=400, detail="订单已进入配送流程，请联系客服处理")
        from app.services.admin.store_retail_order_admin_service import admin_wechat_refund_store_retail_order

        admin_wechat_refund_store_retail_order(db, order_id=int(order_id), store_id=int(row.store_id))
        row = db.get(StoreRetailOrder, order_id)
        if row is None:
            raise HTTPException(status_code=404, detail="订单不存在")
        return "订单已取消，款项将原路退回"

    row.fulfillment_status = "cancelled"
    row.courier_id = None
    release_member_coupon_for_order(
        db, order_biz=CouponLockedOrderBiz.STORE_RETAIL, order_id=int(order_id)
    )
    db.add(row)
    db.commit()
    return "订单已取消"


def store_retail_fulfillment_allows_dispatch(fs: str | None) -> bool:
    return str(fs or "").strip().lower() in ("pending", "sf_cancelled")
