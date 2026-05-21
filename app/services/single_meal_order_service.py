from __future__ import annotations

from typing import Any

import logging
import secrets
from datetime import date, time, timedelta
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.courier_delivery_fee import courier_delivery_fee_yuan_for_meal_units
from app.core.timeutil import now_shanghai, shanghai_naive_range_for_calendar_day, today_shanghai
from app.integrations.wechat_pay_v2 import (
    WeChatPayV2Error,
    WechatPayNotifyParsed,
    build_miniprogram_pay_params,
    parse_wechat_pay_notify,
    query_order_by_out_trade_no,
    refund_order_v2,
    unified_order_jsapi,
    yuan_decimal_to_fen,
)
from app.services.tenant_integration_service import (
    get_merged_pay_config,
    wechat_pay_misconfiguration_detail_merged,
)
from app.models.courier import Courier
from app.models.delivery_region import DeliveryRegion, DeliveryRegionCourier
from app.models.member import Member
from app.models.member_address import MemberAddress
from app.models.menu_dish import MenuDish
from app.models.menu_schedule import MenuSchedule
from app.models.sf_same_city_push import SfSameCityPush
from app.models.single_meal_order import SingleMealOrder
from app.models.weekly_menu_slot import WeeklyMenuSlot
from app.schemas.courier import CourierTaskMemberOut
from app.schemas.single_meal_order import (
    AdminSingleMealOrderListOut,
    SingleMealOrderCreateIn,
    SingleMealOrderOut,
)
from app.utils.sql_like import escape_like_fragment
from app.services.courier_task_sorting import (
    centroid_from_task_rows,
    distance_from_anchor_m,
    order_task_rows_by_nearest_neighbor,
)
from app.services.member_address_service import delivery_region_name_map, full_address_line, routing_area_label
from app.services.store_config_service import load_store_coordinates_for_sorting

logger = logging.getLogger(__name__)

_RETAIL_STOP_PREFIX = "retail-smo-"
_SF_PUSH_KIND_SINGLE_MEAL_RETAIL = "single_meal_retail"
_SF_TERMINAL_CANCEL_STATUSES = (2, 22)
_SF_TERMINAL_DELIVERED_STATUS = 17
_SF_CANCEL_CALLBACK_KINDS = frozenset({"cancel_by_sf", "rider_cancel"})


def sf_push_is_terminal_cancel(pus: SfSameCityPush) -> bool:
    """顺丰侧已取消/撤单：看回调状态码，或最近一次回调路由为 cancel_by_sf / rider_cancel。"""
    st = pus.sf_callback_order_status
    if st is not None:
        try:
            if int(st) in _SF_TERMINAL_CANCEL_STATUSES:
                return True
        except (TypeError, ValueError):
            pass
    kind = (pus.last_callback_kind or "").strip()
    return kind in _SF_CANCEL_CALLBACK_KINDS


def sf_push_is_terminal_delivered(pus: SfSameCityPush) -> bool:
    st = pus.sf_callback_order_status
    if st is None:
        return False
    try:
        return int(st) == _SF_TERMINAL_DELIVERED_STATUS
    except (TypeError, ValueError):
        return False


def _retail_order_id_from_stop_id(stop_id: str | None) -> int | None:
    s = (stop_id or "").strip()
    if not s.startswith(_RETAIL_STOP_PREFIX):
        return None
    try:
        return int(s[len(_RETAIL_STOP_PREFIX) :])
    except (TypeError, ValueError):
        return None


def _latest_success_sf_push_for_retail_order(
    db: Session, *, store_id: int, order_id: int
) -> SfSameCityPush | None:
    """取该单次零售订单最近一次创单成功的顺丰推单（忽略后续失败重试行）。"""
    stop_id = f"{_RETAIL_STOP_PREFIX}{int(order_id)}"
    row = db.scalars(
        select(SfSameCityPush)
        .where(
            SfSameCityPush.stop_id == stop_id,
            SfSameCityPush.error_code == 0,
            SfSameCityPush.store_id == int(store_id),
        )
        .order_by(SfSameCityPush.id.desc())
        .limit(1)
    ).first()
    if row is not None:
        return row
    # 门店 id 不一致时仍尝试按 stop_id 找回推单（历史数据/多门店迁移）
    return db.scalars(
        select(SfSameCityPush)
        .where(
            SfSameCityPush.stop_id == stop_id,
            SfSameCityPush.error_code == 0,
        )
        .order_by(SfSameCityPush.id.desc())
        .limit(1)
    ).first()


