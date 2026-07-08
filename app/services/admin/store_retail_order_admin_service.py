"""商城零售订单：管理端列表、履约与退款。"""

from __future__ import annotations

import logging
import time
import uuid
from copy import copy
from decimal import Decimal
from typing import Any

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
from app.schemas.store_retail_order import AdminStoreRetailOrderListOut
from app.services.shared.store_config_service import get_store_config
from app.services.shared.tenant_integration_service import get_merged_pay_config
from app.services.client.store_retail_order_service import (
    _FULFILLMENT_AWAITING_ACCEPT,
    _FULFILLMENT_SF_AWAITING_PICKUP,
    _RETAIL_STOP_PREFIX,
    _row_to_out,
    store_retail_fulfillment_allows_dispatch,
)
from app.utils.sql_like import escape_like_fragment

logger = logging.getLogger(__name__)

_SF_PUSH_KIND_STORE_RETAIL = "store_retail_order"


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
    from app.integrations.sf_open_client import SfOpenApiError, SfOpenClient
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

    with SfOpenClient() as httpc:
        with _sf_retail_order_push_lock(db, order_id=int(order.id)):
            if _has_active_success_push(db, d, stop_id, store_id=int(store_id)):
                raise ValueError("该订单仍有进行中的顺丰单，请勿重复推送")
            pld = _create_order_payload(
                row_sfc,
                shop_order_id=soid,
                gset=gset,
                store=store,
                now_ts=now_ts,
                delivery_date=d,
            )
            snap_db = _sf_push_request_snapshot(snap_preview, pld, gset=gset)
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
    results: list[dict[str, Any]] = []
    for oid in order_ids:
        try:
            out = push_store_retail_order_to_sf(db, order_id=int(oid), store_id=int(store_id))
            results.append({"order_id": int(oid), "ok": True, "message": out.get("message", "ok")})
        except ValueError as e:
            results.append({"order_id": int(oid), "ok": False, "message": str(e)})
    return {"results": results}


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
