"""配送业务日锁单：大表顺丰推单后冻结订阅名单；全部履约完成后口径与冻结快照一致。"""

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


def _delivery_sheet_push_kind_clause():
    from app.services.delivery.sf_order_fulfillment_service import SF_PUSH_KIND_DELIVERY_SHEET

    return or_(
        SfSameCityPush.push_kind.is_(None),
        SfSameCityPush.push_kind == "",
        SfSameCityPush.push_kind == SF_PUSH_KIND_DELIVERY_SHEET,
    )


def _dinner_delivery_sheet_push_kind_clause():
    from app.services.delivery.sf_order_fulfillment_service import SF_PUSH_KIND_DINNER_DELIVERY_SHEET

    return SfSameCityPush.push_kind == SF_PUSH_KIND_DINNER_DELIVERY_SHEET


def has_dinner_delivery_sheet_sf_push_on_date(
    db: Session,
    *,
    store_id: int,
    delivery_date: date,
) -> bool:
    """当日是否存在创单成功的晚餐配送大表顺丰推单（与午餐 push_kind 隔离）。"""
    row_id = db.scalar(
        select(SfSameCityPush.id)
        .where(
            *_sf_push_lock_filter(int(store_id), delivery_date),
            _dinner_delivery_sheet_push_kind_clause(),
        )
        .limit(1)
    )
    return row_id is not None


def _sf_push_lock_filter_for_meal_period(
    store_id: int,
    delivery_date: date,
    meal_period: str,
) -> tuple:
    """按餐段选择顺丰推单 push_kind 过滤条件。"""
    from app.services.meal_period.constants import DEFAULT_MEAL_PERIOD

    period = (meal_period or DEFAULT_MEAL_PERIOD).strip().lower()
    base = list(_sf_push_lock_filter(int(store_id), delivery_date))
    if period == "dinner":
        base.append(_dinner_delivery_sheet_push_kind_clause())
    else:
        base.append(_delivery_sheet_push_kind_clause())
    return tuple(base)