def _apply_sf_monitor_status_to_retail_order_no_commit(
    db: Session,
    o: SingleMealOrder,
    pus: SfSameCityPush,
) -> str | None:
    """
    按顺丰监控行回写单次零售订单履约状态（不 commit）。
    返回：``updated_delivered`` / ``updated_cancel`` / ``already_*`` / ``skipped_*``。
    """
    if str(o.pay_status or "").strip() != "已支付":
        return "skipped_unpaid"
    if bool(getattr(o, "store_pickup", False)):
        return "skipped_store_pickup"
    if int(pus.error_code or -1) != 0:
        return "skipped_sf_not_success_push"

    prev_f = str(o.fulfillment_status or "").strip().lower()
    st = pus.sf_callback_order_status
    try:
        n = int(st) if st is not None else None
    except (TypeError, ValueError):
        n = None

    if n == 31:
        return "skipped_sf_cancel"
    if sf_push_is_terminal_cancel(pus):
        if prev_f == "sf_cancelled":
            return "already_sf_cancelled"
        mark_single_meal_sf_cancelled_no_commit(db, int(o.id))
        after = str(o.fulfillment_status or "").strip().lower()
        return "updated_cancel" if after == "sf_cancelled" else "skipped_sf_cancel"
    if sf_push_is_terminal_delivered(pus):
        if prev_f == "delivered":
            return "already_completed"
        if pus.merchant_cancel_requested_at is not None:
            return "skipped_merchant_cancel_marker"
        mark_single_meal_delivered_sf_completion_no_commit(db, int(o.id))
        after = str(o.fulfillment_status or "").strip().lower()
        return "updated" if after == "delivered" else "skipped_sf_status_not_terminal"
    return "skipped_sf_status_not_terminal"


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


def dish_planned_for_date(db: Session, dish_id: int, d: date, *, store_id: int) -> bool:
    sid = int(store_id)
    if db.scalar(
        select(MenuSchedule.id).where(
            MenuSchedule.menu_date == d,
            MenuSchedule.dish_id == dish_id,
            MenuSchedule.store_id == sid,
        )
    ):
        return True
    slots = db.scalars(
        select(WeeklyMenuSlot).where(
            WeeklyMenuSlot.dish_id == dish_id,
            WeeklyMenuSlot.store_id == sid,
        )
    ).all()
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
    mem = db.get(Member, member_id)
    if not mem or mem.deleted_at is not None:
        raise HTTPException(status_code=404, detail="用户不存在")
    if int(dish.store_id) != int(mem.store_id):
        raise HTTPException(status_code=404, detail="餐品不存在或已停用")
    if dish.single_order_price_yuan is None:
        raise HTTPException(status_code=400, detail="该餐品暂未开放单点")
    if not dish_planned_for_date(db, int(dish.id), body.delivery_date, store_id=int(mem.store_id)):
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
        detail_line = full_address_line(addr.map_location_text, addr.door_detail)
        address_summary = f"{area} {detail_line}".strip()
        addr_id = int(addr.id)

    from app.services.menu_day_stock_service import assert_single_order_stock_available

    assert_single_order_stock_available(
        db, int(dish.id), body.delivery_date, qty, store_id=int(mem.store_id)
    )

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
        tenant_id=int(mem.tenant_id),
        store_id=int(mem.store_id),
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
                detail_line = full_address_line(addr.map_location_text, addr.door_detail)
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


