"""配送大表顺丰推单后名单：首次推单捕获当日请假会员，供 merged 冻结扩容白名单使用。"""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.timeutil import today_shanghai
from app.models.delivery_sheet_push_absent_snapshot import DeliverySheetPushAbsentSnapshot
from app.models.member import Member
from app.services.leave import is_absent_on_delivery_date


def _collect_absent_member_ids_for_delivery_date(
    db: Session,
    *,
    store_id: int,
    delivery_date: date,
) -> list[int]:
    """门店内：配送到家、仍激活，且业务日命中请假规则的会员 id。"""
    today = today_shanghai()
    sid = int(store_id)
    rows = db.scalars(
        select(Member).where(
            Member.store_id == sid,
            Member.deleted_at.is_(None),
            Member.is_active.is_(True),
            Member.store_pickup.is_(False),
        )
    ).all()
    out: list[int] = []
    for m in rows:
        if is_absent_on_delivery_date(m, delivery_date, today=today):
            out.append(int(m.id))
    return sorted(set(out))


def capture_delivery_sheet_absent_members_on_first_push(
    db: Session,
    *,
    store_id: int,
    delivery_date: date,
) -> None:
    """
    当日首次成功大表推单后写入请假快照（同店同日仅一条，不覆盖）。
    须在推单行 commit 前/后同会话调用；不单独 commit。
    """
    sid = int(store_id)
    d = delivery_date
    existing = db.get(DeliverySheetPushAbsentSnapshot, {"store_id": sid, "delivery_date": d})
    if existing is not None:
        return
    ids = _collect_absent_member_ids_for_delivery_date(db, store_id=sid, delivery_date=d)
    db.add(
        DeliverySheetPushAbsentSnapshot(
            store_id=sid,
            delivery_date=d,
            absent_member_ids=ids,
        )
    )
    db.flush()


def absent_member_ids_at_first_push(
    db: Session,
    *,
    store_id: int,
    delivery_date: date,
) -> frozenset[int] | None:
    """
    返回首次推单时捕获的请假会员 id；无快照行返回 None（推单前或历史日未落库）。
    """
    row = db.get(
        DeliverySheetPushAbsentSnapshot,
        {"store_id": int(store_id), "delivery_date": delivery_date},
    )
    if row is None:
        return None
    raw = row.absent_member_ids
    if not isinstance(raw, list):
        return frozenset()
    seen: set[int] = set()
    for x in raw:
        try:
            seen.add(int(x))
        except (TypeError, ValueError):
            continue
    return frozenset(seen)


def member_qualifies_post_push_whitelist(m: Member, *, delivery_date: date) -> bool:
    """推单后允许并入大表：起送业务日恰为当日（首餐新客）。"""
    ds = getattr(m, "delivery_start_date", None)
    return ds is not None and ds == delivery_date
