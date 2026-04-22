from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.constants import UNASSIGNED_DELIVERY_AREA
from app.models.delivery_region import DeliveryRegion
from app.models.member import Member
from app.models.member_address import MemberAddress
from app.schemas.member_address import MemberAddressCreateIn, MemberAddressOut, MemberAddressUpdateIn
from app.schemas.user import Location
from app.services import amap
from app.services.region_assignment import assign_region_for_coords

_MAX_ADDRESSES_PER_MEMBER = 20


def default_address_pick_subquery():
    """每人一条默认地址：若存在多条 is_default，取 id 最大者（与管理端会员列表一致）。"""
    return (
        select(
            MemberAddress.member_id.label("mid"),
            func.max(MemberAddress.id).label("addr_id"),
        )
        .where(MemberAddress.is_default.is_(True))
        .group_by(MemberAddress.member_id)
    ).subquery("daf")


def get_default_address(db: Session, member_id: int) -> MemberAddress | None:
    return db.scalars(
        select(MemberAddress).where(
            MemberAddress.member_id == member_id,
            MemberAddress.is_default.is_(True),
        )
    ).first()


def load_default_address_map(db: Session, member_ids: list[int]) -> dict[int, MemberAddress | None]:
    """按会员 id 批量取默认配送地址；无默认地址时值为 None。"""
    if not member_ids:
        return {}
    uniq = list(dict.fromkeys(member_ids))
    daf = default_address_pick_subquery()
    rows = db.scalars(
        select(MemberAddress).join(daf, MemberAddress.id == daf.c.addr_id).where(daf.c.mid.in_(uniq))
    ).all()
    by_mid: dict[int, MemberAddress] = {int(r.member_id): r for r in rows}
    return {mid: by_mid.get(mid) for mid in uniq}


def delivery_region_name_map(db: Session, ids: set[int]) -> dict[int, str]:
    if not ids:
        return {}
    rows = db.execute(select(DeliveryRegion.id, DeliveryRegion.name).where(DeliveryRegion.id.in_(ids))).all()
    out: dict[int, str] = {}
    for rid, name in rows:
        n = (name or "").strip()
        out[int(rid)] = n if n else UNASSIGNED_DELIVERY_AREA
    return out


def routing_area_label(addr: MemberAddress | None, id_to_name: dict[int, str]) -> str:
    """展示用片区名：仅依赖 delivery_region_id 与名称映射。"""
    if addr is None or addr.delivery_region_id is None:
        return UNASSIGNED_DELIVERY_AREA
    return id_to_name.get(int(addr.delivery_region_id)) or UNASSIGNED_DELIVERY_AREA


def upsert_default_address_after_register(
    db: Session,
    *,
    member_id: int,
    contact_name: str,
    contact_phone: str,
    detail_address: str,
    remarks: str | None,
    delivery_region_id: int | None,
    lng: float | None,
    lat: float | None,
) -> None:
    """登记/更新会员资料时写入或更新默认配送地址（不 commit）。"""
    row = get_default_address(db, member_id)
    detail = (detail_address or "").strip()
    if row:
        row.contact_name = contact_name
        row.contact_phone = contact_phone
        row.detail_address = detail
        row.remarks = remarks
        row.delivery_region_id = delivery_region_id
        row.lng = lng
        row.lat = lat
        return
    _clear_defaults(db, member_id, except_id=None)
    db.add(
        MemberAddress(
            member_id=member_id,
            contact_name=contact_name,
            contact_phone=contact_phone,
            delivery_region_id=delivery_region_id,
            detail_address=detail,
            remarks=remarks,
            lng=lng,
            lat=lat,
            is_default=True,
        )
    )


def admin_set_default_address_detail(
    db: Session,
    *,
    member_id: int,
    detail_line: str,
    contact_name: str,
    contact_phone: str,
) -> None:
    """管理端修改配送地址：写默认地址行并地理编码+自动划区（不 commit）。"""
    detail = (detail_line or "").strip()
    lng, lat, rid = _geocode_bundle(db, detail)
    row = get_default_address(db, member_id)
    if row:
        row.contact_name = contact_name
        row.contact_phone = contact_phone
        row.detail_address = detail
        row.lng, row.lat = lng, lat
        row.delivery_region_id = rid
        return
    _clear_defaults(db, member_id, except_id=None)
    db.add(
        MemberAddress(
            member_id=member_id,
            contact_name=contact_name,
            contact_phone=contact_phone,
            delivery_region_id=rid,
            detail_address=detail,
            remarks=None,
            lng=lng,
            lat=lat,
            is_default=True,
        )
    )


def _geocode_bundle(db: Session, detail: str) -> tuple[float | None, float | None, int | None]:
    line = (detail or "").strip()
    coords = amap.geocode_address(line) if line else None
    if coords:
        lng_f, lat_f = float(coords[0]), float(coords[1])
        r = assign_region_for_coords(db, lng_f, lat_f)
        return lng_f, lat_f, (int(r.id) if r else None)
    return None, None, None


def apply_auto_area_from_coords_or_geocode(db: Session, row: MemberAddress) -> None:
    """管理端「恢复自动划区」：已有坐标则按多边形划区；无坐标则按详细地址尝试高德地理编码后再划区。"""
    if row.lng is not None and row.lat is not None:
        r = assign_region_for_coords(db, float(row.lng), float(row.lat))
        row.delivery_region_id = int(r.id) if r else None
        return
    lng, lat, rid = _geocode_bundle(db, row.detail_address)
    row.lng, row.lat = lng, lat
    row.delivery_region_id = rid


