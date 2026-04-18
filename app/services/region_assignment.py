import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.constants import UNASSIGNED_DELIVERY_AREA
from app.models.delivery_region import DeliveryRegion
from app.services.region_geo import extract_outer_ring, point_in_polygon

logger = logging.getLogger(__name__)


def assign_region_for_coords(db: Session, lng: float, lat: float) -> DeliveryRegion | None:
    """按启用区域的 priority 顺序做点选，返回首个命中的区域行；否则 None（未分配）。"""
    stmt = (
        select(DeliveryRegion)
        .where(DeliveryRegion.is_active.is_(True))
        .order_by(DeliveryRegion.priority.asc(), DeliveryRegion.id.asc())
    )
    regions = db.scalars(stmt).all()
    for r in regions:
        try:
            ring = extract_outer_ring(r.polygon_json)
            if point_in_polygon(lng, lat, ring):
                return r
        except (ValueError, TypeError, KeyError) as e:
            logger.warning(
                "配送区域 polygon 无效，已跳过点选: id=%s name=%s err=%s",
                r.id,
                r.name,
                e,
            )
            continue
    return None


def assign_area_name_for_coords(db: Session, lng: float, lat: float) -> str:
    """兼容：返回首个命中区域名，否则「未分配」。"""
    r = assign_region_for_coords(db, lng, lat)
    if r is None:
        return UNASSIGNED_DELIVERY_AREA
    n = (r.name or "").strip()
    return n if n else UNASSIGNED_DELIVERY_AREA
