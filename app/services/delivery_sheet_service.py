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
from app.services.courier_service import eligible_members_for_delivery
from app.services.member_address_service import effective_routing_area, load_default_address_map


def _normalize_address_key(s: str) -> str:
    return " ".join(s.strip().split()).casefold()


@dataclass(frozen=True)
class _ResolvedStopLine:
    area: str
    detail: str
    address_line: str


def _resolve_delivery_line(addr: MemberAddress | None) -> _ResolvedStopLine:
    """仅使用默认配送地址；members 表地址字段已废弃。"""
    if addr:
        area = (addr.area or "").strip() or UNASSIGNED_DELIVERY_AREA
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


def _active_region_names_ordered(db: Session) -> list[str]:
    rows = db.scalars(
        select(DeliveryRegion.name)
        .where(DeliveryRegion.is_active.is_(True))
        .order_by(DeliveryRegion.priority.asc(), DeliveryRegion.id.asc())
    ).all()
    return [str(n).strip() for n in rows if n and str(n).strip()]


def _known_active_region_set(names: list[str]) -> set[str]:
    return set(names)


def _area_needs_attention(label: str | None, known_active: set[str]) -> bool:
    """空、未分配，或在已有启用区域配置时不在目录内。"""
    a = (label or "").strip()
    if not a:
        return True
    if a == UNASSIGNED_DELIVERY_AREA:
        return True
    if known_active and a not in known_active:
        return True
    return False


def _member_area_issue(addr: MemberAddress | None, known: set[str]) -> bool:
    if addr is None:
        return True
    return _area_needs_attention(addr.area, known)


def build_delivery_sheet(
    db: Session,
    *,
    delivery_date: date | None = None,
    area: str | None = None,
) -> DeliverySheetOut:
    d = delivery_date or today_shanghai()
    active_region_list = _active_region_names_ordered(db)
    known = _known_active_region_set(active_region_list)
    members = eligible_members_for_delivery(db, delivery_date=d, area=area)
    default_by_id = load_default_address_map(db, [m.id for m in members])

    # 分组：片区 = 默认地址 effective_routing_area；配送点 = 规范化 (展示 area, detail)
    buckets: dict[str, dict[tuple[str, str], list[Member]]] = defaultdict(lambda: defaultdict(list))
    for m in members:
        addr = default_by_id.get(m.id)
        routing_area = effective_routing_area(addr)
        resolved = _resolve_delivery_line(addr)
        key = (_normalize_address_key(resolved.area), _normalize_address_key(resolved.detail))
        buckets[routing_area][key].append(m)

    groups_out: list[DeliverySheetGroupOut] = []
    for area_name in sorted(buckets.keys()):
        stop_map = buckets[area_name]
        stops: list[DeliverySheetStopOut] = []
        for (_ka, _kd), ms in stop_map.items():
            ms_sorted = sorted(ms, key=lambda x: x.phone)
            first = ms_sorted[0]
            resolved = _resolve_delivery_line(default_by_id.get(first.id))
            lines: list[DeliverySheetMemberOut] = []
            combined_parts: list[str] = []
            for mem in ms_sorted:
                addr = default_by_id.get(mem.id)
                rmk = _member_line_remarks(mem, addr)
                lines.append(
                    DeliverySheetMemberOut(
                        phone=mem.phone,
                        name=mem.name,
                        remarks=rmk,
                        area_issue=_member_area_issue(addr, known),
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
                or _area_needs_attention(resolved.area, known)
                or _area_needs_attention(area_name, known)
            )
            stops.append(
                DeliverySheetStopOut(
                    meal_count=len(ms_sorted),
                    address_line=resolved.address_line,
                    area=resolved.area,
                    members=lines,
                    remarks_combined="；".join(uniq_combined) if uniq_combined else None,
                    has_area_issue=stop_area_issue,
                )
            )
        stops.sort(key=lambda s: (s.address_line.casefold(), s.area.casefold()))
        meal_total = sum(s.meal_count for s in stops)
        group_issue = any(s.has_area_issue for s in stops) or _area_needs_attention(area_name, known)
        groups_out.append(
            DeliverySheetGroupOut(
                area=area_name,
                stops=stops,
                stop_count=len(stops),
                meal_total=meal_total,
                has_area_issue=group_issue,
            )
        )

    return DeliverySheetOut(
        delivery_date=d.isoformat(),
        groups=groups_out,
        active_regions=active_region_list,
    )
