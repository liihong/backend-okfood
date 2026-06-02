"""配送业务日锁单：门店当日顺丰推单全部履约完成后，当日到家名单不再随请假等实时扩表。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.delivery_log import DeliveryLog
from app.models.enums import DeliveryStatus
from app.models.sf_same_city_push import SfSameCityPush
from app.models.single_meal_order import SingleMealOrder


@dataclass(frozen=True)
class _SfPushLockLite:
    """锁单探测用轻量行：不加载 request_snapshot JSON，避免当日百条推单拖垮读接口。"""

    id: int
    store_id: int
    delivery_date: date
    stop_id: str
    push_kind: str
    error_code: int | None
    merchant_cancel_requested_at: object
    sf_callback_order_status: int | None


def _sf_push_lock_filter(store_id: int, delivery_date: date) -> tuple:
    return (
        SfSameCityPush.store_id == int(store_id),
        SfSameCityPush.delivery_date == delivery_date,
        SfSameCityPush.error_code == 0,
        SfSameCityPush.merchant_cancel_requested_at.is_(None),
        or_(
            SfSameCityPush.sf_callback_order_status.is_(None),
            SfSameCityPush.sf_callback_order_status.not_in((2, 22)),
        ),
    )


def _sf_push_lock_lite_rows(
    db: Session,
    *,
    store_id: int,
    delivery_date: date,
) -> list[_SfPushLockLite]:
    rows = db.execute(
        select(
            SfSameCityPush.id,
            SfSameCityPush.store_id,
            SfSameCityPush.delivery_date,
            SfSameCityPush.stop_id,
            SfSameCityPush.push_kind,
            SfSameCityPush.error_code,
            SfSameCityPush.merchant_cancel_requested_at,
            SfSameCityPush.sf_callback_order_status,
        ).where(*_sf_push_lock_filter(store_id, delivery_date))
    ).all()
    return [
        _SfPushLockLite(
            id=int(r[0]),
            store_id=int(r[1]),
            delivery_date=r[2],
            stop_id=str(r[3] or ""),
            push_kind=str(r[4] or ""),
            error_code=r[5],
            merchant_cancel_requested_at=r[6],
            sf_callback_order_status=r[7],
        )
        for r in rows
    ]


def _sf_push_rows_for_delivery_day_lock(
    db: Session,
    *,
    store_id: int,
    delivery_date: date,
) -> list[SfSameCityPush]:
    """当日创单成功且未商户取消的推单（未要求顺丰回调状态非空，避免 NULL 误判无推单）。"""
    return list(
        db.scalars(
            select(SfSameCityPush).where(*_sf_push_lock_filter(store_id, delivery_date))
        ).all()
    )


def _member_ids_delivered_on_date(db: Session, member_ids: set[int], delivery_date: date) -> set[int]:
    if not member_ids:
        return set()
    rows = db.scalars(
        select(DeliveryLog.member_id)
        .where(
            DeliveryLog.member_id.in_(member_ids),
            DeliveryLog.delivery_date == delivery_date,
            DeliveryLog.status == DeliveryStatus.DELIVERED.value,
        )
        .distinct()
    ).all()
    return {int(x) for x in rows}


def _retail_order_delivered(db: Session, order_id: int) -> bool:
    o = db.get(SingleMealOrder, int(order_id))
    return o is not None and str(getattr(o, "fulfillment_status", "") or "").strip().lower() == "delivered"


def _push_fulfilled_for_lock_check(db: Session, lite: _SfPushLockLite, *, delivered_mids: set[int] | None = None) -> bool:
    """单条推单是否已履约；无快照时回退完整行校验（旧数据）。"""
    from app.services.sf_order_fulfillment_service import (
        SF_ORDER_STATUS_DELIVERED_TUOTOU,
        SF_PUSH_KIND_SINGLE_MEAL_RETAIL,
        _ids_from_push_snapshot,
        _retail_smo_order_id_from_stop,
        _sf_push_effective_order_status,
        _sf_push_skip_auto_fulfillment_due_to_cancel,
        sf_push_create_succeeded,
        sf_push_fulfilled_quick_check,
    )

    class _PusShim:
        pass

    pus = _PusShim()
    pus.error_code = lite.error_code
    pus.merchant_cancel_requested_at = lite.merchant_cancel_requested_at
    pus.sf_callback_order_status = lite.sf_callback_order_status

    if not sf_push_create_succeeded(pus):
        return True
    if _sf_push_skip_auto_fulfillment_due_to_cancel(pus):
        return True
    if _sf_push_effective_order_status(pus) == SF_ORDER_STATUS_DELIVERED_TUOTOU:
        return True

    kind = (lite.push_kind or "").strip() or "delivery_sheet"
    oid_retail = _retail_smo_order_id_from_stop(lite.stop_id)
    if kind == SF_PUSH_KIND_SINGLE_MEAL_RETAIL or oid_retail is not None:
        if oid_retail is None:
            return False
        return _retail_order_delivered(db, oid_retail)

    snap = db.scalar(select(SfSameCityPush.request_snapshot).where(SfSameCityPush.id == lite.id))
    snap_mids, snap_oids = _ids_from_push_snapshot(snap)
    if snap_mids or snap_oids:
        mids_set = delivered_mids
        if snap_mids and mids_set is None:
            mids_set = _member_ids_delivered_on_date(db, {int(x) for x in snap_mids}, lite.delivery_date)
        for mid in snap_mids:
            if mids_set is None or int(mid) not in mids_set:
                return False
        for oid in snap_oids:
            if not _retail_order_delivered(db, int(oid)):
                return False
        return True

    full = db.get(SfSameCityPush, lite.id)
    if full is None:
        return True
    return sf_push_fulfilled_quick_check(db, full)


def is_delivery_day_sheet_locked(
    db: Session,
    *,
    store_id: int,
    delivery_date: date,
) -> bool:
    """
    当日是否存在有效顺丰推单且已全部履约完毕。
    无推单或未全部送达时不锁，其它业务保持原实时口径。

    读路径优化：先扫轻量元数据；顺丰回调已非妥投则立即判未锁；仅对回调为空的推单按需拉快照，
    未锁单时遇首条未履约即返回，避免当日上百条推单全量加载 JSON。
    """
    lite_rows = _sf_push_lock_lite_rows(db, store_id=int(store_id), delivery_date=delivery_date)
    if not lite_rows:
        return False

    from app.services.sf_order_fulfillment_service import SF_ORDER_STATUS_DELIVERED_TUOTOU, _sf_push_effective_order_status

    class _CallbackShim:
        pass

    pus = _CallbackShim()
    pending: list[_SfPushLockLite] = []
    for lite in lite_rows:
        pus.sf_callback_order_status = lite.sf_callback_order_status
        st = _sf_push_effective_order_status(pus)
        if st == SF_ORDER_STATUS_DELIVERED_TUOTOU:
            continue
        if st is not None:
            return False
        pending.append(lite)

    if not pending:
        return True

    # 未锁单：逐条探测，首条未履约即返回（通常仅 1 次快照查询）
    for lite in pending:
        if not _push_fulfilled_for_lock_check(db, lite):
            return False

    return True


def sf_frozen_subscription_member_ids_for_delivery_date(
    db: Session,
    *,
    store_id: int,
    delivery_date: date,
) -> frozenset[int]:
    """当日有效顺丰推单 ``fulfillment_member_ids`` 并集（与扣次快照同源）。"""
    from app.services.sf_order_fulfillment_service import (
        _ids_from_push_snapshot,
        _subscription_member_ids_for_push,
    )

    snap_rows = db.execute(
        select(SfSameCityPush.id, SfSameCityPush.request_snapshot).where(
            *_sf_push_lock_filter(int(store_id), delivery_date)
        )
    ).all()

    seen: set[int] = set()
    need_fallback: list[SfSameCityPush] = []
    for pid, snap in snap_rows:
        snap_mids, _ = _ids_from_push_snapshot(snap)
        if snap_mids:
            for mid in snap_mids:
                seen.add(int(mid))
            continue
        row = db.get(SfSameCityPush, int(pid))
        if row is not None:
            need_fallback.append(row)

    for pus in need_fallback:
        for mid in _subscription_member_ids_for_push(db, pus, None):
            seen.add(int(mid))
    return frozenset(seen)
