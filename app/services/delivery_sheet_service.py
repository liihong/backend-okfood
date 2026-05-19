"""管理端配送大表：按请假规则筛选会员，默认收件地址聚合为配送点。

送达状态：配送到家会员与 ``delivery_logs``（DELIVERED、业务日）对齐，与骑手端任务列表一致；
门店自提仅备餐归组，份数不计入「到家已/未送达」汇总。
扣次后无剩余、不再满足应送 SQL 的会员，若当日已有已送达记录，仍并入本大表，避免从当日统计中消失。
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date

from fastapi import HTTPException
from sqlalchemy import and_, case, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.constants import UNASSIGNED_DELIVERY_AREA
from app.core.config import get_settings
from app.core.delivery_calendar import is_subscription_delivery_day
from app.core.timeutil import today_shanghai
from app.models.delivery_log import DeliveryLog
from app.models.delivery_region import DeliveryRegion
from app.models.enums import DeliveryStatus
from app.models.member import Member
from app.models.member_address import MemberAddress
from app.models.store import Store
from app.schemas.admin import DeliverySheetGroupOut, DeliverySheetMemberOut, DeliverySheetOut, DeliverySheetStopOut
from app.services.courier_service import (
    eligible_members_for_delivery,
    eligible_members_for_store_pickup,
    extra_delivered_ineligible_subscribers,
)
from app.services.member_address_service import delivery_region_name_map, full_address_line, routing_area_label
from app.services.member_service import effective_daily_meal_units


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


def _member_ids_delivered_on_date(db: Session, delivery_date: date, member_ids: list[int]) -> set[int]:
    """查询当日已在 ``delivery_logs`` 标记为送达的会员 id（与 ``courier_service.list_today_tasks`` 同一条件）。"""
    if not member_ids:
        return set()
    rows = db.scalars(
        select(DeliveryLog.member_id).where(
            DeliveryLog.delivery_date == delivery_date,
            DeliveryLog.status == DeliveryStatus.DELIVERED.value,
            DeliveryLog.member_id.in_(member_ids),
        )
    ).all()
    return {int(x) for x in rows}


def _store_membership_counts(db: Session, *, store_id: int) -> dict[str, int]:
    """与会员列表 ``validity=active|expired`` 一致：仅按 balance；按 ``plan_type`` 拆周卡/月卡。"""
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
        .where(Member.deleted_at.is_(None), Member.store_id == int(store_id))
    ).one()
    return {
        "total_members": int(row.total or 0),
        "active_weekly_members": int(row.wa or 0),
        "expired_weekly_members": int(row.we or 0),
        "active_monthly_members": int(row.ma or 0),
        "expired_monthly_members": int(row.me or 0),
    }


def total_meal_units_for_delivery_sheet(
    db: Session, *, delivery_date: date, store_id: int | None = None
) -> int:
    """与 ``build_delivery_sheet`` 各分组 ``meal_total`` 之和一致（到家+自提，含已送后不再应送仍并入大表者）。

    不构建停靠点分组与 Pydantic 结构，仅复用同源会员名单做一次份数聚合，供仪表盘等大表同源统计。
    """
    if not is_subscription_delivery_day(delivery_date):
        return 0
    cfg = get_settings()
    sid = int(store_id) if store_id is not None else int(cfg.DEFAULT_STORE_ID)
    members, _default_home = eligible_members_for_delivery(
        db, delivery_date=delivery_date, delivery_region_id=None, store_id=sid
    )
    pu_members, _pu_defaults = eligible_members_for_store_pickup(db, delivery_date=delivery_date, store_id=sid)
    already_home = {int(m.id) for m in members}
    already_pickup = {int(m.id) for m in pu_members}
    ex_h, _ex_dh, ex_pu, _ex_pud = extra_delivered_ineligible_subscribers(
        db,
        delivery_date=delivery_date,
        already_home=already_home,
        already_pickup=already_pickup,
        delivery_region_id=None,
        store_id=sid,
    )
    members.extend(ex_h)
    pu_members.extend(ex_pu)
    total = 0
    for m in members:
        total += effective_daily_meal_units(m)
    for m in pu_members:
        total += effective_daily_meal_units(m)
    return int(total)


def meal_units_totals_for_delivery_dates(
    db: Session,
    *,
    dates: Iterable[date],
    store_id: int | None = None,
) -> dict[date, int]:
    """与 ``total_meal_units_for_delivery_sheet`` 同源的对日映射；可多日一次拉齐。

    非 SQLite 且多日均为订阅配送日时，独占会话并行查库以降低 dashboard 等场景的串行延迟。
    """
    cfg = get_settings()
    sid = int(store_id) if store_id is not None else int(cfg.DEFAULT_STORE_ID)

    uniq: list[date] = []
    seen: set[date] = set()
    for d in dates:
        if d not in seen:
            seen.add(d)
            uniq.append(d)

    out: dict[date, int] = {}
    todo: list[date] = []
    for d in uniq:
        if not is_subscription_delivery_day(d):
            out[d] = 0
        else:
            todo.append(d)

    if not todo:
        return out

    bind = db.get_bind()
    use_threads = bind.dialect.name != "sqlite" and len(todo) > 1
    if not use_threads:
        for d in todo:
            out[d] = total_meal_units_for_delivery_sheet(db, delivery_date=d, store_id=sid)
        return out

    mk = sessionmaker(bind=bind, autoflush=False, autocommit=False, expire_on_commit=False)

    def _compute_one(delivery_d: date) -> tuple[date, int]:
        sess = mk()
        try:
            val = total_meal_units_for_delivery_sheet(sess, delivery_date=delivery_d, store_id=sid)
            return delivery_d, val
        finally:
            sess.close()

    max_workers = min(4, len(todo))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(_compute_one, d) for d in todo]
        for fut in as_completed(futures):
            d_key, val = fut.result()
            out[d_key] = val

    return out


def build_delivery_sheet(
    db: Session,
    *,
    delivery_date: date | None = None,
    area: str | None = None,
    phone: str | None = None,
    store_id: int | None = None,
) -> DeliverySheetOut:
    cfg = get_settings()
    sid = int(store_id) if store_id is not None else int(cfg.DEFAULT_STORE_ID)
    st = db.get(Store, sid)
    if not st or not st.is_active:
        raise HTTPException(status_code=404, detail="门店不存在或已停用")
    tid = int(st.tenant_id)
    mem_stats = _store_membership_counts(db, store_id=sid)
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
                **mem_stats,
            )
        region_filter_id = int(rid)

    members, default_by_id = eligible_members_for_delivery(
        db, delivery_date=d, delivery_region_id=region_filter_id, store_id=sid
    )
    # 与到家列表一并拉取自提会员，便于单次查询 delivery_logs（片区筛选不改变自提分组是否出现）
    pu_members, pu_defaults = eligible_members_for_store_pickup(db, delivery_date=d, store_id=sid)
    ex_h, ex_dh, ex_pu, ex_pud = extra_delivered_ineligible_subscribers(
        db,
        delivery_date=d,
        already_home={int(m.id) for m in members},
        already_pickup={int(m.id) for m in pu_members},
        delivery_region_id=region_filter_id,
        store_id=sid,
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
    delivered_set = _member_ids_delivered_on_date(
        db, d, [m.id for m in members] + [m.id for m in pu_members]
    )

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
                lines.append(
                    DeliverySheetMemberOut(
                        member_id=int(mem.id),
                        phone=mem.phone,
                        name=mem.name,
                        daily_meal_units=effective_daily_meal_units(mem),
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
            stop_meals = sum(effective_daily_meal_units(mem) for mem in ms_sorted)
            stop_delivered = sum(
                effective_daily_meal_units(mem) for mem in ms_sorted if mem.id in delivered_set
            )
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
            lines.append(
                DeliverySheetMemberOut(
                    member_id=int(mem.id),
                    phone=mem.phone,
                    name=mem.name,
                    daily_meal_units=effective_daily_meal_units(mem),
                    remarks=rmk,
                    area_issue=False,
                    is_delivered=mem.id in delivered_set,
                )
            )
        pu_meal_total = sum(effective_daily_meal_units(m) for m in pu_members)
        pu_delivered = sum(
            effective_daily_meal_units(m) for m in pu_members if m.id in delivered_set
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
        **mem_stats,
    )
