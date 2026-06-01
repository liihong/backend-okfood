"""配送业务日锁单：门店当日顺丰推单全部履约完成后，当日到家名单不再随请假等实时扩表。"""

from __future__ import annotations

from datetime import date

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.sf_same_city_push import SfSameCityPush


def _sf_push_rows_for_delivery_day_lock(
    db: Session,
    *,
    store_id: int,
    delivery_date: date,
) -> list[SfSameCityPush]:
    """当日创单成功且未商户取消的推单（未要求顺丰回调状态非空，避免 NULL 误判无推单）。"""
    return list(
        db.scalars(
            select(SfSameCityPush).where(
                SfSameCityPush.store_id == int(store_id),
                SfSameCityPush.delivery_date == delivery_date,
                SfSameCityPush.error_code == 0,
                SfSameCityPush.merchant_cancel_requested_at.is_(None),
                or_(
                    SfSameCityPush.sf_callback_order_status.is_(None),
                    SfSameCityPush.sf_callback_order_status.not_in((2, 22)),
                ),
            )
        ).all()
    )


def is_delivery_day_sheet_locked(
    db: Session,
    *,
    store_id: int,
    delivery_date: date,
) -> bool:
    """
    当日是否存在有效顺丰推单且已全部履约完毕。
    无推单或未全部送达时不锁，其它业务保持原实时口径。
    """
    from app.services.sf_order_fulfillment_service import sf_push_fulfilled_quick_check

    rows = _sf_push_rows_for_delivery_day_lock(db, store_id=int(store_id), delivery_date=delivery_date)
    if not rows:
        return False
    return all(sf_push_fulfilled_quick_check(db, pus) for pus in rows)


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

    seen: set[int] = set()
    for pus in _sf_push_rows_for_delivery_day_lock(
        db, store_id=int(store_id), delivery_date=delivery_date
    ):
        snap_mids, _ = _ids_from_push_snapshot(pus.request_snapshot)
        mids = snap_mids if snap_mids else _subscription_member_ids_for_push(db, pus, None)
        for mid in mids:
            seen.add(int(mid))
    return frozenset(seen)