def list_admin_store_single_meal_orders_by_order_day(
    db: Session,
    *,
    store_id: int,
    order_day: date,
    q: str | None = None,
    pay_status: str | None = None,
    delivery_phase: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[AdminSingleMealOrderListOut], int]:
    """管理端：按上海自然日筛选「下单时间」落在当日的单次点餐订单（created_at 存北京时间 naive）。

    ``delivery_phase``：``awaiting``=待配送（履约未完成，含 pending/accepted）；``delivered``=已配送（delivered）。
    """
    start_bj, end_bj = shanghai_naive_range_for_calendar_day(order_day)
    page = max(1, page)
    page_size = min(100, max(1, page_size))
    join_on = Member.id == SingleMealOrder.member_id
    filters = [
        SingleMealOrder.store_id == int(store_id),
        SingleMealOrder.created_at >= start_bj,
        SingleMealOrder.created_at < end_bj,
    ]
    ps = (pay_status or "").strip()
    if ps:
        filters.append(SingleMealOrder.pay_status == ps)
    dp = (delivery_phase or "").strip().lower()
    if dp == "awaiting":
        filters.append(
            SingleMealOrder.fulfillment_status.in_(("pending", "accepted")),
        )
    elif dp == "delivered":
        filters.append(SingleMealOrder.fulfillment_status == "delivered")
    if q and q.strip():
        esc = escape_like_fragment(q.strip())
        filters.append(
            or_(
                Member.phone.like(f"{esc}%", escape="\\"),
                Member.name.like(f"%{esc}%", escape="\\"),
            )
        )

    count_stmt = select(func.count()).select_from(SingleMealOrder).join(Member, join_on)
    for f in filters:
        count_stmt = count_stmt.where(f)
    total = int(db.scalar(count_stmt) or 0)

    list_stmt = (
        select(SingleMealOrder)
        .join(Member, join_on)
        .order_by(SingleMealOrder.created_at.desc(), SingleMealOrder.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    for f in filters:
        list_stmt = list_stmt.where(f)
    rows = db.scalars(list_stmt).all()
    out: list[AdminSingleMealOrderListOut] = []
    for r in rows:
        m = db.get(Member, r.member_id)
        base = _single_meal_order_row_to_out(db, r)
        out.append(
            AdminSingleMealOrderListOut(
                **base.model_dump(),
                member_id=int(r.member_id),
                member_phone=(m.phone or "") if m else "",
                member_name=(((m.name or "").strip()) if m else "") or "",
            )
        )
    return out, total


def list_member_single_meal_orders(
    db: Session,
    member_id: int,
    *,
    page: int = 1,
    page_size: int = 20,
    list_status: str | None = None,
) -> tuple[list[SingleMealOrderOut], int]:
    """会员端列表。``list_status``：``all``（默认）、``pending_pay`` 待支付、``pending_delivery`` 待送达（配送且未妥投）、``completed`` 已完成（自提或已送达）。"""
    page = max(1, page)
    page_size = min(50, max(1, page_size))
    ls = (list_status or "all").strip().lower()
    filters: list = [SingleMealOrder.member_id == member_id]
    if ls == "pending_pay":
        filters.append(SingleMealOrder.pay_status == "未支付")
    elif ls == "pending_delivery":
        filters.append(SingleMealOrder.pay_status == "已支付")
        filters.append(SingleMealOrder.store_pickup.is_(False))
        filters.append(SingleMealOrder.fulfillment_status.in_(("pending", "accepted")))
    elif ls == "completed":
        filters.append(SingleMealOrder.pay_status == "已支付")
        filters.append(
            or_(
                SingleMealOrder.store_pickup.is_(True),
                SingleMealOrder.fulfillment_status == "delivered",
            )
        )
    elif ls != "all":
        ls = "all"

    count_stmt = select(func.count()).select_from(SingleMealOrder).where(*filters)
    total = int(db.scalar(count_stmt) or 0)
    offset = (page - 1) * page_size
    rows = db.scalars(
        select(SingleMealOrder)
        .where(*filters)
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
    order = db.get(SingleMealOrder, order_id)
    if not order or int(order.member_id) != int(member_id):
        raise HTTPException(status_code=404, detail="订单不存在")
    if order.pay_status == "已支付":
        raise HTTPException(status_code=400, detail="订单已支付")
    if order.pay_status == "已退款":
        raise HTTPException(status_code=400, detail="订单已退款")

    pay_cfg = get_merged_pay_config(db, int(order.tenant_id), store_id=int(order.store_id))
    perr = wechat_pay_misconfiguration_detail_merged(pay_cfg)
    if perr:
        raise HTTPException(status_code=503, detail=perr)

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
            pay=pay_cfg,
        )
    except WeChatPayV2Error as e:
        raise HTTPException(status_code=e.status_code, detail=str(e)) from e

    return build_miniprogram_pay_params(
        prepay_id, appid=pay_cfg.wx_mini_appid, api_key=pay_cfg.wechat_pay_api_key
    )


def finalize_single_meal_order_wechat_pay(db: Session, parsed: WechatPayNotifyParsed) -> tuple[bool, str]:
    """单笔点餐：根据已验签通知入账；无匹配订单返回 order_not_found。"""
    order = db.scalar(
        select(SingleMealOrder)
        .where(SingleMealOrder.out_trade_no == parsed.out_trade_no)
        .with_for_update()
    )
    if not order:
        return False, "order_not_found"

    if order.pay_status == "已退款":
        return False, "order_refunded"

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
    ok, reason, parsed = parse_wechat_pay_notify(data, db=db)
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
            SingleMealOrder.fulfillment_status.in_(("pending", "accepted")),
            SingleMealOrder.courier_id == courier_id,
        )
    )
    store_lng, store_lat = load_store_coordinates_for_sorting(db)
    out: list[CourierTaskMemberOut] = []
    for order, member, a, dsh in db.execute(stmt).all():
        nm = delivery_region_name_map(db, {int(a.delivery_region_id)} if a.delivery_region_id else set())
        ar = (order.routing_area or "").strip() or routing_area_label(a, nm)
        detail = full_address_line(a.map_location_text, a.door_detail)
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
    fee_yuan = courier_delivery_fee_yuan_for_meal_units(db, qty, store_id=int(row.store_id))
    courier_row = db.execute(select(Courier).where(Courier.courier_id == courier_id).with_for_update()).scalar_one_or_none()
    if not courier_row:
        raise HTTPException(status_code=500, detail="配送员账户异常")
    prev = courier_row.fee_pending if courier_row.fee_pending is not None else Decimal("0.00")
    courier_row.fee_pending = prev + fee_yuan
    row.fulfillment_status = "delivered"
    db.commit()


