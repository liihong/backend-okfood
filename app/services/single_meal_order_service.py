from __future__ import annotations

import logging
import secrets
from datetime import date, timedelta
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.integrations.wechat_pay_v2 import (
    WeChatPayV2Error,
    build_miniprogram_pay_params,
    unified_order_jsapi,
    verify_response_sign,
    wechat_pay_configured,
    yuan_decimal_to_fen,
)
from app.models.courier import Courier
from app.models.delivery_region import DeliveryRegion, DeliveryRegionCourier
from app.models.member import Member
from app.models.member_address import MemberAddress
from app.models.menu_dish import MenuDish
from app.models.menu_schedule import MenuSchedule
from app.models.single_meal_order import SingleMealOrder
from app.models.weekly_menu_slot import WeeklyMenuSlot
from app.schemas.courier import CourierTaskMemberOut
from app.schemas.single_meal_order import SingleMealOrderCreateIn, SingleMealOrderOut
from app.services.member_address_service import effective_routing_area

logger = logging.getLogger(__name__)


def _format_amount_yuan(v: Decimal) -> str:
    return f"{v.quantize(Decimal('0.01')):.2f}"


def _new_temp_out_trade_no() -> str:
    """插入前占位商户号，flush 后替换为 OKF{id}。"""
    return f"T{secrets.token_hex(14)}"[:32]


def _final_out_trade_no(order_id: int) -> str:
    s = f"OKF{order_id}"
    if len(s) > 32:
        raise HTTPException(status_code=500, detail="订单号超长")
    return s


def dish_planned_for_date(db: Session, dish_id: int, d: date) -> bool:
    if db.scalar(select(MenuSchedule.id).where(MenuSchedule.menu_date == d, MenuSchedule.dish_id == dish_id)):
        return True
    slots = db.scalars(select(WeeklyMenuSlot).where(WeeklyMenuSlot.dish_id == dish_id)).all()
    for s in slots:
        svc = s.week_start + timedelta(days=int(s.slot) - 1)
        if svc == d:
            return True
    return False


def primary_courier_for_area(db: Session, area_name: str) -> str | None:
    """按片区名取启用区域，优先 is_primary 骑手，否则 sort_order 最小且账号启用者。"""
    a = (area_name or "").strip()
    if not a:
        return None
    rid = db.scalar(
        select(DeliveryRegion.id).where(DeliveryRegion.is_active.is_(True), DeliveryRegion.name == a).limit(1)
    )
    if rid is None:
        return None
    cid = db.scalar(
        select(DeliveryRegionCourier.courier_id).where(
            DeliveryRegionCourier.region_id == rid,
            DeliveryRegionCourier.is_primary.is_(True),
        ).limit(1)
    )
    if cid:
        c = db.get(Courier, cid)
        if c and c.is_active:
            return str(cid)
    for cid2 in db.scalars(
        select(DeliveryRegionCourier.courier_id)
        .where(DeliveryRegionCourier.region_id == rid)
        .order_by(DeliveryRegionCourier.sort_order.asc(), DeliveryRegionCourier.id.asc())
    ).all():
        c = db.get(Courier, cid2)
        if c and c.is_active:
            return str(cid2)
    return None


def create_single_meal_order(db: Session, member_id: int, body: SingleMealOrderCreateIn) -> SingleMealOrderOut:
    dish = db.get(MenuDish, body.dish_id)
    if not dish or not dish.is_enabled:
        raise HTTPException(status_code=404, detail="餐品不存在或已停用")
    if dish.single_order_price_yuan is None:
        raise HTTPException(status_code=400, detail="该餐品暂未开放单点")
    if not dish_planned_for_date(db, int(dish.id), body.delivery_date):
        raise HTTPException(status_code=400, detail="所选日期未排该餐品")

    addr = db.get(MemberAddress, body.member_address_id)
    if not addr or int(addr.member_id) != int(member_id):
        raise HTTPException(status_code=404, detail="配送地址不存在")

    m = db.get(Member, member_id)
    if not m:
        raise HTTPException(status_code=404, detail="用户不存在")

    area = effective_routing_area(addr)
    amt = dish.single_order_price_yuan
    if amt is None:
        raise HTTPException(status_code=400, detail="该餐品暂未开放单点")

    detail_line = (addr.detail_address or "").strip()
    address_summary = f"{area} {detail_line}".strip()

    row = SingleMealOrder(
        out_trade_no=_new_temp_out_trade_no(),
        member_id=member_id,
        dish_id=int(dish.id),
        member_address_id=int(addr.id),
        delivery_date=body.delivery_date,
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
    db.commit()
    db.refresh(row)

    return SingleMealOrderOut(
        id=int(row.id),
        dish_id=int(row.dish_id),
        dish_title=str(dish.name),
        member_address_id=int(row.member_address_id),
        delivery_date=row.delivery_date,
        routing_area=row.routing_area,
        amount_yuan=_format_amount_yuan(Decimal(row.amount_yuan)),
        pay_status=row.pay_status,
        pay_channel=row.pay_channel,
        fulfillment_status=row.fulfillment_status,
        courier_id=row.courier_id,
        address_summary=address_summary,
    )


def prepare_wechat_jsapi_for_order(db: Session, member_id: int, order_id: int, client_ip: str) -> dict[str, str]:
    """调微信统一下单并返回小程序调起支付参数。"""
    if not wechat_pay_configured():
        raise HTTPException(status_code=503, detail="微信支付未配置或配置不完整（商户号、32位 API v2 密钥、回调 URL、小程序 AppId）")

    order = db.get(SingleMealOrder, order_id)
    if not order or int(order.member_id) != int(member_id):
        raise HTTPException(status_code=404, detail="订单不存在")
    if order.pay_status == "已支付":
        raise HTTPException(status_code=400, detail="订单已支付")

    member = db.get(Member, member_id)
    if not member:
        raise HTTPException(status_code=404, detail="用户不存在")
    openid = (member.wx_mini_openid or "").strip()
    if not openid:
        raise HTTPException(status_code=400, detail="请使用微信小程序授权登录后再支付")

    dish = db.get(MenuDish, order.dish_id)
    body_desc = (dish.name if dish else "") or "单次点餐"
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
        )
    except WeChatPayV2Error as e:
        raise HTTPException(status_code=e.status_code, detail=str(e)) from e

    return build_miniprogram_pay_params(prepay_id)


