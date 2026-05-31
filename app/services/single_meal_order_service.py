from __future__ import annotations

from typing import Any

import logging
import secrets
from datetime import date, timedelta
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session

from app.core.courier_delivery_fee import courier_delivery_fee_yuan_for_meal_units
from app.core.timeutil import beijing_now_naive, shanghai_naive_range_for_calendar_day
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
from app.models.enums import CouponLockedOrderBiz
from app.models.courier import Courier
from app.models.delivery_region import DeliveryRegion, DeliveryRegionCourier
from app.models.member import Member
from app.models.member_address import MemberAddress
from app.models.menu_dish import MenuDish
from app.models.menu_schedule import MenuSchedule
from app.models.sf_same_city_push import SfSameCityPush
from app.models.single_meal_order import SingleMealOrder
from app.constants import STUB_MEMBER_NAME
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
from app.services.admin_system_notification_service import create_single_meal_order_paid_notification
from app.services.store_config_service import load_store_coordinates_for_sorting
from app.services.marketing.coupon_checkout_service import (
    CouponCheckoutContext,
    lock_member_coupon_for_order,
    mark_member_coupon_used_for_order,
    release_member_coupon_for_order,
)

logger = logging.getLogger(__name__)


def _admin_single_meal_member_display_name(
    db: Session,
    member: Member | None,
    *,
    member_address_id: int | None,
    order_address: MemberAddress | None = None,
) -> str:
    """管理端展示名：档案仍为占位「待完善」时，优先用订单关联地址的收件人姓名。"""
    profile = ((member.name or "").strip() if member else "") or ""

    def _usable_contact(raw: str | None) -> str:
        c = (raw or "").strip()
        if not c or c == STUB_MEMBER_NAME:
            return ""
        return c

    if profile and profile != STUB_MEMBER_NAME:
        return profile

    addr = order_address
    if addr is None and member_address_id:
        addr = db.get(MemberAddress, int(member_address_id))
    contact = _usable_contact(addr.contact_name if addr else None)
    if contact:
        return contact

    # 订单地址无收件人时：回退该会员默认/最近一条地址
    if member is not None:
        fallback_addr = db.scalar(
            select(MemberAddress)
            .where(MemberAddress.member_id == int(member.id))
            .order_by(MemberAddress.is_default.desc(), MemberAddress.id.desc())
            .limit(1)
        )
        contact = _usable_contact(fallback_addr.contact_name if fallback_addr else None)
        if contact:
            return contact

    return profile


def _admin_single_meal_recipient_contact_name(
    *,
    member_address_id: int | None,
    order_address: MemberAddress | None = None,
) -> str:
    """订单关联地址上的收件人姓名（不做占位回退）。"""
    if order_address is None:
        return ""
    return (order_address.contact_name or "").strip()


def _admin_single_meal_member_list_fields(
    db: Session,
    member: Member | None,
    *,
    member_address_id: int | None,
    order_address: MemberAddress | None = None,
) -> tuple[str, str]:
    addr = order_address
    if addr is None and member_address_id:
        addr = db.get(MemberAddress, int(member_address_id))
    recipient = _admin_single_meal_recipient_contact_name(
        member_address_id=member_address_id, order_address=addr
    )
    display = _admin_single_meal_member_display_name(
        db,
        member,
        member_address_id=member_address_id,
        order_address=addr,
    )
    return display, recipient


def _member_address_remarks_text(addr: MemberAddress | None) -> str:
    return (addr.remarks or "").strip() if addr else ""


def _build_admin_single_meal_order_list_out(
    db: Session,
    row: SingleMealOrder,
    *,
    order_address: MemberAddress | None = None,
) -> AdminSingleMealOrderListOut:
    m = db.get(Member, row.member_id)
    aid = int(row.member_address_id) if row.member_address_id is not None else None
    addr = order_address
    if addr is None and aid is not None:
        addr = db.get(MemberAddress, aid)
    base = _single_meal_order_row_to_out(db, row)
    member_name, recipient_name = _admin_single_meal_member_list_fields(
        db,
        m,
        member_address_id=aid,
        order_address=addr,
    )
    return AdminSingleMealOrderListOut(
        **base.model_dump(),
        member_id=int(row.member_id),
        member_phone=(m.phone or "") if m else "",
        member_name=member_name,
        recipient_contact_name=recipient_name,
        address_remarks=_member_address_remarks_text(addr),
    )


_RETAIL_STOP_PREFIX = "retail-smo-"
_SF_PUSH_KIND_SINGLE_MEAL_RETAIL = "single_meal_retail"
_SF_TERMINAL_CANCEL_STATUSES = (2, 22)
_SF_TERMINAL_DELIVERED_STATUS = 17
_SF_ORDER_STATUS_PICKED_UP = 15  # 顺丰：配送员已取货，配送中
_FULFILLMENT_SF_AWAITING_PICKUP = "sf_awaiting_pickup"
_SF_CANCEL_CALLBACK_KINDS = frozenset({"cancel_by_sf", "rider_cancel"})


def single_meal_fulfillment_allows_dispatch(fs: str | None) -> bool:
    """管理端可发起配送（顺丰/UU/门店自配送）：待发货，或顺丰侧已取消待重推。"""
    return str(fs or "").strip().lower() in ("pending", "sf_cancelled")


def sf_push_create_succeeded(pus: SfSameCityPush) -> bool:
    """创单 ``error_code == 0`` 为成功；``0`` 为合法值，不可用 ``or`` 默认值。"""
    ec = getattr(pus, "error_code", None)
    if ec is None:
        return False
    try:
        return int(ec) == 0
    except (TypeError, ValueError):
        return False


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