def mark_single_meal_delivered_sf_completion_no_commit(db: Session, order_id: int) -> None:
    """
    顺丰订单完成：单点餐标履约已送达；餐费已预付，不扣会员次数、不产生骑手待结算。
    不符合条件时静默跳过（幂等）。
    """
    row = db.get(SingleMealOrder, order_id)
    if not row:
        return
    if row.pay_status != "已支付":
        return
    if row.fulfillment_status == "delivered":
        return
    if bool(getattr(row, "store_pickup", False)):
        return
    row.fulfillment_status = "delivered"


def mark_single_meal_sf_cancelled_no_commit(db: Session, order_id: int) -> None:
    """
    顺丰取消/撤单(回调 order_status 2/22)：单点餐标 ``sf_cancelled``。
    已送达的不覆盖；退款仍走管理端原路退。
    """
    row = db.get(SingleMealOrder, order_id)
    if not row:
        return
    if row.pay_status != "已支付":
        return
    prev = str(row.fulfillment_status or "").strip().lower()
    if prev in ("delivered", "sf_cancelled"):
        return
    if bool(getattr(row, "store_pickup", False)):
        return
    row.fulfillment_status = "sf_cancelled"


def admin_resync_single_meal_from_sf_monitor(
    db: Session,
    *,
    order_id: int,
    store_id: int,
) -> str:
    """
    单次零售顺丰单：按「顺丰订单监控」中已落库的终态，幂等回写 ``single_meal_orders``。

    - 妥投 (17) → ``delivered``
    - 取消/撤单 (2/22) → ``sf_cancelled``（展示「顺丰取消」）
    """
    o = db.get(SingleMealOrder, int(order_id))
    if o is None or int(o.store_id) != int(store_id):
        raise ValueError("订单不存在或不属于当前门店")
    pus = _latest_success_sf_push_for_retail_order(db, store_id=int(store_id), order_id=int(order_id))
    if pus is None:
        raise ValueError("未找到本订单已成功创单的顺丰推送记录（请确认已推顺丰单次零售）")
    if pus.sf_callback_order_status is None and not (pus.last_callback_kind or "").strip():
        raise ValueError("尚未收到顺丰配送回调（请先确认开放平台回调可达且验签通过）")
    if not sf_push_is_terminal_cancel(pus) and not sf_push_is_terminal_delivered(pus):
        st = pus.sf_callback_order_status
        kind = (pus.last_callback_kind or "").strip() or "—"
        raise ValueError(
            f"顺丰推送尚未处于可对齐的终态（当前状态编码 {st!r}，最近回调 {kind}）。"
            "请在「顺丰订单监控」确认已为妥投(17)或取消/撤单。"
        )

    prev = str(o.fulfillment_status or "").strip().lower()
    outcome = _apply_sf_monitor_status_to_retail_order_no_commit(db, o, pus)
    db.commit()
    db.refresh(o)
    after = str(o.fulfillment_status or "").strip().lower()

    if sf_push_is_terminal_cancel(pus):
        if after != "sf_cancelled":
            diag = diagnose_single_meal_sf_sync(db, order_id=int(order_id), store_id=int(store_id))
            raise ValueError(
                "不满足标为顺丰取消条件（例如未支付、门店自提等），未修改订单状态。"
                f" 诊断：{diag.get('hint') or diag}"
            )
        if prev == "sf_cancelled":
            return "订单已是顺丰取消，无需重复同步"
        return "已与顺丰监控中的取消/撤单状态对齐（顺丰取消）"

    if after != "delivered":
        raise ValueError("不满足标为已完成条件（例如未支付、门店自提等），未修改订单状态")
    if prev == "delivered":
        return "订单已是已完成，无需重复同步"
    if outcome == "skipped_merchant_cancel_marker":
        raise ValueError("该顺丰单商户侧已标记取消请求，不设为已完成")
    return "已与顺丰监控中的妥投状态(编码 17) 对齐"


