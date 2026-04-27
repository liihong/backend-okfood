"""营业概览：配送区域地图所需的一次性聚合数据（区域多边形 + 有余额会员坐标）。"""

from __future__ import annotations

from sqlalchemy import func, select

from sqlalchemy.orm import Session

from app.core.timeutil import today_shanghai, tomorrow_shanghai
from app.models.delivery_log import DeliveryLog
from app.models.enums import DeliveryStatus
from app.models.member import Member
from app.models.member_address import MemberAddress
from app.models.single_meal_order import SingleMealOrder
from app.schemas.delivery_region import (
    DeliveryRegionMapOverviewOut,
    MapOverviewMemberMarkerOut,
    StoreMapAnchorOut,
)
from app.services.store_config_service import get_store_config
from app.services.delivery_region_service import list_delivery_regions
from app.services.member_address_service import delivery_region_name_map, routing_area_label
from app.services.leave import is_absent_on_delivery_date


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

    mids = [int(m.id) for m, _addr in rows]
    biz_today = today_shanghai()
    biz_tomorrow = tomorrow_shanghai()
    delivered_today_ids: set[int] = set()
    if mids:
        # 订阅配送：骑手确认送达写入 delivery_logs
        delivered_today_ids = set(
            db.scalars(
                select(DeliveryLog.member_id).where(
                    DeliveryLog.delivery_date == biz_today,
                    DeliveryLog.status == DeliveryStatus.DELIVERED.value,
                    DeliveryLog.member_id.in_(mids),
                )
            ).all()
        )
        # 单次点餐：仅更新 single_meal_orders，无 delivery_logs，需一并统计否则地图仍为黄色
        single_delivered = set(
            db.scalars(
                select(SingleMealOrder.member_id).where(
                    SingleMealOrder.member_id.in_(mids),
                    SingleMealOrder.delivery_date == biz_today,
                    SingleMealOrder.pay_status == "已支付",
                    SingleMealOrder.fulfillment_status == "delivered",
                )
            ).all()
        )
        delivered_today_ids |= single_delivered

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
                delivered_today=int(m.id) in delivered_today_ids,
                delivery_deferred=bool(m.delivery_deferred),
                absent_today=is_absent_on_delivery_date(m, biz_today, today=biz_today),
                absent_tomorrow=is_absent_on_delivery_date(m, biz_tomorrow, today=biz_today),
            )
        )

    sc = get_store_config(db)
    store_anchor = StoreMapAnchorOut(
        store_name=sc.store_name,
        store_logo_url=sc.store_logo_url,
        store_lng=sc.store_lng,
        store_lat=sc.store_lat,
    )
    return DeliveryRegionMapOverviewOut(regions=regions, members=markers, store=store_anchor)