def link_single_meal_orders_to_sf_push_no_commit(
    db: Session,
    order_ids: list[int] | tuple[int, ...],
    pus: SfSameCityPush,
) -> int:
    """创单/重推成功后：单次订单绑定推单主键，并冗余顺丰运单号。"""
    if pus.id is None:
        return 0
    push_id = int(pus.id)
    sf_oid = (pus.sf_order_id or "").strip() or None
    linked = 0
    for raw in order_ids:
        try:
            oid = int(raw)
        except (TypeError, ValueError):
            continue
        row = db.get(SingleMealOrder, oid)
        if not row:
            continue
        row.sf_same_city_push_id = push_id
        if sf_oid:
            row.sf_order_id = sf_oid
        linked += 1
    return linked


def sync_single_meal_sf_order_id_for_push_no_commit(db: Session, pus: SfSameCityPush) -> int:
    """顺丰回调写入 push.sf_order_id 后，同步到已绑定该 push 的单次订单。"""
    sf_oid = (pus.sf_order_id or "").strip() or None
    if pus.id is None or not sf_oid:
        return 0
    rows = db.scalars(
        select(SingleMealOrder).where(SingleMealOrder.sf_same_city_push_id == int(pus.id))
    ).all()
    n = 0
    for row in rows:
        if row.sf_order_id != sf_oid:
            row.sf_order_id = sf_oid
            n += 1
    return n


def resolve_sf_push_for_single_meal_order(
    db: Session, *, store_id: int, order_id: int
) -> SfSameCityPush | None:
    """
    单次订单 → 顺丰推单：优先 ``single_meal_orders.sf_same_city_push_id``（须非大表合并单），
    其次 stop_id = retail-smo-{order_id} 且创单成功的推单。
    """
    oid = int(order_id)
    o = db.get(SingleMealOrder, oid)
    if o is not None and o.sf_same_city_push_id is not None:
        pus = db.get(SfSameCityPush, int(o.sf_same_city_push_id))
        if pus is not None and sf_push_create_succeeded(pus):
            # 历史误差：单笔曾绑定到大表 merged 推送行 → 不参与单笔顺丰对齐，交由下方 retail stop 兜底
            if str(getattr(pus, "push_kind", "") or "").strip().lower() != "delivery_sheet":
                if int(o.store_id) == int(store_id) or int(pus.store_id) == int(store_id):
                    return pus
    return _legacy_resolve_sf_push_for_single_meal_order(db, store_id=int(store_id), order_id=oid)


def _legacy_resolve_sf_push_for_single_meal_order(
    db: Session, *, store_id: int, order_id: int
) -> SfSameCityPush | None:
    oid = int(order_id)
    stop_id = f"{_RETAIL_STOP_PREFIX}{oid}"
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
    row = db.scalars(
        select(SfSameCityPush)
        .where(
            SfSameCityPush.stop_id == stop_id,
            SfSameCityPush.error_code == 0,
        )
        .order_by(SfSameCityPush.id.desc())
        .limit(1)
    ).first()
    if row is not None:
        return row
    # 业务约定：单笔零售不得通过「订阅大表 delivery_sheet」回溯到顺丰，
    # 否则会与同一天同停靠点的预购单笔（供餐日为当日、下单在前一日）混入早间大表推单对齐。
    return None


def _latest_success_sf_push_for_retail_order(
    db: Session, *, store_id: int, order_id: int
) -> SfSameCityPush | None:
    """兼容旧调用方：等同 ``resolve_sf_push_for_single_meal_order``。"""
    return resolve_sf_push_for_single_meal_order(db, store_id=int(store_id), order_id=int(order_id))


def _apply_sf_monitor_status_to_retail_order_no_commit(
    db: Session,
    o: SingleMealOrder,
    pus: SfSameCityPush,
) -> str | None:
    """
    按顺丰监控行回写单次零售订单履约状态（不 commit）。
    返回：``updated_delivered`` / ``updated_cancel`` / ``updated_in_delivery`` / ``updated_awaiting_pickup`` / ``already_*`` / ``skipped_*``。
    """
    if str(o.pay_status or "").strip() != "已支付":
        return "skipped_unpaid"
    if bool(getattr(o, "store_pickup", False)):
        return "skipped_store_pickup"
    if not sf_push_create_succeeded(pus):
        return "skipped_sf_not_success_push"
    if str(getattr(pus, "push_kind", "") or "").strip().lower() == "delivery_sheet":
        return "skipped_delivery_sheet_push"

    if o.sf_same_city_push_id is not None and int(o.sf_same_city_push_id) != int(pus.id):
        return "skipped_push_order_mismatch"

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

    # 已推顺丰、回调尚未到取货：纠正误标为「配送中」的历史单
    if n is None or n < _SF_ORDER_STATUS_PICKED_UP:
        if prev_f == "accepted":
            o.fulfillment_status = _FULFILLMENT_SF_AWAITING_PICKUP
            return "updated_awaiting_pickup"
        if prev_f == "pending" and sf_push_create_succeeded(pus):
            if mark_single_meals_sf_awaiting_pickup_on_push_no_commit(db, [int(o.id)]) > 0:
                return "updated_awaiting_pickup"
        return "skipped_sf_status_not_terminal"

    if prev_f == _FULFILLMENT_SF_AWAITING_PICKUP:
        if mark_single_meals_in_delivery_on_sf_pickup_no_commit(db, [int(o.id)]) > 0:
            prev_f = "accepted"

    if sf_push_is_terminal_delivered(pus):
        if prev_f == "delivered":
            return "already_completed"
        if pus.merchant_cancel_requested_at is not None:
            return "skipped_merchant_cancel_marker"
        mark_single_meal_delivered_sf_completion_no_commit(db, int(o.id))
        after = str(o.fulfillment_status or "").strip().lower()
        return "updated" if after == "delivered" else "skipped_sf_status_not_terminal"

    if prev_f == "accepted":
        return "already_accepted"
    if prev_f == _FULFILLMENT_SF_AWAITING_PICKUP:
        return "skipped_sf_status_not_terminal"
    if mark_single_meals_in_delivery_on_sf_pickup_no_commit(db, [int(o.id)]) > 0:
        return "updated_in_delivery"
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


UNPAID_SINGLE_MEAL_ORDER_EXPIRE_MINUTES = 30


