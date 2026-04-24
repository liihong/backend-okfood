"""管理端配送大表：按请假规则筛选会员，默认收件地址聚合为配送点。"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.constants import UNASSIGNED_DELIVERY_AREA
from app.core.timeutil import today_shanghai
from app.models.delivery_region import DeliveryRegion
from app.models.member import Member
from app.models.member_address import MemberAddress
from app.schemas.admin import DeliverySheetGroupOut, DeliverySheetMemberOut, DeliverySheetOut, DeliverySheetStopOut
from app.services.courier_service import eligible_members_for_delivery, eligible_members_for_store_pickup
from app.services.member_address_service import delivery_region_name_map, routing_area_label
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
        detail = (addr.detail_address or "").strip()
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


def _active_regions_meta(db: Session) -> tuple[list[str], set[int]]:
    """启用片区：一次查询同时得到排序后的名称列表与 id 集合（减少高延迟库上的往返）。"""
    rows = db.execute(
        select(DeliveryRegion.id, DeliveryRegion.name)
        .where(DeliveryRegion.is_active.is_(True))
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


def build_delivery_sheet(
    db: Session,
    *,
    delivery_date: date | None = None,
    area: str | None = None,
) -> DeliverySheetOut:
    d = delivery_date or today_shanghai()
    active_region_list, known_ids = _active_regions_meta(db)
    known_names = set(active_region_list)

    region_filter_id: int | None = None
    if area and (a := area.strip()):
        rid = db.scalar(select(DeliveryRegion.id).where(DeliveryRegion.name == a))
        if rid is None:
            return DeliverySheetOut(
                delivery_date=d.isoformat(),
                groups=[],
                active_regions=active_region_list,
            )
        region_filter_id = int(rid)

    members, default_by_id = eligible_members_for_delivery(
        db, delivery_date=d, delivery_region_id=region_filter_id
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
            ms_sorted = sorted(ms, key=lambda x: x.phone)
            first = ms_sorted[0]
            resolved = _resolve_delivery_line(default_by_id.get(first.id), id_to_name)
            lines: list[DeliverySheetMemberOut] = []
            combined_parts: list[str] = []
            for mem in ms_sorted:
                addr = default_by_id.get(mem.id)
                rmk = _member_line_remarks(mem, addr)
                lines.append(
                    DeliverySheetMemberOut(
                        phone=mem.phone,
                        name=mem.name,
                        daily_meal_units=effective_daily_meal_units(mem),
                        remarks=rmk,
                        area_issue=_member_area_issue(addr, known_ids),
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
            stops.append(
                DeliverySheetStopOut(
                    meal_count=stop_meals,
                    address_line=resolved.address_line,
                    area=resolved.area,
                    members=lines,
                    remarks_combined="；".join(uniq_combined) if uniq_combined else None,
                    has_area_issue=stop_area_issue,
                )
            )
        stops.sort(key=lambda s: (s.address_line.casefold(), s.area.casefold()))
        meal_total = sum(s.meal_count for s in stops)
        group_issue = any(s.has_area_issue for s in stops) or _area_needs_attention(area_name, known_names)
        groups_out.append(
            DeliverySheetGroupOut(
                area=area_name,
                stops=stops,
                stop_count=len(stops),
                meal_total=meal_total,
                has_area_issue=group_issue,
            )
        )

    pu_members, pu_defaults = eligible_members_for_store_pickup(db, delivery_date=d)
    if pu_members:
        lines: list[DeliverySheetMemberOut] = []
        for mem in sorted(pu_members, key=lambda x: x.phone):
            addr = pu_defaults.get(mem.id)
            rmk = _member_line_remarks(mem, addr)
            lines.append(
                DeliverySheetMemberOut(
                    phone=mem.phone,
                    name=mem.name,
                    daily_meal_units=effective_daily_meal_units(mem),
                    remarks=rmk,
                    area_issue=False,
                )
            )
        pu_meal_total = sum(effective_daily_meal_units(m) for m in pu_members)
        groups_out.append(
            DeliverySheetGroupOut(
                area="门店自提",
                stops=[
                    DeliverySheetStopOut(
                        meal_count=pu_meal_total,
                        address_line="门店自提（到店取餐）",
                        area="门店自提",
                        members=lines,
                        remarks_combined=None,
                        has_area_issue=False,
                    )
                ],
                stop_count=1,
                meal_total=pu_meal_total,
                has_area_issue=False,
            )
        )

    return DeliverySheetOut(
        delivery_date=d.isoformat(),
        groups=groups_out,
        active_regions=active_region_list,
    )
