from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.courier import Courier
from app.models.delivery_region import DeliveryRegion, DeliveryRegionCourier
from app.schemas.admin_courier import CourierAdminOut, CourierCreateIn, CourierRegionOut, CourierUpdateIn


def _regions_by_courier(db: Session) -> dict[str, list[CourierRegionOut]]:
    stmt = (
        select(DeliveryRegionCourier.courier_id, DeliveryRegion.id, DeliveryRegion.name, DeliveryRegionCourier.is_primary)
        .join(DeliveryRegion, DeliveryRegionCourier.region_id == DeliveryRegion.id)
        .order_by(DeliveryRegion.name.asc())
    )
    rows = db.execute(stmt).all()
    m: dict[str, list[CourierRegionOut]] = defaultdict(list)
    for courier_id, rid, rname, is_primary in rows:
        m[courier_id].append(
            CourierRegionOut(region_id=int(rid), name=rname, is_primary=bool(is_primary)),
        )
    return m


def regions_for_courier(db: Session, courier_id: str) -> list[CourierRegionOut]:
    stmt = (
        select(DeliveryRegion.id, DeliveryRegion.name, DeliveryRegionCourier.is_primary)
        .join(DeliveryRegionCourier, DeliveryRegionCourier.region_id == DeliveryRegion.id)
        .where(DeliveryRegionCourier.courier_id == courier_id)
        .order_by(DeliveryRegion.name.asc())
    )
    return [
        CourierRegionOut(region_id=int(rid), name=n, is_primary=bool(ip))
        for rid, n, ip in db.execute(stmt).all()
    ]


def _to_out(c: Courier, regions: list[CourierRegionOut]) -> CourierAdminOut:
    return CourierAdminOut(
        courier_id=c.courier_id,
        name=c.name,
        phone=c.phone,
        is_active=c.is_active,
        fee_pending=c.fee_pending if c.fee_pending is not None else Decimal("0.00"),
        fee_settled=c.fee_settled if c.fee_settled is not None else Decimal("0.00"),
        regions=regions,
    )


def list_couriers_admin(db: Session) -> list[CourierAdminOut]:
    region_map = _regions_by_courier(db)
    couriers = db.scalars(select(Courier).order_by(Courier.courier_id.asc())).all()
    return [_to_out(c, region_map.get(c.courier_id, [])) for c in couriers]


def create_courier_admin(db: Session, body: CourierCreateIn) -> CourierAdminOut:
    cid = body.courier_id.strip()
    if not cid:
        raise HTTPException(status_code=400, detail="工号无效")
    if db.get(Courier, cid):
        raise HTTPException(status_code=400, detail="工号已存在")
    phone = body.phone.strip() if body.phone and body.phone.strip() else None
    name = body.name.strip() if body.name and body.name.strip() else None
    c = Courier(
        courier_id=cid,
        name=name,
        phone=phone,
        pin_hash=hash_password(body.pin),
        is_active=body.is_active,
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return _to_out(c, [])


def update_courier_admin(db: Session, courier_id: str, body: CourierUpdateIn) -> CourierAdminOut:
    c = db.get(Courier, courier_id)
    if not c:
        raise HTTPException(status_code=404, detail="配送员不存在")
    if body.name is not None:
        c.name = body.name.strip() if body.name.strip() else None
    if body.phone is not None:
        c.phone = body.phone.strip() if body.phone.strip() else None
    if body.is_active is not None:
        c.is_active = body.is_active
    if body.fee_pending is not None:
        c.fee_pending = body.fee_pending
    if body.fee_settled is not None:
        c.fee_settled = body.fee_settled
    db.commit()
    db.refresh(c)
    return _to_out(c, regions_for_courier(db, courier_id))


def reset_courier_pin(db: Session, courier_id: str, pin_plain: str) -> None:
    c = db.get(Courier, courier_id)
    if not c:
        raise HTTPException(status_code=404, detail="配送员不存在")
    c.pin_hash = hash_password(pin_plain)
    db.commit()