def _unpaid_single_order_expire_cutoff():
    return beijing_now_naive() - timedelta(minutes=UNPAID_SINGLE_MEAL_ORDER_EXPIRE_MINUTES)


def expire_stale_unpaid_single_meal_orders(db: Session, *, member_id: int | None = None) -> int:
    """单次零售：创建超过 ``UNPAID_SINGLE_MEAL_ORDER_EXPIRE_MINUTES`` 仍未支付则自动取消（履约 cancelled）。"""
    cutoff = _unpaid_single_order_expire_cutoff()
    filters = [
        SingleMealOrder.pay_status == "未支付",
        SingleMealOrder.fulfillment_status == "pending",
        SingleMealOrder.created_at < cutoff,
    ]
    if member_id is not None:
        filters.append(SingleMealOrder.member_id == int(member_id))
    stale_ids = list(db.scalars(select(SingleMealOrder.id).where(*filters)).all())
    if not stale_ids:
        return 0
    for oid in stale_ids:
        release_member_coupon_for_order(
            db, order_biz=CouponLockedOrderBiz.SINGLE_MEAL, order_id=int(oid)
        )
    db.execute(
        update(SingleMealOrder)
        .where(SingleMealOrder.id.in_(stale_ids))
        .values(fulfillment_status="cancelled", courier_id=None)
    )
    db.commit()
    return len(stale_ids)


def _assert_no_pending_unpaid_single_order(db: Session, member_id: int) -> None:
    """同一会员仅允许一笔待支付单次点餐单，避免取消支付后重复下单。"""
    oid = db.scalars(
        select(SingleMealOrder.id)
        .where(
            SingleMealOrder.member_id == int(member_id),
            SingleMealOrder.pay_status == "未支付",
            SingleMealOrder.fulfillment_status != "cancelled",
        )
        .order_by(SingleMealOrder.id.desc())
        .limit(1)
    ).first()
    if oid is not None:
        raise HTTPException(
            status_code=409,
            detail=f"您有未支付的单次点餐订单（#{int(oid)}），请先完成支付或取消后再下单",
        )


def create_single_meal_order(db: Session, member_id: int, body: SingleMealOrderCreateIn) -> SingleMealOrderOut:
    expire_stale_unpaid_single_meal_orders(db, member_id=member_id)
    _assert_no_pending_unpaid_single_order(db, member_id)
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

    coupon_id = body.member_coupon_id
    if coupon_id is not None:
        ctx = CouponCheckoutContext(
            checkout_biz=CouponLockedOrderBiz.SINGLE_MEAL,
            original_amount_yuan=amt,
            dish_id=int(dish.id),
        )
        orig, disc, payable = lock_member_coupon_for_order(
            db,
            member_coupon_id=int(coupon_id),
            member_id=int(member_id),
            store_id=int(mem.store_id),
            ctx=ctx,
            order_id=int(row.id),
        )
        row.original_amount_yuan = orig
        row.coupon_discount_yuan = disc
        row.amount_yuan = payable
        row.member_coupon_id = int(coupon_id)

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
        address_summary=address_summary,
        created_at=row.created_at,
    )