def admin_resync_single_meal_delivered_from_sf_monitor(
    db: Session,
    *,
    order_id: int,
    store_id: int,
) -> str:
    """兼容旧调用方：等同 ``admin_resync_single_meal_from_sf_monitor``。"""
    return admin_resync_single_meal_from_sf_monitor(db, order_id=order_id, store_id=store_id)


def bulk_admin_resync_single_meal_from_sf_monitor_for_order_day(
    db: Session,
    *,
    store_id: int,
    order_day: date,
    max_orders: int = 500,
) -> dict[str, Any]:
    """
    单日·单门店单次点餐：对齐顺丰监控终态到 ``single_meal_orders``。

    两路扫描（幂等）：
    1. 按「下单日」筛订单，关联最近一次创单成功的推单；
    2. 按「供餐/业务日 = order_day」扫顺丰零售推单，反向更新仍滞后的订单。
    """
    mx = max(1, min(500, int(max_orders or 500)))
    start_bj, end_bj = shanghai_naive_range_for_calendar_day(order_day)
    rows = list(
        db.scalars(
            select(SingleMealOrder)
            .where(
                SingleMealOrder.store_id == int(store_id),
                SingleMealOrder.created_at >= start_bj,
                SingleMealOrder.created_at < end_bj,
            )
            .order_by(SingleMealOrder.id.desc())
            .limit(mx)
        ).all()
    )
    scanned = len(rows)
    counts: dict[str, int] = {
        "updated": 0,
        "updated_cancel": 0,
        "already_completed": 0,
        "already_sf_cancelled": 0,
        "skipped_unpaid": 0,
        "skipped_store_pickup": 0,
        "skipped_no_sf_push": 0,
        "skipped_sf_not_success_push": 0,
        "skipped_sf_status_not_tuotou": 0,
        "skipped_sf_cancel": 0,
        "skipped_merchant_cancel_marker": 0,
    }
    touched: set[int] = set()

    def _bump(outcome: str | None) -> None:
        if not outcome:
            return
        key = outcome
        if key == "updated":
            counts["updated"] += 1
        elif key == "updated_cancel":
            counts["updated_cancel"] += 1
        elif key == "already_completed":
            counts["already_completed"] += 1
        elif key == "already_sf_cancelled":
            counts["already_sf_cancelled"] += 1
        elif key in counts:
            counts[key] += 1
        else:
            counts["skipped_sf_status_not_tuotou"] += 1

    for o in rows:
        pus = _latest_success_sf_push_for_retail_order(db, store_id=int(store_id), order_id=int(o.id))
        if pus is None:
            counts["skipped_no_sf_push"] += 1
            continue
        outcome = _apply_sf_monitor_status_to_retail_order_no_commit(db, o, pus)
        if outcome in ("updated", "updated_cancel"):
            db.commit()
            db.refresh(o)
        _bump(outcome)
        touched.add(int(o.id))

    delivery_days: set[date] = {order_day}
    for o in rows:
        if o.delivery_date is not None:
            delivery_days.add(o.delivery_date)

    seen_push_ids: set[int] = set()
    push_rows: list[SfSameCityPush] = []
    for dday in sorted(delivery_days):
        batch = list(
            db.scalars(
                select(SfSameCityPush)
                .where(
                    SfSameCityPush.store_id == int(store_id),
                    SfSameCityPush.delivery_date == dday,
                    SfSameCityPush.error_code == 0,
                    or_(
                        SfSameCityPush.push_kind == _SF_PUSH_KIND_SINGLE_MEAL_RETAIL,
                        SfSameCityPush.stop_id.like(f"{_RETAIL_STOP_PREFIX}%"),
                    ),
                    or_(
                        SfSameCityPush.sf_callback_order_status.in_(
                            (*_SF_TERMINAL_CANCEL_STATUSES, _SF_TERMINAL_DELIVERED_STATUS)
                        ),
                        SfSameCityPush.last_callback_kind.in_(tuple(_SF_CANCEL_CALLBACK_KINDS)),
                    ),
                )
                .order_by(SfSameCityPush.id.desc())
            ).all()
        )
        for pus in batch:
            pid = int(pus.id)
            if pid in seen_push_ids:
                continue
            seen_push_ids.add(pid)
            push_rows.append(pus)

    for pus in push_rows:
        oid = _retail_order_id_from_stop_id(str(pus.stop_id or ""))
        if oid is None or oid in touched:
            continue
        o = db.get(SingleMealOrder, oid)
        if o is None or int(o.store_id) != int(store_id):
            continue
        outcome = _apply_sf_monitor_status_to_retail_order_no_commit(db, o, pus)
        if outcome in ("updated", "updated_cancel"):
            db.commit()
            db.refresh(o)
        _bump(outcome)
        touched.add(oid)

    parts = [
        f"扫描下单日订单 {scanned} 条",
        f"新对齐妥投 {counts['updated']} 条",
        f"新对齐顺丰取消 {counts['updated_cancel']} 条",
        f"已是已完成 {counts['already_completed']}",
        f"已是顺丰取消 {counts['already_sf_cancelled']}",
        f"无顺丰推单 {counts['skipped_no_sf_push']}",
        f"顺丰未妥投(17)/未取消或未回调 {counts['skipped_sf_status_not_tuotou']}",
    ]
    summary = (
        "；".join(parts)
        + "。（依据本系统收到的顺丰推送落库对齐；不向运力主动查询；UU/门店自配送仍由骑手端或手工标记）"
    )
    return {"scanned": scanned, "sf_push_scanned": len(push_rows), **counts, "summary": summary}


