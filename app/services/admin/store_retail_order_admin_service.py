"""商城零售订单：管理端列表、履约与退款。"""

from __future__ import annotations

import logging
import time
import uuid
from copy import copy
from datetime import date
from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.integrations.wechat_pay_v2 import query_order_by_out_trade_no, refund_order_v2
from app.models.courier import Courier
from app.models.member import Member
from app.models.member_address import MemberAddress
from app.models.sf_same_city_push import SfSameCityPush
from app.models.store import Store
from app.models.store_retail_order import StoreRetailOrder
from app.schemas.admin import SfSameCityRowBase
from app.models.store_retail_product import StoreRetailProduct
from app.schemas.store_retail_order import AdminStoreRetailOrderCreateIn, AdminStoreRetailOrderListOut
from app.services.shared.store_config_service import get_store_config
from app.services.shared.tenant_integration_service import get_merged_pay_config
from app.services.client.store_retail_order_service import (
    _FULFILLMENT_AWAITING_ACCEPT,
    _FULFILLMENT_SF_AWAITING_PICKUP,
    _RETAIL_STOP_PREFIX,
    _assert_retail_product_orderable,
    _compute_retail_order_amount,
    _final_out_trade_no,
    _new_temp_out_trade_no,
    _notify_store_retail_order_paid,
    _row_to_out,
    store_retail_fulfillment_allows_dispatch,
)
from app.core.timeutil import today_shanghai
from app.services.member.member_address_service import full_address_line
from app.services.member.member_address_service import delivery_region_name_map, routing_area_label
from app.utils.sql_like import escape_like_fragment

from app.services.order.single_meal_order_service import (
    sf_push_create_succeeded,
    sf_push_is_terminal_cancel,
    sf_push_is_terminal_delivered,
)

logger = logging.getLogger(__name__)

_SF_PUSH_KIND_STORE_RETAIL = "store_retail_order"
_SF_ORDER_STATUS_PICKED_UP = 15  # 顺丰：配送员已取货
_SF_CANCEL_CALLBACK_KINDS = frozenset({"cancel_by_sf", "rider_cancel"})


def _admin_member_display_name(member: Member | None, addr: MemberAddress | None) -> str:
    if member and (member.name or "").strip() and (member.name or "").strip() not in ("微信用户", "会员"):
        return (member.name or "").strip()
    if addr and (addr.contact_name or "").strip():
        return (addr.contact_name or "").strip()
    return (member.name or "").strip() if member else ""


def _build_admin_list_out(
    db: Session, row: StoreRetailOrder, *, order_address: MemberAddress | None = None
) -> AdminStoreRetailOrderListOut:
    m = db.get(Member, row.member_id)
    aid = int(row.member_address_id) if row.member_address_id is not None else None
    addr = order_address
    if addr is None and aid is not None:
        addr = db.get(MemberAddress, aid)
    base = _row_to_out(db, row)
    return AdminStoreRetailOrderListOut(
        **base.model_dump(),
        member_id=int(row.member_id),
        member_phone=(m.phone or "") if m else "",
        member_name=_admin_member_display_name(m, addr),
        recipient_contact_name=(addr.contact_name or "").strip() if addr else "",
        address_remarks=(addr.remarks or "").strip() if addr else "",
        remark=(row.remark or "").strip() or None,
    )


def admin_accept_store_retail_order(
    db: Session, *, order_id: int, store_id: int
) -> AdminStoreRetailOrderListOut:
    """管理端：确认接单，进入待发货备货阶段。"""
    o = db.get(StoreRetailOrder, int(order_id))
    if o is None or int(o.store_id) != int(store_id):
        raise ValueError("订单不存在或不属于当前门店")
    if (o.pay_status or "").strip() != "已支付":
        raise ValueError("仅「已支付」订单可接单")
    fs = str(o.fulfillment_status or "").strip().lower()
    if fs != _FULFILLMENT_AWAITING_ACCEPT:
        raise ValueError("仅「待接单」订单可执行接单")
    o.fulfillment_status = "pending"
    db.add(o)
    db.commit()
    db.refresh(o)
    return _build_admin_list_out(db, o)


def admin_revoke_accept_store_retail_order(
    db: Session, *, order_id: int, store_id: int
) -> AdminStoreRetailOrderListOut:
    """管理端：取消接单，将订单从待发货退回待接单。"""
    o = db.get(StoreRetailOrder, int(order_id))
    if o is None or int(o.store_id) != int(store_id):
        raise ValueError("订单不存在或不属于当前门店")
    if (o.pay_status or "").strip() != "已支付":
        raise ValueError("仅「已支付」订单可取消接单")
    fs = str(o.fulfillment_status or "").strip().lower()
    if fs != "pending":
        raise ValueError("仅「待发货」订单可取消接单")
    o.fulfillment_status = _FULFILLMENT_AWAITING_ACCEPT
    o.courier_id = None
    db.add(o)
    db.commit()
    db.refresh(o)
    return _build_admin_list_out(db, o)


def update_admin_store_retail_order_remark(
    db: Session,
    *,
    order_id: int,
    store_id: int,
    remark: str | None,
) -> AdminStoreRetailOrderListOut:
    """管理端：更新商城订单后台备注。"""
    row = db.get(StoreRetailOrder, int(order_id))
    if row is None or int(row.store_id) != int(store_id):
        raise ValueError("订单不存在或不属于当前门店")
    cleaned = (remark or "").strip() or None
    row.remark = cleaned
    db.add(row)
    db.commit()
    db.refresh(row)
    return _build_admin_list_out(db, row)