def _admin_store_single_meal_scope_filters_for_delivery_day(
    *,
    store_id: int,
    delivery_day: date,
    q: str | None,
    delivery_phase: str | None,
) -> list:
    """单次点餐：供餐日列表/统计的公共范围（不含支付 Tab 对应条件）。

    ``delivery_phase``：``awaiting``=待配送（pending/accepted）；``delivered``=已送达；留空=不按阶段过滤。
    """
    filters: list = [
        SingleMealOrder.store_id == int(store_id),
        SingleMealOrder.delivery_date == delivery_day,
    ]
    dp = (delivery_phase or "").strip().lower()
    if dp == "awaiting":
        filters.append(
            SingleMealOrder.fulfillment_status.in_(
                ("pending", _FULFILLMENT_SF_AWAITING_PICKUP, "accepted"),
            ),
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
    return filters


def summarize_admin_store_single_meal_orders_by_delivery_day(
    db: Session,
    *,
    store_id: int,
    delivery_day: date,
    q: str | None = None,
    delivery_phase: str | None = None,
) -> dict[str, int]:
    """订单管理：统计当前范围下各状态笔数（与供餐日、搜索、配送维度一致，不含支付 Tab）。

    - ``pending_ship``：已支付且履约 pending（含待发货与待自提口径，与列表「订单状态」pending 一致）。
    """
    join_on = Member.id == SingleMealOrder.member_id
    base = _admin_store_single_meal_scope_filters_for_delivery_day(
        store_id=store_id,
        delivery_day=delivery_day,
        q=q,
        delivery_phase=delivery_phase,
    )

    def _count(extra: list) -> int:
        stmt = select(func.count()).select_from(SingleMealOrder).join(Member, join_on)
        for f in base + extra:
            stmt = stmt.where(f)
        return int(db.scalar(stmt) or 0)

    return {
        "paid": _count([SingleMealOrder.pay_status == "已支付"]),
        "unpaid": _count([SingleMealOrder.pay_status == "未支付"]),
        "cancelled": _count([SingleMealOrder.fulfillment_status == "cancelled"]),
        "pending_ship": _count(
            [
                SingleMealOrder.pay_status == "已支付",
                SingleMealOrder.fulfillment_status == "pending",
            ]
        ),
    }


def list_admin_store_single_meal_orders_by_delivery_day(
    db: Session,
    *,
    store_id: int,
    delivery_day: date,
    q: str | None = None,
    pay_status: str | None = None,
    delivery_phase: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[AdminSingleMealOrderListOut], int]:
    """管理端：按供餐日筛选单次点餐订单（``delivery_date``）。

    ``delivery_phase``：``awaiting``=待配送（履约未完成，含 pending/accepted）；``delivered``=已配送（delivered）。
    """
    page = max(1, page)
    page_size = min(100, max(1, page_size))
    join_on = Member.id == SingleMealOrder.member_id
    filters = list(
        _admin_store_single_meal_scope_filters_for_delivery_day(
            store_id=store_id,
            delivery_day=delivery_day,
            q=q,
            delivery_phase=delivery_phase,
        )
    )
    ps = (pay_status or "").strip()
    if ps == "已取消":
        filters.append(SingleMealOrder.fulfillment_status == "cancelled")
    elif ps:
        filters.append(SingleMealOrder.pay_status == ps)

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
    addr_ids = {int(r.member_address_id) for r in rows if r.member_address_id is not None}
    addr_map: dict[int, MemberAddress] = {}
    if addr_ids:
        for addr_row in db.scalars(
            select(MemberAddress).where(MemberAddress.id.in_(addr_ids))
        ).all():
            addr_map[int(addr_row.id)] = addr_row

    out: list[AdminSingleMealOrderListOut] = []
    for r in rows:
        aid = int(r.member_address_id) if r.member_address_id is not None else None
        order_addr = addr_map.get(aid) if aid is not None else None
        out.append(_build_admin_single_meal_order_list_out(db, r, order_address=order_addr))
    return out, total


def list_member_single_meal_orders(
    db: Session,
    member_id: int,
    *,
    page: int = 1,
    page_size: int = 20,
    list_status: str | None = None,
) -> tuple[list[SingleMealOrderOut], int]:
    """会员端列表。``list_status``：``all``（默认）、``pending_pay`` 待支付、``pending_delivery`` 待送达/待取货（已支付且未妥投/未自提）、``completed`` 已完成（已送达或已自提）。"""
    expire_stale_unpaid_single_meal_orders(db, member_id=member_id)
    page = max(1, page)
    page_size = min(50, max(1, page_size))
    ls = (list_status or "all").strip().lower()
    filters: list = [SingleMealOrder.member_id == member_id]
    if ls == "pending_pay":
        filters.append(SingleMealOrder.pay_status == "未支付")
        filters.append(SingleMealOrder.fulfillment_status == "pending")
    elif ls == "pending_delivery":
        filters.append(SingleMealOrder.pay_status == "已支付")
        filters.append(
            SingleMealOrder.fulfillment_status.in_(("pending", _FULFILLMENT_SF_AWAITING_PICKUP, "accepted"))
        )
    elif ls == "completed":
        filters.append(SingleMealOrder.pay_status == "已支付")
        filters.append(SingleMealOrder.fulfillment_status == "delivered")
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
    expire_stale_unpaid_single_meal_orders(db, member_id=member_id)
    row = db.get(SingleMealOrder, order_id)
    if not row or int(row.member_id) != int(member_id):
        raise HTTPException(status_code=404, detail="订单不存在")
    out = _single_meal_order_row_to_out(db, row)
    from app.services.store_config_service import get_store_config

    cfg = get_store_config(db, store_id=int(row.store_id))
    phone = (cfg.store_contact_phone or "").strip() or None
    return out.model_copy(update={"store_contact_phone": phone})


def member_cancel_single_meal_order(db: Session, *, member_id: int, order_id: int) -> str:
    """会员端取消本人单次点餐订单（规则同管理端；已支付不退款）。"""
    row = db.get(SingleMealOrder, order_id)
    if not row or int(row.member_id) != int(member_id):
        raise HTTPException(status_code=404, detail="订单不存在")
    try:
        return admin_cancel_single_meal_order(
            db,
            order_id=int(order_id),
            store_id=int(row.store_id),
            cancel_reason="用户取消订单",
            cancel_sf=True,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


def prepare_wechat_jsapi_for_order(db: Session, member_id: int, order_id: int, client_ip: str) -> dict[str, str]:
    """调微信统一下单并返回小程序调起支付参数。"""
    expire_stale_unpaid_single_meal_orders(db, member_id=member_id)
    order = db.get(SingleMealOrder, order_id)
    if not order or int(order.member_id) != int(member_id):
        raise HTTPException(status_code=404, detail="订单不存在")
    if order.pay_status == "已支付":
        raise HTTPException(status_code=400, detail="订单已支付")
    if order.pay_status == "已退款":
        raise HTTPException(status_code=400, detail="订单已退款")
    if str(order.fulfillment_status or "").strip().lower() == "cancelled":
        raise HTTPException(status_code=400, detail="订单已超时关闭，请重新下单")

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


def _notify_single_meal_order_paid_cs_review(db: Session, order: SingleMealOrder) -> None:
    """写入客服系统消息；失败仅回滚 savepoint，不得阻断支付入账。"""
    member = db.get(Member, int(order.member_id))
    dish = db.get(MenuDish, int(order.dish_id)) if order.dish_id else None
    try:
        with db.begin_nested():
            create_single_meal_order_paid_notification(
                db,
                store_id=int(order.store_id),
                order_id=int(order.id),
                delivery_date=order.delivery_date,
                dish_name=(dish.name if dish else None),
                quantity=int(order.quantity or 1),
                amount_yuan=_format_amount_yuan(Decimal(order.amount_yuan)),
                store_pickup=bool(getattr(order, "store_pickup", False)),
                member_id=int(order.member_id),
                member_phone=(member.phone if member else None),
                member_name=(member.name if member else None),
            )
    except Exception:
        logger.exception(
            "单次零售支付成功但系统消息写入失败 order_id=%s out=%s delivery_date=%s",
            int(order.id),
            order.out_trade_no,
            order.delivery_date,
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
        mark_member_coupon_used_for_order(
            db, order_biz=CouponLockedOrderBiz.SINGLE_MEAL, order_id=int(order.id)
        )
        db.commit()
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
    # 超时未支付被自动取消后补同步入账：恢复为待履约
    if str(order.fulfillment_status or "").strip().lower() == "cancelled":
        order.fulfillment_status = "pending"
    if bool(getattr(order, "store_pickup", False)):
        order.courier_id = None
        # 门店自提：支付后仍为 pending，待管理员在后台标记取货完成
    else:
        pay_addr = db.get(MemberAddress, order.member_address_id)
        order.courier_id = primary_courier_for_region_id(
            db, int(pay_addr.delivery_region_id) if pay_addr and pay_addr.delivery_region_id else None
        )
    _notify_single_meal_order_paid_cs_review(db, order)
    mark_member_coupon_used_for_order(
        db, order_biz=CouponLockedOrderBiz.SINGLE_MEAL, order_id=int(order.id)
    )
    db.commit()
    return True, "paid"


def sync_single_meal_order_from_wechat_query(
    db: Session, member_id: int, order_id: int
) -> tuple[bool, str]:
    """
    支付成功后由小程序主动拉单：调微信 orderquery，若已支付则与异步通知同路径入账（幂等）。

    弥补异步通知 URL 不可达、IP 白名单/漏配等导致「钱已付但库未更」。
    """
    order = db.get(SingleMealOrder, order_id)
    if not order or int(order.member_id) != int(member_id):
        return False, "order_not_found"

    out_no = (order.out_trade_no or "").strip()
    if not out_no:
        return False, "missing_out_trade_no"

    if (order.pay_status or "").strip() == "已退款":
        return False, "order_refunded"

    if (order.pay_status or "").strip() == "已支付":
        return True, "already_synced"

    try:
        pay_cfg = get_merged_pay_config(db, int(order.tenant_id), store_id=int(order.store_id))
        data = query_order_by_out_trade_no(out_no, pay=pay_cfg)
    except WeChatPayV2Error as e:
        return False, f"wechat_query:{str(e)}"[:220]

    if (data.get("result_code") or "").upper() != "SUCCESS":
        err_c = (data.get("err_code") or "").strip().upper()
        if err_c == "ORDERNOTEXIST":
            return False, "wechat_order_not_found"
        err_msg = (data.get("err_code_des") or data.get("err_code") or "query_fail")[:200]
        return False, err_msg

    ts = (data.get("trade_state") or "").strip().upper()
    if ts in ("", "NOTPAY"):
        return False, "not_paid"
    if ts == "USERPAYING":
        return False, "PAY_USERPAYING"
    if ts != "SUCCESS":
        return False, f"trade_state_{ts}"

    out_p = (data.get("out_trade_no") or "").strip() or out_no
    tx_id = (data.get("transaction_id") or "").strip()
    try:
        total_fee = int((data.get("total_fee") or "0").strip() or 0)
    except ValueError:
        return False, "invalid_total_fee"
    if not out_p:
        return False, "missing_out_in_response"

    parsed = WechatPayNotifyParsed(
        out_trade_no=out_p,
        transaction_id=tx_id,
        total_fee=total_fee,
    )
    ok, reason = finalize_single_meal_order_wechat_pay(db, parsed)
    if ok:
        return True, reason
    return False, reason


def sync_single_meal_from_wechat_or_raise(db: Session, member_id: int, order_id: int) -> None:
    """供 HTTP 层调用：拉单成功则已 commit 入账；失败时抛出与会员端一致的 HTTPException。"""
    ok, reason = sync_single_meal_order_from_wechat_query(db, member_id, order_id)
    if not ok:
        if reason == "PAY_USERPAYING":
            raise HTTPException(
                status_code=400,
                detail="微信侧支付处理中，请稍候再试或下拉刷新订单详情",
            )
        if reason == "order_not_found":
            raise HTTPException(status_code=404, detail="订单不存在")
        if reason == "order_refunded":
            raise HTTPException(status_code=400, detail="订单已退款")
        if reason.startswith("wechat_query:"):
            raise HTTPException(
                status_code=502, detail=reason.replace("wechat_query:", "", 1)[:200]
            )
        raise HTTPException(status_code=400, detail=reason[:200])


def sync_single_meal_from_wechat_admin_or_raise(
    db: Session, order_id: int, *, store_id: int | None = None
) -> None:
    """管理端：按订单 id 向微信查单并记已支付（补救「已扣款但库未更」）。"""
    order = db.get(SingleMealOrder, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    if store_id is not None and int(order.store_id) != int(store_id):
        raise HTTPException(status_code=404, detail="订单不存在")
    sync_single_meal_from_wechat_or_raise(db, int(order.member_id), int(order_id))


def get_admin_single_meal_order_list_out(
    db: Session, *, order_id: int, store_id: int
) -> AdminSingleMealOrderListOut:
    """管理端：按主键取单次零售订单列表项（供同步支付等接口返回）。"""
    o = db.get(SingleMealOrder, int(order_id))
    if o is None or int(o.store_id) != int(store_id):
        raise HTTPException(status_code=404, detail="订单不存在")
    order_addr = (
        db.get(MemberAddress, int(o.member_address_id))
        if o.member_address_id is not None
        else None
    )
    return _build_admin_single_meal_order_list_out(db, o, order_address=order_addr)


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


def mark_single_meals_sf_awaiting_pickup_on_push_no_commit(
    db: Session, order_ids: list[int] | tuple[int, ...]
) -> int:
    """
    顺丰创单成功：单点餐进入「顺丰待取货」，等配送员取货后由回调 order_status≥15 标「配送中」。
    幂等；已送达/已取消/已在途不覆盖。
    """
    updated = 0
    for raw in order_ids:
        try:
            oid = int(raw)
        except (TypeError, ValueError):
            continue
        row = db.get(SingleMealOrder, oid)
        if not row:
            continue
        if row.pay_status != "已支付":
            continue
        if bool(getattr(row, "store_pickup", False)):
            continue
        prev = str(row.fulfillment_status or "").strip().lower()
        if prev in ("delivered", "sf_cancelled", "cancelled"):
            continue
        if prev in ("accepted", _FULFILLMENT_SF_AWAITING_PICKUP):
            continue
        if not single_meal_fulfillment_allows_dispatch(prev):
            continue
        row.fulfillment_status = _FULFILLMENT_SF_AWAITING_PICKUP
        updated += 1
    return updated


def mark_single_meals_in_delivery_on_sf_pickup_no_commit(
    db: Session, order_ids: list[int] | tuple[int, ...]
) -> int:
    """顺丰回调已取货（order_status≥15）：「顺丰待取货」→「配送中」。"""
    updated = 0
    for raw in order_ids:
        try:
            oid = int(raw)
        except (TypeError, ValueError):
            continue
        row = db.get(SingleMealOrder, oid)
        if not row:
            continue
        if row.pay_status != "已支付":
            continue
        if bool(getattr(row, "store_pickup", False)):
            continue
        prev = str(row.fulfillment_status or "").strip().lower()
        if prev == "accepted":
            continue
        if prev != _FULFILLMENT_SF_AWAITING_PICKUP:
            continue
        row.fulfillment_status = "accepted"
        updated += 1
    return updated


def _single_meal_order_ids_for_sf_push(db: Session, pus: SfSameCityPush) -> list[int]:
    oids: set[int] = set()
    snap = pus.request_snapshot if isinstance(pus.request_snapshot, dict) else {}
    raw = snap.get("fulfillment_single_meal_order_ids")
    if isinstance(raw, list):
        for x in raw:
            try:
                oids.add(int(x))
            except (TypeError, ValueError):
                pass
    oid_retail = _retail_order_id_from_stop_id(str(pus.stop_id or ""))
    if oid_retail is not None:
        oids.add(int(oid_retail))
    if pus.id is not None:
        for row in db.scalars(
            select(SingleMealOrder.id).where(SingleMealOrder.sf_same_city_push_id == int(pus.id))
        ).all():
            oids.add(int(row))
    return sorted(oids)


def sync_single_meal_pickup_status_from_sf_push_no_commit(db: Session, pus: SfSameCityPush) -> int:
    """顺丰配送状态回调：已取货时把关联单次订单标为配送中。"""
    if not sf_push_create_succeeded(pus):
        return 0
    if sf_push_is_terminal_cancel(pus):
        return 0
    st = pus.sf_callback_order_status
    if st is None:
        return 0
    try:
        n = int(st)
    except (TypeError, ValueError):
        return 0
    if n == 31 or n < _SF_ORDER_STATUS_PICKED_UP:
        return 0
    oids = _single_meal_order_ids_for_sf_push(db, pus)
    if not oids:
        return 0
    return mark_single_meals_in_delivery_on_sf_pickup_no_commit(db, oids)


# 兼容旧调用方（大表推单等）
def mark_single_meals_accepted_on_sf_push_no_commit(
    db: Session, order_ids: list[int] | tuple[int, ...]
) -> int:
    return mark_single_meals_sf_awaiting_pickup_on_push_no_commit(db, order_ids)


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


def bulk_admin_resync_single_meal_from_sf_monitor_for_delivery_day(
    db: Session,
    *,
    store_id: int,
    delivery_day: date,
    max_orders: int = 500,
) -> dict[str, Any]:
    """
    单日·单门店单次点餐：对齐顺丰监控终态到 ``single_meal_orders``。

    两路扫描（幂等）：
    1. 按「供餐日」筛订单，关联最近一次创单成功的推单；
    2. 按「供餐/业务日 = delivery_day」扫顺丰零售推单，反向更新仍滞后的订单。
    """
    mx = max(1, min(500, int(max_orders or 500)))
    rows = list(
        db.scalars(
            select(SingleMealOrder)
            .where(
                SingleMealOrder.store_id == int(store_id),
                SingleMealOrder.delivery_date == delivery_day,
            )
            .order_by(SingleMealOrder.id.desc())
            .limit(mx)
        ).all()
    )
    scanned = len(rows)
    counts: dict[str, int] = {
        "updated": 0,
        "updated_accepted": 0,
        "updated_awaiting_pickup": 0,
        "updated_in_delivery": 0,
        "updated_cancel": 0,
        "already_completed": 0,
        "already_sf_cancelled": 0,
        "already_accepted": 0,
        "skipped_unpaid": 0,
        "skipped_store_pickup": 0,
        "skipped_no_sf_push": 0,
        "skipped_sf_not_success_push": 0,
        "skipped_delivery_sheet_push": 0,
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
        elif key == "updated_accepted":
            counts["updated_accepted"] += 1
            counts["updated_in_delivery"] += 1
        elif key == "updated_awaiting_pickup":
            counts["updated_awaiting_pickup"] += 1
        elif key == "updated_in_delivery":
            counts["updated_in_delivery"] += 1
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
        # 防御：单笔不得以大表订阅合并单归因（与 resolve 收口一致）
        if str(getattr(pus, "push_kind", "") or "").strip().lower() == "delivery_sheet":
            counts["skipped_delivery_sheet_push"] += 1
            continue
        prev_f = str(o.fulfillment_status or "").strip().lower()
        if prev_f in ("pending", "sf_cancelled") and sf_push_create_succeeded(pus):
            if mark_single_meals_sf_awaiting_pickup_on_push_no_commit(db, [int(o.id)]) > 0:
                db.commit()
                db.refresh(o)
                _bump("updated_awaiting_pickup")
                touched.add(int(o.id))
                prev_f = str(o.fulfillment_status or "").strip().lower()
        elif prev_f == "accepted":
            _bump("already_accepted")
        outcome = _apply_sf_monitor_status_to_retail_order_no_commit(db, o, pus)
        if outcome in ("updated", "updated_cancel", "updated_in_delivery", "updated_awaiting_pickup"):
            db.commit()
            db.refresh(o)
        _bump(outcome)
        touched.add(int(o.id))

    delivery_days: set[date] = {delivery_day}
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
        if outcome in ("updated", "updated_cancel", "updated_in_delivery", "updated_awaiting_pickup"):
            db.commit()
            db.refresh(o)
        _bump(outcome)
        touched.add(oid)

    parts = [
        f"扫描供餐日订单 {scanned} 条",
        f"新对齐待取货 {counts['updated_awaiting_pickup']} 条",
        f"新对齐配送中 {counts['updated_in_delivery']} 条",
        f"新对齐妥投 {counts['updated']} 条",
        f"新对齐顺丰取消 {counts['updated_cancel']} 条",
        f"已是已完成 {counts['already_completed']}",
        f"已是顺丰取消 {counts['already_sf_cancelled']}",
        f"无顺丰推单 {counts['skipped_no_sf_push']}",
        f"跳过归因大表合并推单 {counts['skipped_delivery_sheet_push']}",
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
        hint_parts.append("未找到 error_code=0 的单笔顺丰推单（stop_id 须为 retail-smo-{订单id}）；大表订阅合并推单不参与单笔归因")
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
    fs = str(o.fulfillment_status or "").strip().lower()
    if fs == "accepted" or fs == _FULFILLMENT_SF_AWAITING_PICKUP:
        raise ValueError("仅「待发货」订单可指派门店配送员（已进入「待取货/配送中」请走运力侧完成送达）")
    if not single_meal_fulfillment_allows_dispatch(o.fulfillment_status):
        raise ValueError("仅「待发货」或「顺丰取消」订单可指派门店配送员")
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
    return _build_admin_single_meal_order_list_out(db, o)


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
    # 微信已退款但本地仍为「已支付」：首次退款 API 成功而 commit 失败时的补救（幂等）
    if trade_state == "REFUND":
        out_refund_no = f"RFSM{o.id}"[:32]
        if (o.pay_status or "").strip() != "已退款":
            o.pay_status = "已退款"
            db.add(o)
            db.commit()
        return {
            "message": "微信侧已完成退款，本地订单状态已同步为「已退款」",
            "out_refund_no": out_refund_no,
        }
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


def _can_admin_cancel_single_meal_order(o: SingleMealOrder) -> tuple[bool, str]:
    pay = (o.pay_status or "").strip()
    f = str(o.fulfillment_status or "").strip().lower()
    if pay == "已退款":
        return False, "已退款订单不可取消"
    if f == "delivered":
        return False, "已完成订单不可取消"
    if f == "cancelled":
        return False, "订单已是取消状态"
    if pay == "未支付":
        if f == "pending":
            return True, ""
        return False, f"当前状态不可取消（{f}）"
    if pay == "已支付" and f in ("pending", _FULFILLMENT_SF_AWAITING_PICKUP, "accepted", "sf_cancelled"):
        return True, ""
    return False, f"当前状态不可取消（支付={pay}，履约={f or '—'}）"


def _try_cancel_sf_for_retail_order(
    db: Session,
    *,
    store_id: int,
    order_id: int,
    cancel_reason: str | None,
) -> str | None:
    """若存在可取消的顺丰推单则调用 cancelorder；无推单或已终态时返回 None。"""
    from app.services.sf_same_city_service import cancel_sf_same_city_push

    pus = _latest_success_sf_push_for_retail_order(db, store_id=int(store_id), order_id=int(order_id))
    if pus is None:
        return None
    st = pus.sf_callback_order_status
    if st is not None and int(st) in (2, 17, 22, 31):
        return None
    if pus.merchant_cancel_requested_at is not None:
        return None
    cancel_sf_same_city_push(db, push_id=int(pus.id), cancel_reason=cancel_reason)
    return "已向顺丰发起取消"


def admin_cancel_single_meal_order(
    db: Session,
    *,
    order_id: int,
    store_id: int,
    cancel_reason: str | None = None,
    cancel_sf: bool = True,
) -> str:
    """管理端取消单次点餐订单（不退款）；已推顺丰时可同步请求顺丰取消。"""
    o = db.get(SingleMealOrder, int(order_id))
    if o is None or int(o.store_id) != int(store_id):
        raise ValueError("订单不存在或不属于当前门店")
    ok, err = _can_admin_cancel_single_meal_order(o)
    if not ok:
        raise ValueError(err)

    sf_msg: str | None = None
    f = str(o.fulfillment_status or "").strip().lower()
    if cancel_sf and f in ("accepted", _FULFILLMENT_SF_AWAITING_PICKUP) and not bool(getattr(o, "store_pickup", False)):
        try:
            sf_msg = _try_cancel_sf_for_retail_order(
                db,
                store_id=int(store_id),
                order_id=int(order_id),
                cancel_reason=cancel_reason,
            )
        except HTTPException as e:
            detail = e.detail if isinstance(e.detail, str) else str(e.detail)
            raise ValueError(f"顺丰取消失败：{detail}") from e

    o.fulfillment_status = "cancelled"
    o.courier_id = None
    if (o.pay_status or "").strip() == "未支付":
        release_member_coupon_for_order(
            db, order_biz=CouponLockedOrderBiz.SINGLE_MEAL, order_id=int(order_id)
        )
    db.add(o)
    db.commit()
    if sf_msg:
        return f"订单已取消（{sf_msg}）"
    return "订单已取消"


def bulk_admin_cancel_single_meal_orders(
    db: Session,
    *,
    order_ids: list[int],
    store_id: int,
    cancel_reason: str | None = None,
    cancel_sf: bool = True,
) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    for oid in order_ids:
        try:
            msg = admin_cancel_single_meal_order(
                db,
                order_id=int(oid),
                store_id=int(store_id),
                cancel_reason=cancel_reason,
                cancel_sf=cancel_sf,
            )
            results.append({"order_id": int(oid), "ok": True, "message": msg})
        except ValueError as e:
            results.append({"order_id": int(oid), "ok": False, "message": str(e)})
    return {"results": results}


def bulk_push_single_meal_retail_to_sf(
    db: Session,
    *,
    order_ids: list[int],
    store_id: int,
) -> dict[str, Any]:
    from concurrent.futures import ThreadPoolExecutor, as_completed

    from app.core.config import get_settings
    from app.db.session import SessionLocal
    from app.services.sf_same_city_service import push_single_meal_retail_to_sf

    oids = [int(x) for x in order_ids]
    if not oids:
        return {"results": []}

    def _push_one(oid: int) -> dict[str, Any]:
        sdb = SessionLocal()
        try:
            try:
                r = push_single_meal_retail_to_sf(sdb, order_id=int(oid), store_id=int(store_id))
                return {
                    "order_id": int(oid),
                    "ok": True,
                    "message": r.message or "已提交顺丰",
                    "sf_order_id": r.sf_order_id,
                }
            except ValueError as e:
                return {"order_id": int(oid), "ok": False, "message": str(e)}
        finally:
            sdb.close()

    from app.services.sf_open.user_messages import (
        MSG_BALANCE_INSUFFICIENT,
        MSG_SKIPPED_AFTER_BALANCE,
        is_sf_balance_insufficient,
    )

    balance_halt = False
    hint: str | None = None

    def _append_result(item: dict[str, Any]) -> None:
        nonlocal balance_halt, hint
        results.append(item)
        if not item.get("ok") and is_sf_balance_insufficient(
            error_code=None, message=str(item.get("message") or "")
        ):
            balance_halt = True
            hint = MSG_BALANCE_INSUFFICIENT

    results: list[dict[str, Any]] = []
    concurrency = int(get_settings().SF_PUSH_HTTP_CONCURRENCY or 1)
    if concurrency <= 1 or len(oids) == 1:
        for oid in oids:
            if balance_halt:
                _append_result(
                    {"order_id": int(oid), "ok": False, "message": MSG_SKIPPED_AFTER_BALANCE}
                )
                continue
            _append_result(_push_one(oid))
        return {"results": results, "hint": hint}

    workers = min(concurrency, len(oids))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        fut_map = {pool.submit(_push_one, oid): oid for oid in oids}
        for fut in as_completed(fut_map):
            _append_result(fut.result())
    results.sort(key=lambda x: int(x["order_id"]))
    if hint is None and any(
        not r.get("ok")
        and is_sf_balance_insufficient(error_code=None, message=str(r.get("message") or ""))
        for r in results
    ):
        hint = MSG_BALANCE_INSUFFICIENT
    return {"results": results, "hint": hint}


def bulk_admin_assign_courier_single_meal_orders(
    db: Session,
    *,
    order_ids: list[int],
    store_id: int,
    courier_id: str,
    tenant_id: int,
) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    for oid in order_ids:
        try:
            admin_assign_courier_single_meal_order(
                db,
                order_id=int(oid),
                store_id=int(store_id),
                courier_id=courier_id,
                tenant_id=int(tenant_id),
            )
            results.append({"order_id": int(oid), "ok": True, "message": "已指派配送员"})
        except ValueError as e:
            results.append({"order_id": int(oid), "ok": False, "message": str(e)})
    return {"results": results}


def admin_mark_single_meal_order_delivered(
    db: Session,
    *,
    order_id: int,
    store_id: int,
) -> str:
    """管理端：人工标记单次点餐订单已完成（适用于顺丰/UU/门店自配送等任意履约方式）。"""
    o = db.get(SingleMealOrder, int(order_id))
    if o is None or int(o.store_id) != int(store_id):
        raise ValueError("订单不存在或不属于当前门店")
    if (o.pay_status or "").strip() != "已支付":
        raise ValueError("仅已支付订单可标记完成")
    f = str(o.fulfillment_status or "").strip().lower()
    if f == "delivered":
        return "订单已是已完成"
    if f in ("cancelled", "sf_cancelled"):
        raise ValueError("已取消订单不可标记完成")
    if f not in ("pending", _FULFILLMENT_SF_AWAITING_PICKUP, "accepted"):
        raise ValueError(f"当前状态不可标记完成（{f or '—'}）")
    o.fulfillment_status = "delivered"
    db.add(o)
    db.commit()
    return "已标记为已完成"


def bulk_admin_mark_single_meal_orders_delivered(
    db: Session,
    *,
    order_ids: list[int],
    store_id: int,
) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    for oid in order_ids:
        try:
            msg = admin_mark_single_meal_order_delivered(
                db,
                order_id=int(oid),
                store_id=int(store_id),
            )
            results.append({"order_id": int(oid), "ok": True, "message": msg})
        except ValueError as e:
            results.append({"order_id": int(oid), "ok": False, "message": str(e)})
    return {"results": results}


def _can_admin_update_single_meal_fulfillment(o: SingleMealOrder) -> tuple[bool, str]:
    pay = (o.pay_status or "").strip()
    f = str(o.fulfillment_status or "").strip().lower()
    if pay == "已退款":
        return False, "已退款订单不可修改"
    if f == "cancelled":
        return False, "已取消订单不可修改"
    if f in ("accepted", _FULFILLMENT_SF_AWAITING_PICKUP):
        return False, "已推顺丰/配送中订单不可修改，请先取消配送或标记完成"
    if f in ("pending", "sf_cancelled", "delivered"):
        return True, ""
    return False, f"当前状态不可修改（履约={f or '—'}）"


def admin_update_single_meal_order(
    db: Session,
    *,
    order_id: int,
    store_id: int,
    store_pickup: bool,
    member_address_id: int | None,
) -> AdminSingleMealOrderListOut:
    """管理端修改单次点餐订单的配送方式与收货地址。"""
    o = db.get(SingleMealOrder, int(order_id))
    if o is None or int(o.store_id) != int(store_id):
        raise ValueError("订单不存在或不属于当前门店")
    ok, err = _can_admin_update_single_meal_fulfillment(o)
    if not ok:
        raise ValueError(err)

    addr_id: int | None
    area: str
    if store_pickup:
        addr_id = None
        area = "门店自提"
    else:
        addr = db.get(MemberAddress, int(member_address_id or 0))
        if not addr or int(addr.member_id) != int(o.member_id):
            raise ValueError("配送地址不存在或不属于该会员")
        nm = delivery_region_name_map(db, {int(addr.delivery_region_id)} if addr.delivery_region_id else set())
        area = routing_area_label(addr, nm)
        addr_id = int(addr.id)

    o.store_pickup = bool(store_pickup)
    o.member_address_id = addr_id
    o.routing_area = area
    if store_pickup:
        o.courier_id = None
    db.add(o)
    db.commit()
    db.refresh(o)
    return _build_admin_single_meal_order_list_out(db, o)
