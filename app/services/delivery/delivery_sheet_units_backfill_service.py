"""从历史顺丰推单快照回填配送大表份数快照，并可选将当日生效份数对齐推单口径。"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.timeutil import beijing_now_naive
from app.models.balance_log import BalanceLog
from app.models.delivery_log import DeliveryLog
from app.models.delivery_sheet_push_units_snapshot import DeliverySheetPushUnitsSnapshot
from app.models.enums import BalanceReason, DeliveryStatus
from app.models.member import Member
from app.models.sf_same_city_push import SfSameCityPush
from app.services.delivery.delivery_day_lock_service import (
    _sf_push_lock_filter,
    sf_frozen_subscription_member_ids_for_delivery_date,
)
from app.services.delivery.delivery_sheet_push_snapshot_service import (
    FROZEN_MEMBER_IDS_SNAPSHOT_KEY,
    member_meal_units_snapshot_for_date,
)
from app.services.member.member_service import effective_daily_meal_units
from app.services.delivery.sf_order_fulfillment_service import _ids_from_push_snapshot
from app.services.delivery.sf_same_city_service import load_agg_for_stop_id

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class UnitsSnapshotBackfillReport:
    """回填结果摘要，供脚本与管理端排查。"""

    delivery_date: date
    store_id: int
    member_count: int
    meal_units_total: int
    from_sf_pushes: int
    from_balance_log: int
    from_agg_fallback: int
    from_member_fallback: int
    overwritten_snapshot: bool
    aligned_member_rows: int
    dry_run: bool


def _delivery_deduct_units_on_date(
    db: Session,
    *,
    member_id: int,
    delivery_date: date,
) -> int | None:
    """当日已确认送达时，以 balance_logs 配送扣次绝对值作为推单份数（与扣次口径一致）。"""
    delivered = db.scalar(
        select(DeliveryLog.id).where(
            DeliveryLog.member_id == int(member_id),
            DeliveryLog.delivery_date == delivery_date,
            DeliveryLog.status == DeliveryStatus.DELIVERED.value,
        )
    )
    if delivered is None:
        return None
    row = db.scalar(
        select(BalanceLog.change)
        .where(
            BalanceLog.member_id == int(member_id),
            BalanceLog.reason == BalanceReason.DELIVERY.value,
            BalanceLog.change < 0,
            BalanceLog.created_at >= datetime.combine(delivery_date, datetime.min.time()),
            BalanceLog.created_at < datetime.combine(
                delivery_date.fromordinal(delivery_date.toordinal() + 1),
                datetime.min.time(),
            ),
        )
        .order_by(BalanceLog.id.asc())
        .limit(1)
    )
    if row is None:
        return None
    try:
        u = abs(int(row))
    except (TypeError, ValueError):
        return None
    return u if u >= 1 else None


def _member_units_from_agg_stop(
    db: Session,
    pus: SfSameCityPush,
    member_id: int,
) -> int | None:
    """同址多会员停靠点：用当前聚合子行份数兜底（仅无扣次记录时）。"""
    sid = int(pus.store_id) if pus.store_id is not None else None
    if sid is None:
        return None
    agg = load_agg_for_stop_id(
        db,
        pus.delivery_date,
        str(pus.stop_id or ""),
        store_id=sid,
    )
    if agg is None:
        return None
    for sl in getattr(agg, "sub_lines", None) or []:
        try:
            mid = int(sl["member_id"])
        except (KeyError, TypeError, ValueError):
            continue
        if mid != int(member_id):
            continue
        try:
            u = int(sl.get("units") or 0)
        except (TypeError, ValueError):
            u = 0
        return max(1, u) if u > 0 else None
    return None


def _preview_subscription_units(snap: dict) -> int:
    pr = snap.get("preview_row")
    if not isinstance(pr, dict):
        return 0
    try:
        return max(0, int(pr.get("subscription_pending_units") or 0))
    except (TypeError, ValueError):
        return 0


def build_member_meal_units_from_sf_pushes(
    db: Session,
    *,
    store_id: int,
    delivery_date: date,
) -> tuple[dict[int, int], dict[str, int]]:
    """
    从当日有效大表顺丰推单 request_snapshot 重建 member_id→份数。

    口径优先级（同一会员仅记录首次命中）：
    1. 独占停靠点：preview_row.subscription_pending_units
    2. 同址多会员：当日已送达则用 balance_logs 扣次份数
    3. 同址多会员未送达：停靠点聚合子行 units 兜底
    """
    pushes = db.scalars(
        select(SfSameCityPush)
        .where(*_sf_push_lock_filter(int(store_id), delivery_date, delivery_sheet_only=True))
        .order_by(SfSameCityPush.created_at.asc(), SfSameCityPush.id.asc())
    ).all()

    member_units: dict[int, int] = {}
    stats = {
        "from_sf_pushes": 0,
        "from_balance_log": 0,
        "from_agg_fallback": 0,
        "from_member_fallback": 0,
    }

    for pus in pushes:
        snap = pus.request_snapshot if isinstance(pus.request_snapshot, dict) else {}
        mids, _ = _ids_from_push_snapshot(snap)
        if not mids:
            continue
        stop_total = _preview_subscription_units(snap)
        pending = [int(m) for m in mids if int(m) not in member_units]
        if not pending:
            continue

        if len(mids) == 1:
            member_units[int(mids[0])] = max(1, stop_total or 1)
            stats["from_sf_pushes"] += 1
            continue

        for mid in pending:
            deducted = _delivery_deduct_units_on_date(db, member_id=mid, delivery_date=delivery_date)
            if deducted is not None:
                member_units[mid] = deducted
                stats["from_balance_log"] += 1
                continue
            agg_u = _member_units_from_agg_stop(db, pus, mid)
            if agg_u is not None:
                member_units[mid] = agg_u
                stats["from_agg_fallback"] += 1
            else:
                m = db.get(Member, mid)
                member_units[mid] = effective_daily_meal_units(m) if m else 1
                stats["from_member_fallback"] += 1

    frozen = sf_frozen_subscription_member_ids_for_delivery_date(
        db, store_id=int(store_id), delivery_date=delivery_date
    )
    for mid in frozen:
        if int(mid) in member_units:
            continue
        m = db.get(Member, int(mid))
        if m is None:
            continue
        deducted = _delivery_deduct_units_on_date(db, member_id=int(mid), delivery_date=delivery_date)
        if deducted is not None:
            member_units[int(mid)] = deducted
            stats["from_balance_log"] += 1
        else:
            member_units[int(mid)] = effective_daily_meal_units(m)
            stats["from_member_fallback"] += 1

    return member_units, stats


def upsert_delivery_sheet_units_snapshot(
    db: Session,
    *,
    store_id: int,
    delivery_date: date,
    member_units: dict[int, int],
    overwrite: bool = True,
    frozen_member_ids: frozenset[int] | None = None,
    meal_period: str | None = None,
) -> bool:
    """
    写入/覆盖份数快照。overwrite=False 时若已有行则跳过。
    返回是否写入了库。
    """
    from app.services.delivery.delivery_sheet_push_snapshot_service import _snapshot_pk

    sid = int(store_id)
    d = delivery_date
    pk = _snapshot_pk(store_id=sid, delivery_date=d, meal_period=meal_period or "lunch")
    payload: dict[str, object] = {
        str(int(k)): max(1, int(v)) for k, v in sorted(member_units.items())
    }
    if frozen_member_ids is not None:
        payload[FROZEN_MEMBER_IDS_SNAPSHOT_KEY] = sorted(int(x) for x in frozen_member_ids)
    row = db.get(DeliverySheetPushUnitsSnapshot, pk)
    if row is not None and not overwrite:
        return False
    if row is None:
        db.add(
            DeliverySheetPushUnitsSnapshot(
                store_id=sid,
                delivery_date=d,
                meal_period=pk["meal_period"],
                member_meal_units=payload,
                recorded_at=beijing_now_naive(),
            )
        )
    else:
        row.member_meal_units = payload
        row.recorded_at = beijing_now_naive()
    db.flush()
    return True


def align_member_daily_units_to_snapshot(
    db: Session,
    member_units: dict[int, int],
    *,
    dry_run: bool = False,
) -> int:
    """
    将 members.daily_meal_units 回退为快照值（当日生效），保留 daily_meal_units_pending。
    用于推单后误改当日份数的补救；不影响已送达幂等扣次记录。
    """
    n = 0
    for mid, snap_u in member_units.items():
        m = db.get(Member, int(mid))
        if m is None or m.deleted_at is not None:
            continue
        target = max(1, int(snap_u))
        current = effective_daily_meal_units(m)
        if current == target:
            continue
        n += 1
        if dry_run:
            continue
        m.daily_meal_units = target
    return n


def backfill_and_refreeze_delivery_sheet_units(
    db: Session,
    *,
    store_id: int,
    delivery_date: date,
    overwrite_snapshot: bool = True,
    align_member_daily_units: bool = True,
    dry_run: bool = False,
) -> UnitsSnapshotBackfillReport:
    """
    从历史顺丰推单回填份数快照，并可选对齐当日 daily_meal_units（重新冻结当日生效份数）。
    """
    member_units, stats = build_member_meal_units_from_sf_pushes(
        db, store_id=int(store_id), delivery_date=delivery_date
    )
    # 回填时以推单并集为准，勿读可能偏小的快照 frozen 缓存
    frozen_ids = frozenset(int(k) for k in member_units.keys())
    had_snapshot = (
        member_meal_units_snapshot_for_date(db, store_id=int(store_id), delivery_date=delivery_date)
        is not None
    )
    written = False
    aligned = 0

    if not dry_run:
        written = upsert_delivery_sheet_units_snapshot(
            db,
            store_id=int(store_id),
            delivery_date=delivery_date,
            member_units=member_units,
            overwrite=overwrite_snapshot,
            frozen_member_ids=frozen_ids,
        )
        if align_member_daily_units:
            aligned = align_member_daily_units_to_snapshot(db, member_units, dry_run=False)
        db.commit()
    else:
        written = overwrite_snapshot or not had_snapshot
        if align_member_daily_units:
            aligned = align_member_daily_units_to_snapshot(db, member_units, dry_run=True)

    total = sum(int(v) for v in member_units.values())
    logger.info(
        "份数快照回填 store=%s date=%s members=%s total=%s dry_run=%s",
        store_id,
        delivery_date.isoformat(),
        len(member_units),
        total,
        dry_run,
    )
    return UnitsSnapshotBackfillReport(
        delivery_date=delivery_date,
        store_id=int(store_id),
        member_count=len(member_units),
        meal_units_total=total,
        from_sf_pushes=int(stats["from_sf_pushes"]),
        from_balance_log=int(stats["from_balance_log"]),
        from_agg_fallback=int(stats["from_agg_fallback"]),
        from_member_fallback=int(stats["from_member_fallback"]),
        overwritten_snapshot=bool(written and had_snapshot),
        aligned_member_rows=aligned,
        dry_run=dry_run,
    )
