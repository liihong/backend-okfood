"""客服/管理端：配送资质咨询（仅依据启用配送片区多边形，与顺丰无关）。"""

from __future__ import annotations

import math

from sqlalchemy.orm import Session

from app.schemas.delivery_region import DeliveryRegionConsultIn, DeliveryRegionConsultOut
from app.services import amap
from app.services.member_address_service import check_coords_in_delivery_region
from app.services.store_config_service import get_store_config


def _haversine_km(lng1: float, lat1: float, lng2: float, lat2: float) -> float:
    """球面大圆距离（公里），GCJ-02 平面误差可接受，用于客服参考展示。"""
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1.0 - a)))
    return r * c


def consult_delivery_region(
    db: Session,
    *,
    tenant_id: int,
    store_id: int,
    body: DeliveryRegionConsultIn,
) -> DeliveryRegionConsultOut:
    """
    给定坐标优先；否则用关键词走服务端高德地理编码。
    判定坐标是否落入租户下任一**启用**配送片区（priority 次序命中首个）。
    """
    addr_kw = (body.address_keyword or "").strip()
    lng_lat: tuple[float, float] | None = None

    if body.location is not None:
        lng_lat = (float(body.location.lng), float(body.location.lat))
        label = addr_kw if addr_kw else "地图选点"
    elif addr_kw:
        coords = amap.geocode_address(addr_kw)
        if coords is None:
            return DeliveryRegionConsultOut(
                coords_resolved=False,
                lng=None,
                lat=None,
                geocode_failed=True,
                in_region=False,
                delivery_region_id=None,
                region_name=None,
                distance_to_store_km=None,
                query_label=addr_kw,
                message="高德地理编码无结果或未配置服务端 AMAP_KEY，请让客户在地图上精确选点后重试。",
            )
        lng_lat = (float(coords[0]), float(coords[1]))
        label = addr_kw
    else:
        # Pydantic 已挡；兜底
        return DeliveryRegionConsultOut(
            coords_resolved=False,
            geocode_failed=False,
            in_region=False,
            delivery_region_id=None,
            region_name=None,
            distance_to_store_km=None,
            query_label=None,
            message="请提供地址关键词或地图坐标。",
        )

    lng, lat = lng_lat
    in_region, rid, rname = check_coords_in_delivery_region(db, lng, lat, tenant_id=int(tenant_id))

    dist_km: float | None = None
    sc = get_store_config(db, store_id=int(store_id))
    if sc.store_lng is not None and sc.store_lat is not None:
        dist_km = round(_haversine_km(lng, lat, float(sc.store_lng), float(sc.store_lat)), 1)

    return DeliveryRegionConsultOut(
        coords_resolved=True,
        lng=lng,
        lat=lat,
        geocode_failed=False,
        in_region=in_region,
        delivery_region_id=rid,
        region_name=rname,
        distance_to_store_km=dist_km,
        query_label=label,
        message=None,
    )
