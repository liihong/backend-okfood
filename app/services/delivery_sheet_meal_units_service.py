"""配送大表份数口径：推单冻结日读首次推单快照（方案 A）。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from sqlalchemy.orm import Session

from app.models.member import Member
from app.services.delivery_day_lock_service import is_delivery_day_sheet_frozen_after_sf_push
from app.services.delivery_sheet_push_snapshot_service import (
    DeliverySheetDaySnapshots,
    member_meal_units_snapshot_for_date,
)
from app.services.member_service import MAX_DAILY_MEAL_UNITS, effective_daily_meal_units


def _clamp_units(units: int) -> int:
    return max(1, min(int(units), MAX_DAILY_MEAL_UNITS))


def _units_from_snapshot_or_member(
    member: Member,
    *,
    is_frozen: bool,
    snapshot: dict[int, int] | None,
) -> int:
    """冻结态与快照已加载时的纯内存份数口径（与 meal_units_for_delivery_sheet_member 一致）。"""
    if not is_frozen:
        return effective_daily_meal_units(member)
    if not snapshot:
        return effective_daily_meal_units(member)
    mid = int(member.id)
    if mid in snapshot:
        return _clamp_units(snapshot[mid])
    return effective_daily_meal_units(member)


@dataclass
class DeliverySheetMealUnitsContext:
    """
    单次大表构建内缓存推单冻结态与份数快照。
    build_delivery_sheet 对同一会员会多次取份数，无缓存时每次都会重复查库。
    """

    store_id: int
    delivery_date: date
    is_frozen: bool
    snapshot: dict[int, int] | None
    _member_units_cache: dict[int, int] = field(default_factory=dict)

    @classmethod
    def load(cls, db: Session, *, store_id: int, delivery_date: date) -> DeliverySheetMealUnitsContext:
        return cls.from_day_snapshots(
            DeliverySheetDaySnapshots.load(db, store_id=int(store_id), delivery_date=delivery_date)
        )

    @classmethod
    def from_day_snapshots(cls, day_snap: DeliverySheetDaySnapshots) -> DeliverySheetMealUnitsContext:
        """复用已加载的 ``DeliverySheetDaySnapshots``，避免重复查推单与份数快照。"""
        return cls(
            store_id=day_snap.store_id,
            delivery_date=day_snap.delivery_date,
            is_frozen=day_snap.has_sf_push,
            snapshot=day_snap.member_meal_units if day_snap.has_sf_push else None,
        )

    def units_for(self, member: Member) -> int:
        mid = int(member.id)
        cached = self._member_units_cache.get(mid)
        if cached is not None:
            return cached
        units = _units_from_snapshot_or_member(
            member,
            is_frozen=self.is_frozen,
            snapshot=self.snapshot,
        )
        self._member_units_cache[mid] = units
        return units


def meal_units_for_delivery_sheet_member(
    db: Session,
    member: Member,
    *,
    delivery_date: date,
    store_id: int,
    units_ctx: DeliverySheetMealUnitsContext | None = None,
) -> int:
    """
    配送大表展示/汇总用份数。

    未推单冻结日：与 effective_daily_meal_units 一致（当日生效值）。
    已推单冻结日：优先读首次推单快照；快照无该会员（如推单后白名单新客）则回退当日生效值。
    """
    if units_ctx is not None:
        return units_ctx.units_for(member)

    sid = int(store_id)
    d = delivery_date
    frozen = is_delivery_day_sheet_frozen_after_sf_push(db, store_id=sid, delivery_date=d)
    snap = member_meal_units_snapshot_for_date(db, store_id=sid, delivery_date=d) if frozen else None
    return _units_from_snapshot_or_member(member, is_frozen=frozen, snapshot=snap)


def sum_meal_units_for_delivery_sheet_members(
    db: Session,
    members: list[Member],
    *,
    delivery_date: date,
    store_id: int,
    units_ctx: DeliverySheetMealUnitsContext | None = None,
) -> int:
    """冻结日安全汇总：按 meal_units_for_delivery_sheet_member 求和。"""
    ctx = units_ctx or DeliverySheetMealUnitsContext.load(
        db, store_id=int(store_id), delivery_date=delivery_date
    )
    return sum(ctx.units_for(m) for m in members)


def sum_meal_units_for_member_ids_on_frozen_sheet(
    db: Session,
    member_ids: set[int],
    *,
    delivery_date: date,
    store_id: int,
) -> int:
    """锁单日 SQL 快速路径的 Python 等价：仅对 merged 到家会员 id 求和。"""
    if not member_ids:
        return 0
    snap = member_meal_units_snapshot_for_date(
        db, store_id=int(store_id), delivery_date=delivery_date
    )
    total = 0
    for mid in member_ids:
        m = db.get(Member, int(mid))
        if m is None or m.deleted_at is not None:
            continue
        if snap and int(mid) in snap:
            total += _clamp_units(snap[int(mid)])
        else:
            total += effective_daily_meal_units(m)
    return total