def _can_admin_update_store_retail_delivery(o: StoreRetailOrder) -> tuple[bool, str]:
    """管理端：是否允许修改商城订单配送方式与收货地址。"""
    pay = (o.pay_status or "").strip()
    f = str(o.fulfillment_status or "").strip().lower()
    if pay == "已退款":
        return False, "已退款订单不可修改"
    if f == "cancelled":
        return False, "已取消订单不可修改"
    if f in ("accepted", _FULFILLMENT_SF_AWAITING_PICKUP):
        return False, "配送中订单不可修改，请先取消配送或标记完成"
    if f in (_FULFILLMENT_AWAITING_ACCEPT, "pending", "sf_cancelled", "delivered"):
        return True, ""
    return False, f"当前状态不可修改（履约={f or '—'}）"


def admin_update_store_retail_order_delivery(
    db: Session,
    *,
    order_id: int,
    store_id: int,
    store_pickup: bool,
    member_address_id: int | None,
) -> AdminStoreRetailOrderListOut:
    """管理端：修改商城订单配送方式与收货地址。"""
    o = db.get(StoreRetailOrder, int(order_id))
    if o is None or int(o.store_id) != int(store_id):
        raise ValueError("订单不存在或不属于当前门店")
    ok, err = _can_admin_update_store_retail_delivery(o)
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
    return _build_admin_list_out(db, o)


def _apply_admin_retail_fulfillment_phase_filter(filters: list, fulfillment_phase: str | None) -> None:
    """管理端商城订单：按配送阶段 Tab 过滤。

    - ``awaiting_accept``：待接单（已支付且 fulfillment=awaiting_accept，未支付订单不展示）
    - ``pending_ship``：待发货（已支付且 pending / 顺丰取消可重推）
    - ``in_delivery``：配送中（顺丰待取货 / 门店配送中）
    - ``delivered``：已完成
    - ``after_sale``：退单/售后（已取消或已退款）
    """
    fp = (fulfillment_phase or "").strip().lower()
    if fp == "awaiting_accept":
        filters.append(StoreRetailOrder.pay_status == "已支付")
        filters.append(StoreRetailOrder.fulfillment_status == _FULFILLMENT_AWAITING_ACCEPT)
    elif fp == "pending_ship":
        filters.append(StoreRetailOrder.pay_status == "已支付")
        filters.append(
            StoreRetailOrder.fulfillment_status.in_(("pending", "sf_cancelled")),
        )
    elif fp == "in_delivery":
        filters.append(StoreRetailOrder.pay_status == "已支付")
        filters.append(
            StoreRetailOrder.fulfillment_status.in_(
                (_FULFILLMENT_SF_AWAITING_PICKUP, "accepted"),
            ),
        )
    elif fp == "delivered":
        filters.append(StoreRetailOrder.fulfillment_status == "delivered")
    elif fp == "after_sale":
        filters.append(
            or_(
                StoreRetailOrder.fulfillment_status == "cancelled",
                StoreRetailOrder.pay_status == "已退款",
            ),
        )


