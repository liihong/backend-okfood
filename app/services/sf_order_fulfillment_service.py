"""顺丰同城「订单完成」回调触发：与同停靠点的智能配送大表标记送达对齐（到家扣次）；单点餐仅标履约。"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.sf_same_city_push import SfSameCityPush
from app.services.admin_delivery_fulfillment_service import subscription_fulfilled_try_sf_home_no_commit
from app.services.sf_same_city_service import load_agg_for_stop_id
from app.services.single_meal_order_service import mark_single_meal_delivered_sf_completion_no_commit

logger = logging.getLogger(__name__)


def apply_sf_order_complete_fulfillment(db: Session, pus: SfSameCityPush) -> None:
    """
    ``route_kind=order_complete`` 且验签通过、已匹配推单记录时调用（由回调落库前写入，同一事务 commit）。

    - 仅处理 ``error_code == 0`` 的成功创单记录。
    - 订阅：按停靠点聚合内待送达会员逐条执行与 admin 大表「标记送达（到家）」相同扣次。
    - 单次点餐：标 ``fulfillment_status=delivered``（已付餐费，不扣次数）。
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
            subscription_fulfilled_try_sf_home_no_commit(db, member_id=mid, delivery_date=pus.delivery_date)
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


def list_sf_same_city_pushes_for_monitor(
    db: Session,
    *,
    delivery_date: date | None,
    page: int,
    page_size: int,
) -> tuple[list[dict[str, Any]], int]:
    """按业务日可选筛选，创建时间倒序分页。"""
    fq = select(func.count()).select_from(SfSameCityPush)
    if delivery_date is not None:
        fq = fq.where(SfSameCityPush.delivery_date == delivery_date)
    total = int(db.scalar(fq) or 0)

    q = select(SfSameCityPush)
    if delivery_date is not None:
        q = q.where(SfSameCityPush.delivery_date == delivery_date)
    q = q.order_by(SfSameCityPush.id.desc())
    off = max(0, (page - 1) * page_size)
    rows = list(db.scalars(q.offset(off).limit(page_size)).all())

    out: list[dict[str, Any]] = []
    for r in rows:

        def iso_dt(x: Any) -> str | None:
            if x is None:
                return None
            if hasattr(x, "isoformat"):
                return x.isoformat()
            return str(x)

        out.append(
            {
                "id": int(r.id),
                "delivery_date": r.delivery_date.isoformat() if r.delivery_date else "",
                "stop_id": str(r.stop_id),
                "shop_order_id": str(r.shop_order_id),
                "sf_order_id": str(r.sf_order_id) if r.sf_order_id else None,
                "sf_bill_id": str(r.sf_bill_id) if r.sf_bill_id else None,
                "error_code": int(r.error_code) if r.error_code is not None else None,
                "error_msg": (r.error_msg or "")[:500] if r.error_msg else None,
                "created_at": iso_dt(r.created_at),
                "last_callback_at": iso_dt(r.last_callback_at),
                "last_callback_kind": r.last_callback_kind,
                "sf_callback_order_status": int(r.sf_callback_order_status)
                if r.sf_callback_order_status is not None
                else None,
            }
        )
    return out, total