def _sf_push_lock_filter(store_id: int, delivery_date: date, *, delivery_sheet_only: bool = False) -> tuple:
    clauses: list = [
        SfSameCityPush.store_id == int(store_id),
        SfSameCityPush.delivery_date == delivery_date,
        SfSameCityPush.error_code == 0,
        SfSameCityPush.merchant_cancel_requested_at.is_(None),
        or_(
            SfSameCityPush.sf_callback_order_status.is_(None),
            SfSameCityPush.sf_callback_order_status.not_in((2, 22)),
        ),
    ]
    if delivery_sheet_only:
        clauses.append(_delivery_sheet_push_kind_clause())
    return tuple(clauses)


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
    from app.services.delivery.sf_order_fulfillment_service import (
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


def has_delivery_sheet_sf_push_on_date(
    db: Session,
    *,
    store_id: int,
    delivery_date: date,
) -> bool:
    """当日是否存在创单成功的智能配送大表（订阅合并）顺丰推单。"""
    row_id = db.scalar(
        select(SfSameCityPush.id).where(
            *_sf_push_lock_filter(int(store_id), delivery_date, delivery_sheet_only=True)
        ).limit(1)
    )
    return row_id is not None


def is_delivery_day_sheet_frozen_after_sf_push(
    db: Session,
    *,
    store_id: int,
    delivery_date: date,
) -> bool:
    """大表已向顺丰推单后冻结当日订阅扩表（与 ``has_delivery_sheet_sf_push_on_date`` 同义）。"""
    return has_delivery_sheet_sf_push_on_date(
        db, store_id=int(store_id), delivery_date=delivery_date
    )


def is_delivery_day_sheet_locked_for_period(
    db: Session,
    *,
    store_id: int,
    delivery_date: date,
    meal_period: str,
) -> bool:
    """按餐段判断当日推单是否已全部履约（用于取消请假是否通知运维）。"""
    from app.services.meal_period.constants import DEFAULT_MEAL_PERIOD
    from app.services.delivery.sf_order_fulfillment_service import (
        SF_ORDER_STATUS_DELIVERED_TUOTOU,
        SF_PUSH_KIND_DINNER_DELIVERY_SHEET,
        SF_PUSH_KIND_DELIVERY_SHEET,
        _sf_push_effective_order_status,
    )

    period = (meal_period or DEFAULT_MEAL_PERIOD).strip().lower()
    lite_rows = _sf_push_lock_lite_rows(db, store_id=int(store_id), delivery_date=delivery_date)
    if period == "dinner":
        lite_rows = [r for r in lite_rows if r.push_kind == SF_PUSH_KIND_DINNER_DELIVERY_SHEET]
    else:
        lite_rows = [r for r in lite_rows if r.push_kind != SF_PUSH_KIND_DINNER_DELIVERY_SHEET]
    if not lite_rows:
        return False

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

    from app.services.delivery.sf_order_fulfillment_service import sf_push_fulfilled_quick_check

    for lite in pending:
        full = db.get(SfSameCityPush, int(lite.id))
        if full is None:
            return False
        if not sf_push_fulfilled_quick_check(db, full):
            return False
    return True


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

    from app.services.delivery.sf_order_fulfillment_service import SF_ORDER_STATUS_DELIVERED_TUOTOU, _sf_push_effective_order_status

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


def sf_cancelled_sheet_member_ids_for_delivery_date(
    db: Session,
    *,
    store_id: int,
    delivery_date: date,
    meal_period: str | None = None,
) -> frozenset[int]:
    """
    当日已取消的大表合并推单 ``fulfillment_member_ids`` 并集。

    锁单日大表待送名单补全：取消后会员可能不在首次推单 frozen 快照内，仍须可见以便重推。
    meal_period 区分午/晚餐 push_kind，避免交叉污染。
    """
    from app.services.delivery.sf_order_fulfillment_service import _ids_from_push_snapshot
    from app.services.delivery.sf_same_city_service import (
        _delivery_sheet_push_kind_predicate,
        _sf_push_row_cancelled_predicate,
    )
    from app.services.meal_period.constants import DEFAULT_MEAL_PERIOD

    period = (meal_period or DEFAULT_MEAL_PERIOD).strip().lower()
    if period == "dinner":
        kind_clause = _dinner_delivery_sheet_push_kind_clause()
    else:
        kind_clause = _delivery_sheet_push_kind_predicate()

    filt = (
        SfSameCityPush.store_id == int(store_id),
        SfSameCityPush.delivery_date == delivery_date,
        SfSameCityPush.error_code == 0,
        _sf_push_row_cancelled_predicate(),
        kind_clause,
    )
    seen: set[int] = set()
    for snap in db.scalars(select(SfSameCityPush.request_snapshot).where(*filt)).all():
        snap_mids, _ = _ids_from_push_snapshot(snap)
        for mid in snap_mids:
            seen.add(int(mid))
    return frozenset(seen)


def sf_push_fulfillment_member_ids_live(
    db: Session,
    *,
    store_id: int,
    delivery_date: date,
    meal_period: str | None = None,
) -> frozenset[int]:
    """当日有效大表推单 ``fulfillment_member_ids`` 并集（不读份数快照缓存）。"""
    import json

    from sqlalchemy import func

    from app.services.meal_period.constants import DEFAULT_MEAL_PERIOD
    from app.services.delivery.sf_order_fulfillment_service import (
        _db_dialect_name,
        _ids_from_push_snapshot,
        _subscription_member_ids_for_push,
    )

    period = (meal_period or DEFAULT_MEAL_PERIOD).strip().lower()
    filt = _sf_push_lock_filter_for_meal_period(int(store_id), delivery_date, period)
    seen: set[int] = set()
    need_fallback_ids: list[int] = []

    if _db_dialect_name(db) == "mysql":
        snap_rows = db.execute(
            select(
                SfSameCityPush.id,
                func.json_extract(SfSameCityPush.request_snapshot, "$.fulfillment_member_ids"),
            ).where(*filt)
        ).all()
        for pid, raw_mids in snap_rows:
            mids: list[int] = []
            if raw_mids is not None:
                parsed = raw_mids
                if isinstance(parsed, (bytes, str)):
                    try:
                        parsed = json.loads(parsed)
                    except (json.JSONDecodeError, TypeError, ValueError):
                        parsed = None
                if isinstance(parsed, list):
                    for x in parsed:
                        try:
                            mids.append(int(x))
                        except (TypeError, ValueError):
                            pass
            if mids:
                for mid in mids:
                    seen.add(int(mid))
                continue
            need_fallback_ids.append(int(pid))
    else:
        snap_rows = db.execute(
            select(SfSameCityPush.id, SfSameCityPush.request_snapshot).where(*filt)
        ).all()
        for pid, snap in snap_rows:
            snap_mids, _ = _ids_from_push_snapshot(snap)
            if snap_mids:
                for mid in snap_mids:
                    seen.add(int(mid))
                continue
            need_fallback_ids.append(int(pid))

    for pid in need_fallback_ids:
        row = db.get(SfSameCityPush, int(pid))
        if row is not None:
            for mid in _subscription_member_ids_for_push(db, row, None):
                seen.add(int(mid))
    return frozenset(seen)


def sf_frozen_subscription_member_ids_for_delivery_date(
    db: Session,
    *,
    store_id: int,
    delivery_date: date,
    meal_period: str | None = None,
) -> frozenset[int]:
    """当日有效顺丰推单 ``fulfillment_member_ids`` 并集（与扣次快照同源）。"""
    from app.services.delivery.delivery_sheet_push_snapshot_service import frozen_member_ids_from_units_snapshot
    from app.services.meal_period.constants import DEFAULT_MEAL_PERIOD

    period = (meal_period or DEFAULT_MEAL_PERIOD).strip().lower()
    cached = frozen_member_ids_from_units_snapshot(
        db, store_id=int(store_id), delivery_date=delivery_date, meal_period=period
    )
    if cached is not None:
        return cached

    return sf_push_fulfillment_member_ids_live(
        db, store_id=int(store_id), delivery_date=delivery_date, meal_period=period
    )
