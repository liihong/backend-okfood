from __future__ import annotations

import logging
import secrets
from datetime import date, time, timedelta
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.courier_delivery_fee import courier_delivery_fee_yuan_for_meal_units
from app.core.timeutil import now_shanghai, today_shanghai
from app.integrations.wechat_pay_v2 import (
    WeChatPayV2Error,
    WechatPayNotifyParsed,
    build_miniprogram_pay_params,
    parse_wechat_pay_notify,
    unified_order_jsapi,
    wechat_pay_misconfiguration_detail,
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
from app.services.courier_task_sorting import (
    centroid_from_task_rows,
    distance_from_anchor_m,
    order_task_rows_by_nearest_neighbor,
)
from app.services.member_address_service import delivery_region_name_map, routing_area_label
from app.services.store_config_service import load_store_coordinates_for_sorting

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


def primary_courier_for_region_id(db: Session, region_id: int | None) -> str | None:
    """按片区主键取绑定骑手：优先 is_primary，否则 sort_order 最小且账号启用者。"""
    if region_id is None:
        return None
    rid = int(region_id)
    if not db.get(DeliveryRegion, rid):
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

    qty = int(body.quantity)
    if qty < 1 or qty > 50:
        raise HTTPException(status_code=400, detail="份数须在 1～50 之间")

    addr: MemberAddress | None = None
    if body.store_pickup:
        address_summary = "门店自提"
        area = "门店自提"
        addr_id: int | None = None
    else:
        addr = db.get(MemberAddress, body.member_address_id)
        if not addr or int(addr.member_id) != int(member_id):
            raise HTTPException(status_code=404, detail="配送地址不存在")
        nm = delivery_region_name_map(db, {int(addr.delivery_region_id)} if addr.delivery_region_id else set())
        area = routing_area_label(addr, nm)
        detail_line = (addr.detail_address or "").strip()
        address_summary = f"{area} {detail_line}".strip()
        addr_id = int(addr.id)

    mem = db.get(Member, member_id)
    if not mem or mem.deleted_at is not None:
        raise HTTPException(status_code=404, detail="用户不存在")

    from app.services.menu_day_stock_service import assert_single_order_stock_available

    assert_single_order_stock_available(db, int(dish.id), body.delivery_date, qty)

    # 单点：上海时间当日 10:00 起不可再下「当日供餐」单（与小程序规则一致，不分会员套餐）
    if body.delivery_date == today_shanghai() and now_shanghai().time() >= time(10, 0, 0):
        raise HTTPException(
            status_code=400,
            detail="每日 10:00 后仅可下次日及之后的单点单",
        )

    unit = dish.single_order_price_yuan
    if unit is None:
        raise HTTPException(status_code=400, detail="该餐品暂未开放单点")
    amt = (Decimal(unit) * Decimal(qty)).quantize(Decimal("0.01"))

    row = SingleMealOrder(
        out_trade_no=_new_temp_out_trade_no(),
        member_id=member_id,
        dish_id=int(dish.id),
        member_address_id=addr_id,
        store_pickup=bool(body.store_pickup),
        quantity=qty,
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

    return _single_meal_order_row_to_out(db, row, dish_title=str(dish.name), address_summary=address_summary)


def _single_meal_order_row_to_out(
    db: Session,
    row: SingleMealOrder,
    *,
    dish_title: str | None = None,
    address_summary: str | None = None,
) -> SingleMealOrderOut:
    if dish_title is None:
        dsh = db.get(MenuDish, row.dish_id)
        dish_title = (dsh.name or "").strip() if dsh else "餐品"
    if address_summary is None:
        if bool(getattr(row, "store_pickup", False)):
            address_summary = "门店自提"
        else:
            addr = db.get(MemberAddress, row.member_address_id)
            if addr:
                nm = delivery_region_name_map(
                    db, {int(addr.delivery_region_id)} if addr.delivery_region_id else set()
                )
                ar = routing_area_label(addr, nm)
                detail_line = (addr.detail_address or "").strip()
                address_summary = f"{ar} {detail_line}".strip()
            else:
                address_summary = (row.routing_area or "").strip() or "—"
    return SingleMealOrderOut(
        id=int(row.id),
        out_trade_no=str(row.out_trade_no or ""),
        dish_id=int(row.dish_id),
        dish_title=dish_title,
        member_address_id=int(row.member_address_id) if row.member_address_id is not None else None,
        store_pickup=bool(row.store_pickup),
        quantity=int(row.quantity or 1),
        delivery_date=row.delivery_date,
        routing_area=str(row.routing_area or ""),
        amount_yuan=_format_amount_yuan(Decimal(row.amount_yuan)),
        pay_status=str(row.pay_status or ""),
        pay_channel=row.pay_channel,
        fulfillment_status=str(row.fulfillment_status or ""),
        courier_id=row.courier_id,
        address_summary=address_summary,
        created_at=row.created_at,
    )


def list_member_single_meal_orders(
    db: Session,
    member_id: int,
    *,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[SingleMealOrderOut], int]:
    page = max(1, page)
    page_size = min(50, max(1, page_size))
    total = int(db.scalar(select(func.count()).where(SingleMealOrder.member_id == member_id)) or 0)
    offset = (page - 1) * page_size
    rows = db.scalars(
        select(SingleMealOrder)
        .where(SingleMealOrder.member_id == member_id)
        .order_by(SingleMealOrder.created_at.desc(), SingleMealOrder.id.desc())
        .offset(offset)
        .limit(page_size)
    ).all()
    return [_single_meal_order_row_to_out(db, r) for r in rows], total


def get_member_single_meal_order(db: Session, member_id: int, order_id: int) -> SingleMealOrderOut:
    row = db.get(SingleMealOrder, order_id)
    if not row or int(row.member_id) != int(member_id):
        raise HTTPException(status_code=404, detail="订单不存在")
    return _single_meal_order_row_to_out(db, row)


def prepare_wechat_jsapi_for_order(db: Session, member_id: int, order_id: int, client_ip: str) -> dict[str, str]:
    """调微信统一下单并返回小程序调起支付参数。"""
    pay_cfg = wechat_pay_misconfiguration_detail()
    if pay_cfg:
        raise HTTPException(status_code=503, detail=pay_cfg)

    order = db.get(SingleMealOrder, order_id)
    if not order or int(order.member_id) != int(member_id):
        raise HTTPException(status_code=404, detail="订单不存在")
    if order.pay_status == "已支付":
        raise HTTPException(status_code=400, detail="订单已支付")

    member = db.get(Member, member_id)
    if not member or member.deleted_at is not None:
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


def finalize_single_meal_order_wechat_pay(db: Session, parsed: WechatPayNotifyParsed) -> tuple[bool, str]:
    """单笔点餐：根据已验签通知入账；无匹配订单返回 order_not_found。"""
    order = db.scalar(
        select(SingleMealOrder)
        .where(SingleMealOrder.out_trade_no == parsed.out_trade_no)
        .with_for_update()
    )
    if not order:
        return False, "order_not_found"

    if order.pay_status == "已支付":
        return True, "already_paid"

    expect_fen = yuan_decimal_to_fen(order.amount_yuan)
    if parsed.total_fee != expect_fen:
        logger.error(
            "微信回调金额不一致 out=%s expect_fen=%s got_fen=%s",
            parsed.out_trade_no,
            expect_fen,
            parsed.total_fee,
        )
        return False, "amount_mismatch"

    order.pay_status = "已支付"
    order.pay_channel = "微信"
    tid = (parsed.transaction_id or "").strip()
    order.wx_transaction_id = tid or order.wx_transaction_id
    if bool(getattr(order, "store_pickup", False)):
        order.courier_id = None
        order.fulfillment_status = "delivered"
    else:
        pay_addr = db.get(MemberAddress, order.member_address_id)
        order.courier_id = primary_courier_for_region_id(
            db, int(pay_addr.delivery_region_id) if pay_addr and pay_addr.delivery_region_id else None
        )
    db.commit()
    return True, "paid"


def apply_single_meal_order_wechat_notify(db: Session, data: dict[str, str]) -> tuple[bool, str]:
    """
    处理微信支付结果通知（仅单笔点餐订单）。
    返回 (是否应回复微信 SUCCESS, 日志/失败原因)。
    """
    ok, reason, parsed = parse_wechat_pay_notify(data)
    if not ok or parsed is None:
        return False, reason
    return finalize_single_meal_order_wechat_pay(db, parsed)


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
    store_lng, store_lat = load_store_coordinates_for_sorting(db)
    out: list[CourierTaskMemberOut] = []
    for order, member, a, dsh in db.execute(stmt).all():
        nm = delivery_region_name_map(db, {int(a.delivery_region_id)} if a.delivery_region_id else set())
        ar = (order.routing_area or "").strip() or routing_area_label(a, nm)
        detail = (a.detail_address or "").strip()
        display_addr = f"{ar} {detail}".strip()
        sort_m = distance_from_anchor_m(
            store_lng,
            store_lat,
            float(a.lng) if a.lng is not None else None,
            float(a.lat) if a.lat is not None else None,
        )
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
                daily_meal_units=max(1, int(order.quantity or 1)),
                sort_distance_m=sort_m,
                is_delivered=False,
                task_kind="single",
                single_order_id=int(order.id),
                dish_title=(dsh.name or "").strip() or None,
            )
        )
    depot_lng, depot_lat = (
        (float(store_lng), float(store_lat))
        if store_lng is not None and store_lat is not None
        else centroid_from_task_rows(out)
    )
    order_task_rows_by_nearest_neighbor(out, depot_lng, depot_lat)
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
    if bool(getattr(row, "store_pickup", False)):
        raise HTTPException(status_code=400, detail="门店自提订单无需骑手确认")
    qty = max(1, int(row.quantity or 1))
    fee_yuan = courier_delivery_fee_yuan_for_meal_units(db, qty)
    courier_row = db.execute(select(Courier).where(Courier.courier_id == courier_id).with_for_update()).scalar_one_or_none()
    if not courier_row:
        raise HTTPException(status_code=500, detail="配送员账户异常")
    prev = courier_row.fee_pending if courier_row.fee_pending is not None else Decimal("0.00")
    courier_row.fee_pending = prev + fee_yuan
    row.fulfillment_status = "delivered"
    db.commit()
