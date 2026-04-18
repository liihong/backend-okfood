from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, defer, selectinload

from app.models.courier import Courier
from app.models.delivery_region import DeliveryRegion, DeliveryRegionCourier
from app.schemas.delivery_region import (
    DeliveryRegionCreateIn,
    DeliveryRegionOut,
    DeliveryRegionSummaryOut,
    DeliveryRegionUpdateIn,
    RegionCourierOut,
)


def _validate_courier_list(db: Session, couriers: list) -> None:
    primary_count = sum(1 for c in couriers if c.is_primary)
    if primary_count > 1:
        raise HTTPException(status_code=400, detail="每个配送区域至多指定一名主责配送员")
    seen: set[str] = set()
    for c in couriers:
        if c.courier_id in seen:
            raise HTTPException(status_code=400, detail=f"配送员 {c.courier_id} 重复")
        seen.add(c.courier_id)
        row = db.get(Courier, c.courier_id)
        if not row:
            raise HTTPException(status_code=400, detail=f"配送员不存在: {c.courier_id}")


def _couriers_from_region(r: DeliveryRegion) -> list[RegionCourierOut]:
    couriers_out: list[RegionCourierOut] = []
    for link in sorted(r.courier_links, key=lambda x: (x.sort_order, x.id)):
        nm = link.courier.name if link.courier else None
        couriers_out.append(
            RegionCourierOut(
                courier_id=link.courier_id,
                name=nm,
                is_primary=link.is_primary,
                sort_order=link.sort_order,
            )
        )
    return couriers_out


def _to_region_summary(r: DeliveryRegion) -> DeliveryRegionSummaryOut:
    return DeliveryRegionSummaryOut(
        id=int(r.id),
        name=r.name,
        code=r.code,
        priority=r.priority,
        is_active=r.is_active,
        couriers=_couriers_from_region(r),
    )


def _to_region_out(r: DeliveryRegion) -> DeliveryRegionOut:
    return DeliveryRegionOut(**_to_region_summary(r).model_dump(), polygon_json=r.polygon_json)


def list_delivery_regions(db: Session, *, include_polygon: bool = False) -> list[DeliveryRegionSummaryOut] | list[DeliveryRegionOut]:
    load_opts: list = [
        selectinload(DeliveryRegion.courier_links).selectinload(DeliveryRegionCourier.courier),
    ]
    if not include_polygon:
        load_opts.insert(0, defer(DeliveryRegion.polygon_json))
    stmt = (
        select(DeliveryRegion)
        .options(*load_opts)
        .order_by(DeliveryRegion.priority.asc(), DeliveryRegion.id.asc())
    )
    rows = db.scalars(stmt).all()
    if include_polygon:
        return [_to_region_out(r) for r in rows]
    return [_to_region_summary(r) for r in rows]


def get_delivery_region(db: Session, region_id: int) -> DeliveryRegionOut:
    stmt = (
        select(DeliveryRegion)
        .options(selectinload(DeliveryRegion.courier_links).selectinload(DeliveryRegionCourier.courier))
        .where(DeliveryRegion.id == region_id)
    )
    r = db.scalars(stmt).first()
    if not r:
        raise HTTPException(status_code=404, detail="配送区域不存在")
    return _to_region_out(r)


def create_delivery_region(db: Session, body: DeliveryRegionCreateIn) -> DeliveryRegionOut:
    _validate_courier_list(db, body.couriers)
    r = DeliveryRegion(
        name=body.name.strip(),
        code=body.code.strip() if body.code else None,
        polygon_json=body.polygon_json,
        priority=body.priority,
        is_active=body.is_active,
    )
    db.add(r)
    db.flush()
    for c in body.couriers:
        db.add(
            DeliveryRegionCourier(
                region_id=r.id,
                courier_id=c.courier_id.strip(),
                is_primary=c.is_primary,
                sort_order=c.sort_order,
            )
        )
    db.commit()
    db.refresh(r)
    return get_delivery_region(db, int(r.id))


def update_delivery_region(db: Session, region_id: int, body: DeliveryRegionUpdateIn) -> DeliveryRegionOut:
    r = db.get(DeliveryRegion, region_id)
    if not r:
        raise HTTPException(status_code=404, detail="配送区域不存在")
    if body.couriers is not None:
        _validate_courier_list(db, body.couriers)
    if body.name is not None:
        r.name = body.name.strip()
    if body.code is not None:
        r.code = body.code.strip() if body.code else None
    if body.polygon_json is not None:
        r.polygon_json = body.polygon_json
    if body.priority is not None:
        r.priority = body.priority
    if body.is_active is not None:
        r.is_active = body.is_active
    if body.couriers is not None:
        for link in list(r.courier_links):
            db.delete(link)
        db.flush()
        for c in body.couriers:
            db.add(
                DeliveryRegionCourier(
                    region_id=r.id,
                    courier_id=c.courier_id.strip(),
                    is_primary=c.is_primary,
                    sort_order=c.sort_order,
                )
            )
    db.commit()
    return get_delivery_region(db, region_id)


def delete_delivery_region(db: Session, region_id: int) -> None:
    r = db.get(DeliveryRegion, region_id)
    if not r:
        raise HTTPException(status_code=404, detail="配送区域不存在")
    db.delete(r)
    db.commit()
