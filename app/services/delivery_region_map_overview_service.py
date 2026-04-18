"""营业概览：配送区域地图所需的一次性聚合数据（区域多边形 + 有余额会员坐标）。"""

from __future__ import annotations

from sqlalchemy import func, select

from sqlalchemy.orm import Session

from app.models.member import Member
from app.models.member_address import MemberAddress
from app.schemas.delivery_region import DeliveryRegionMapOverviewOut, MapOverviewMemberMarkerOut
from app.services.delivery_region_service import list_delivery_regions
from app.services.member_address_service import delivery_region_name_map, routing_area_label


def delivery_region_map_overview(db: Session) -> DeliveryRegionMapOverviewOut:
    """有余额会员（与列表 active 口径一致）及其默认地址上的坐标与展示片区。"""
    regions = list_delivery_regions(db, include_polygon=True)

    default_addr_pick = (
        select(
            MemberAddress.member_id.label("mid"),
            func.max(MemberAddress.id).label("addr_id"),
        )
        .where(MemberAddress.is_default.is_(True))
        .group_by(MemberAddress.member_id)
    ).subquery("def_addr_ov")

    stmt = (
        select(Member, MemberAddress)
        .select_from(Member)
        .join(default_addr_pick, default_addr_pick.c.mid == Member.id)
        .join(MemberAddress, MemberAddress.id == default_addr_pick.c.addr_id)
        .where(Member.balance > 0)
        .order_by(Member.id.asc())
    )
    rows = db.execute(stmt).all()

    region_ids: set[int] = set()
    for _m, addr in rows:
        if addr.delivery_region_id is not None:
            region_ids.add(int(addr.delivery_region_id))
    id_to_name = delivery_region_name_map(db, region_ids)

    markers: list[MapOverviewMemberMarkerOut] = []
    for m, addr in rows:
        lng = float(addr.lng) if addr.lng is not None else None
        lat = float(addr.lat) if addr.lat is not None else None
        ar = routing_area_label(addr, id_to_name)
        markers.append(
            MapOverviewMemberMarkerOut(
                id=int(m.id),
                name=m.name or "",
                phone=m.phone,
                area=ar,
                lng=lng,
                lat=lat,
            )
        )

    return DeliveryRegionMapOverviewOut(regions=regions, members=markers)
