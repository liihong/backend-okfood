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
from app.services.member.leave import is_absent_on_delivery_date
from app.services.member.member_service import effective_daily_meal_units
from app.services.meal_period.constants import DEFAULT_MEAL_PERIOD
from app.services.meal_period.leave import is_absent_on_delivery_date_for_period
from app.models.enums import MealPeriod


def _snapshot_pk(*, store_id: int, delivery_date: date, meal_period: str = DEFAULT_MEAL_PERIOD) -> dict:
    """推单快照复合主键；午餐链路不传参时等价于 meal_period=lunch。"""
    return {
        "store_id": int(store_id),
        "delivery_date": delivery_date,
        "meal_period": (meal_period or DEFAULT_MEAL_PERIOD).strip().lower(),
    }

# 写入 member_meal_units JSON 的元数据键：推单时刻 frozen 会员 id 并集（读大表时避免扫全量顺丰推单行）
FROZEN_MEMBER_IDS_SNAPSHOT_KEY = "__frozen_member_ids__"


def _collect_absent_member_ids_for_delivery_date(
    db: Session,
    *,
    store_id: int,
    delivery_date: date,
    meal_period: str = DEFAULT_MEAL_PERIOD,
) -> list[int]:
    """门店内：配送到家、仍激活，且业务日命中该餐段请假规则的会员 id。"""
    today = today_shanghai()
    sid = int(store_id)
    period = (meal_period or DEFAULT_MEAL_PERIOD).strip().lower()
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
        if period == MealPeriod.LUNCH.value:
            if is_absent_on_delivery_date(m, delivery_date, today=today):
                out.append(int(m.id))
        elif is_absent_on_delivery_date_for_period(
            db, m, delivery_date, meal_period=period, today=today
        ):
            out.append(int(m.id))
    return sorted(set(out))


def capture_delivery_sheet_absent_members_on_first_push(
    db: Session,
    *,
    store_id: int,
    delivery_date: date,
    meal_period: str = DEFAULT_MEAL_PERIOD,
) -> None:
    """
    当日首次成功大表推单后写入请假快照（同店同日同餐段仅一条，不覆盖）。
    须在推单行 commit 前/后同会话调用；不单独 commit。
    """
    sid = int(store_id)
    d = delivery_date
    pk = _snapshot_pk(store_id=sid, delivery_date=d, meal_period=meal_period)
    existing = db.get(DeliverySheetPushAbsentSnapshot, pk)
    if existing is not None:
        return
    ids = _collect_absent_member_ids_for_delivery_date(
        db, store_id=sid, delivery_date=d, meal_period=meal_period
    )
    db.add(
        DeliverySheetPushAbsentSnapshot(
            store_id=sid,
            delivery_date=d,
            meal_period=pk["meal_period"],
            absent_member_ids=ids,
        )
    )
    db.flush()


def absent_member_ids_at_first_push(
    db: Session,
    *,
    store_id: int,
    delivery_date: date,
    meal_period: str = DEFAULT_MEAL_PERIOD,
) -> frozenset[int] | None:
    """
    返回首次推单时捕获的请假会员 id；无快照行返回 None（推单前或历史日未落库）。
    """
    row = db.get(
        DeliverySheetPushAbsentSnapshot,
        _snapshot_pk(store_id=int(store_id), delivery_date=delivery_date, meal_period=meal_period),
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
    meal_period: str = DEFAULT_MEAL_PERIOD,
) -> dict[str, int]:
    """
    首次大表推单时刻：按当日顺丰停靠点聚合中的订阅行快照 member_id→份数。
    与 createorder 预览/推单口径同源，避免推单后改份数导致大表统计漂移。
    """
    from app.services.delivery.sf_same_city_service import aggs_for_delivery_date

    sid = int(store_id)
    period = (meal_period or DEFAULT_MEAL_PERIOD).strip().lower()
    ags = aggs_for_delivery_date(db, delivery_date, store_id=sid, meal_period=period)
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
                from app.services.meal_period.units import effective_daily_meal_units_for_period

                out[key] = effective_daily_meal_units_for_period(db, m, period)
    return out