def list_admin_store_retail_orders(
    db: Session,
    *,
    store_id: int,
    q: str | None = None,
    fulfillment_phase: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[AdminStoreRetailOrderListOut], int]:
    """管理端商城订单列表：仅按配送阶段 Tab 与搜索条件过滤，不按下单日限制。"""
    page = max(1, page)
    page_size = min(100, max(1, page_size))
    join_on = Member.id == StoreRetailOrder.member_id
    filters: list = [
        StoreRetailOrder.store_id == int(store_id),
    ]
    _apply_admin_retail_fulfillment_phase_filter(filters, fulfillment_phase)
    if q and q.strip():
        esc = escape_like_fragment(q.strip())
        filters.append(
            or_(
                Member.phone.like(f"{esc}%", escape="\\"),
                Member.name.like(f"%{esc}%", escape="\\"),
            )
        )

    total = int(
        db.scalar(select(func.count()).select_from(StoreRetailOrder).join(Member, join_on).where(*filters)) or 0
    )
    rows = db.scalars(
        select(StoreRetailOrder)
        .join(Member, join_on)
        .where(*filters)
        .order_by(StoreRetailOrder.created_at.desc(), StoreRetailOrder.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    addr_ids = {int(r.member_address_id) for r in rows if r.member_address_id is not None}
    addr_map: dict[int, MemberAddress] = {}
    if addr_ids:
        for a in db.scalars(select(MemberAddress).where(MemberAddress.id.in_(addr_ids))).all():
            addr_map[int(a.id)] = a
    return [_build_admin_list_out(db, r, order_address=addr_map.get(int(r.member_address_id or 0))) for r in rows], total


def _sync_store_retail_wechat_refunded_local(db: Session, o: StoreRetailOrder) -> bool:
    changed = False
    if (o.pay_status or "").strip() != "已退款":
        o.pay_status = "已退款"
        changed = True
    if str(o.fulfillment_status or "").strip().lower() != "cancelled":
        o.fulfillment_status = "cancelled"
        o.courier_id = None
        changed = True
    if changed:
        db.add(o)
        db.commit()
    return changed


def admin_wechat_refund_store_retail_order(db: Session, *, order_id: int, store_id: int) -> dict[str, str]:
    o = db.get(StoreRetailOrder, int(order_id))
    if o is None or int(o.store_id) != int(store_id):
        raise ValueError("订单不存在或不属于当前门店")
    pay = (o.pay_status or "").strip()
    if pay == "已退款":
        _sync_store_retail_wechat_refunded_local(db, o)
        return {"message": "订单已退款", "out_refund_no": f"RFRO{o.id}"[:32]}
    if pay != "已支付":
        raise ValueError("仅「已支付」订单可发起微信退款")
    if (o.pay_channel or "").strip() != "微信":
        raise ValueError("仅微信支付订单可原路退回")
    out_no = (o.out_trade_no or "").strip()
    if not out_no:
        raise ValueError("订单缺少商户单号，无法退款")

    pay_cfg = get_merged_pay_config(db, int(o.tenant_id), store_id=int(o.store_id))
    q = query_order_by_out_trade_no(out_no, pay=pay_cfg)
    trade_state = (q.get("trade_state") or "").strip().upper()
    out_refund_no = f"RFRO{o.id}"[:32]
    if trade_state == "REFUND":
        _sync_store_retail_wechat_refunded_local(db, o)
        return {"message": "微信侧已完成退款，本地订单状态已同步", "out_refund_no": out_refund_no}
    if trade_state != "SUCCESS":
        raise ValueError(f"微信侧订单状态为「{trade_state or '未知'}」，不可退款")
    try:
        total_fee = int((q.get("total_fee") or "0").strip())
    except ValueError as e:
        raise ValueError("无法解析微信订单金额") from e
    refund_order_v2(
        out_trade_no=out_no,
        out_refund_no=out_refund_no,
        total_fee_fen=total_fee,
        refund_fee_fen=total_fee,
        pay=pay_cfg,
        transaction_id=(o.wx_transaction_id or "").strip() or None,
    )
    _sync_store_retail_wechat_refunded_local(db, o)
    return {"message": "微信退款已受理，资金将原路退回", "out_refund_no": out_refund_no}


def admin_assign_courier_store_retail_order(
    db: Session,
    *,
    order_id: int,
    store_id: int,
    courier_id: str,
    tenant_id: int,
) -> AdminStoreRetailOrderListOut:
    o = db.get(StoreRetailOrder, int(order_id))
    if o is None or int(o.store_id) != int(store_id):
        raise ValueError("订单不存在或不属于当前门店")
    fs = str(o.fulfillment_status or "").strip().lower()
    if fs == "accepted" or fs == _FULFILLMENT_SF_AWAITING_PICKUP:
        raise ValueError("仅「待发货」订单可指派门店配送员")
    if not store_retail_fulfillment_allows_dispatch(o.fulfillment_status):
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
    return _build_admin_list_out(db, o)


def admin_mark_store_retail_order_delivered(db: Session, *, order_id: int, store_id: int) -> str:
    o = db.get(StoreRetailOrder, int(order_id))
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


def admin_cancel_store_retail_order(
    db: Session,
    *,
    order_id: int,
    store_id: int,
    cancel_reason: str | None = None,
    cancel_sf: bool = True,
) -> str:
    o = db.get(StoreRetailOrder, int(order_id))
    if o is None or int(o.store_id) != int(store_id):
        raise ValueError("订单不存在或不属于当前门店")
    pay = (o.pay_status or "").strip()
    f = str(o.fulfillment_status or "").strip().lower()
    if f == "delivered":
        raise ValueError("已完成订单不可取消")
    if f == "cancelled" and pay != "已支付":
        raise ValueError("订单已是取消状态")
    sf_msg = None
    if cancel_sf and pay == "已支付" and not o.store_pickup:
        sf_msg = _try_cancel_sf_for_store_retail(db, store_id=store_id, order_id=int(order_id), cancel_reason=cancel_reason)
    o.fulfillment_status = "cancelled"
    o.courier_id = None
    db.add(o)
    db.commit()
    parts = ["订单已取消"]
    if sf_msg:
        parts.append(sf_msg)
    return "，".join(parts)


def _resolve_sf_push_for_store_retail_order(
    db: Session, *, store_id: int, order_id: int
) -> SfSameCityPush | None:
    o = db.get(StoreRetailOrder, int(order_id))
    if o is not None and o.sf_same_city_push_id is not None:
        pus = db.get(SfSameCityPush, int(o.sf_same_city_push_id))
        if pus is not None and pus.error_code == 0:
            return pus
    stop_id = f"{_RETAIL_STOP_PREFIX}{int(order_id)}"
    return db.scalars(
        select(SfSameCityPush)
        .where(
            SfSameCityPush.stop_id == stop_id,
            SfSameCityPush.error_code == 0,
            SfSameCityPush.store_id == int(store_id),
        )
        .order_by(SfSameCityPush.id.desc())
        .limit(1)
    ).first()


def _try_cancel_sf_for_store_retail(
    db: Session,
    *,
    store_id: int,
    order_id: int,
    cancel_reason: str | None,
) -> str | None:
    from app.services.delivery.sf_same_city_service import cancel_sf_same_city_push

    pus = _resolve_sf_push_for_store_retail_order(db, store_id=int(store_id), order_id=int(order_id))
    if pus is None:
        return None
    st = pus.sf_callback_order_status
    if st is not None and int(st) in (2, 17, 22, 31):
        return None
    if pus.merchant_cancel_requested_at is not None:
        return None
    cancel_sf_same_city_push(db, push_id=int(pus.id), cancel_reason=cancel_reason)
    return "已向顺丰发起取消"


def link_store_retail_order_to_sf_push_no_commit(
    db: Session, order_id: int, pus: SfSameCityPush
) -> None:
    if pus.id is None:
        return
    row = db.get(StoreRetailOrder, int(order_id))
    if not row:
        return
    row.sf_same_city_push_id = int(pus.id)
    sf_oid = (pus.sf_order_id or "").strip() or None
    if sf_oid:
        row.sf_order_id = sf_oid
    if str(row.fulfillment_status or "").strip().lower() in ("pending", "sf_cancelled"):
        row.fulfillment_status = _FULFILLMENT_SF_AWAITING_PICKUP


def push_store_retail_order_to_sf(db: Session, *, order_id: int, store_id: int) -> dict[str, Any]:
    """商城零售订单推顺丰（stop_id=retail-sro-{id}）。"""
    from app.services.sf_open.client import SfOpenApiError, SfOpenClient
    from app.services.delivery.sf_same_city_service import (
        _create_order_payload,
        _has_active_success_push,
        _persist_fail,
        _sf_push_request_snapshot,
        _sf_retail_order_push_lock,
        merged_sf_integration_namespace,
        sf_push_user_message,
    )

    order = db.get(StoreRetailOrder, int(order_id))
    if order is None or int(order.store_id) != int(store_id):
        raise ValueError("订单不存在或不属于当前门店")
    if (order.pay_status or "").strip() != "已支付":
        raise ValueError("仅已支付订单可推送顺丰")
    if bool(order.store_pickup):
        raise ValueError("门店自提订单无需发顺丰")
    if not order.member_address_id:
        raise ValueError("订单无收货地址，无法推顺丰")
    if not store_retail_fulfillment_allows_dispatch(order.fulfillment_status):
        raise ValueError("仅「待发货」或「顺丰取消」订单可推送顺丰")

    st_row = db.get(Store, int(store_id))
    if not st_row:
        raise ValueError("门店不存在")
    retail_shop = (getattr(st_row, "sf_retail_push_shop_id", None) or "").strip()
    if not retail_shop:
        raise ValueError("请先在「门店设置」填写「零售推顺丰店铺ID」")

    tid = int(st_row.tenant_id)
    gset = merged_sf_integration_namespace(db, tid)
    if not gset.SF_OPEN_DEV_ID or not (gset.SF_OPEN_SECRET or "").strip():
        raise ValueError("请配置顺丰开发者 dev_id 与 secret")
    if not (gset.SF_PICKUP_PHONE or "").strip() or not (gset.SF_PICKUP_ADDRESS or "").strip():
        raise ValueError("请配置顺丰取件电话与取件地址")

    gset = copy(gset)
    gset.SF_OPEN_SHOP_ID = retail_shop
    if getattr(st_row, "sf_retail_push_shop_type", None) is not None:
        gset.SF_OPEN_SHOP_TYPE = int(st_row.sf_retail_push_shop_type)

    addr = db.get(MemberAddress, int(order.member_address_id))
    if not addr:
        raise ValueError("收货地址不存在")

    product_name = (order.product_title or "商城商品").strip()
    base = get_settings()
    kg_unit = float(getattr(base, "SF_KG_PER_MEAL_UNIT", None) or 0.5)
    weight_kg = max(0.01, kg_unit * max(1, int(order.quantity or 1)))

    stop_id = f"{_RETAIL_STOP_PREFIX}{order.id}"
    d = order.fulfillment_date
    if d is None:
        raise ValueError("订单缺少履约日")

    if _has_active_success_push(db, d, stop_id, store_id=int(store_id)):
        raise ValueError("该订单仍有进行中的顺丰单，请勿重复推送")

    row_sfc = SfSameCityRowBase(
        stop_id=stop_id,
        pickup_phone=(gset.SF_PICKUP_PHONE or "")[:20],
        map_location_text=(addr.map_location_text or "").strip(),
        door_detail=(addr.door_detail or "").strip(),
        recv_address=(addr.map_location_text or "").strip(),
        recv_building=(addr.door_detail or "").strip(),
        recv_name=(addr.contact_name or "").strip() or "收件人",
        recv_phone=(addr.contact_phone or "").strip(),
        recv_lng=float(addr.lng) if addr.lng is not None else None,
        recv_lat=float(addr.lat) if addr.lat is not None else None,
        product_category=product_name[:80],
        weight_kg=weight_kg,
        push_immediately=True,
        expect_delivery_at=None,
        remark=f"商城订单 #{order.id}"[:2000],
        is_direct=False,
        vehicle_type=(gset.SF_DEFAULT_VEHICLE_TYPE or "小轿车").strip(),
        is_insured=False,
        goods_value_yuan=None,
        subscription_pending_units=0,
        single_meal_count=max(1, int(order.quantity or 1)),
    )

    store_cfg = get_store_config(db, store_id=int(store_id))

    class _StoreWrap:
        __slots__ = ("store_name", "store_lng", "store_lat")

        def __init__(self, name: str | None, lng: float | None, lat: float | None):
            self.store_name = name
            self.store_lng = lng
            self.store_lat = lat

    store = _StoreWrap(store_cfg.store_name, store_cfg.store_lng, store_cfg.store_lat)
    now_ts = int(time.time())
    soid = f"OKRSRO{order.id}{uuid.uuid4().hex[:10]}"[:64]
    snap_preview = row_sfc.model_dump(mode="json")
    pld = _create_order_payload(
        row_sfc,
        shop_order_id=soid,
        gset=gset,
        store=store,
        now_ts=now_ts,
        delivery_date=d,
    )
    snap_db = _sf_push_request_snapshot(snap_preview, pld, gset=gset)

    with SfOpenClient() as httpc:
        with _sf_retail_order_push_lock(db, order_id=int(order.id)):
            if _has_active_success_push(db, d, stop_id, store_id=int(store_id)):
                raise ValueError("该订单仍有进行中的顺丰单，请勿重复推送")
            try:
                res = httpc.create_order(
                    pld,
                    dev_id=int(gset.SF_OPEN_DEV_ID),
                    app_key=(gset.SF_OPEN_SECRET or "").strip(),
                )
                r = res.get("result")
                sfo, sfb = None, None
                if isinstance(r, dict):
                    sfo, sfb = r.get("sf_order_id"), r.get("sf_bill_id")
                row_db = SfSameCityPush(
                    store_id=int(store_id),
                    delivery_date=d,
                    stop_id=stop_id,
                    push_kind=_SF_PUSH_KIND_STORE_RETAIL,
                    shop_order_id=soid,
                    sf_order_id=str(sfo) if sfo is not None else None,
                    sf_bill_id=str(sfb) if sfb is not None else None,
                    error_code=0,
                    error_msg="",
                    request_snapshot=snap_db,
                    response_json=res if isinstance(res, dict) else None,
                )
                db.add(row_db)
                db.flush()
                link_store_retail_order_to_sf_push_no_commit(db, int(order.id), row_db)
                db.add(order)
                db.commit()
                return {
                    "ok": True,
                    "message": "已提交顺丰（商城零售）",
                    "sf_order_id": str(sfo) if sfo is not None else None,
                    "stop_id": stop_id,
                }
            except SfOpenApiError as e:
                db.rollback()
                ec = int(e.error_code) if e.error_code is not None else -1
                user_msg = sf_push_user_message(error_code=ec, message=str(e))
                _persist_fail(
                    db,
                    d,
                    stop_id,
                    soid,
                    snap_db,
                    ec,
                    user_msg,
                    store_id=int(store_id),
                    push_kind=_SF_PUSH_KIND_STORE_RETAIL,
                )
                raise ValueError(user_msg) from e


def bulk_push_store_retail_orders_to_sf(
    db: Session, *, order_ids: list[int], store_id: int
) -> dict[str, Any]:
    from app.db.session import SessionLocal
    from app.services.delivery.sf_same_city_service import run_retail_sf_bulk_in_waves

    _ = db

    def _push_one(oid: int) -> dict[str, Any]:
        sdb = SessionLocal()
        try:
            try:
                out = push_store_retail_order_to_sf(db=sdb, order_id=int(oid), store_id=int(store_id))
                return {"order_id": int(oid), "ok": True, "message": out.get("message", "ok")}
            except ValueError as e:
                return {"order_id": int(oid), "ok": False, "message": str(e)}
        finally:
            sdb.close()

    return run_retail_sf_bulk_in_waves([int(x) for x in order_ids], push_one=_push_one)


def bulk_admin_assign_courier_store_retail_orders(
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
            admin_assign_courier_store_retail_order(
                db,
                order_id=int(oid),
                store_id=int(store_id),
                courier_id=courier_id,
                tenant_id=int(tenant_id),
            )
            results.append({"order_id": int(oid), "ok": True, "message": "已指派"})
        except ValueError as e:
            results.append({"order_id": int(oid), "ok": False, "message": str(e)})
    return {"results": results}


def bulk_admin_mark_store_retail_orders_delivered(
    db: Session, *, order_ids: list[int], store_id: int
) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    for oid in order_ids:
        try:
            msg = admin_mark_store_retail_order_delivered(db, order_id=int(oid), store_id=int(store_id))
            results.append({"order_id": int(oid), "ok": True, "message": msg})
        except ValueError as e:
            results.append({"order_id": int(oid), "ok": False, "message": str(e)})
    return {"results": results}


def _resolve_member_for_admin_retail_order(
    db: Session,
    *,
    phone: str,
    name: str | None,
    tenant_id: int,
    store_id: int,
) -> Member:
    """管理端建单：按手机号匹配会员；不存在时按姓名创建新会员。"""
    ph = phone.strip()
    m = db.scalar(
        select(Member).where(
            Member.phone == ph,
            Member.store_id == int(store_id),
            Member.deleted_at.is_(None),
        )
    )
    if m:
        return m
    nm = (name or "").strip()
    if not nm:
        raise HTTPException(status_code=404, detail="会员不存在，请填写姓名以创建新会员")
    m = Member(
        phone=ph[:20],
        name=nm[:100],
        tenant_id=int(tenant_id),
        store_id=int(store_id),
        wechat_name=None,
        remarks=None,
        avatar_url=None,
        balance=0,
        daily_meal_units=1,
        meal_quota_total=0,
        plan_type=None,
        is_active=False,
        is_leaved_tomorrow=False,
        leave_range_start=None,
        leave_range_end=None,
        wx_mini_openid=None,
    )
    db.add(m)
    db.flush()
    return m


def create_admin_store_retail_order(
    db: Session,
    *,
    body: AdminStoreRetailOrderCreateIn,
    tenant_id: int,
    store_id: int,
    operator: str,
) -> AdminStoreRetailOrderListOut:
    """管理端：手动创建商城零售订单（可已支付待接单或未支付）。"""
    _ = operator
    member = _resolve_member_for_admin_retail_order(
        db,
        phone=body.phone,
        name=body.name,
        tenant_id=int(tenant_id),
        store_id=int(store_id),
    )

    prod = db.get(StoreRetailProduct, int(body.retail_product_id))
    if not prod:
        raise HTTPException(status_code=404, detail="商城商品不存在")
    _assert_retail_product_orderable(db, product=prod, store_id=int(store_id))

    qty = int(body.quantity)
    if body.store_pickup:
        area = "门店自提"
        addr_id = None
    else:
        addr = db.get(MemberAddress, int(body.member_address_id or 0))
        if not addr or int(addr.member_id) != int(member.id):
            raise HTTPException(status_code=404, detail="配送地址不存在或不属于该会员")
        nm = delivery_region_name_map(db, {int(addr.delivery_region_id)} if addr.delivery_region_id else set())
        area = routing_area_label(addr, nm)
        addr_id = int(addr.id)

    if body.amount_yuan is not None:
        amount = Decimal(body.amount_yuan).quantize(Decimal("0.01"))
    else:
        amount = _compute_retail_order_amount(
            db,
            unit_price=Decimal(prod.unit_price_yuan),
            quantity=qty,
            store_pickup=bool(body.store_pickup),
            store_id=int(store_id),
        )

    pay_status = str(body.pay_status)
    pay_channel = str(body.pay_channel)
    if pay_status == "已支付":
        fulfillment_status = _FULFILLMENT_AWAITING_ACCEPT
    else:
        fulfillment_status = "pending"

    row = StoreRetailOrder(
        tenant_id=int(tenant_id),
        store_id=int(store_id),
        out_trade_no=_new_temp_out_trade_no(),
        member_id=int(member.id),
        retail_product_id=int(prod.id),
        product_title=(prod.title or "").strip() or "商品",
        member_address_id=addr_id,
        store_pickup=bool(body.store_pickup),
        quantity=qty,
        fulfillment_date=today_shanghai(),
        routing_area=area,
        amount_yuan=amount,
        pay_status=pay_status,
        pay_channel=pay_channel if pay_status == "已支付" else None,
        fulfillment_status=fulfillment_status,
        courier_id=None,
        remark=(body.remark or "管理员手动建单")[:500],
    )
    db.add(row)
    db.flush()
    row.out_trade_no = _final_out_trade_no(int(row.id))
    if pay_status == "已支付":
        _notify_store_retail_order_paid(db, row)
    db.commit()
    db.refresh(row)
    return _build_admin_list_out(db, row)


def _retail_order_id_from_stop_id(stop_id: str | None) -> int | None:
    """商城零售推单 stop_id 形如 retail-sro-{store_retail_orders.id}。"""
    s = (stop_id or "").strip()
    if not s.startswith(_RETAIL_STOP_PREFIX):
        return None
    try:
        return int(s[len(_RETAIL_STOP_PREFIX) :])
    except (TypeError, ValueError):
        return None


def _store_retail_order_bound_to_push(db: Session, order_id: int, pus: SfSameCityPush) -> bool:
    """订单已绑定 push 时，回调/同步须 push.id 一致（防同址多单串单）。"""
    o = db.get(StoreRetailOrder, int(order_id))
    if o is None:
        return False
    if o.sf_same_city_push_id is None:
        return True
    if pus.id is None:
        return False
    return int(o.sf_same_city_push_id) == int(pus.id)


def sync_store_retail_sf_order_id_for_push_no_commit(db: Session, pus: SfSameCityPush) -> int:
    """顺丰回调写入 push.sf_order_id 后，同步到已绑定该 push 的商城订单。"""
    sf_oid = (pus.sf_order_id or "").strip() or None
    if pus.id is None or not sf_oid:
        return 0
    rows = db.scalars(
        select(StoreRetailOrder).where(StoreRetailOrder.sf_same_city_push_id == int(pus.id))
    ).all()
    n = 0
    for row in rows:
        if row.sf_order_id != sf_oid:
            row.sf_order_id = sf_oid
            n += 1
    return n


def mark_store_retail_orders_in_delivery_on_sf_pickup_no_commit(
    db: Session, order_ids: list[int] | tuple[int, ...]
) -> int:
    """
    顺丰回调已取货（order_status≥15）：商城订单标为「配送中」。

    支持：
    - ``sf_awaiting_pickup`` → ``accepted``
    - ``sf_cancelled`` → ``accepted``（骑士撤单后重派并取货）
    """
    updated = 0
    for raw in order_ids:
        try:
            oid = int(raw)
        except (TypeError, ValueError):
            continue
        row = db.get(StoreRetailOrder, oid)
        if not row:
            continue
        if (row.pay_status or "").strip() != "已支付":
            continue
        if bool(row.store_pickup):
            continue
        prev = str(row.fulfillment_status or "").strip().lower()
        if prev == "accepted":
            continue
        if prev not in (_FULFILLMENT_SF_AWAITING_PICKUP, "sf_cancelled"):
            continue
        row.fulfillment_status = "accepted"
        updated += 1
    return updated


def mark_store_retail_delivered_sf_completion_no_commit(db: Session, order_id: int) -> None:
    """顺丰妥投：商城订单标履约已送达（幂等）。"""
    row = db.get(StoreRetailOrder, int(order_id))
    if not row:
        return
    if (row.pay_status or "").strip() != "已支付":
        return
    if str(row.fulfillment_status or "").strip().lower() == "delivered":
        return
    if bool(row.store_pickup):
        return
    row.fulfillment_status = "delivered"


def mark_store_retail_sf_cancelled_no_commit(db: Session, order_id: int) -> None:
    """顺丰取消/撤单：商城订单标 ``sf_cancelled``（已送达的不覆盖）。"""
    row = db.get(StoreRetailOrder, int(order_id))
    if not row:
        return
    if (row.pay_status or "").strip() != "已支付":
        return
    prev = str(row.fulfillment_status or "").strip().lower()
    if prev in ("delivered", "sf_cancelled"):
        return
    if bool(row.store_pickup):
        return
    row.fulfillment_status = "sf_cancelled"


def _store_retail_order_ids_for_sf_push(db: Session, pus: SfSameCityPush) -> list[int]:
    oids: set[int] = set()
    oid_retail = _retail_order_id_from_stop_id(str(pus.stop_id or ""))
    if oid_retail is not None:
        oids.add(int(oid_retail))
    if pus.id is not None:
        for row in db.scalars(
            select(StoreRetailOrder.id).where(StoreRetailOrder.sf_same_city_push_id == int(pus.id))
        ).all():
            oids.add(int(row))
    return sorted(oids)


def sync_store_retail_pickup_status_from_sf_push_no_commit(db: Session, pus: SfSameCityPush) -> int:
    """顺丰配送状态回调：已取货时把关联商城订单标为配送中。"""
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
    oids = _store_retail_order_ids_for_sf_push(db, pus)
    if not oids:
        return 0
    return mark_store_retail_orders_in_delivery_on_sf_pickup_no_commit(db, oids)


def _apply_sf_monitor_status_to_store_retail_order_no_commit(
    db: Session,
    o: StoreRetailOrder,
    pus: SfSameCityPush,
) -> str | None:
    """
    按顺丰监控行回写商城零售订单履约状态（不 commit）。
    返回与单次零售对齐的 outcome 字符串。
    """
    if (o.pay_status or "").strip() != "已支付":
        return "skipped_unpaid"
    if bool(o.store_pickup):
        return "skipped_store_pickup"
    if not sf_push_create_succeeded(pus):
        return "skipped_sf_not_success_push"
    pk = str(getattr(pus, "push_kind", "") or "").strip().lower()
    if pk and pk not in (_SF_PUSH_KIND_STORE_RETAIL,):
        return "skipped_wrong_push_kind"

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
        mark_store_retail_sf_cancelled_no_commit(db, int(o.id))
        after = str(o.fulfillment_status or "").strip().lower()
        return "updated_cancel" if after == "sf_cancelled" else "skipped_sf_cancel"

    if n is None or n < _SF_ORDER_STATUS_PICKED_UP:
        if prev_f == "accepted":
            o.fulfillment_status = _FULFILLMENT_SF_AWAITING_PICKUP
            return "updated_awaiting_pickup"
        if prev_f == "pending" and sf_push_create_succeeded(pus):
            link_store_retail_order_to_sf_push_no_commit(db, int(o.id), pus)
            if str(o.fulfillment_status or "").strip().lower() == _FULFILLMENT_SF_AWAITING_PICKUP:
                return "updated_awaiting_pickup"
        return "skipped_sf_status_not_terminal"

    if prev_f == _FULFILLMENT_SF_AWAITING_PICKUP:
        if mark_store_retail_orders_in_delivery_on_sf_pickup_no_commit(db, [int(o.id)]) > 0:
            prev_f = "accepted"

    if sf_push_is_terminal_delivered(pus):
        if prev_f == "delivered":
            return "already_completed"
        if pus.merchant_cancel_requested_at is not None:
            return "skipped_merchant_cancel_marker"
        mark_store_retail_delivered_sf_completion_no_commit(db, int(o.id))
        after = str(o.fulfillment_status or "").strip().lower()
        return "updated" if after == "delivered" else "skipped_sf_status_not_terminal"

    if prev_f == "accepted":
        return "already_accepted"
    if prev_f == _FULFILLMENT_SF_AWAITING_PICKUP:
        return "skipped_sf_status_not_terminal"
    if mark_store_retail_orders_in_delivery_on_sf_pickup_no_commit(db, [int(o.id)]) > 0:
        return "updated_in_delivery"
    return "skipped_sf_status_not_terminal"


def admin_resync_store_retail_from_sf_monitor(
    db: Session,
    *,
    order_id: int,
    store_id: int,
) -> str:
    """商城零售顺丰单：按监控终态幂等回写 ``store_retail_orders``。"""
    o = db.get(StoreRetailOrder, int(order_id))
    if o is None or int(o.store_id) != int(store_id):
        raise ValueError("订单不存在或不属于当前门店")
    pus = _resolve_sf_push_for_store_retail_order(db, store_id=int(store_id), order_id=int(order_id))
    if pus is None:
        raise ValueError("未找到本订单已成功创单的顺丰推送记录（请确认已推顺丰）")
    if pus.sf_callback_order_status is None and not (pus.last_callback_kind or "").strip():
        raise ValueError("尚未收到顺丰配送回调（请先确认开放平台回调可达且验签通过）")
    if not sf_push_is_terminal_cancel(pus) and not sf_push_is_terminal_delivered(pus):
        st = pus.sf_callback_order_status
        kind = (pus.last_callback_kind or "").strip() or "—"
        # 非终态但已取货(≥15)仍可对齐为配送中
        try:
            n = int(st) if st is not None else None
        except (TypeError, ValueError):
            n = None
        if n is None or n < _SF_ORDER_STATUS_PICKED_UP:
            raise ValueError(
                f"顺丰推送尚未处于可对齐的状态（当前状态编码 {st!r}，最近回调 {kind}）。"
                "请在「顺丰订单监控」确认已为妥投(17)或取消/撤单，或配送员已取货(≥15)。"
            )

    prev = str(o.fulfillment_status or "").strip().lower()
    outcome = _apply_sf_monitor_status_to_store_retail_order_no_commit(db, o, pus)
    db.commit()
    db.refresh(o)
    after = str(o.fulfillment_status or "").strip().lower()

    if sf_push_is_terminal_cancel(pus):
        if after != "sf_cancelled":
            raise ValueError("不满足标为顺丰取消条件（例如未支付、门店自提等），未修改订单状态")
        if prev == "sf_cancelled":
            return "订单已是顺丰取消，无需重复同步"
        return "已同步为顺丰取消"

    if sf_push_is_terminal_delivered(pus):
        if after != "delivered":
            raise ValueError("不满足标为已完成条件，未修改订单状态")
        if prev == "delivered":
            return "订单已是已完成，无需重复同步"
        return "已同步为已完成"

    if outcome == "updated_in_delivery":
        return "已同步为配送中"
    if outcome == "updated_awaiting_pickup":
        return "已同步为顺丰待取货"
    if outcome == "already_accepted":
        return "订单已是配送中，无需重复同步"
    raise ValueError("顺丰状态未能对齐到订单，请查看监控详情")


def bulk_admin_resync_store_retail_from_sf_monitor(
    db: Session,
    *,
    store_id: int,
    max_orders: int = 500,
    fulfillment_date: date | None = None,
) -> dict[str, Any]:
    """
    批量对齐商城零售订单与顺丰监控状态（幂等）。

    - 扫描未完成的顺丰商城订单，按 push 回调回写待取货/配送中/已完成/顺丰取消
    - 可选 ``fulfillment_date`` 限定履约日；默认扫描全部门店未完成顺丰单
    """
    mx = max(1, min(500, int(max_orders or 500)))
    filters = [
        StoreRetailOrder.store_id == int(store_id),
        StoreRetailOrder.pay_status == "已支付",
        StoreRetailOrder.store_pickup.is_(False),
        StoreRetailOrder.fulfillment_status.in_(
            ("pending", _FULFILLMENT_SF_AWAITING_PICKUP, "accepted", "sf_cancelled")
        ),
    ]
    if fulfillment_date is not None:
        filters.append(StoreRetailOrder.fulfillment_date == fulfillment_date)

    rows = list(
        db.scalars(
            select(StoreRetailOrder)
            .where(*filters)
            .order_by(StoreRetailOrder.id.desc())
            .limit(mx)
        ).all()
    )
    scanned = len(rows)
    counts: dict[str, int] = {
        "updated": 0,
        "updated_in_delivery": 0,
        "updated_awaiting_pickup": 0,
        "updated_cancel": 0,
        "already_completed": 0,
        "already_sf_cancelled": 0,
        "already_accepted": 0,
        "skipped_unpaid": 0,
        "skipped_store_pickup": 0,
        "skipped_no_sf_push": 0,
        "skipped_sf_not_success_push": 0,
        "skipped_wrong_push_kind": 0,
        "skipped_sf_status_not_tuotou": 0,
        "skipped_sf_cancel": 0,
        "skipped_merchant_cancel_marker": 0,
    }
    touched: set[int] = set()

    def _bump(outcome: str | None) -> None:
        if not outcome:
            return
        if outcome == "updated":
            counts["updated"] += 1
        elif outcome == "updated_in_delivery":
            counts["updated_in_delivery"] += 1
        elif outcome == "updated_awaiting_pickup":
            counts["updated_awaiting_pickup"] += 1
        elif outcome == "updated_cancel":
            counts["updated_cancel"] += 1
        elif outcome in counts:
            counts[outcome] += 1
        else:
            counts["skipped_sf_status_not_tuotou"] += 1

    for o in rows:
        pus = _resolve_sf_push_for_store_retail_order(db, store_id=int(store_id), order_id=int(o.id))
        if pus is None:
            counts["skipped_no_sf_push"] += 1
            continue
        prev_f = str(o.fulfillment_status or "").strip().lower()
        if prev_f in ("pending", "sf_cancelled") and sf_push_create_succeeded(pus):
            link_store_retail_order_to_sf_push_no_commit(db, int(o.id), pus)
            if str(o.fulfillment_status or "").strip().lower() == _FULFILLMENT_SF_AWAITING_PICKUP:
                db.commit()
                db.refresh(o)
                _bump("updated_awaiting_pickup")
                touched.add(int(o.id))
                prev_f = str(o.fulfillment_status or "").strip().lower()
        elif prev_f == "accepted":
            _bump("already_accepted")
        outcome = _apply_sf_monitor_status_to_store_retail_order_no_commit(db, o, pus)
        if outcome in ("updated", "updated_cancel", "updated_in_delivery", "updated_awaiting_pickup"):
            db.commit()
            db.refresh(o)
        _bump(outcome)
        touched.add(int(o.id))

    push_filters = [
        SfSameCityPush.store_id == int(store_id),
        SfSameCityPush.error_code == 0,
        SfSameCityPush.push_kind == _SF_PUSH_KIND_STORE_RETAIL,
        SfSameCityPush.stop_id.like(f"{_RETAIL_STOP_PREFIX}%"),
        or_(
            SfSameCityPush.sf_callback_order_status >= _SF_ORDER_STATUS_PICKED_UP,
            SfSameCityPush.last_callback_kind.in_(tuple(_SF_CANCEL_CALLBACK_KINDS)),
        ),
    ]
    if fulfillment_date is not None:
        push_filters.append(SfSameCityPush.delivery_date == fulfillment_date)

    push_rows = list(
        db.scalars(
            select(SfSameCityPush)
            .where(*push_filters)
            .order_by(SfSameCityPush.id.desc())
            .limit(mx)
        ).all()
    )

    for pus in push_rows:
        oid = _retail_order_id_from_stop_id(str(pus.stop_id or ""))
        if oid is None or oid in touched:
            continue
        o = db.get(StoreRetailOrder, oid)
        if o is None or int(o.store_id) != int(store_id):
            continue
        outcome = _apply_sf_monitor_status_to_store_retail_order_no_commit(db, o, pus)
        if outcome in ("updated", "updated_cancel", "updated_in_delivery", "updated_awaiting_pickup"):
            db.commit()
            db.refresh(o)
        _bump(outcome)
        touched.add(oid)

    parts = [
        f"扫描商城订单 {scanned} 条",
        f"新对齐待取货 {counts['updated_awaiting_pickup']} 条",
        f"新对齐配送中 {counts['updated_in_delivery']} 条",
        f"新对齐妥投 {counts['updated']} 条",
        f"新对齐顺丰取消 {counts['updated_cancel']} 条",
        f"已是已完成 {counts['already_completed']}",
        f"已是顺丰取消 {counts['already_sf_cancelled']}",
        f"无顺丰推单 {counts['skipped_no_sf_push']}",
        f"顺丰未妥投/未取货或未回调 {counts['skipped_sf_status_not_tuotou']}",
    ]
    summary = (
        "；".join(parts)
        + "。（依据本系统收到的顺丰推送落库对齐；不向运力主动查询；门店自配送仍由手工标记）"
    )
    return {"scanned": scanned, "sf_push_scanned": len(push_rows), **counts, "summary": summary}
