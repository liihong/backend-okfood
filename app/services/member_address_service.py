from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.constants import UNASSIGNED_DELIVERY_AREA
from app.models.member import Member
from app.models.member_address import MemberAddress
from app.schemas.member_address import MemberAddressCreateIn, MemberAddressOut, MemberAddressUpdateIn
from app.schemas.user import Location
from app.services import amap
from app.services.region_assignment import assign_area_name_for_coords

_MAX_ADDRESSES_PER_MEMBER = 20


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
    rows = db.scalars(
        select(MemberAddress).where(
            MemberAddress.member_id.in_(uniq),
            MemberAddress.is_default.is_(True),
        )
    ).all()
    by_mid: dict[int, MemberAddress] = {}
    for r in rows:
        if r.member_id not in by_mid:
            by_mid[r.member_id] = r
    return {mid: by_mid.get(mid) for mid in uniq}


def effective_routing_area(addr: MemberAddress | None) -> str:
    """配送分组/筛选用片区：仅来自默认地址；无默认地址视为未分配。"""
    if addr is None:
        return UNASSIGNED_DELIVERY_AREA
    a = (addr.area or "").strip()
    return a if a else UNASSIGNED_DELIVERY_AREA


def upsert_default_address_after_register(
    db: Session,
    *,
    member_id: int,
    contact_name: str,
    contact_phone: str,
    detail_address: str,
    remarks: str | None,
    area: str,
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
        row.area = area
        row.area_manual = False
        row.lng = lng
        row.lat = lat
        return
    _clear_defaults(db, member_id, except_id=None)
    db.add(
        MemberAddress(
            member_id=member_id,
            contact_name=contact_name,
            contact_phone=contact_phone,
            area=area,
            area_manual=False,
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
    lng, lat, area_resolved = _geocode_bundle(db, "", detail)
    row = get_default_address(db, member_id)
    if row:
        row.contact_name = contact_name
        row.contact_phone = contact_phone
        row.detail_address = detail
        row.lng, row.lat = lng, lat
        if not row.area_manual:
            row.area = area_resolved
        return
    _clear_defaults(db, member_id, except_id=None)
    db.add(
        MemberAddress(
            member_id=member_id,
            contact_name=contact_name,
            contact_phone=contact_phone,
            area=area_resolved,
            area_manual=False,
            detail_address=detail,
            remarks=None,
            lng=lng,
            lat=lat,
            is_default=True,
        )
    )


def _compose_geocode_line(area: str, detail: str) -> str:
    a = (area or "").strip()
    d = (detail or "").strip()
    if not a or a == UNASSIGNED_DELIVERY_AREA:
        return d
    return f"{a}{d}"


def _geocode_bundle(db: Session, area: str, detail: str) -> tuple[float | None, float | None, str]:
    line = _compose_geocode_line(area, detail)
    coords = amap.geocode_address(line) if line else None
    if coords:
        lng_f, lat_f = float(coords[0]), float(coords[1])
        return lng_f, lat_f, assign_area_name_for_coords(db, lng_f, lat_f)
    fallback_area = (area or "").strip() or UNASSIGNED_DELIVERY_AREA
    return None, None, fallback_area


def _to_out(row: MemberAddress) -> MemberAddressOut:
    loc = None
    if row.lng is not None and row.lat is not None:
        loc = Location(lng=float(row.lng), lat=float(row.lat))
    return MemberAddressOut(
        id=int(row.id),
        member_id=int(row.member_id),
        contact_name=row.contact_name,
        contact_phone=row.contact_phone,
        area=row.area,
        area_manual=bool(row.area_manual),
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
    return [_to_out(r) for r in rows]


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
        area_resolved = assign_area_name_for_coords(db, lng_f, lat_f)
    else:
        lng, lat, area_resolved = _geocode_bundle(db, body.area, body.detail_address)

    if effective_default:
        _clear_defaults(db, member_id, except_id=None)

    row = MemberAddress(
        member_id=member_id,
        contact_name=body.contact_name,
        contact_phone=body.contact_phone,
        area=area_resolved,
        area_manual=False,
        detail_address=body.detail_address,
        remarks=body.remarks,
        lng=lng,
        lat=lat,
        is_default=effective_default,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _to_out(row)


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
        if not row.area_manual:
            row.area = assign_area_name_for_coords(db, lng_f, lat_f)
    elif "area" in patch or "detail_address" in patch:
        lng, lat, area_resolved = _geocode_bundle(db, row.area, row.detail_address)
        row.lng, row.lat, row.area = lng, lat, area_resolved

    if is_default_new is True:
        _clear_defaults(db, member_id, except_id=row.id)
        row.is_default = True
    elif is_default_new is False:
        row.is_default = False
        _assign_default_if_none(db, member_id)

    db.commit()
    db.refresh(row)
    return _to_out(row)


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