def _to_out(row: MemberAddress, id_to_name: dict[int, str]) -> MemberAddressOut:
    loc = None
    if row.lng is not None and row.lat is not None:
        loc = Location(lng=float(row.lng), lat=float(row.lat))
    return MemberAddressOut(
        id=int(row.id),
        member_id=int(row.member_id),
        contact_name=row.contact_name,
        contact_phone=row.contact_phone,
        delivery_region_id=int(row.delivery_region_id) if row.delivery_region_id is not None else None,
        area=routing_area_label(row, id_to_name),
        detail_address=row.detail_address,
        remarks=row.remarks,
        location=loc,
        is_default=bool(row.is_default),
        created_at=row.created_at.isoformat() if row.created_at else "",
        updated_at=row.updated_at.isoformat() if row.updated_at else "",
    )


def _ensure_member_exists(db: Session, member_id: int) -> None:
    if not db.get(Member, member_id):
        raise HTTPException(status_code=404, detail="用户不存在")


def _clear_defaults(db: Session, member_id: int, except_id: int | None = None) -> None:
    stmt = select(MemberAddress).where(MemberAddress.member_id == member_id, MemberAddress.is_default.is_(True))
    if except_id is not None:
        stmt = stmt.where(MemberAddress.id != except_id)
    for row in db.scalars(stmt).all():
        row.is_default = False


def _assign_default_if_none(db: Session, member_id: int) -> None:
    has_default = db.scalar(
        select(func.count()).select_from(MemberAddress).where(
            MemberAddress.member_id == member_id, MemberAddress.is_default.is_(True)
        )
    )
    if has_default:
        return
    last = db.scalars(
        select(MemberAddress)
        .where(MemberAddress.member_id == member_id)
        .order_by(MemberAddress.id.desc())
        .limit(1)
    ).first()
    if last:
        last.is_default = True


def list_addresses(db: Session, member_id: int) -> list[MemberAddressOut]:
    _ensure_member_exists(db, member_id)
    rows = db.scalars(
        select(MemberAddress)
        .where(MemberAddress.member_id == member_id)
        .order_by(MemberAddress.is_default.desc(), MemberAddress.id.desc())
    ).all()
    ids = {int(r.delivery_region_id) for r in rows if r.delivery_region_id is not None}
    nm = delivery_region_name_map(db, ids)
    return [_to_out(r, nm) for r in rows]


def create_address(db: Session, member_id: int, body: MemberAddressCreateIn) -> MemberAddressOut:
    _ensure_member_exists(db, member_id)
    count = (
        db.scalar(select(func.count()).select_from(MemberAddress).where(MemberAddress.member_id == member_id)) or 0
    )
    if count >= _MAX_ADDRESSES_PER_MEMBER:
        raise HTTPException(status_code=400, detail=f"每位会员最多保存 {_MAX_ADDRESSES_PER_MEMBER} 条地址")

    effective_default = True if count == 0 else body.is_default
    if body.location is not None:
        lng_f, lat_f = float(body.location.lng), float(body.location.lat)
        lng, lat = lng_f, lat_f
        r = assign_region_for_coords(db, lng_f, lat_f)
        rid = int(r.id) if r else None
    else:
        lng, lat, rid = _geocode_bundle(db, body.detail_address)

    if effective_default:
        _clear_defaults(db, member_id, except_id=None)

    row = MemberAddress(
        member_id=member_id,
        contact_name=body.contact_name,
        contact_phone=body.contact_phone,
        delivery_region_id=rid,
        detail_address=body.detail_address,
        remarks=body.remarks,
        lng=lng,
        lat=lat,
        is_default=effective_default,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    nm = delivery_region_name_map(db, {int(row.delivery_region_id)} if row.delivery_region_id else set())
    return _to_out(row, nm)


def update_address(db: Session, member_id: int, address_id: int, body: MemberAddressUpdateIn) -> MemberAddressOut:
    row = db.get(MemberAddress, address_id)
    if not row or row.member_id != member_id:
        raise HTTPException(status_code=404, detail="地址不存在")

    patch = body.model_dump(exclude_unset=True)
    is_default_new = patch.pop("is_default", None)
    location_patch = patch.pop("location", None)

    for k, v in patch.items():
        setattr(row, k, v)

    if location_patch is not None:
        lng_f = float(location_patch["lng"])
        lat_f = float(location_patch["lat"])
        row.lng, row.lat = lng_f, lat_f
        r = assign_region_for_coords(db, lng_f, lat_f)
        row.delivery_region_id = int(r.id) if r else None
    elif "detail_address" in patch:
        lng, lat, rid = _geocode_bundle(db, row.detail_address)
        row.lng, row.lat, row.delivery_region_id = lng, lat, rid

    if is_default_new is True:
        _clear_defaults(db, member_id, except_id=row.id)
        row.is_default = True
    elif is_default_new is False:
        row.is_default = False
        _assign_default_if_none(db, member_id)

    db.commit()
    db.refresh(row)
    nm = delivery_region_name_map(db, {int(row.delivery_region_id)} if row.delivery_region_id else set())
    return _to_out(row, nm)


def delete_address(db: Session, member_id: int, address_id: int) -> None:
    row = db.get(MemberAddress, address_id)
    if not row or row.member_id != member_id:
        raise HTTPException(status_code=404, detail="地址不存在")
    was_default = bool(row.is_default)
    db.delete(row)
    db.flush()
    if was_default:
        _assign_default_if_none(db, member_id)
    db.commit()