def diagnose_single_meal_sf_sync(
    db: Session,
    *,
    order_id: int,
    store_id: int,
) -> dict[str, Any]:
    """管理端排查：单次零售订单为何未能与顺丰监控对齐（只读，不改库）。"""
    o = db.get(SingleMealOrder, int(order_id))
    if o is None:
        return {"ok": False, "hint": "订单不存在"}
    pus = _latest_success_sf_push_for_retail_order(
        db, store_id=int(store_id), order_id=int(order_id)
    )
    hint_parts: list[str] = [
        f"订单#{order_id} fulfillment={o.fulfillment_status!r} pay={o.pay_status!r} store={o.store_id}",
    ]
    if pus is None:
        hint_parts.append("未找到 error_code=0 的顺丰推单(retail-smo-{id})")
        return {"ok": False, "hint": "；".join(hint_parts)}

    prev_f = str(o.fulfillment_status or "").strip().lower()
    would = "skipped_sf_status_not_terminal"
    if str(o.pay_status or "").strip() != "已支付":
        would = "skipped_unpaid"
    elif bool(getattr(o, "store_pickup", False)):
        would = "skipped_store_pickup"
    elif sf_push_is_terminal_cancel(pus):
        would = "already_sf_cancelled" if prev_f == "sf_cancelled" else "updated_cancel"
    elif sf_push_is_terminal_delivered(pus):
        if prev_f == "delivered":
            would = "already_completed"
        elif pus.merchant_cancel_requested_at is not None:
            would = "skipped_merchant_cancel_marker"
        else:
            would = "updated"

    hint_parts.extend(
        [
            f"推单 stop_id={pus.stop_id} push_store={pus.store_id}",
            f"sf_status={pus.sf_callback_order_status!r}",
            f"last_kind={pus.last_callback_kind!r}",
            f"cancel={sf_push_is_terminal_cancel(pus)} delivered={sf_push_is_terminal_delivered(pus)}",
            f"would_outcome={would}",
        ]
    )
    if int(pus.store_id) != int(store_id):
        hint_parts.append(f"注意：推单门店({pus.store_id})与当前管理门店({store_id})不一致")
    return {
        "ok": would in ("updated", "updated_cancel", "already_completed", "already_sf_cancelled"),
        "hint": "；".join(hint_parts),
        "would_outcome": would,
        "push": {
            "id": int(pus.id),
            "stop_id": pus.stop_id,
            "store_id": int(pus.store_id),
            "sf_callback_order_status": pus.sf_callback_order_status,
            "last_callback_kind": pus.last_callback_kind,
            "delivery_date": pus.delivery_date.isoformat() if pus.delivery_date else None,
        },
    }