def capture_delivery_sheet_units_on_first_push(
    db: Session,
    *,
    store_id: int,
    delivery_date: date,
    meal_period: str = DEFAULT_MEAL_PERIOD,
) -> None:
    """
    当日首次成功大表推单后写入份数快照（同店同日同餐段仅一条，不覆盖）。
    须在推单行 commit 前/后同会话调用；不单独 commit。
    """
    sid = int(store_id)
    d = delivery_date
    pk = _snapshot_pk(store_id=sid, delivery_date=d, meal_period=meal_period)
    from sqlalchemy.exc import OperationalError, ProgrammingError

    try:
        existing = db.get(DeliverySheetPushUnitsSnapshot, pk)
    except (OperationalError, ProgrammingError):
        return
    if existing is not None:
        return
    units = _collect_member_meal_units_for_sf_push_sheet(
        db, store_id=sid, delivery_date=d, meal_period=meal_period
    )
    units_payload: dict[str, object] = dict(units)
    units_payload[FROZEN_MEMBER_IDS_SNAPSHOT_KEY] = sorted(int(k) for k in units.keys())
    try:
        db.add(
            DeliverySheetPushUnitsSnapshot(
                store_id=sid,
                delivery_date=d,
                meal_period=pk["meal_period"],
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
    meal_period: str = DEFAULT_MEAL_PERIOD,
) -> frozenset[int] | None:
    """读份数快照中的 frozen 会员并集；无行或无元数据键返回 None。"""
    from sqlalchemy.exc import OperationalError, ProgrammingError

    try:
        row = db.get(
            DeliverySheetPushUnitsSnapshot,
            _snapshot_pk(store_id=int(store_id), delivery_date=delivery_date, meal_period=meal_period),
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
    meal_period: str = DEFAULT_MEAL_PERIOD,
) -> dict[int, int] | None:
    """
    返回首次推单时捕获的 member_id→份数；无快照行返回 None（推单前或历史日未落库）。
    迁移未执行导致表不存在时回退 None，大表仍用当日生效份数（兼容旧环境）。
    """
    from sqlalchemy.exc import OperationalError, ProgrammingError

    try:
        row = db.get(
            DeliverySheetPushUnitsSnapshot,
            _snapshot_pk(store_id=int(store_id), delivery_date=delivery_date, meal_period=meal_period),
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
    meal_period: str
    has_sf_push: bool
    member_meal_units: dict[int, int] | None
    frozen_member_ids: frozenset[int] | None
    absent_member_ids: frozenset[int] | None

    @classmethod
    def load(
        cls,
        db: Session,
        *,
        store_id: int,
        delivery_date: date,
        meal_period: str = DEFAULT_MEAL_PERIOD,
    ) -> DeliverySheetDaySnapshots:
        from app.services.delivery.delivery_day_lock_service import (
            has_delivery_sheet_sf_push_on_date,
            sf_frozen_subscription_member_ids_for_delivery_date,
        )

        sid = int(store_id)
        d = delivery_date
        period = (meal_period or DEFAULT_MEAL_PERIOD).strip().lower()

        if reconcile_frozen_ids_with_sf_pushes_no_commit(
            db, store_id=sid, delivery_date=d, meal_period=period
        ):
            db.commit()

        units_map: dict[int, int] | None = None
        frozen_from_row: frozenset[int] | None = None
        units_row = _get_units_snapshot_row(
            db, store_id=sid, delivery_date=d, meal_period=period
        )
        if units_row is not None:
            units_map = _parse_member_meal_units_json(units_row.member_meal_units) or None
            frozen_from_row = _frozen_member_ids_from_units_json(units_row.member_meal_units)

        if units_row is not None:
            has_push = True
        elif period == MealPeriod.DINNER.value:
            from app.services.delivery.delivery_day_lock_service import has_dinner_delivery_sheet_sf_push_on_date

            has_push = has_dinner_delivery_sheet_sf_push_on_date(
                db, store_id=sid, delivery_date=d
            )
        else:
            has_push = has_delivery_sheet_sf_push_on_date(db, store_id=sid, delivery_date=d)

        frozen_ids: frozenset[int] | None = None
        if has_push:
            frozen_ids = (
                frozen_from_row
                if frozen_from_row is not None
                else sf_frozen_subscription_member_ids_for_delivery_date(
                    db, store_id=sid, delivery_date=d, meal_period=period
                )
            )

        absent = (
            absent_member_ids_at_first_push(
                db, store_id=sid, delivery_date=d, meal_period=period
            )
            if has_push
            else None
        )
        return cls(
            store_id=sid,
            delivery_date=d,
            meal_period=period,
            has_sf_push=has_push,
            member_meal_units=units_map,
            frozen_member_ids=frozen_ids,
            absent_member_ids=absent,
        )


def merge_delivery_sheet_push_into_units_snapshot(
    db: Session,
    *,
    store_id: int,
    delivery_date: date,
    fulfillment_member_ids: list[int],
    meal_period: str = DEFAULT_MEAL_PERIOD,
) -> None:
    """
    大表推单成功后：将本次履约会员并入份数快照 frozen 并集及份数字典。
    修复首次仅局部创单成功时 frozen 偏小、或大表与顺丰记录不一致。
    """
    mids = sorted({int(x) for x in fulfillment_member_ids if x is not None})
    if not mids:
        return
    row = _get_units_snapshot_row(
        db, store_id=int(store_id), delivery_date=delivery_date, meal_period=meal_period
    )
    if row is None:
        return
    raw = row.member_meal_units
    payload: dict[str, object] = dict(raw) if isinstance(raw, dict) else {}
    frozen_raw = payload.get(FROZEN_MEMBER_IDS_SNAPSHOT_KEY)
    frozen_set: set[int] = set()
    if isinstance(frozen_raw, list):
        for x in frozen_raw:
            try:
                frozen_set.add(int(x))
            except (TypeError, ValueError):
                pass
    changed = False
    for mid in mids:
        key = str(mid)
        if mid not in frozen_set:
            frozen_set.add(mid)
            changed = True
        if key not in payload:
            m = db.get(Member, mid)
            if m is not None:
                from app.services.meal_period.units import effective_daily_meal_units_for_period

                payload[key] = effective_daily_meal_units_for_period(
                    db, m, row.meal_period if row else DEFAULT_MEAL_PERIOD
                )
                changed = True
    if not changed:
        return
    payload[FROZEN_MEMBER_IDS_SNAPSHOT_KEY] = sorted(frozen_set)
    row.member_meal_units = payload
    db.flush()


def reconcile_frozen_ids_with_sf_pushes_no_commit(
    db: Session,
    *,
    store_id: int,
    delivery_date: date,
    meal_period: str = DEFAULT_MEAL_PERIOD,
) -> bool:
    """
    份数快照 frozen 并集若小于当日有效大表推单 fulfillment 并集则自动补齐。
    供读大表时自愈历史错误快照；返回是否写入了快照行。
    """
    row = _get_units_snapshot_row(
        db, store_id=int(store_id), delivery_date=delivery_date, meal_period=meal_period
    )
    if row is None:
        return False
    from app.services.delivery.delivery_day_lock_service import sf_push_fulfillment_member_ids_live

    live_ids = sf_push_fulfillment_member_ids_live(
        db, store_id=int(store_id), delivery_date=delivery_date, meal_period=meal_period
    )
    if not live_ids:
        return False
    cached = _frozen_member_ids_from_units_json(row.member_meal_units) or frozenset()
    if live_ids <= cached:
        return False
    merge_delivery_sheet_push_into_units_snapshot(
        db,
        store_id=int(store_id),
        delivery_date=delivery_date,
        fulfillment_member_ids=sorted(live_ids),
        meal_period=meal_period,
    )
    return True


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
    row = _get_units_snapshot_row(
        db, store_id=int(store_id), delivery_date=delivery_date, meal_period=meal_period
    )
    if row is None:
        return False
    if _frozen_member_ids_from_units_json(row.member_meal_units) is not None:
        return False
    from app.services.delivery.delivery_day_lock_service import sf_push_fulfillment_member_ids_live

    frozen = sf_push_fulfillment_member_ids_live(
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
    meal_period: str = DEFAULT_MEAL_PERIOD,
) -> DeliverySheetPushUnitsSnapshot | None:
    from sqlalchemy.exc import OperationalError, ProgrammingError

    try:
        return db.get(
            DeliverySheetPushUnitsSnapshot,
            _snapshot_pk(store_id=int(store_id), delivery_date=delivery_date, meal_period=meal_period),
        )
    except (OperationalError, ProgrammingError):
        return None
