"""配送大表顺丰推单后快照：首次推单捕获请假会员与每配送日份数，供冻结日大表口径使用。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.timeutil import today_shanghai
from app.models.delivery_sheet_push_absent_snapshot import DeliverySheetPushAbsentSnapshot
from app.models.delivery_sheet_push_units_snapshot import DeliverySheetPushUnitsSnapshot
from app.models.member import Member
from app.services.leave import is_absent_on_delivery_date
from app.services.member_service import effective_daily_meal_units

# 写入 member_meal_units JSON 的元数据键：推单时刻 frozen 会员 id 并集（读大表时避免扫全量顺丰推单行）
FROZEN_MEMBER_IDS_SNAPSHOT_KEY = "__frozen_member_ids__"


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


def _collect_member_meal_units_for_sf_push_sheet(
    db: Session,
    *,
    store_id: int,
    delivery_date: date,
) -> dict[str, int]:
    """
    首次大表推单时刻：按当日顺丰停靠点聚合中的订阅行快照 member_id→份数。
    与 createorder 预览/推单口径同源，避免推单后改份数导致大表统计漂移。
    """
    from app.services.sf_same_city_service import aggs_for_delivery_date

    sid = int(store_id)
    ags = aggs_for_delivery_date(db, delivery_date, store_id=sid)
    out: dict[str, int] = {}
    for agg in ags.values():
        for line in agg.sub_lines:
            if line.get("is_delivered"):
                continue
            try:
                mid = int(line["member_id"])
            except (KeyError, TypeError, ValueError):
                continue
            key = str(mid)
            if key in out:
                continue
            m = db.get(Member, mid)
            if m is not None:
                out[key] = effective_daily_meal_units(m)
    return out


def capture_delivery_sheet_units_on_first_push(
    db: Session,
    *,
    store_id: int,
    delivery_date: date,
) -> None:
    """
    当日首次成功大表推单后写入份数快照（同店同日仅一条，不覆盖）。
    须在推单行 commit 前/后同会话调用；不单独 commit。
    """
    sid = int(store_id)
    d = delivery_date
    from sqlalchemy.exc import OperationalError, ProgrammingError

    try:
        existing = db.get(DeliverySheetPushUnitsSnapshot, {"store_id": sid, "delivery_date": d})
    except (OperationalError, ProgrammingError):
        return
    if existing is not None:
        return
    units = _collect_member_meal_units_for_sf_push_sheet(db, store_id=sid, delivery_date=d)
    from app.services.delivery_day_lock_service import sf_frozen_subscription_member_ids_for_delivery_date

    units_payload: dict[str, object] = dict(units)
    units_payload[FROZEN_MEMBER_IDS_SNAPSHOT_KEY] = sorted(
        sf_frozen_subscription_member_ids_for_delivery_date(db, store_id=sid, delivery_date=d)
    )
    try:
        db.add(
            DeliverySheetPushUnitsSnapshot(
                store_id=sid,
                delivery_date=d,
                member_meal_units=units_payload,
            )
        )
        db.flush()
    except (OperationalError, ProgrammingError):
        return


def _frozen_member_ids_from_units_json(raw: object) -> frozenset[int] | None:
    """从份数快照 JSON 读取推单时缓存的 frozen 会员 id；无元数据键返回 None（需走慢路径）。"""
    if not isinstance(raw, dict) or FROZEN_MEMBER_IDS_SNAPSHOT_KEY not in raw:
        return None
    meta = raw[FROZEN_MEMBER_IDS_SNAPSHOT_KEY]
    if not isinstance(meta, list):
        return frozenset()
    seen: set[int] = set()
    for x in meta:
        try:
            seen.add(int(x))
        except (TypeError, ValueError):
            continue
    return frozenset(seen)


def frozen_member_ids_from_units_snapshot(
    db: Session,
    *,
    store_id: int,
    delivery_date: date,
) -> frozenset[int] | None:
    """读份数快照中的 frozen 会员并集；无行或无元数据键返回 None。"""
    from sqlalchemy.exc import OperationalError, ProgrammingError

    try:
        row = db.get(
            DeliverySheetPushUnitsSnapshot,
            {"store_id": int(store_id), "delivery_date": delivery_date},
        )
    except (OperationalError, ProgrammingError):
        return None
    if row is None:
        return None
    return _frozen_member_ids_from_units_json(row.member_meal_units)


def _parse_member_meal_units_json(raw: object) -> dict[int, int]:
    """JSON 映射 member_id→份数；键兼容字符串/整数。"""
    if not isinstance(raw, dict):
        return {}
    out: dict[int, int] = {}
    for k, v in raw.items():
        try:
            mid = int(k)
            u = int(v)
        except (TypeError, ValueError):
            continue
        if u >= 1:
            out[mid] = u
    return out


def member_meal_units_snapshot_for_date(
    db: Session,
    *,
    store_id: int,
    delivery_date: date,
) -> dict[int, int] | None:
    """
    返回首次推单时捕获的 member_id→份数；无快照行返回 None（推单前或历史日未落库）。
    迁移未执行导致表不存在时回退 None，大表仍用当日生效份数（兼容旧环境）。
    """
    from sqlalchemy.exc import OperationalError, ProgrammingError

    try:
        row = db.get(
            DeliverySheetPushUnitsSnapshot,
            {"store_id": int(store_id), "delivery_date": delivery_date},
        )
    except (OperationalError, ProgrammingError):
        return None
    if row is None:
        return None
    parsed = _parse_member_meal_units_json(row.member_meal_units)
    return parsed if parsed else None


@dataclass(frozen=True)
class DeliverySheetDaySnapshots:
    """
    单次大表请求内一次加载推单相关快照与冻结态。
    避免 has_sf_push / 份数快照 / 请假快照 / frozen 并集重复查库。
    """

    store_id: int
    delivery_date: date
    has_sf_push: bool
    member_meal_units: dict[int, int] | None
    frozen_member_ids: frozenset[int] | None
    absent_member_ids: frozenset[int] | None

    @classmethod
    def load(cls, db: Session, *, store_id: int, delivery_date: date) -> DeliverySheetDaySnapshots:
        from app.services.delivery_day_lock_service import (
            has_delivery_sheet_sf_push_on_date,
            sf_frozen_subscription_member_ids_for_delivery_date,
        )

        sid = int(store_id)
        d = delivery_date

        units_map: dict[int, int] | None = None
        frozen_from_row: frozenset[int] | None = None
        units_row = _get_units_snapshot_row(db, store_id=sid, delivery_date=d)
        if units_row is not None:
            units_map = _parse_member_meal_units_json(units_row.member_meal_units) or None
            frozen_from_row = _frozen_member_ids_from_units_json(units_row.member_meal_units)

        # 份数快照仅首次推单后写入；有行即可视为已推单，省一次 sf_same_city_pushes 探测
        if units_row is not None:
            has_push = True
        else:
            has_push = has_delivery_sheet_sf_push_on_date(db, store_id=sid, delivery_date=d)

        frozen_ids: frozenset[int] | None = None
        if has_push:
            frozen_ids = (
                frozen_from_row
                if frozen_from_row is not None
                else sf_frozen_subscription_member_ids_for_delivery_date(
                    db, store_id=sid, delivery_date=d
                )
            )

        absent = (
            absent_member_ids_at_first_push(db, store_id=sid, delivery_date=d)
            if has_push
            else None
        )
        return cls(
            store_id=sid,
            delivery_date=d,
            has_sf_push=has_push,
            member_meal_units=units_map,
            frozen_member_ids=frozen_ids,
            absent_member_ids=absent,
        )


def patch_frozen_member_ids_on_units_snapshot_if_missing(
    db: Session,
    *,
    store_id: int,
    delivery_date: date,
) -> bool:
    """
    份数快照已存在但缺少 ``__frozen_member_ids__`` 时补齐（一次性慢路径，之后读大表走缓存）。
    返回是否写入了元数据。
    """
    row = _get_units_snapshot_row(db, store_id=int(store_id), delivery_date=delivery_date)
    if row is None:
        return False
    if _frozen_member_ids_from_units_json(row.member_meal_units) is not None:
        return False
    from app.services.delivery_day_lock_service import sf_frozen_subscription_member_ids_for_delivery_date

    frozen = sf_frozen_subscription_member_ids_for_delivery_date(
        db, store_id=int(store_id), delivery_date=delivery_date
    )
    raw = row.member_meal_units
    payload: dict[str, object] = dict(raw) if isinstance(raw, dict) else {}
    payload[FROZEN_MEMBER_IDS_SNAPSHOT_KEY] = sorted(int(x) for x in frozen)
    row.member_meal_units = payload
    db.flush()
    return True


def _get_units_snapshot_row(
    db: Session,
    *,
    store_id: int,
    delivery_date: date,
) -> DeliverySheetPushUnitsSnapshot | None:
    from sqlalchemy.exc import OperationalError, ProgrammingError

    try:
        return db.get(
            DeliverySheetPushUnitsSnapshot,
            {"store_id": int(store_id), "delivery_date": delivery_date},
        )
    except (OperationalError, ProgrammingError):
        return None
