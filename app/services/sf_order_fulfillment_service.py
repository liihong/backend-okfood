"""顺丰同城「订单完成」回调触发：与同停靠点的智能配送大表标记送达对齐（到家扣次）；单点餐仅标履约。"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from fastapi import HTTPException
from sqlalchemy import String, and_, cast, func, or_, select, true as sql_true
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.member import Member
from app.models.single_meal_order import SingleMealOrder
from app.models.sf_same_city_push import SfSameCityPush
from app.services.admin_delivery_fulfillment_service import subscription_fulfilled_try_sf_home_no_commit
from app.services.sf_same_city_service import aggs_for_delivery_date, load_agg_for_stop_id
from app.services.single_meal_order_service import mark_single_meal_delivered_sf_completion_no_commit

logger = logging.getLogger(__name__)

# 顺丰开放平台配送推送 order_status：17=配送员妥投完单（与后台监控文案一致）
SF_ORDER_STATUS_DELIVERED_TUOTOU = 17

SF_PUSH_KIND_DELIVERY_SHEET = "delivery_sheet"
SF_PUSH_KIND_SINGLE_MEAL_RETAIL = "single_meal_retail"


def _retail_smo_order_id_from_stop(stop_id: str | None) -> int | None:
    """零售单次推单 stop_id 形如 retail-smo-{single_meal_orders.id}。"""
    s = (stop_id or "").strip()
    prefix = "retail-smo-"
    if not s.startswith(prefix):
        return None
    tail = s[len(prefix) :].strip()
    try:
        return int(tail)
    except (TypeError, ValueError):
        return None


def _push_kind_label(kind: str | None) -> str:
    k = (kind or "").strip() or SF_PUSH_KIND_DELIVERY_SHEET
    if k == SF_PUSH_KIND_SINGLE_MEAL_RETAIL:
        return "单次零售"
    return "大表合并"


def _members_from_retail_single_meal_order(db: Session, order_id: int) -> list[dict[str, Any]]:
    row = db.get(SingleMealOrder, int(order_id))
    if not row:
        return []
    m = db.get(Member, int(row.member_id)) if row.member_id else None
    return [
        {
            "member_id": int(row.member_id) if row.member_id is not None else None,
            "name": ((m.name or "").strip() if m else "") or "—",
            "phone": ((m.phone or "").strip() if m else "") or "—",
            "kind": "single_meal",
        }
    ]


def _sf_push_monitor_cancelled_clause():
    """商户已发起取消（本地标记）或顺丰回调已为取消/撤单终态；与监控页「取消订单」口径一致。"""
    return or_(
        SfSameCityPush.merchant_cancel_requested_at.isnot(None),
        SfSameCityPush.sf_callback_order_status.in_((2, 22)),
    )


def sf_monitor_create_status_label(
    *,
    error_code: int | None,
    sf_callback_order_status: int | None,
    merchant_cancel_requested_at: Any,
) -> str:
    """
    监控列表 / 导出「创单状态」列：顺丰确认取消优先于本地取消标记，其次创单 error_code。
    """
    cb = int(sf_callback_order_status) if sf_callback_order_status is not None else None
    if cb is not None and cb in (2, 22):
        return "取消订单"
    if merchant_cancel_requested_at is not None:
        return "取消订单"
    if error_code == 0:
        return "创单成功"
    if error_code is None:
        return "—"
    return f"失败 ({error_code})"


def _sf_push_monitor_where_clauses(
    *,
    delivery_date: date | None,
    store_id: int | None,
    sf_callback_order_status: int | None,
    callback_order_status_unknown: bool,
    sf_create_status: str | None = None,
    sf_order_id_contains: str | None = None,
    member_phone_contains: str | None = None,
    push_kind: str | None = None,
) -> list[Any]:
    """
    顺丰监控列表 / 导出共用 WHERE 条件。
    会员手机：在 request_snapshot JSON 文本中 LIKE（停靠点快照含 recv_phone 等）。
    顺丰单号：sf_order_id 模糊匹配。
    创单状态：ok=创单成功且未取消；fail=创单非成功；cancelled=取消订单（本地取消标记或回调 2/22）。
    """
    clauses: list[Any] = []
    if delivery_date is not None:
        clauses.append(SfSameCityPush.delivery_date == delivery_date)
    if store_id is not None:
        clauses.append(SfSameCityPush.store_id == int(store_id))
    if callback_order_status_unknown:
        clauses.append(SfSameCityPush.sf_callback_order_status.is_(None))
    elif sf_callback_order_status is not None:
        clauses.append(SfSameCityPush.sf_callback_order_status == int(sf_callback_order_status))

    st = (sf_create_status or "").strip().lower()
    if st in ("ok", "success"):
        clauses.append(SfSameCityPush.error_code == 0)
        clauses.append(~_sf_push_monitor_cancelled_clause())
    elif st in ("fail", "failed"):
        clauses.append(or_(SfSameCityPush.error_code.is_(None), SfSameCityPush.error_code != 0))
    elif st in ("cancelled", "canceled"):
        clauses.append(_sf_push_monitor_cancelled_clause())

    oid = (sf_order_id_contains or "").strip()
    if oid:
        clauses.append(SfSameCityPush.sf_order_id.isnot(None))
        clauses.append(SfSameCityPush.sf_order_id.like(f"%{oid}%"))

    ph = (member_phone_contains or "").strip()
    if ph:
        clauses.append(SfSameCityPush.request_snapshot.isnot(None))
        clauses.append(cast(SfSameCityPush.request_snapshot, String).like(f"%{ph}%"))

    pk = (push_kind or "").strip()
    if pk:
        clauses.append(SfSameCityPush.push_kind == pk)

    return clauses


def _iso_dt(x: Any) -> str | None:
    if x is None:
        return None
    if hasattr(x, "isoformat"):
        return x.isoformat()
    return str(x)


def _fallback_members_from_snapshot(snap: Any) -> list[dict[str, Any]]:
    """创单快照中的收件人姓名/电话（停靠点无法再解析时的回退）。"""
    if not isinstance(snap, dict):
        return []
    pr = snap.get("preview_row")
    if not isinstance(pr, dict):
        return []
    rname = (pr.get("recv_name") or "").strip()
    rphone = (pr.get("recv_phone") or "").strip()
    if rphone in ("—",):
        rphone = ""
    if not rname and not rphone:
        return []
    return [
        {
            "member_id": None,
            "name": rname or "—",
            "phone": rphone or "—",
            "kind": "snapshot",
        }
    ]


def _member_rows_from_agg(db: Session, agg: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for x in getattr(agg, "sub_lines", None) or []:
        mid = x.get("member_id")
        if mid is None:
            continue
        try:
            im = int(mid)
        except (TypeError, ValueError):
            continue
        out.append(
            {
                "member_id": im,
                "name": (x.get("name") or "").strip() or "—",
                "phone": (x.get("phone") or "").strip() or "—",
                "kind": "subscription",
            }
        )
    singles = getattr(agg, "singles", None) or []
    if singles:
        ids = []
        for sng in singles:
            try:
                ids.append(int(sng["id"]))
            except (KeyError, TypeError, ValueError):
                pass
        oid_mid: dict[int, int] = {}
        if ids:
            rows = db.execute(
                select(SingleMealOrder.id, SingleMealOrder.member_id).where(SingleMealOrder.id.in_(ids))
            ).all()
            for oid, mid in rows:
                if mid is not None:
                    oid_mid[int(oid)] = int(mid)
        for sng in singles:
            try:
                oid = int(sng["id"])
            except (KeyError, TypeError, ValueError):
                continue
            out.append(
                {
                    "member_id": oid_mid.get(oid),
                    "name": (sng.get("member_name") or "").strip() or "—",
                    "phone": (sng.get("member_phone") or "").strip() or "—",
                    "kind": "single_meal",
                }
            )
    return out


def _sf_push_monitor_row_dict(
    db: Session,
    r: SfSameCityPush,
    aggs: dict[str, Any],
) -> dict[str, Any]:
    agg = aggs.get(str(r.stop_id)) if aggs else None
    kind_raw = (getattr(r, "push_kind", None) or "").strip() or SF_PUSH_KIND_DELIVERY_SHEET
    oid_retail = _retail_smo_order_id_from_stop(str(r.stop_id or ""))

    members = _member_rows_from_agg(db, agg) if agg is not None else []
    if not members:
        members = _fallback_members_from_snapshot(r.request_snapshot)
    if oid_retail is not None and kind_raw == SF_PUSH_KIND_SINGLE_MEAL_RETAIL:
        alt = _members_from_retail_single_meal_order(db, oid_retail)
        if alt:
            members = alt

    return {
        "id": int(r.id),
        "store_id": int(r.store_id) if getattr(r, "store_id", None) is not None else 1,
        "delivery_date": r.delivery_date.isoformat() if r.delivery_date else "",
        "stop_id": str(r.stop_id),
        "push_kind": kind_raw,
        "push_kind_label": _push_kind_label(kind_raw),
        "shop_order_id": str(r.shop_order_id),
        "sf_order_id": str(r.sf_order_id) if r.sf_order_id else None,
        "sf_bill_id": str(r.sf_bill_id) if r.sf_bill_id else None,
        "error_code": int(r.error_code) if r.error_code is not None else None,
        "error_msg": (r.error_msg or "")[:500] if r.error_msg else None,
        "created_at": _iso_dt(r.created_at),
        "last_callback_at": _iso_dt(r.last_callback_at),
        "last_callback_kind": r.last_callback_kind,
        "sf_callback_order_status": int(r.sf_callback_order_status)
        if r.sf_callback_order_status is not None
        else None,
        "merchant_cancel_requested_at": _iso_dt(getattr(r, "merchant_cancel_requested_at", None)),
        "sf_create_status_label": sf_monitor_create_status_label(
            error_code=int(r.error_code) if r.error_code is not None else None,
            sf_callback_order_status=int(r.sf_callback_order_status)
            if r.sf_callback_order_status is not None
            else None,
            merchant_cancel_requested_at=getattr(r, "merchant_cancel_requested_at", None),
        ),
        "members": members,
    }


def _sf_push_skip_auto_fulfillment_due_to_cancel(pus: SfSameCityPush) -> bool:
    """商户已发起取消或顺丰侧已为取消流程/终态时，勿再自动扣次/标履约。"""
    if getattr(pus, "merchant_cancel_requested_at", None) is not None:
        return True
    st = pus.sf_callback_order_status
    if st is None:
        return False
    try:
        n = int(st)
    except (TypeError, ValueError):
        return False
    return n in (2, 22, 31)


def _apply_sf_same_city_stop_fulfillment(db: Session, pus: SfSameCityPush, *, operator_tag: str) -> None:
    """
    同一停靠点的订阅扣次 + 单点餐履约标记；已由各类顺丰回调按需调用。

    ``single_meal_retail``（或 stop_id 为 retail-smo-*）仅处理对应单次订单，不走大表聚合。
    """
    if int(pus.error_code or -1) != 0:
        return
    if _sf_push_skip_auto_fulfillment_due_to_cancel(pus):
        return
    kind = (getattr(pus, "push_kind", None) or "").strip() or SF_PUSH_KIND_DELIVERY_SHEET
    oid_retail = _retail_smo_order_id_from_stop(str(pus.stop_id or ""))
    if kind == SF_PUSH_KIND_SINGLE_MEAL_RETAIL or oid_retail is not None:
        if oid_retail is not None:
            mark_single_meal_delivered_sf_completion_no_commit(db, oid_retail)
        else:
            logger.warning(
                "顺丰零售推单无法解析订单号 push_kind=%s stop_id=%s",
                kind,
                pus.stop_id,
            )
        return

    sid = int(pus.store_id) if getattr(pus, "store_id", None) is not None else int(get_settings().DEFAULT_STORE_ID)
    agg = load_agg_for_stop_id(db, pus.delivery_date, pus.stop_id, store_id=sid)
    if agg is None:
        logger.warning(
            "顺丰履约未解析到停靠点 stop_id=%s date=%s store_id=%s",
            pus.stop_id,
            pus.delivery_date,
            sid,
        )
        return
    for sl in agg.sub_lines:
        if sl.get("is_delivered"):
            continue
        u = int(sl.get("units") or 0)
        if u <= 0:
            continue
        mid = int(sl["member_id"])
        try:
            subscription_fulfilled_try_sf_home_no_commit(
                db,
                member_id=mid,
                delivery_date=pus.delivery_date,
                operator_tag=operator_tag,
                store_id=sid,
            )
        except HTTPException as e:
            logger.info(
                "顺丰自动履约跳过订阅 member_id=%s date=%s detail=%s",
                mid,
                pus.delivery_date,
                getattr(e, "detail", e),
            )
    for sng in agg.singles:
        oid = int(sng["id"])
        mark_single_meal_delivered_sf_completion_no_commit(db, oid)


def apply_sf_order_complete_fulfillment(db: Session, pus: SfSameCityPush) -> None:
    """
    ``route_kind=order_complete`` 且验签通过、已匹配推单记录时调用（由回调落库前写入，同一事务 commit）。

    - 仅处理 ``error_code == 0`` 的成功创单记录。
    - 订阅：按停靠点聚合内待送达会员逐条执行与 admin 大表「标记送达（到家）」相同扣次。
    - 单次点餐：标 ``fulfillment_status=delivered``（已付餐费，不扣次数）。
    """
    _apply_sf_same_city_stop_fulfillment(db, pus, operator_tag="sf:order_complete")


def apply_sf_delivery_status_tuotou(db: Session, pus: SfSameCityPush) -> None:
    """
    「配送状态变更」回调中 ``order_status=17``（妥投完单）时调用。

    按推单行上的业务配送日执行扣次 / 单次标履约（与 ``order_complete`` 路径一致）。
    妥投常在深夜回调，不再限制「须等于上海当日日期」，避免静默跳过；
    重复回调由送达流水幂等处理。
    """
    if pus.delivery_date is None:
        return
    _apply_sf_same_city_stop_fulfillment(db, pus, operator_tag="sf:delivery_status")


def list_sf_same_city_pushes_for_monitor(
    db: Session,
    *,
    delivery_date: date | None,
    page: int,
    page_size: int,
    sf_callback_order_status: int | None = None,
    callback_order_status_unknown: bool = False,
    store_id: int | None = None,
    sf_create_status: str | None = None,
    sf_order_id_contains: str | None = None,
    member_phone_contains: str | None = None,
    push_kind: str | None = None,
) -> tuple[list[dict[str, Any]], int]:
    """按业务日、顺丰回调配送状态可选筛选，创建时间倒序分页。"""
    if callback_order_status_unknown and sf_callback_order_status is not None:
        raise ValueError("不可同时指定具体回调状态与「暂无回调状态」筛选")

    wc = _sf_push_monitor_where_clauses(
        delivery_date=delivery_date,
        store_id=store_id,
        sf_callback_order_status=sf_callback_order_status,
        callback_order_status_unknown=callback_order_status_unknown,
        sf_create_status=sf_create_status,
        sf_order_id_contains=sf_order_id_contains,
        member_phone_contains=member_phone_contains,
        push_kind=push_kind,
    )
    flt = and_(*wc) if wc else sql_true()
    fq = select(func.count()).select_from(SfSameCityPush).where(flt)
    total = int(db.scalar(fq) or 0)

    q = select(SfSameCityPush).where(flt).order_by(SfSameCityPush.id.desc())
    off = max(0, (page - 1) * page_size)
    rows = list(db.scalars(q.offset(off).limit(page_size)).all())

    agg_cache: dict[tuple[date, int], dict[str, Any]] = {}

    def _aggs_for_row(r: SfSameCityPush) -> dict[str, Any]:
        d0 = r.delivery_date
        if d0 is None:
            return {}
        sid = int(r.store_id) if getattr(r, "store_id", None) is not None else int(get_settings().DEFAULT_STORE_ID)
        k = (d0, sid)
        if k not in agg_cache:
            agg_cache[k] = aggs_for_delivery_date(db, d0, store_id=sid)
        return agg_cache[k]

    out = [_sf_push_monitor_row_dict(db, r, _aggs_for_row(r)) for r in rows]
    return out, total


def list_sf_same_city_pushes_for_monitor_export(
    db: Session,
    *,
    delivery_date: date | None,
    sf_callback_order_status: int | None = None,
    callback_order_status_unknown: bool = False,
    store_id: int | None = None,
    sf_create_status: str | None = None,
    sf_order_id_contains: str | None = None,
    member_phone_contains: str | None = None,
    push_kind: str | None = None,
) -> list[dict[str, Any]]:
    """与监控列表同源筛选，不分页；用于 Excel 导出。"""
    if delivery_date is None:
        raise ValueError("导出须指定业务日 delivery_date")

    if callback_order_status_unknown and sf_callback_order_status is not None:
        raise ValueError("不可同时指定具体回调状态与「暂无回调状态」筛选")

    wc = _sf_push_monitor_where_clauses(
        delivery_date=delivery_date,
        store_id=store_id,
        sf_callback_order_status=sf_callback_order_status,
        callback_order_status_unknown=callback_order_status_unknown,
        sf_create_status=sf_create_status,
        sf_order_id_contains=sf_order_id_contains,
        member_phone_contains=member_phone_contains,
        push_kind=push_kind,
    )
    flt = and_(*wc) if wc else sql_true()
    q = select(SfSameCityPush).where(flt).order_by(SfSameCityPush.id.desc())
    rows = list(db.scalars(q).all())

    agg_cache: dict[tuple[date, int], dict[str, Any]] = {}

    def _aggs_for_row(r: SfSameCityPush) -> dict[str, Any]:
        d0 = r.delivery_date
        if d0 is None:
            return {}
        sid = int(r.store_id) if getattr(r, "store_id", None) is not None else int(get_settings().DEFAULT_STORE_ID)
        k = (d0, sid)
        if k not in agg_cache:
            agg_cache[k] = aggs_for_delivery_date(db, d0, store_id=sid)
        return agg_cache[k]

    return [_sf_push_monitor_row_dict(db, r, _aggs_for_row(r)) for r in rows]


def count_sf_same_city_pushes_for_delivery_date(
    db: Session,
    *,
    store_id: int | None,
    delivery_date: date,
) -> dict[str, int]:
    """按推送记录上的配送业务日 ``delivery_date`` 统计创单成功 / 失败 / 取消（与列表筛选口径一致）。"""
    conds = [SfSameCityPush.delivery_date == delivery_date]
    if store_id is not None:
        conds.append(SfSameCityPush.store_id == int(store_id))

    flt = and_(*conds)
    cancelled_flt = _sf_push_monitor_cancelled_clause()
    total = int(db.scalar(select(func.count()).select_from(SfSameCityPush).where(flt)) or 0)
    cancelled = int(
        db.scalar(select(func.count()).select_from(SfSameCityPush).where(flt, cancelled_flt)) or 0
    )
    success = int(
        db.scalar(
            select(func.count()).select_from(SfSameCityPush).where(
                flt,
                SfSameCityPush.error_code == 0,
                ~cancelled_flt,
            )
        )
        or 0
    )
    failed = int(
        db.scalar(
            select(func.count()).select_from(SfSameCityPush).where(
                flt,
                or_(SfSameCityPush.error_code.is_(None), SfSameCityPush.error_code != 0),
            )
        )
        or 0
    )
    return {"total": total, "success": success, "failed": failed, "cancelled": cancelled}