def apply_single_meal_order_wechat_notify(db: Session, data: dict[str, str]) -> tuple[bool, str]:
    """
    处理微信支付结果通知。
    返回 (是否应回复微信 SUCCESS, 日志/失败原因)。
    """
    if (data.get("return_code") or "").upper() != "SUCCESS":
        return False, (data.get("return_msg") or "return_fail")[:200]
    if not verify_response_sign(data):
        logger.error("微信回调签名校验失败: %s", {k: data.get(k) for k in ("out_trade_no", "result_code")})
        return False, "sign"
    if (data.get("result_code") or "").upper() != "SUCCESS":
        return False, (data.get("err_code_des") or data.get("err_code") or "result_fail")[:200]

    out_no = (data.get("out_trade_no") or "").strip()
    tx_id = (data.get("transaction_id") or "").strip()
    fee_s = (data.get("total_fee") or "").strip()
    if not out_no or not fee_s:
        return False, "missing_field"
    try:
        total_fee = int(fee_s)
    except ValueError:
        return False, "total_fee"

    order = db.scalar(select(SingleMealOrder).where(SingleMealOrder.out_trade_no == out_no).with_for_update())
    if not order:
        logger.warning("微信回调商户单号无匹配订单: %s", out_no)
        return False, "order_not_found"

    if order.pay_status == "已支付":
        return True, "already_paid"

    expect_fen = yuan_decimal_to_fen(order.amount_yuan)
    if total_fee != expect_fen:
        logger.error("微信回调金额不一致 out=%s expect_fen=%s got_fen=%s", out_no, expect_fen, total_fee)
        return False, "amount_mismatch"

    order.pay_status = "已支付"
    order.pay_channel = "微信"
    order.wx_transaction_id = tx_id or order.wx_transaction_id
    order.courier_id = primary_courier_for_area(db, order.routing_area)
    db.commit()
    return True, "paid"


def list_courier_single_order_tasks(
    db: Session,
    courier_id: str,
    delivery_date: date,
) -> list[CourierTaskMemberOut]:
    stmt = (
        select(SingleMealOrder, Member, MemberAddress, MenuDish)
        .join(Member, SingleMealOrder.member_id == Member.id)
        .join(MemberAddress, SingleMealOrder.member_address_id == MemberAddress.id)
        .join(MenuDish, SingleMealOrder.dish_id == MenuDish.id)
        .where(
            SingleMealOrder.delivery_date == delivery_date,
            SingleMealOrder.pay_status == "已支付",
            SingleMealOrder.fulfillment_status == "pending",
            SingleMealOrder.courier_id == courier_id,
        )
    )
    out: list[CourierTaskMemberOut] = []
    for order, member, a, dsh in db.execute(stmt).all():
        ar = (order.routing_area or "").strip() or effective_routing_area(a)
        detail = (a.detail_address or "").strip()
        display_addr = f"{ar} {detail}".strip()
        out.append(
            CourierTaskMemberOut(
                member_id=int(member.id),
                phone=member.phone or "",
                name=(member.name or "").strip() or "会员",
                address=display_addr or "（地址异常）",
                lng=float(a.lng) if a.lng is not None else None,
                lat=float(a.lat) if a.lat is not None else None,
                area=ar,
                remarks=member.remarks,
                sort_distance_m=None,
                is_delivered=False,
                task_kind="single",
                single_order_id=int(order.id),
                dish_title=(dsh.name or "").strip() or None,
            )
        )
    return out


def confirm_single_order_delivery(db: Session, courier_id: str, order_id: int) -> None:
    row = db.get(SingleMealOrder, order_id)
    if not row:
        raise HTTPException(status_code=404, detail="订单不存在")
    if (row.courier_id or "").strip() != (courier_id or "").strip():
        raise HTTPException(status_code=403, detail="无权操作该单次订单")
    if row.pay_status != "已支付":
        raise HTTPException(status_code=400, detail="订单未支付")
    if row.fulfillment_status == "delivered":
        return
    row.fulfillment_status = "delivered"
    db.commit()
