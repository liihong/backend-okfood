"""顺丰同城「订单完成」回调触发：与同停靠点的智能配送大表标记送达对齐（到家扣次）；单点餐仅标履约。"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.single_meal_order import SingleMealOrder
from app.models.sf_same_city_push import SfSameCityPush
from app.services.admin_delivery_fulfillment_service import subscription_fulfilled_try_sf_home_no_commit
from app.services.sf_same_city_service import aggs_for_delivery_date, load_agg_for_stop_id
from app.services.single_meal_order_service import mark_single_meal_delivered_sf_completion_no_commit

logger = logging.getLogger(__name__)

# 顺丰开放平台配送推送 order_status：17=配送员妥投完单（与后台监控文案一致）
SF_ORDER_STATUS_DELIVERED_TUOTOU = 17


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
    agg_by_date: dict[date, dict[str, Any]],
) -> dict[str, Any]:
    agg = agg_by_date.get(r.delivery_date, {}).get(str(r.stop_id)) if r.delivery_date else None
    members = _member_rows_from_agg(db, agg) if agg is not None else []
    if not members:
        members = _fallback_members_from_snapshot(r.request_snapshot)

    return {
        "id": int(r.id),
        "delivery_date": r.delivery_date.isoformat() if r.delivery_date else "",
        "stop_id": str(r.stop_id),
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
        "members": members,
    }


def _apply_sf_same_city_stop_fulfillment(db: Session, pus: SfSameCityPush, *, operator_tag: str) -> None:
    """
    同一停靠点的订阅扣次 + 单点餐履约标记；已由各类顺丰回调按需调用。
    """
    if int(pus.error_code or -1) != 0:
        return
    agg = load_agg_for_stop_id(db, pus.delivery_date, pus.stop_id)
    if agg is None:
        logger.warning("顺丰履约未解析到停靠点 stop_id=%s date=%s", pus.stop_id, pus.delivery_date)
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
                db, member_id=mid, delivery_date=pus.delivery_date, operator_tag=operator_tag
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
) -> tuple[list[dict[str, Any]], int]:
    """按业务日、顺丰回调配送状态可选筛选，创建时间倒序分页。"""
    if callback_order_status_unknown and sf_callback_order_status is not None:
        raise ValueError("不可同时指定具体回调状态与「暂无回调状态」筛选")

    fq = select(func.count()).select_from(SfSameCityPush)
    if delivery_date is not None:
        fq = fq.where(SfSameCityPush.delivery_date == delivery_date)
    if callback_order_status_unknown:
        fq = fq.where(SfSameCityPush.sf_callback_order_status.is_(None))
    elif sf_callback_order_status is not None:
        fq = fq.where(SfSameCityPush.sf_callback_order_status == int(sf_callback_order_status))
    total = int(db.scalar(fq) or 0)

    q = select(SfSameCityPush)
    if delivery_date is not None:
        q = q.where(SfSameCityPush.delivery_date == delivery_date)
    if callback_order_status_unknown:
        q = q.where(SfSameCityPush.sf_callback_order_status.is_(None))
    elif sf_callback_order_status is not None:
        q = q.where(SfSameCityPush.sf_callback_order_status == int(sf_callback_order_status))
    q = q.order_by(SfSameCityPush.id.desc())
    off = max(0, (page - 1) * page_size)
    rows = list(db.scalars(q.offset(off).limit(page_size)).all())

    agg_by_date: dict[date, dict[str, Any]] = {}
    for d0 in {r.delivery_date for r in rows if r.delivery_date is not None}:
        agg_by_date[d0] = aggs_for_delivery_date(db, d0)

    out = [_sf_push_monitor_row_dict(db, r, agg_by_date) for r in rows]
    return out, total


def list_sf_same_city_pushes_for_monitor_export(
    db: Session,
    *,
    delivery_date: date | None,
    sf_callback_order_status: int | None = None,
    callback_order_status_unknown: bool = False,
) -> list[dict[str, Any]]:
    """与监控列表同源筛选，不分页；用于 Excel 导出。"""
    if delivery_date is None:
        raise ValueError("导出须指定业务日 delivery_date")

    if callback_order_status_unknown and sf_callback_order_status is not None:
        raise ValueError("不可同时指定具体回调状态与「暂无回调状态」筛选")

    q = select(SfSameCityPush).where(SfSameCityPush.delivery_date == delivery_date)
    if callback_order_status_unknown:
        q = q.where(SfSameCityPush.sf_callback_order_status.is_(None))
    elif sf_callback_order_status is not None:
        q = q.where(SfSameCityPush.sf_callback_order_status == int(sf_callback_order_status))
    q = q.order_by(SfSameCityPush.id.desc())
    rows = list(db.scalars(q).all())

    agg_by_date: dict[date, dict[str, Any]] = {}
    if rows:
        agg_by_date[delivery_date] = aggs_for_delivery_date(db, delivery_date)

    return [_sf_push_monitor_row_dict(db, r, agg_by_date) for r in rows]

