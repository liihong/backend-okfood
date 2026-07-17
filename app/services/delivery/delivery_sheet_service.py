"""管理端配送大表：按请假规则筛选会员，默认收件地址聚合为配送点。

送达状态：配送到家会员与 ``delivery_logs``（DELIVERED、业务日）对齐，与骑手端任务列表一致；
门店自提仅备餐归组，份数不计入「到家已/未送达」汇总。
扣次后无剩余、不再满足应送 SQL 的会员，若当日已有已送达记录，仍并入本大表，避免从当日统计中消失。
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date

from fastapi import HTTPException
from sqlalchemy import and_, case, func, select
from sqlalchemy.orm import Session

from app.constants import UNASSIGNED_DELIVERY_AREA
from app.core.config import get_settings
from app.core.delivery_calendar import is_subscription_delivery_day
from app.core.timeutil import today_shanghai
from app.models.delivery_log import DeliveryLog
from app.models.delivery_region import DeliveryRegion
from app.models.enums import CardOrderKind, CardOrderPayStatus, DeliveryStatus
from app.models.member import Member
from app.models.member_card_order import MemberCardOrder
from app.models.member_address import MemberAddress
from app.models.store import Store
from app.schemas.admin import DeliverySheetGroupOut, DeliverySheetMemberOut, DeliverySheetOut, DeliverySheetStopOut
from app.services.delivery.courier_service import (
    _member_subscription_eligibility_where,
    eligible_members_for_delivery,
    eligible_members_for_store_pickup,
    extra_delivered_ineligible_subscribers,
    post_push_first_day_whitelist_member_ids,
)
from app.services.member.member_address_service import delivery_region_name_map, full_address_line, load_default_address_map, routing_area_label
from app.services.delivery.delivery_sheet_meal_units_service import DeliverySheetMealUnitsContext
from app.services.delivery.delivery_sheet_push_snapshot_service import DeliverySheetDaySnapshots
from app.services.member.member_service import (
    effective_daily_meal_units,
    sql_effective_daily_meal_units_column,
    sql_prep_preview_daily_meal_units_column,
)
from app.models.enums import DeliverySheetView, MealPeriod
from app.services.meal_period.card_eligibility import filter_member_groups_for_sheet_view
from app.services.meal_period.constants import DEFAULT_MEAL_PERIOD


def _merged_home_member_ids_when_sheet_frozen(
    db: Session,
    *,
    delivery_date: date,
    store_id: int,
    delivery_region_id: int | None = None,
    frozen_ids: frozenset[int] | None = None,
    absent_at_push: frozenset[int] | None = None,
    meal_period: str = DEFAULT_MEAL_PERIOD,
) -> set[int]:
    """
    大表已推单：顺丰快照 frozen ∪ 推单后白名单（当日首餐新客）。
    推单当日曾请假的会员（首次推单快照）不因取消请假再并入；无快照行时仅 frozen（兼容历史日）。
    meal_period 区分午/晚餐 push_kind 与白名单口径。
    """
    from app.services.delivery.delivery_day_lock_service import (
        sf_cancelled_sheet_member_ids_for_delivery_date,
        sf_frozen_subscription_member_ids_for_delivery_date,
    )
    from app.services.delivery.delivery_sheet_push_snapshot_service import absent_member_ids_at_first_push

    sid = int(store_id)
    period = (meal_period or DEFAULT_MEAL_PERIOD).strip().lower()
    frozen = (
        frozen_ids
        if frozen_ids is not None
        else sf_frozen_subscription_member_ids_for_delivery_date(
            db, store_id=sid, delivery_date=delivery_date, meal_period=period
        )
    )
    if absent_at_push is None:
        absent_at_push = absent_member_ids_at_first_push(
            db, store_id=sid, delivery_date=delivery_date, meal_period=period
        )
    merged = set(frozen)
    # 已取消推单中的订阅会员仍保留在大表待送名单（便于运营核对与重推）
    for mid in sf_cancelled_sheet_member_ids_for_delivery_date(
        db, store_id=sid, delivery_date=delivery_date, meal_period=period
    ):
        if absent_at_push is not None and mid in absent_at_push:
            continue
        merged.add(int(mid))
    whitelist = post_push_first_day_whitelist_member_ids(
        db,
        delivery_date=delivery_date,
        delivery_region_id=delivery_region_id,
        store_id=sid,
        meal_period=period,
    )
    for mid in whitelist:
        if mid in merged:
            continue
        if absent_at_push is not None and mid in absent_at_push:
            continue
        merged.add(mid)
    return merged


def _load_home_members_with_default_addresses(
    db: Session,
    *,
    member_ids: set[int],
    store_id: int,
    delivery_region_id: int | None = None,
) -> tuple[list[Member], dict[int, MemberAddress | None]]:
    """按 id 批量加载到家会员与默认地址（一次 JOIN，供推单冻结大表用）。"""
    from app.services.member.member_address_service import default_address_pick_subquery

    if not member_ids:
        return [], {}
    sid = int(store_id)
    daf = default_address_pick_subquery()
    q = (
        select(Member, MemberAddress)
        .outerjoin(daf, daf.c.mid == Member.id)
        .outerjoin(MemberAddress, MemberAddress.id == daf.c.addr_id)
        .where(
            Member.id.in_(member_ids),
            Member.deleted_at.is_(None),
            Member.store_pickup.is_(False),
            Member.store_id == sid,
        )
    )
    if delivery_region_id is not None:
        q = q.where(MemberAddress.delivery_region_id == int(delivery_region_id))
    members: list[Member] = []
    defaults: dict[int, MemberAddress | None] = {}
    for m, addr in db.execute(q).all():
        members.append(m)
        defaults[int(m.id)] = addr
    return members, defaults


def _home_members_for_delivery_sheet(
    db: Session,
    *,
    delivery_date: date,
    delivery_region_id: int | None,
    store_id: int,
    day_snap: DeliverySheetDaySnapshots | None = None,
) -> tuple[list[Member], dict[int, MemberAddress | None]]:
    """
    到家应配送会员。大表顺丰推单后：快照 ∪ 当日首餐白名单；推单当日曾请假者取消请假不并入。
    """
    sid = int(store_id)
    if not is_subscription_delivery_day(delivery_date):
        return [], {}

    snap = day_snap or DeliverySheetDaySnapshots.load(
        db, store_id=sid, delivery_date=delivery_date
    )
    if snap.has_sf_push:
        frozen_ids = snap.frozen_member_ids or frozenset()
        merged_ids = _merged_home_member_ids_when_sheet_frozen(
            db,
            delivery_date=delivery_date,
            store_id=sid,
            delivery_region_id=delivery_region_id,
            frozen_ids=frozen_ids,
            absent_at_push=snap.absent_member_ids,
        )
        return _load_home_members_with_default_addresses(
            db,
            member_ids=merged_ids,
            store_id=sid,
            delivery_region_id=delivery_region_id,
        )

    return eligible_members_for_delivery(
        db,
        delivery_date=delivery_date,
        delivery_region_id=delivery_region_id,
        store_id=sid,
    )


def _home_members_for_dinner_delivery_sheet(
    db: Session,
    *,
    delivery_date: date,
    delivery_region_id: int | None,
    store_id: int,
    day_snap: DeliverySheetDaySnapshots | None = None,
) -> tuple[list[Member], dict[int, MemberAddress | None]]:
    """晚餐到家应配送会员；推单冻结逻辑与午餐平行，餐段为 dinner。"""
    from app.services.dinner.eligibility import eligible_members_for_dinner_delivery

    sid = int(store_id)
    if not is_subscription_delivery_day(delivery_date):
        return [], {}

    snap = day_snap or DeliverySheetDaySnapshots.load(
        db, store_id=sid, delivery_date=delivery_date, meal_period=MealPeriod.DINNER.value
    )
    if snap.has_sf_push:
        frozen_ids = snap.frozen_member_ids or frozenset()
        merged_ids = _merged_home_member_ids_when_sheet_frozen(
            db,
            delivery_date=delivery_date,
            store_id=sid,
            delivery_region_id=delivery_region_id,
            frozen_ids=frozen_ids,
            absent_at_push=snap.absent_member_ids,
            meal_period=MealPeriod.DINNER.value,
        )
        return _load_home_members_with_default_addresses(
            db,
            member_ids=merged_ids,
            store_id=sid,
            delivery_region_id=delivery_region_id,
        )

    return eligible_members_for_dinner_delivery(
        db,
        delivery_date=delivery_date,
        delivery_region_id=delivery_region_id,
        store_id=sid,
    )


def _member_balance_quota(mem: Member) -> tuple[int, int]:
    """剩余次数与展示用总次数（次卡无 quota 时用 balance 作为分母）；午餐口径。"""
    from app.services.meal_period.balance import balance_quota_for_sheet_period

    return balance_quota_for_sheet_period(mem, meal_period=MealPeriod.LUNCH.value)


def _normalize_address_key(s: str) -> str:
    return " ".join(s.strip().split()).casefold()


@dataclass(frozen=True)
class _ResolvedStopLine:
    area: str
    detail: str
    address_line: str


def _resolve_delivery_line(addr: MemberAddress | None, id_to_name: dict[int, str]) -> _ResolvedStopLine:
    """仅使用默认配送地址；members 表地址字段已废弃。"""
    if addr:
        area = routing_area_label(addr, id_to_name)
        detail = full_address_line(addr.map_location_text, addr.door_detail)
        line = f"{area} {detail}".strip()
        return _ResolvedStopLine(area=area, detail=detail, address_line=line or detail or "（无详细地址）")
    return _ResolvedStopLine(
        area=UNASSIGNED_DELIVERY_AREA,
        detail="",
        address_line="（未设置默认配送地址）",
    )


def _member_line_remarks(m: Member, addr: MemberAddress | None) -> str | None:
    parts: list[str] = []
    if m.remarks and m.remarks.strip():
        parts.append(m.remarks.strip())
    if addr and addr.remarks and addr.remarks.strip():
        parts.append(addr.remarks.strip())
    return "；".join(parts) if parts else None


def _active_regions_meta(db: Session, *, tenant_id: int) -> tuple[list[str], set[int]]:
    """启用片区：限定租户，与会员/门店维度一致。"""
    rows = db.execute(
        select(DeliveryRegion.id, DeliveryRegion.name)
        .where(DeliveryRegion.is_active.is_(True), DeliveryRegion.tenant_id == int(tenant_id))
        .order_by(DeliveryRegion.priority.asc(), DeliveryRegion.id.asc())
    ).all()
    names: list[str] = []
    ids: set[int] = set()
    for rid, n in rows:
        ids.add(int(rid))
        s = str(n).strip() if n is not None else ""
        if s:
            names.append(s)
    return names, ids


def _area_needs_attention(label: str | None, known_active_names: set[str]) -> bool:
    """展示名：空、未分配，或不在当前启用区域名称表内。"""
    a = (label or "").strip()
    if not a:
        return True
    if a == UNASSIGNED_DELIVERY_AREA:
        return True
    if known_active_names and a not in known_active_names:
        return True
    return False


def _member_area_issue(addr: MemberAddress | None, active_ids: set[int]) -> bool:
    if addr is None:
        return True
    if addr.delivery_region_id is None:
        return True
    return int(addr.delivery_region_id) not in active_ids


def _filter_members_by_phone_hint(members: list[Member], phone_hint: str) -> list[Member]:
    """按手机号筛选：忽略空格与符号，仅比较数字串是否包含输入中的连续数字（可输后四位或完整 11 位）。"""
    needle = re.sub(r"\D", "", (phone_hint or "").strip())
    if not needle:
        return members
    out: list[Member] = []
    for m in members:
        hay = re.sub(r"\D", "", (m.phone or "").strip())
        if needle in hay:
            out.append(m)
    return out


@dataclass(frozen=True)
class HomeDeliveryStopForAgg:
    """顺丰停靠点聚合用：与 ``build_delivery_sheet`` 到家分组同源，不含完整 Pydantic 树。"""

    area: str
    address_line: str
    members: tuple[tuple[Member, bool], ...]  # (member, is_delivered)


def home_delivery_stops_for_aggs(
    db: Session,
    *,
    delivery_date: date,
    store_id: int,
    members: list[Member],
    default_by_id: dict[int, MemberAddress | None],
    area: str | None = None,
    phone: str | None = None,
    meal_period: str = DEFAULT_MEAL_PERIOD,
) -> list[HomeDeliveryStopForAgg]:
    """
    构建到家停靠点列表，供顺丰 ``_build_aggs`` 使用。
    复用调用方已加载的 eligible 会员，仅补 ``extra_delivered_ineligible`` 与分桶逻辑，避免重复 ``build_delivery_sheet``。
    """
    sid = int(store_id)
    d = delivery_date
    region_filter_id: int | None = None
    if area and (a := area.strip()):
        st = db.get(Store, sid)
        if st is None:
            return []
        rid = db.scalar(
            select(DeliveryRegion.id).where(
                DeliveryRegion.name == a,
                DeliveryRegion.tenant_id == int(st.tenant_id),
            )
        )
        if rid is None:
            return []
        region_filter_id = int(rid)

    sheet_members = list(members)
    sheet_defaults = dict(default_by_id)
    period = (meal_period or DEFAULT_MEAL_PERIOD).strip().lower()
    day_delivered_ids = _store_delivered_member_ids_on_date(
        db, store_id=sid, delivery_date=d, meal_period=period
    )
    pu_members, _pu_defaults = eligible_members_for_store_pickup(db, delivery_date=d, store_id=sid)
    ex_h, ex_dh, _ex_pu, _ex_pud = extra_delivered_ineligible_subscribers(
        db,
        delivery_date=d,
        already_home={int(m.id) for m in sheet_members},
        already_pickup={int(m.id) for m in pu_members},
        delivery_region_id=region_filter_id,
        store_id=sid,
        day_delivered_member_ids=day_delivered_ids,
    )
    for m in ex_h:
        sheet_members.append(m)
        sheet_defaults[m.id] = ex_dh.get(int(m.id))

    ph = (phone or "").strip()
    if ph:
        sheet_members = _filter_members_by_phone_hint(sheet_members, ph)

    if not sheet_members:
        return []

    all_mids = {int(m.id) for m in sheet_members}
    delivered_set = day_delivered_ids & all_mids
    region_ids: set[int] = set()
    for m in sheet_members:
        addr = sheet_defaults.get(m.id)
        if addr and addr.delivery_region_id is not None:
            region_ids.add(int(addr.delivery_region_id))
    id_to_name = delivery_region_name_map(db, region_ids)

    buckets: dict[str, dict[tuple[str, str], list[Member]]] = defaultdict(lambda: defaultdict(list))
    for m in sheet_members:
        addr = sheet_defaults.get(m.id)
        routing_area = routing_area_label(addr, id_to_name)
        resolved = _resolve_delivery_line(addr, id_to_name)
        key = (_normalize_address_key(resolved.area), _normalize_address_key(resolved.detail))
        buckets[routing_area][key].append(m)

    out: list[HomeDeliveryStopForAgg] = []
    for area_name in sorted(buckets.keys()):
        stop_map = buckets[area_name]
        for ms in stop_map.values():
            ms_sorted = sorted(ms, key=lambda x: (x.id in delivered_set, (x.phone or "")))
            first = ms_sorted[0]
            resolved = _resolve_delivery_line(sheet_defaults.get(first.id), id_to_name)
            member_pairs = tuple((mem, mem.id in delivered_set) for mem in ms_sorted)
            out.append(
                HomeDeliveryStopForAgg(
                    area=area_name,
                    address_line=resolved.address_line,
                    members=member_pairs,
                )
            )
    return out


@dataclass(frozen=True)
class DeliverySheetDayMetrics:
    """与 ``build_delivery_sheet`` 根级汇总及到家停靠点计数同源，不含完整 groups 树。"""

    home_pending_meal_total: int
    home_delivered_meal_total: int
    pickup_meal_total: int
    pickup_pending_meal_total: int
    pickup_delivered_meal_total: int
    home_stop_count: int

    @property
    def meal_total(self) -> int:
        return (
            int(self.home_pending_meal_total)
            + int(self.home_delivered_meal_total)
            + int(self.pickup_meal_total)
        )


def _count_home_delivery_stops(
    sheet_members: list[Member],
    sheet_defaults: dict[int, MemberAddress | None],
    db: Session,
) -> int:
    """到家停靠点数：按片区+地址去重计数，供 dashboard metrics 使用（不构建完整停靠点结构）。"""
    if not sheet_members:
        return 0
    region_ids: set[int] = set()
    for m in sheet_members:
        addr = sheet_defaults.get(int(m.id))
        if addr and addr.delivery_region_id is not None:
            region_ids.add(int(addr.delivery_region_id))
    id_to_name = delivery_region_name_map(db, region_ids)
    buckets: dict[str, set[tuple[str, str]]] = defaultdict(set)
    for m in sheet_members:
        addr = sheet_defaults.get(int(m.id))
        routing_area = routing_area_label(addr, id_to_name)
        resolved = _resolve_delivery_line(addr, id_to_name)
        addr_key = (_normalize_address_key(resolved.area), _normalize_address_key(resolved.detail))
        buckets[routing_area].add(addr_key)
    return sum(len(stop_map) for stop_map in buckets.values())


def delivery_sheet_metrics_for_date(
    db: Session,
    *,
    delivery_date: date,
    store_id: int,
    metrics_cache: dict[date, DeliverySheetDayMetrics] | None = None,
) -> DeliverySheetDayMetrics:
    """营业概览用：备餐拆分 / 履约进度 / 到家配送点数，避免拉整张大表 JSON。"""
    if metrics_cache is not None and delivery_date in metrics_cache:
        return metrics_cache[delivery_date]
    empty = DeliverySheetDayMetrics(0, 0, 0, 0, 0, 0)
    if not is_subscription_delivery_day(delivery_date):
        if metrics_cache is not None:
            metrics_cache[delivery_date] = empty
        return empty

    sid = int(store_id)
    d = delivery_date
    day_snap = DeliverySheetDaySnapshots.load(db, store_id=sid, delivery_date=d)
    day_delivered_ids = _store_delivered_member_ids_on_date(db, store_id=sid, delivery_date=d)
    members, default_by_id = _home_members_for_delivery_sheet(
        db, delivery_date=d, delivery_region_id=None, store_id=sid, day_snap=day_snap
    )
    mlist = list(members)
    pu_members, _pu_defaults = eligible_members_for_store_pickup(db, delivery_date=d, store_id=sid)
    ex_h, ex_dh, ex_pu, _ex_pud = extra_delivered_ineligible_subscribers(
        db,
        delivery_date=d,
        already_home={int(m.id) for m in mlist},
        already_pickup={int(m.id) for m in pu_members},
        delivery_region_id=None,
        store_id=sid,
        day_delivered_member_ids=day_delivered_ids,
    )
    sheet_members = mlist + list(ex_h)
    sheet_defaults: dict[int, MemberAddress | None] = dict(default_by_id)
    for mid, addr in ex_dh.items():
        sheet_defaults[int(mid)] = addr

    home_mids = {int(m.id) for m in sheet_members}
    home_delivered_set = day_delivered_ids & home_mids
    units_ctx = DeliverySheetMealUnitsContext.from_day_snapshots(day_snap)
    home_pending = 0
    home_delivered = 0
    for m in sheet_members:
        u = units_ctx.units_for(m)
        if int(m.id) in home_delivered_set:
            home_delivered += u
        else:
            home_pending += u
    home_stop_count = _count_home_delivery_stops(sheet_members, sheet_defaults, db)

    all_pu = list(pu_members) + list(ex_pu)
    pu_mids = {int(m.id) for m in all_pu}
    pu_delivered_set = day_delivered_ids & pu_mids
    pu_delivered = sum(
        units_ctx.units_for(m)
        for m in all_pu
        if int(m.id) in pu_delivered_set
    )
    pu_pending = sum(
        units_ctx.units_for(m)
        for m in all_pu
        if int(m.id) not in pu_delivered_set
    )

    result = DeliverySheetDayMetrics(
        home_pending_meal_total=home_pending,
        home_delivered_meal_total=home_delivered,
        pickup_meal_total=pu_delivered + pu_pending,
        pickup_pending_meal_total=pu_pending,
        pickup_delivered_meal_total=pu_delivered,
        home_stop_count=home_stop_count,
    )
    if metrics_cache is not None:
        metrics_cache[delivery_date] = result
    return result


def delivery_sheet_metrics_for_dinner_date(
    db: Session,
    *,
    delivery_date: date,
    store_id: int,
    metrics_cache: dict[date, DeliverySheetDayMetrics] | None = None,
) -> DeliverySheetDayMetrics:
    """晚餐营业概览：仅到家配送，不含自提；餐段 delivery_logs / 推单快照为 dinner。"""
    if metrics_cache is not None and delivery_date in metrics_cache:
        return metrics_cache[delivery_date]
    empty = DeliverySheetDayMetrics(0, 0, 0, 0, 0, 0)
    if not is_subscription_delivery_day(delivery_date):
        if metrics_cache is not None:
            metrics_cache[delivery_date] = empty
        return empty

    sid = int(store_id)
    d = delivery_date
    day_snap = DeliverySheetDaySnapshots.load(
        db, store_id=sid, delivery_date=d, meal_period=MealPeriod.DINNER.value
    )
    day_delivered_ids = _store_delivered_member_ids_on_date(
        db, store_id=sid, delivery_date=d, meal_period=MealPeriod.DINNER.value
    )
    members, default_by_id = _home_members_for_dinner_delivery_sheet(
        db, delivery_date=d, delivery_region_id=None, store_id=sid, day_snap=day_snap
    )
    sheet_members = list(members)
    home_mids = {int(m.id) for m in sheet_members}
    home_delivered_set = day_delivered_ids & home_mids
    units_ctx = DeliverySheetMealUnitsContext.from_day_snapshots(day_snap, db=db)
    home_pending = 0
    home_delivered = 0
    for m in sheet_members:
        u = units_ctx.units_for(m)
        if int(m.id) in home_delivered_set:
            home_delivered += u
        else:
            home_pending += u
    home_stop_count = _count_home_delivery_stops(sheet_members, default_by_id, db)

    result = DeliverySheetDayMetrics(
        home_pending_meal_total=home_pending,
        home_delivered_meal_total=home_delivered,
        pickup_meal_total=0,
        pickup_pending_meal_total=0,
        pickup_delivered_meal_total=0,
        home_stop_count=home_stop_count,
    )
    if metrics_cache is not None:
        metrics_cache[delivery_date] = result
    return result


def delivery_sheet_metrics_pending_sql_for_dinner_future_date(
    db: Session, *, delivery_date: date, store_id: int
) -> DeliverySheetDayMetrics:
    """未来供餐日晚餐：SQL 聚合晚餐 eligible 到家份数（无自提）。"""
    from app.services.dinner.eligibility import eligible_members_for_dinner_delivery
    from app.services.meal_period.units import effective_daily_meal_units_for_period

    empty = DeliverySheetDayMetrics(0, 0, 0, 0, 0, 0)
    if not is_subscription_delivery_day(delivery_date):
        return empty
    members, _ = eligible_members_for_dinner_delivery(
        db, delivery_date=delivery_date, delivery_region_id=None, store_id=int(store_id)
    )
    total = sum(
        effective_daily_meal_units_for_period(db, m, MealPeriod.DINNER.value) for m in members
    )
    return DeliverySheetDayMetrics(
        home_pending_meal_total=int(total),
        home_delivered_meal_total=0,
        pickup_meal_total=0,
        pickup_pending_meal_total=0,
        pickup_delivered_meal_total=0,
        home_stop_count=0,
    )


def delivery_sheet_metrics_for_period(
    db: Session,
    *,
    delivery_date: date,
    store_id: int,
    meal_period: str = DEFAULT_MEAL_PERIOD,
    metrics_cache: dict | None = None,
) -> DeliverySheetDayMetrics:
    """分餐段 metrics；metrics_cache 键为 (date, period) 或 date（仅 lunch 兼容旧调用）。"""
    period = (meal_period or DEFAULT_MEAL_PERIOD).strip().lower()
    cached = period_metrics_cache_get(metrics_cache, delivery_date, period)
    if cached is not None:
        return cached
    if period == MealPeriod.DINNER.value:
        result = delivery_sheet_metrics_for_dinner_date(
            db, delivery_date=delivery_date, store_id=int(store_id)
        )
    else:
        from app.core.timeutil import today_shanghai
        from app.services.delivery.delivery_day_lock_service import is_delivery_day_sheet_frozen_after_sf_push

        sid = int(store_id)
        d = delivery_date
        cal_today = today_shanghai()
        if d > cal_today:
            result = delivery_sheet_metrics_pending_sql_for_future_date(db, delivery_date=d, store_id=sid)
        elif is_delivery_day_sheet_frozen_after_sf_push(db, store_id=sid, delivery_date=d):
            result = delivery_sheet_metrics_via_sql_for_locked_date(db, delivery_date=d, store_id=sid)
        else:
            result = delivery_sheet_metrics_via_sql_for_unlocked_date(db, delivery_date=d, store_id=sid)
    period_metrics_cache_put(metrics_cache, delivery_date, period, result)
    return result


def _sum_meal_units_home_eligible_on_date(db: Session, *, delivery_date: date, store_id: int) -> int:
    units_sql = sql_effective_daily_meal_units_column()
    q = select(func.coalesce(func.sum(units_sql), 0)).where(
        *_member_subscription_eligibility_where(delivery_date, store_id=int(store_id)),
        Member.store_pickup.is_(False),
    )
    return int(db.scalar(q) or 0)


def _sum_meal_units_pickup_eligible_on_date(db: Session, *, delivery_date: date, store_id: int) -> int:
    units_sql = sql_effective_daily_meal_units_column()
    q = select(func.coalesce(func.sum(units_sql), 0)).where(
        *_member_subscription_eligibility_where(delivery_date, store_id=int(store_id)),
        Member.store_pickup.is_(True),
    )
    return int(db.scalar(q) or 0)


def _sum_meal_units_extra_delivered_on_date(db: Session, *, delivery_date: date, store_id: int) -> int:
    """扣次后不再应送、但当日 delivery_logs 已 DELIVERED 的会员份数（到家+自提）。"""
    sid = int(store_id)
    units_sql = sql_effective_daily_meal_units_column()
    home_elig = select(Member.id).where(
        *_member_subscription_eligibility_where(delivery_date, store_id=sid),
        Member.store_pickup.is_(False),
    )
    pu_elig = select(Member.id).where(
        *_member_subscription_eligibility_where(delivery_date, store_id=sid),
        Member.store_pickup.is_(True),
    )
    delivered = (
        select(DeliveryLog.member_id)
        .join(Member, Member.id == DeliveryLog.member_id)
        .where(
            DeliveryLog.delivery_date == delivery_date,
            DeliveryLog.status == DeliveryStatus.DELIVERED.value,
            Member.store_id == sid,
            Member.deleted_at.is_(None),
        )
        .distinct()
    )
    q = (
        select(func.coalesce(func.sum(units_sql), 0))
        .select_from(Member)
        .where(
            Member.store_id == sid,
            Member.deleted_at.is_(None),
            Member.id.in_(delivered),
            Member.id.notin_(home_elig),
            Member.id.notin_(pu_elig),
        )
    )
    return int(db.scalar(q) or 0)


def _member_ids_delivered_on_date(
    db: Session,
    delivery_date: date,
    member_ids: list[int],
    *,
    meal_period: str = DEFAULT_MEAL_PERIOD,
) -> set[int]:
    """查询当日已在 ``delivery_logs`` 标记为送达的会员 id（按餐段隔离）。"""
    if not member_ids:
        return set()
    period = (meal_period or DEFAULT_MEAL_PERIOD).strip().lower()
    rows = db.scalars(
        select(DeliveryLog.member_id).where(
            DeliveryLog.delivery_date == delivery_date,
            DeliveryLog.status == DeliveryStatus.DELIVERED.value,
            DeliveryLog.meal_period == period,
            DeliveryLog.member_id.in_(member_ids),
        )
    ).all()
    return {int(x) for x in rows}


def _store_delivered_member_ids_on_date(
    db: Session,
    *,
    store_id: int,
    delivery_date: date,
    meal_period: str = DEFAULT_MEAL_PERIOD,
) -> set[int]:
    """门店当日指定餐段已送达会员 id（一次索引扫描，供大表与 extra_delivered 复用）。"""
    period = (meal_period or DEFAULT_MEAL_PERIOD).strip().lower()
    rows = db.scalars(
        select(DeliveryLog.member_id)
        .distinct()
        .join(Member, Member.id == DeliveryLog.member_id)
        .where(
            DeliveryLog.delivery_date == delivery_date,
            DeliveryLog.status == DeliveryStatus.DELIVERED.value,
            DeliveryLog.meal_period == period,
            Member.store_id == int(store_id),
        )
    ).all()
    return {int(x) for x in rows}


def _store_membership_counts(db: Session, *, store_id: int) -> dict[str, int]:
    """
    大表顶栏会员统计。
    午餐周/月卡仍读 members.balance + plan_type（现网口径）；
    另附 active_dinner_members：晚餐池有余次的去重会员数。
    """
    from app.models.enums import MealPeriod
    from app.models.member_meal_period_state import MemberMealPeriodState

    sid = int(store_id)
    row = db.execute(
        select(
            func.count().label("total"),
            func.coalesce(
                func.sum(case((and_(Member.plan_type == "周卡", Member.balance > 0), 1), else_=0)),
                0,
            ).label("wa"),
            func.coalesce(
                func.sum(case((and_(Member.plan_type == "周卡", Member.balance == 0), 1), else_=0)),
                0,
            ).label("we"),
            func.coalesce(
                func.sum(case((and_(Member.plan_type == "月卡", Member.balance > 0), 1), else_=0)),
                0,
            ).label("ma"),
            func.coalesce(
                func.sum(case((and_(Member.plan_type == "月卡", Member.balance == 0), 1), else_=0)),
                0,
            ).label("me"),
        )
        .select_from(Member)
        .where(Member.deleted_at.is_(None), Member.store_id == sid)
    ).one()
    dinner_active = int(
        db.scalar(
            select(func.count(func.distinct(MemberMealPeriodState.member_id)))
            .select_from(MemberMealPeriodState)
            .join(Member, Member.id == MemberMealPeriodState.member_id)
            .where(
                MemberMealPeriodState.meal_period == MealPeriod.DINNER.value,
                MemberMealPeriodState.balance > 0,
                Member.deleted_at.is_(None),
                Member.store_id == sid,
            )
        )
        or 0
    )
    return {
        "total_members": int(row.total or 0),
        "active_weekly_members": int(row.wa or 0),
        "expired_weekly_members": int(row.we or 0),
        "active_monthly_members": int(row.ma or 0),
        "expired_monthly_members": int(row.me or 0),
        "active_dinner_members": dinner_active,
    }


def _card_reorder_stats_for_kinds(
    db: Session, *, store_id: int, card_kinds: list[str]
) -> dict[str, tuple[int, int]]:
    """各卡型续卡率分子/分母（字段名历史沿用 reorder_*）。

    分母：曾有过该卡型「已缴且已入账」工单的去重会员数。
    分子：同一卡型有第 2 笔及以上入账的去重会员数；含提前续卡（如 6 次只吃 1 次又续）
    与过期后续购，不要求先 balance 归零。
    """
    kinds = [str(k).strip() for k in card_kinds if str(k).strip()]
    if not kinds:
        return {}
    sid = int(store_id)
    paid_filters = (
        MemberCardOrder.store_id == sid,
        MemberCardOrder.card_kind.in_(kinds),
        MemberCardOrder.pay_status == CardOrderPayStatus.PAID.value,
        MemberCardOrder.applied_to_member.is_(True),
        Member.deleted_at.is_(None),
    )
    base_rows = db.execute(
        select(
            MemberCardOrder.card_kind,
            func.count(func.distinct(MemberCardOrder.member_id)),
        )
        .select_from(MemberCardOrder)
        .join(Member, Member.id == MemberCardOrder.member_id)
        .where(*paid_filters)
        .group_by(MemberCardOrder.card_kind)
    ).all()
    base_map = {str(k): int(c or 0) for k, c in base_rows}

    reorder_subq = (
        select(MemberCardOrder.card_kind.label("card_kind"))
        .select_from(MemberCardOrder)
        .join(Member, Member.id == MemberCardOrder.member_id)
        .where(*paid_filters)
        .group_by(MemberCardOrder.card_kind, MemberCardOrder.member_id)
        .having(func.count(MemberCardOrder.id) >= 2)
        .subquery()
    )
    reorder_rows = db.execute(
        select(reorder_subq.c.card_kind, func.count()).group_by(reorder_subq.c.card_kind)
    ).all()
    reorder_map = {str(k): int(c or 0) for k, c in reorder_rows}

    return {k: (reorder_map.get(k, 0), base_map.get(k, 0)) for k in kinds}


def _card_reorder_members_for_kind(db: Session, *, store_id: int, card_kind: str) -> tuple[int, int]:
    """某卡型续卡率分子/分母（含提前续卡）。"""
    m = _card_reorder_stats_for_kinds(db, store_id=store_id, card_kinds=[card_kind])
    return m.get(card_kind, (0, 0))


def _store_card_reorder_stats(db: Session, *, store_id: int) -> dict[str, int]:
    """仪表盘地图会员库：周卡/月卡续卡率（二次及以上入账，含提前续卡）。"""
    stats = _card_reorder_stats_for_kinds(
        db,
        store_id=store_id,
        card_kinds=[CardOrderKind.WEEK.value, CardOrderKind.MONTH.value],
    )
    week_reorder, week_base = stats.get(CardOrderKind.WEEK.value, (0, 0))
    month_reorder, month_base = stats.get(CardOrderKind.MONTH.value, (0, 0))
    return {
        "weekly_card_reorder_members": week_reorder,
        "weekly_card_reorder_base_members": week_base,
        "monthly_card_reorder_members": month_reorder,
        "monthly_card_reorder_base_members": month_base,
    }


def total_meal_units_sql_sum_only(
    db: Session, *, delivery_date: date, store_id: int
) -> int:
    """仅 SQL SUM 聚合份数，不跑停靠点大表。Dashboard 同比基线等场景用（锁单日亦不走 metrics）。"""
    if not is_subscription_delivery_day(delivery_date):
        return 0
    sid = int(store_id)
    return (
        _sum_meal_units_home_eligible_on_date(db, delivery_date=delivery_date, store_id=sid)
        + _sum_meal_units_pickup_eligible_on_date(db, delivery_date=delivery_date, store_id=sid)
        + _sum_meal_units_extra_delivered_on_date(db, delivery_date=delivery_date, store_id=sid)
    )


def _exclude_store_pickup_members_from_frozen_home_ids(
    db: Session,
    member_ids: set[int],
) -> set[int]:
    """锁单后改自提：仍可能在顺丰快照 merged 集合，库存/到家份数应从 frozen 侧剔除（自提侧按现库统计）。"""
    if not member_ids:
        return set()
    pickup_ids = {
        int(x)
        for x in db.scalars(
            select(Member.id).where(
                Member.id.in_(member_ids),
                Member.deleted_at.is_(None),
                Member.store_pickup.is_(True),
            )
        ).all()
    }
    return member_ids - pickup_ids


def _total_meal_units_locked_date_sql(
    db: Session, *, delivery_date: date, store_id: int
) -> int:
    """锁单日应配送份数合计：冻结到家名单 SQL SUM + 自提应送 + 扣次后已送。

    与 ``delivery_sheet_metrics_for_date(...).meal_total`` 口径一致，但不加载会员行与地址。
    """
    sid = int(store_id)
    merged = _exclude_store_pickup_members_from_frozen_home_ids(
        db,
        _merged_home_member_ids_when_sheet_frozen(
            db, delivery_date=delivery_date, store_id=sid
        ),
    )
    from app.services.delivery.delivery_sheet_meal_units_service import (
        sum_meal_units_for_member_ids_on_frozen_sheet,
    )

    home_frozen = sum_meal_units_for_member_ids_on_frozen_sheet(
        db, merged, delivery_date=delivery_date, store_id=sid
    )
    return (
        home_frozen
        + _sum_meal_units_pickup_eligible_on_date(db, delivery_date=delivery_date, store_id=sid)
        + _sum_meal_units_extra_delivered_on_date(db, delivery_date=delivery_date, store_id=sid)
    )


def _delivered_member_ids_subquery(db: Session, *, delivery_date: date, store_id: int):
    """当日 delivery_logs 已 DELIVERED 的会员 id 子查询（dashboard SQL 快速路径用）。"""
    sid = int(store_id)
    return (
        select(DeliveryLog.member_id)
        .join(Member, Member.id == DeliveryLog.member_id)
        .where(
            DeliveryLog.delivery_date == delivery_date,
            DeliveryLog.status == DeliveryStatus.DELIVERED.value,
            Member.store_id == sid,
            Member.deleted_at.is_(None),
        )
        .distinct()
    )


def _sum_meal_units_split_by_delivery_status(
    db: Session,
    *,
    delivery_date: date,
    store_id: int,
    base_filters: tuple,
) -> tuple[int, int]:
    """按 delivery_logs 是否已 DELIVERED 拆分 SQL 份数（已送 / 待送）。"""
    units_sql = sql_effective_daily_meal_units_column()
    delivered_subq = _delivered_member_ids_subquery(db, delivery_date=delivery_date, store_id=store_id)
    delivered = int(
        db.scalar(
            select(func.coalesce(func.sum(units_sql), 0)).where(
                *base_filters,
                Member.id.in_(delivered_subq),
            )
        )
        or 0
    )
    pending = int(
        db.scalar(
            select(func.coalesce(func.sum(units_sql), 0)).where(
                *base_filters,
                Member.id.notin_(delivered_subq),
            )
        )
        or 0
    )
    return delivered, pending


def _sum_extra_delivered_by_pickup_on_date(
    db: Session, *, delivery_date: date, store_id: int, store_pickup: bool
) -> int:
    """扣次后不再应送、但当日已 DELIVERED 的会员份数；按 store_pickup 拆分。"""
    sid = int(store_id)
    units_sql = sql_effective_daily_meal_units_column()
    home_elig = select(Member.id).where(
        *_member_subscription_eligibility_where(delivery_date, store_id=sid),
        Member.store_pickup.is_(False),
    )
    pu_elig = select(Member.id).where(
        *_member_subscription_eligibility_where(delivery_date, store_id=sid),
        Member.store_pickup.is_(True),
    )
    delivered_subq = _delivered_member_ids_subquery(db, delivery_date=delivery_date, store_id=sid)
    q = (
        select(func.coalesce(func.sum(units_sql), 0))
        .select_from(Member)
        .where(
            Member.store_id == sid,
            Member.deleted_at.is_(None),
            Member.store_pickup.is_(store_pickup),
            Member.id.in_(delivered_subq),
            Member.id.notin_(home_elig),
            Member.id.notin_(pu_elig),
        )
    )
    return int(db.scalar(q) or 0)


def delivery_sheet_metrics_pending_sql_for_future_date(
    db: Session, *, delivery_date: date, store_id: int
) -> DeliverySheetDayMetrics:
    """未来供餐日：尚无送达记录，全部待送；仅 SQL 聚合，不加载会员行。"""
    empty = DeliverySheetDayMetrics(0, 0, 0, 0, 0, 0)
    if not is_subscription_delivery_day(delivery_date):
        return empty
    sid = int(store_id)
    home_pending = _sum_meal_units_home_eligible_on_date(db, delivery_date=delivery_date, store_id=sid)
    pickup_pending = _sum_meal_units_pickup_eligible_on_date(db, delivery_date=delivery_date, store_id=sid)
    return DeliverySheetDayMetrics(
        home_pending_meal_total=home_pending,
        home_delivered_meal_total=0,
        pickup_meal_total=pickup_pending,
        pickup_pending_meal_total=pickup_pending,
        pickup_delivered_meal_total=0,
        home_stop_count=0,
    )


def _member_subscription_eligibility_where_prep_preview(
    delivery_date: date,
    *,
    tenant_id: int | None = None,
    store_id: int | None = None,
) -> list:
    """明日备餐预览专用：资格判定与 SUM 均使用 pending 优先份数。"""
    from app.services.delivery.courier_service import _member_subscription_schedule_where

    units_sql = sql_prep_preview_daily_meal_units_column()
    return [
        *_member_subscription_schedule_where(
            delivery_date, tenant_id=tenant_id, store_id=store_id
        ),
        Member.balance >= units_sql,
    ]


def _sum_meal_units_home_eligible_on_date_prep_preview(
    db: Session, *, delivery_date: date, store_id: int
) -> int:
    units_sql = sql_prep_preview_daily_meal_units_column()
    q = select(func.coalesce(func.sum(units_sql), 0)).where(
        *_member_subscription_eligibility_where_prep_preview(
            delivery_date, store_id=int(store_id)
        ),
        Member.store_pickup.is_(False),
    )
    return int(db.scalar(q) or 0)


def _sum_meal_units_pickup_eligible_on_date_prep_preview(
    db: Session, *, delivery_date: date, store_id: int
) -> int:
    units_sql = sql_prep_preview_daily_meal_units_column()
    q = select(func.coalesce(func.sum(units_sql), 0)).where(
        *_member_subscription_eligibility_where_prep_preview(
            delivery_date, store_id=int(store_id)
        ),
        Member.store_pickup.is_(True),
    )
    return int(db.scalar(q) or 0)


def delivery_sheet_metrics_prep_preview_for_future_date(
    db: Session, *, delivery_date: date, store_id: int
) -> DeliverySheetDayMetrics:
    """营业概览「明日备餐」专用：未来供餐日纳入 daily_meal_units_pending 预览，不影响其它统计口径。"""
    empty = DeliverySheetDayMetrics(0, 0, 0, 0, 0, 0)
    if not is_subscription_delivery_day(delivery_date):
        return empty
    sid = int(store_id)
    home_pending = _sum_meal_units_home_eligible_on_date_prep_preview(
        db, delivery_date=delivery_date, store_id=sid
    )
    pickup_pending = _sum_meal_units_pickup_eligible_on_date_prep_preview(
        db, delivery_date=delivery_date, store_id=sid
    )
    return DeliverySheetDayMetrics(
        home_pending_meal_total=home_pending,
        home_delivered_meal_total=0,
        pickup_meal_total=pickup_pending,
        pickup_pending_meal_total=pickup_pending,
        pickup_delivered_meal_total=0,
        home_stop_count=0,
    )


def delivery_sheet_metrics_prep_preview_for_dinner_future_date(
    db: Session, *, delivery_date: date, store_id: int
) -> DeliverySheetDayMetrics:
    """营业概览「明日晚餐备餐」专用：未来供餐日纳入晚餐 pending 预览。"""
    from app.services.dinner.eligibility import eligible_members_for_dinner_delivery
    from app.services.meal_period.dinner_units import prep_preview_dinner_daily_meal_units
    from app.services.meal_period.units import (
        dinner_daily_meal_units_from_state,
        load_dinner_meal_period_states_map,
    )

    empty = DeliverySheetDayMetrics(0, 0, 0, 0, 0, 0)
    if not is_subscription_delivery_day(delivery_date):
        return empty
    members, _ = eligible_members_for_dinner_delivery(
        db, delivery_date=delivery_date, delivery_region_id=None, store_id=int(store_id)
    )
    state_map = load_dinner_meal_period_states_map(db, [int(m.id) for m in members])
    total = 0
    for m in members:
        row = state_map.get(int(m.id))
        preview_units = prep_preview_dinner_daily_meal_units(row)
        d_bal = max(0, int(row.balance or 0)) if row is not None else 0
        current_units = dinner_daily_meal_units_from_state(row)
        # pending 增份后余额不足时，00:01 落库后将退出大表，预览不计入
        if preview_units > current_units and d_bal < preview_units:
            continue
        total += preview_units
    return DeliverySheetDayMetrics(
        home_pending_meal_total=int(total),
        home_delivered_meal_total=0,
        pickup_meal_total=0,
        pickup_pending_meal_total=0,
        pickup_delivered_meal_total=0,
        home_stop_count=0,
    )


def period_metrics_cache_get(
    metrics_cache: dict | None,
    delivery_date: date,
    meal_period: str = DEFAULT_MEAL_PERIOD,
) -> DeliverySheetDayMetrics | None:
    """请求内 metrics 缓存读取：午餐兼容 ``date`` 与 ``(date, period)`` 双键。"""
    if metrics_cache is None:
        return None
    period = (meal_period or DEFAULT_MEAL_PERIOD).strip().lower()
    hit = metrics_cache.get((delivery_date, period))
    if hit is not None:
        return hit
    if period == MealPeriod.LUNCH.value:
        return metrics_cache.get(delivery_date)
    return None


def period_metrics_cache_put(
    metrics_cache: dict | None,
    delivery_date: date,
    meal_period: str,
    result: DeliverySheetDayMetrics,
) -> None:
    """请求内 metrics 缓存写入：午餐同时写 ``date`` 与 ``(date, lunch)``。"""
    if metrics_cache is None:
        return
    period = (meal_period or DEFAULT_MEAL_PERIOD).strip().lower()
    metrics_cache[(delivery_date, period)] = result
    if period == MealPeriod.LUNCH.value:
        metrics_cache[delivery_date] = result


def _sum_frozen_home_units_for_member_ids(
    member_ids: set[int],
    *,
    snapshot: dict[int, int] | None,
    members_by_id: dict[int, Member],
) -> int:
    """锁单日到家名单（快照份数 + 批量会员）求和。"""
    from app.services.delivery.delivery_sheet_meal_units_service import _clamp_units

    total = 0
    for mid in member_ids:
        m = members_by_id.get(int(mid))
        if m is None:
            continue
        if snapshot and int(mid) in snapshot:
            total += _clamp_units(snapshot[int(mid)])
        else:
            total += effective_daily_meal_units(m)
    return total


def delivery_sheet_metrics_via_sql_for_locked_date(
    db: Session, *, delivery_date: date, store_id: int
) -> DeliverySheetDayMetrics:
    """锁单日：快照聚合拆分已送/待送，dashboard 用，不加载地址/停靠点。"""
    from app.services.delivery.delivery_sheet_push_snapshot_service import (
        member_meal_units_snapshot_for_date,
    )

    empty = DeliverySheetDayMetrics(0, 0, 0, 0, 0, 0)
    if not is_subscription_delivery_day(delivery_date):
        return empty
    sid = int(store_id)
    d = delivery_date
    day_snap = DeliverySheetDaySnapshots.load(db, store_id=sid, delivery_date=d)
    merged_home_ids = _exclude_store_pickup_members_from_frozen_home_ids(
        db,
        _merged_home_member_ids_when_sheet_frozen(
            db,
            delivery_date=d,
            store_id=sid,
            frozen_ids=day_snap.frozen_member_ids or frozenset(),
            absent_at_push=day_snap.absent_member_ids,
        ),
    )
    delivered_subq = _delivered_member_ids_subquery(db, delivery_date=d, store_id=sid)
    if merged_home_ids:
        delivered_home_ids = {
            int(x)
            for x in db.scalars(
                select(Member.id).where(
                    Member.id.in_(merged_home_ids),
                    Member.id.in_(delivered_subq),
                    Member.deleted_at.is_(None),
                )
            ).all()
        }
        pending_home_ids = merged_home_ids - delivered_home_ids
    else:
        delivered_home_ids = set()
        pending_home_ids = set()

    snap = member_meal_units_snapshot_for_date(db, store_id=sid, delivery_date=d)
    all_home_ids = delivered_home_ids | pending_home_ids
    members_by_id: dict[int, Member] = {}
    if all_home_ids:
        for m in db.scalars(
            select(Member).where(
                Member.id.in_(all_home_ids),
                Member.deleted_at.is_(None),
            )
        ).all():
            members_by_id[int(m.id)] = m

    home_delivered = _sum_frozen_home_units_for_member_ids(
        delivered_home_ids, snapshot=snap, members_by_id=members_by_id
    )
    home_pending = _sum_frozen_home_units_for_member_ids(
        pending_home_ids, snapshot=snap, members_by_id=members_by_id
    )

    pu_base = (
        *_member_subscription_eligibility_where(d, store_id=sid),
        Member.store_pickup.is_(True),
    )
    pu_delivered, pu_pending = _sum_meal_units_split_by_delivery_status(
        db, delivery_date=d, store_id=sid, base_filters=pu_base
    )
    # 锁单日到家名单已含推单快照 merged 集合，勿再叠加 extra_home（会与 eligibility 口径重复计 15 份等）
    pu_delivered += _sum_extra_delivered_by_pickup_on_date(
        db, delivery_date=d, store_id=sid, store_pickup=True
    )
    return DeliverySheetDayMetrics(
        home_pending_meal_total=home_pending,
        home_delivered_meal_total=home_delivered,
        pickup_meal_total=pu_delivered + pu_pending,
        pickup_pending_meal_total=pu_pending,
        pickup_delivered_meal_total=pu_delivered,
        home_stop_count=0,
    )


def delivery_sheet_metrics_via_sql_for_unlocked_date(
    db: Session, *, delivery_date: date, store_id: int
) -> DeliverySheetDayMetrics:
    """未锁单日：用 SQL 拆分已送/待送，避免 dashboard 加载整表会员。"""
    empty = DeliverySheetDayMetrics(0, 0, 0, 0, 0, 0)
    if not is_subscription_delivery_day(delivery_date):
        return empty
    sid = int(store_id)
    home_base = (
        *_member_subscription_eligibility_where(delivery_date, store_id=sid),
        Member.store_pickup.is_(False),
    )
    pu_base = (
        *_member_subscription_eligibility_where(delivery_date, store_id=sid),
        Member.store_pickup.is_(True),
    )
    home_delivered, home_pending = _sum_meal_units_split_by_delivery_status(
        db, delivery_date=delivery_date, store_id=sid, base_filters=home_base
    )
    pu_delivered, pu_pending = _sum_meal_units_split_by_delivery_status(
        db, delivery_date=delivery_date, store_id=sid, base_filters=pu_base
    )
    home_delivered += _sum_extra_delivered_by_pickup_on_date(
        db, delivery_date=delivery_date, store_id=sid, store_pickup=False
    )
    pu_delivered += _sum_extra_delivered_by_pickup_on_date(
        db, delivery_date=delivery_date, store_id=sid, store_pickup=True
    )
    return DeliverySheetDayMetrics(
        home_pending_meal_total=home_pending,
        home_delivered_meal_total=home_delivered,
        pickup_meal_total=pu_delivered + pu_pending,
        pickup_pending_meal_total=pu_pending,
        pickup_delivered_meal_total=pu_delivered,
        home_stop_count=0,
    )


def total_meal_units_for_delivery_sheet(
    db: Session,
    *,
    delivery_date: date,
    store_id: int | None = None,
    metrics_cache: dict[date, DeliverySheetDayMetrics] | None = None,
) -> int:
    """与 ``build_delivery_sheet`` 各分组 ``meal_total`` 之和一致（到家+自提，含已送后不再应送仍并入大表者）。

    SQL SUM 聚合，不加载会员行与停靠点结构，供仪表盘等对日份数统计。
    """
    if not is_subscription_delivery_day(delivery_date):
        return 0
    from app.core.tenant_scope import require_store_id_for_service

    sid = require_store_id_for_service(store_id, operation="配送大表份数统计")
    from app.services.delivery.delivery_day_lock_service import is_delivery_day_sheet_frozen_after_sf_push

    if is_delivery_day_sheet_frozen_after_sf_push(
        db, store_id=sid, delivery_date=delivery_date
    ):
        return _total_meal_units_locked_date_sql(db, delivery_date=delivery_date, store_id=sid)
    return (
        _sum_meal_units_home_eligible_on_date(db, delivery_date=delivery_date, store_id=sid)
        + _sum_meal_units_pickup_eligible_on_date(db, delivery_date=delivery_date, store_id=sid)
        + _sum_meal_units_extra_delivered_on_date(db, delivery_date=delivery_date, store_id=sid)
    )


def meal_units_totals_for_delivery_dates(
    db: Session,
    *,
    dates: Iterable[date],
    store_id: int | None = None,
    metrics_cache: dict[date, DeliverySheetDayMetrics] | None = None,
    snapshot_meal_totals: dict[date, int] | None = None,
    sql_sum_only: bool = False,
) -> dict[date, int]:
    """与 ``total_meal_units_for_delivery_sheet`` 同源的对日映射；单会话 SQL SUM 串行计算。

    ``sql_sum_only=True``：同比基线等仅需整数份数时使用，锁单日也不触发 ``delivery_sheet_metrics``。
    """
    from app.core.tenant_scope import require_store_id_for_service

    sid = require_store_id_for_service(store_id, operation="配送大表对日份数")
    snap = snapshot_meal_totals or {}

    uniq: list[date] = []
    seen: set[date] = set()
    for d in dates:
        if d not in seen:
            seen.add(d)
            uniq.append(d)

    out: dict[date, int] = {}
    for d in uniq:
        if d in snap:
            out[d] = int(snap[d])
            continue
        if sql_sum_only:
            out[d] = total_meal_units_sql_sum_only(db, delivery_date=d, store_id=sid)
            continue
        out[d] = total_meal_units_for_delivery_sheet(
            db,
            delivery_date=d,
            store_id=sid,
            metrics_cache=metrics_cache,
        )
    return out


def _empty_sheet_member_stats() -> dict[str, int]:
    """配送页不展示顶栏会员统计时可跳过查库，字段仍保持响应结构。"""
    return {
        "total_members": 0,
        "active_weekly_members": 0,
        "expired_weekly_members": 0,
        "active_monthly_members": 0,
        "expired_monthly_members": 0,
        "active_dinner_members": 0,
    }


def _sheet_member_stats(db: Session, *, store_id: int, include: bool) -> dict[str, int]:
    if not include:
        return _empty_sheet_member_stats()
    return _store_membership_counts(db, store_id=store_id)


def build_delivery_sheet(
    db: Session,
    *,
    delivery_date: date | None = None,
    area: str | None = None,
    phone: str | None = None,
    store_id: int | None = None,
    sheet_view: str = DeliverySheetView.LUNCH.value,
    include_member_stats: bool = True,
) -> DeliverySheetOut:
    """
    配送大表。sheet_view：lunch（默认，与原 /delivery-sheet 一致）/ dinner / lunch_dinner。
    纯晚餐卡会员仅出现在 dinner 视图，不会出现在 lunch 视图。
    """
    view = (sheet_view or DeliverySheetView.LUNCH.value).strip().lower()
    if view == DeliverySheetView.DINNER.value:
        meal_period = MealPeriod.DINNER.value
    else:
        meal_period = MealPeriod.LUNCH.value

    from app.core.tenant_scope import require_store_id_for_service

    sid = require_store_id_for_service(store_id, operation="配送大表")
    st = db.get(Store, sid)
    if not st or not st.is_active:
        raise HTTPException(status_code=404, detail="门店不存在或已停用")
    tid = int(st.tenant_id)
    d = delivery_date or today_shanghai()
    sub_ok = is_subscription_delivery_day(d)
    active_region_list, known_ids = _active_regions_meta(db, tenant_id=tid)
    known_names = set(active_region_list)

    region_filter_id: int | None = None
    if area and (a := area.strip()):
        rid = db.scalar(
            select(DeliveryRegion.id).where(
                DeliveryRegion.name == a,
                DeliveryRegion.tenant_id == tid,
            )
        )
        if rid is None:
            return DeliverySheetOut(
                delivery_date=d.isoformat(),
                groups=[],
                active_regions=active_region_list,
                home_pending_meal_total=0,
                home_delivered_meal_total=0,
                pickup_meal_total=0,
                is_subscription_delivery_day=sub_ok,
                **_sheet_member_stats(db, store_id=sid, include=include_member_stats),
            )
        region_filter_id = int(rid)

    day_snap = DeliverySheetDaySnapshots.load(
        db, store_id=sid, delivery_date=d, meal_period=meal_period
    )
    day_delivered_ids = _store_delivered_member_ids_on_date(
        db, store_id=sid, delivery_date=d, meal_period=meal_period
    )
    if view == DeliverySheetView.DINNER.value:
        members, default_by_id = _home_members_for_dinner_delivery_sheet(
            db,
            delivery_date=d,
            delivery_region_id=region_filter_id,
            store_id=sid,
            day_snap=day_snap,
        )
    else:
        members, default_by_id = _home_members_for_delivery_sheet(
            db,
            delivery_date=d,
            delivery_region_id=region_filter_id,
            store_id=sid,
            day_snap=day_snap,
        )
    # 与到家列表一并拉取自提会员（晚餐视图不含自提）
    if view == DeliverySheetView.DINNER.value:
        pu_members, pu_defaults = [], {}
    else:
        pu_members, pu_defaults = eligible_members_for_store_pickup(db, delivery_date=d, store_id=sid)
        if view == DeliverySheetView.LUNCH.value:
            members, pu_members = filter_member_groups_for_sheet_view(
                db, DeliverySheetView.LUNCH.value, members, pu_members
            )
        elif view == DeliverySheetView.LUNCH_DINNER.value:
            members, pu_members = filter_member_groups_for_sheet_view(
                db, DeliverySheetView.LUNCH_DINNER.value, members, pu_members
            )
    ex_h, ex_dh, ex_pu, ex_pud = extra_delivered_ineligible_subscribers(
        db,
        delivery_date=d,
        already_home={int(m.id) for m in members},
        already_pickup={int(m.id) for m in pu_members},
        delivery_region_id=region_filter_id,
        store_id=sid,
        day_delivered_member_ids=day_delivered_ids,
    )
    for m in ex_h:
        members.append(m)
        default_by_id[m.id] = ex_dh.get(int(m.id))
    for m in ex_pu:
        pu_members.append(m)
        pu_defaults[m.id] = ex_pud.get(int(m.id))
    ph = (phone or "").strip()
    if ph:
        members = _filter_members_by_phone_hint(members, ph)
        pu_members = _filter_members_by_phone_hint(pu_members, ph)
    units_ctx = DeliverySheetMealUnitsContext.from_day_snapshots(day_snap, db=db)
    all_member_ids = {int(m.id) for m in members} | {int(m.id) for m in pu_members}
    delivered_set = day_delivered_ids & all_member_ids
    dinner_state_map: dict[int, object] = {}
    if meal_period == MealPeriod.DINNER.value and all_member_ids:
        from app.services.meal_period.units import load_dinner_meal_period_states_map

        dinner_state_map = load_dinner_meal_period_states_map(db, sorted(all_member_ids))
    from app.services.meal_period.balance import balance_quota_for_sheet_period

    region_ids: set[int] = set()
    for m in members:
        addr = default_by_id.get(m.id)
        if addr and addr.delivery_region_id is not None:
            region_ids.add(int(addr.delivery_region_id))
    id_to_name = delivery_region_name_map(db, region_ids)

    buckets: dict[str, dict[tuple[str, str], list[Member]]] = defaultdict(lambda: defaultdict(list))
    for m in members:
        addr = default_by_id.get(m.id)
        routing_area = routing_area_label(addr, id_to_name)
        resolved = _resolve_delivery_line(addr, id_to_name)
        key = (_normalize_address_key(resolved.area), _normalize_address_key(resolved.detail))
        buckets[routing_area][key].append(m)

    groups_out: list[DeliverySheetGroupOut] = []
    for area_name in sorted(buckets.keys()):
        stop_map = buckets[area_name]
        stops: list[DeliverySheetStopOut] = []
        for (_ka, _kd), ms in stop_map.items():
            # 同址多会员：未送达在上、已送达在下；同状态按手机号
            ms_sorted = sorted(
                ms,
                key=lambda x: (x.id in delivered_set, (x.phone or "")),
            )
            first = ms_sorted[0]
            resolved = _resolve_delivery_line(default_by_id.get(first.id), id_to_name)
            lines: list[DeliverySheetMemberOut] = []
            combined_parts: list[str] = []
            for mem in ms_sorted:
                addr = default_by_id.get(mem.id)
                rmk = _member_line_remarks(mem, addr)
                bal, quota = balance_quota_for_sheet_period(
                    mem,
                    meal_period=meal_period,
                    state_row=dinner_state_map.get(int(mem.id)),
                )
                mem_units = units_ctx.units_for(mem)
                lines.append(
                    DeliverySheetMemberOut(
                        member_id=int(mem.id),
                        phone=mem.phone,
                        name=mem.name,
                        plan_type=(mem.plan_type or "").strip() or None,
                        daily_meal_units=mem_units,
                        balance=bal,
                        meal_quota_total=quota,
                        remarks=rmk,
                        area_issue=_member_area_issue(addr, known_ids),
                        is_delivered=mem.id in delivered_set,
                    )
                )
                if rmk:
                    combined_parts.append(rmk)
            seen: set[str] = set()
            uniq_combined: list[str] = []
            for p in combined_parts:
                if p not in seen:
                    seen.add(p)
                    uniq_combined.append(p)
            stop_area_issue = (
                any(ln.area_issue for ln in lines)
                or _area_needs_attention(resolved.area, known_names)
                or _area_needs_attention(area_name, known_names)
            )
            stop_meals = sum(ln.daily_meal_units for ln in lines)
            stop_delivered = sum(ln.daily_meal_units for ln in lines if ln.is_delivered)
            stop_pending = stop_meals - stop_delivered
            stops.append(
                DeliverySheetStopOut(
                    meal_count=stop_meals,
                    pending_meal_count=stop_pending,
                    delivered_meal_count=stop_delivered,
                    address_line=resolved.address_line,
                    area=resolved.area,
                    members=lines,
                    remarks_combined="；".join(uniq_combined) if uniq_combined else None,
                    has_area_issue=stop_area_issue,
                )
            )
        # 配送点：仍有待送份数的点在上、已全部送达的在下；同档仍按地址稳定排序
        stops.sort(
            key=lambda s: (
                0 if (s.pending_meal_count or 0) > 0 else 1,
                s.address_line.casefold(),
                s.area.casefold(),
            )
        )
        meal_total = sum(s.meal_count for s in stops)
        group_pending = sum(s.pending_meal_count for s in stops)
        group_delivered = sum(s.delivered_meal_count for s in stops)
        group_issue = any(s.has_area_issue for s in stops) or _area_needs_attention(area_name, known_names)
        groups_out.append(
            DeliverySheetGroupOut(
                area=area_name,
                stops=stops,
                stop_count=len(stops),
                meal_total=meal_total,
                pending_meal_total=group_pending,
                delivered_meal_total=group_delivered,
                has_area_issue=group_issue,
            )
        )

    if pu_members:
        lines: list[DeliverySheetMemberOut] = []
        for mem in sorted(
            pu_members,
            key=lambda x: (x.id in delivered_set, (x.phone or "")),
        ):
            addr = pu_defaults.get(mem.id)
            rmk = _member_line_remarks(mem, addr)
            bal, quota = _member_balance_quota(mem)
            mem_units = units_ctx.units_for(mem)
            lines.append(
                DeliverySheetMemberOut(
                    member_id=int(mem.id),
                    phone=mem.phone,
                    name=mem.name,
                    plan_type=(mem.plan_type or "").strip() or None,
                    daily_meal_units=mem_units,
                    balance=bal,
                    meal_quota_total=quota,
                    remarks=rmk,
                    area_issue=False,
                    is_delivered=mem.id in delivered_set,
                )
            )
        pu_meal_total = sum(units_ctx.units_for(m) for m in pu_members)
        pu_delivered = sum(
            units_ctx.units_for(m) for m in pu_members if m.id in delivered_set
        )
        pu_pending = pu_meal_total - pu_delivered
        groups_out.append(
            DeliverySheetGroupOut(
                area="门店自提",
                stops=[
                    DeliverySheetStopOut(
                        meal_count=pu_meal_total,
                        pending_meal_count=pu_pending,
                        delivered_meal_count=pu_delivered,
                        address_line="门店自提（到店取餐）",
                        area="门店自提",
                        members=lines,
                        remarks_combined=None,
                        has_area_issue=False,
                    )
                ],
                stop_count=1,
                meal_total=pu_meal_total,
                pending_meal_total=pu_pending,
                delivered_meal_total=pu_delivered,
                has_area_issue=False,
            )
        )

    home_pending = sum(g.pending_meal_total for g in groups_out if g.area != "门店自提")
    home_delivered = sum(g.delivered_meal_total for g in groups_out if g.area != "门店自提")
    pickup_total = sum(g.meal_total for g in groups_out if g.area == "门店自提")

    return DeliverySheetOut(
        delivery_date=d.isoformat(),
        groups=groups_out,
        active_regions=active_region_list,
        home_pending_meal_total=home_pending,
        home_delivered_meal_total=home_delivered,
        pickup_meal_total=pickup_total,
        is_subscription_delivery_day=sub_ok,
        **_sheet_member_stats(db, store_id=sid, include=include_member_stats),
    )