def admin_assign_courier_single_meal_order(
    db: Session,
    *,
    order_id: int,
    store_id: int,
    courier_id: str,
    tenant_id: int,
) -> AdminSingleMealOrderListOut:
    """管理端：门店自配送，将单次点餐订单绑定租户下已建档的配送员。"""
    o = db.get(SingleMealOrder, int(order_id))
    if o is None or int(o.store_id) != int(store_id):
        raise ValueError("订单不存在或不属于当前门店")
    if (o.fulfillment_status or "").strip() != "pending":
        raise ValueError("仅「待发货」订单可指派门店配送员（已进入「配送中」请走运力侧完成送达）")
    cid = (courier_id or "").strip()
    if not cid:
        raise ValueError("请选择配送员")
    cou = db.get(Courier, cid)
    if cou is None or int(cou.tenant_id) != int(tenant_id):
        raise ValueError("配送员不存在或不属于当前租户")
    if not cou.is_active:
        raise ValueError("该配送员已停用")
    o.courier_id = cid
    o.fulfillment_status = "accepted"
    db.add(o)
    db.commit()
    db.refresh(o)
    m = db.get(Member, o.member_id)
    base = _single_meal_order_row_to_out(db, o)
    return AdminSingleMealOrderListOut(
        **base.model_dump(),
        member_id=int(o.member_id),
        member_phone=(m.phone or "") if m else "",
        member_name=(((m.name or "").strip()) if m else "") or "",
    )


def admin_wechat_refund_single_meal_order(db: Session, *, order_id: int, store_id: int) -> dict[str, str]:
    """管理端：已支付且微信渠道的单次点餐订单，调用微信 v2 退款接口全额原路退回。"""
    o = db.get(SingleMealOrder, int(order_id))
    if o is None or int(o.store_id) != int(store_id):
        raise ValueError("订单不存在或不属于当前门店")
    if (o.pay_status or "").strip() != "已支付":
        raise ValueError("仅「已支付」订单可发起微信退款")
    if (o.pay_channel or "").strip() != "微信":
        raise ValueError("仅微信支付订单可原路退回")
    out_no = (o.out_trade_no or "").strip()
    if not out_no:
        raise ValueError("订单缺少商户单号，无法退款")

    pay_cfg = get_merged_pay_config(db, int(o.tenant_id), store_id=int(o.store_id))
    q = query_order_by_out_trade_no(out_no, pay=pay_cfg)
    trade_state = (q.get("trade_state") or "").strip().upper()
    if trade_state != "SUCCESS":
        raise ValueError(
            f"微信侧订单状态为「{trade_state or '未知'}」，需为支付成功（SUCCESS）才可退款；若已部分/全额退款请以微信商户平台为准",
        )
    try:
        total_fee = int((q.get("total_fee") or "0").strip())
    except ValueError as e:
        raise ValueError("无法解析微信订单金额") from e
    out_refund_no = f"RFSM{o.id}"[:32]
    refund_order_v2(
        out_trade_no=out_no,
        out_refund_no=out_refund_no,
        total_fee_fen=total_fee,
        refund_fee_fen=total_fee,
        pay=pay_cfg,
        transaction_id=(o.wx_transaction_id or "").strip() or None,
    )
    o.pay_status = "已退款"
    db.add(o)
    db.commit()
    return {"message": "微信退款已受理，资金将按支付渠道原路退回用户", "out_refund_no": out_refund_no}
