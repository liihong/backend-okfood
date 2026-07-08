from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.constants import UNASSIGNED_DELIVERY_AREA
from app.models.delivery_region import DeliveryRegion
from app.models.member import Member
from app.models.member_address import MemberAddress
from app.schemas.member_address import MemberAddressCreateIn, MemberAddressOut, MemberAddressUpdateIn
from app.schemas.user import Location
from app.services.shared import amap
from app.services.member.leave import guard_member_self_service_during_sf_fulfillment
from app.services.member.member_operation_log_service import (
    OP_ADDRESS_CREATE,
    OP_ADDRESS_DELETE,
    OP_ADDRESS_SET_DEFAULT,
    OP_ADDRESS_UPDATE,
    record_member_operation,
)
from app.services.shared.region_assignment import assign_region_for_coords

_MAX_ADDRESSES_PER_MEMBER = 20


def full_address_line(map_location_text: str | None, door_detail: str | None) -> str:
    """完整收货展示/地理编码用地址：两段非空时用空格拼接。"""
    m = (map_location_text or "").strip()
    d = (door_detail or "").strip()
    if not m:
        return d
    if not d:
        return m
    return f"{m} {d}".strip()


def _opt_str(v: str | None) -> str | None:
    if v is None:
        return None
    t = v.strip()
    return t if t else None


def _format_pca_compact(province: str | None, city: str | None, district: str | None) -> str:
    """与高德 addressComponent 相同的紧凑拼接：省市区连写，供逆地理前缀。"""
    parts: list[str] = []
    p = (province or "").strip()
    c = (city or "").strip()
    d = (district or "").strip()
    if p:
        parts.append(p)
    if c and c not in p and all(c not in x for x in parts):
        parts.append(c)
    if d and all(d not in x for x in parts):
        parts.append(d)
    return "".join(parts).strip()


def _strip_if_prefix_matches(text: str, prefix: str) -> str:
    """若 text 以 prefix（忽略空白差异的紧凑前缀）开头，去掉该前缀剩余部分。"""
    t = text.strip()
    p = (prefix or "").strip()
    if not t or not p:
        return t
    if t.startswith(p):
        r = t[len(p) :].strip()
        return r if r else t
    pc = "".join(p.split())
    if not pc:
        return t
    built = ""
    i = 0
    while i < len(t) and len(built) < len(pc):
        ch = t[i]
        i += 1
        if not ch.isspace():
            built += ch
        if built == pc:
            break
    if built != pc:
        return t
    return t[i:].strip()


def _normalize_map_location_text_with_regeo_hints(
    *,
    map_text: str | None,
    new_pca_ln: str | None,
    previous_pca_compact: str | None,
) -> str | None:
    """
    map_location_text 存库可并入省市区前缀：优先用高德逆地理的 pca_prefix_line。
    previous_pca_compact 用于 PATCH 挪动选点前，按旧坐标逆地理前缀剥掉冗余省市区。
    """
    p_new = (new_pca_ln or "").strip()
    s_prev = (previous_pca_compact or "").strip()
    raw = (map_text or "").strip()
    if not raw:
        return _opt_str(p_new[:500] if p_new else None)
    core = raw
    for pref in (p_new, s_prev):
        pref = (pref or "").strip()
        if not pref:
            continue
        stripped = _strip_if_prefix_matches(core, pref)
        if stripped != core:
            core = stripped.strip()
            break
    if not core:
        return _opt_str(p_new[:500] if p_new else None)
    if not p_new:
        return _opt_str(core[:500])
    pc_core, pc_new = "".join(core.split()), "".join(p_new.split())
    if core.startswith(p_new) or (pc_new and pc_core.startswith(pc_new)):
        return _opt_str(core[:500])
    combined = f"{p_new} {core}".strip()
    return _opt_str(combined[:500])


def _row_coords(row: MemberAddress) -> tuple[float, float] | None:
    if row.lng is None or row.lat is None:
        return None
    try:
        lng_f = float(row.lng)
        lat_f = float(row.lat)
    except (TypeError, ValueError):
        return None
    return lng_f, lat_f


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
    # 仅扫描本批 member_id，避免全表默认地址子查询
    pick = (
        select(
            MemberAddress.member_id.label("mid"),
            func.max(MemberAddress.id).label("addr_id"),
        )
        .where(
            MemberAddress.member_id.in_(uniq),
            MemberAddress.is_default.is_(True),
        )
        .group_by(MemberAddress.member_id)
    ).subquery("daf_page")
    rows = db.scalars(
        select(MemberAddress).join(pick, MemberAddress.id == pick.c.addr_id)
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
    address_line: str,
    remarks: str | None,
    delivery_region_id: int | None,
    lng: float | None,
    lat: float | None,
) -> None:
    """登记/更新会员资料时写入或更新默认配送地址（整段写入 map_location_text；不 commit）。"""
    row = get_default_address(db, member_id)
    base = (address_line or "").strip()[:500]
    if row:
        row.contact_name = contact_name
        row.contact_phone = contact_phone
        row.map_location_text = base if base else None
        row.door_detail = None
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
            map_location_text=base if base else None,
            door_detail=None,
            remarks=remarks,
            lng=lng,
            lat=lat,
            is_default=True,
        )
    )


def upsert_default_address_from_admin_map_pick(
    db: Session,
    *,
    member_id: int,
    contact_name: str,
    contact_phone: str,
    map_location_text: str,
    door_detail: str | None,
    lng: float,
    lat: float,
    tenant_id: int | None = None,
) -> None:
    """
    管理端地图选点写入或更新默认配送地址（含 map_location_text / door_detail），按坐标自动划区；不 commit。
    map_location_text 与小程序建档一致：按坐标逆地理拼接省市区前缀后再入库。
    """
    map_raw = _opt_str(map_location_text)
    door_raw = (door_detail or "").strip()[:500]
    lng_f, lat_f = float(lng), float(lat)
    r = assign_region_for_coords(db, lng_f, lat_f, tenant_id=tenant_id)
    rid = int(r.id) if r else None
    row = get_default_address(db, member_id)
    old_pca_compact: str | None = None
    if row and row.lng is not None and row.lat is not None:
        try:
            prev_lng, prev_lat = float(row.lng), float(row.lat)
        except (TypeError, ValueError):
            prev_lng, prev_lat = None, None
        if prev_lng is not None and prev_lat is not None:
            osnap = amap.fetch_regeo_snapshot(prev_lng, prev_lat)
            if osnap:
                old_pca_compact = (
                    osnap.pca_prefix_line or _format_pca_compact(osnap.province, osnap.city, osnap.district) or None
                )
    snap = amap.fetch_regeo_snapshot(lng_f, lat_f)
    pca_ln = snap.pca_prefix_line if snap else None
    if not pca_ln and snap:
        pca_ln = _format_pca_compact(snap.province, snap.city, snap.district) or None
    map_eff = _normalize_map_location_text_with_regeo_hints(
        map_text=map_raw,
        new_pca_ln=pca_ln,
        previous_pca_compact=old_pca_compact,
    )
    cn = (contact_name or "").strip()[:100]
    cp = (contact_phone or "").strip()[:20]
    if row:
        row.contact_name = cn
        row.contact_phone = cp
        row.map_location_text = map_eff
        row.door_detail = door_raw if door_raw else None
        row.lng = lng_f
        row.lat = lat_f
        row.delivery_region_id = rid
        return
    _clear_defaults(db, member_id, except_id=None)
    db.add(
        MemberAddress(
            member_id=member_id,
            contact_name=cn,
            contact_phone=cp,
            delivery_region_id=rid,
            map_location_text=map_eff,
            door_detail=door_raw if door_raw else None,
            remarks=None,
            lng=lng_f,
            lat=lat_f,
            is_default=True,
        )
    )


def admin_apply_manual_delivery_region(
    db: Session,
    *,
    member_id: int,
    delivery_region_id: int | None,
) -> None:
    """管理端手动指定默认地址的配送片区（不 commit）。``delivery_region_id`` 为 None 表示清空。"""
    addr = get_default_address(db, member_id)
    if not addr:
        raise HTTPException(status_code=400, detail="该会员暂无默认配送地址，无法分配片区")
    if delivery_region_id is not None:
        r = db.get(DeliveryRegion, int(delivery_region_id))
        if r is None:
            raise HTTPException(status_code=400, detail="配送片区不存在")
    addr.delivery_region_id = delivery_region_id


def admin_set_default_address_plain_line(
    db: Session,
    *,
    member_id: int,
    detail_line: str,
    contact_name: str,
    contact_phone: str,
) -> None:
    """管理端单一文本地址：整段写入 map_location_text，清 door_detail；地理编码+自动划区（不 commit）。"""
    detail = (detail_line or "").strip()
    lng, lat, rid = _geocode_bundle(db, detail)
    row = get_default_address(db, member_id)
    map_text = detail[:500]
    if row:
        row.contact_name = contact_name
        row.contact_phone = contact_phone
        row.map_location_text = map_text
        row.door_detail = None
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
            map_location_text=map_text,
            door_detail=None,
            remarks=None,
            lng=lng,
            lat=lat,
            is_default=True,
        )
    )


def _geocode_bundle(
    db: Session, detail: str, *, tenant_id: int | None = None
) -> tuple[float | None, float | None, int | None]:
    line = (detail or "").strip()
    coords = amap.geocode_address(line) if line else None
    if coords:
        lng_f, lat_f = float(coords[0]), float(coords[1])
        r = assign_region_for_coords(db, lng_f, lat_f, tenant_id=tenant_id)
        return lng_f, lat_f, (int(r.id) if r else None)
    return None, None, None


def apply_auto_area_from_coords_or_geocode(
    db: Session, row: MemberAddress, *, tenant_id: int | None = None
) -> None:
    """
    管理端「恢复自动划区」：已有坐标则按多边形划区；无坐标则按拼接地址尝试高德地理编码后再划区。

    必须按会员所属 ``tenant_id`` 过滤配送区域，避免多租户片区重叠时误划到其它租户区域。
    """
    tid = int(tenant_id) if tenant_id is not None else _resolve_tenant_id_for_member_address(db, row)
    if row.lng is not None and row.lat is not None:
        r = assign_region_for_coords(db, float(row.lng), float(row.lat), tenant_id=tid)
        row.delivery_region_id = int(r.id) if r else None
        return
    line = full_address_line(row.map_location_text, row.door_detail)
    lng, lat, rid = _geocode_bundle(db, line, tenant_id=tid)
    row.lng, row.lat = lng, lat
    row.delivery_region_id = rid


def _resolve_tenant_id_for_member_address(db: Session, row: MemberAddress) -> int:
    """从地址关联会员解析租户 id；无法确定时拒绝自动划区。"""
    from fastapi import HTTPException

    from app.models.member import Member

    m = db.get(Member, int(row.member_id))
    if m is None or m.deleted_at is not None:
        raise HTTPException(status_code=404, detail="会员不存在，无法自动划区")
    return int(m.tenant_id)


def _to_out(row: MemberAddress, id_to_name: dict[int, str]) -> MemberAddressOut:
    loc = None
    if row.lng is not None and row.lat is not None:
        loc = Location(lng=float(row.lng), lat=float(row.lat))
    fa = full_address_line(row.map_location_text, row.door_detail)
    return MemberAddressOut(
        id=int(row.id),
        member_id=int(row.member_id),
        contact_name=row.contact_name,
        contact_phone=row.contact_phone,
        delivery_region_id=int(row.delivery_region_id) if row.delivery_region_id is not None else None,
        area=routing_area_label(row, id_to_name),
        map_location_text=_opt_str(row.map_location_text),
        door_detail=_opt_str(row.door_detail),
        full_address=fa,
        remarks=row.remarks,
        location=loc,
        is_default=bool(row.is_default),
        created_at=row.created_at.isoformat() if row.created_at else "",
        updated_at=row.updated_at.isoformat() if row.updated_at else "",
    )


def _ensure_member_exists(db: Session, member_id: int) -> None:
    m = db.get(Member, member_id)
    if not m or m.deleted_at is not None:
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


def check_coords_in_delivery_region(
    db: Session, lng: float, lat: float, *, tenant_id: int | None = None
) -> tuple[bool, int | None, str | None]:
    """判断坐标是否落在启用的配送片区内；命中时返回片区 id 与名称。"""
    r = assign_region_for_coords(db, float(lng), float(lat), tenant_id=tenant_id)
    if r is None:
        return False, None, None
    name = (r.name or "").strip() or UNASSIGNED_DELIVERY_AREA
    return True, int(r.id), name


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


def create_address(db: Session, member_id: int, body: MemberAddressCreateIn, *, ip_address: str | None = None) -> MemberAddressOut:
    _ensure_member_exists(db, member_id)
    mem = db.get(Member, member_id)
    if mem:
        guard_member_self_service_during_sf_fulfillment(db, mem)
    tid = int(mem.tenant_id) if mem and mem.tenant_id is not None else None
    count = (
        db.scalar(select(func.count()).select_from(MemberAddress).where(MemberAddress.member_id == member_id)) or 0
    )
    if count >= _MAX_ADDRESSES_PER_MEMBER:
        raise HTTPException(status_code=400, detail=f"每位会员最多保存 {_MAX_ADDRESSES_PER_MEMBER} 条地址")

    effective_default = True if count == 0 else body.is_default

    map_raw = _opt_str(body.map_location_text)
    door_eff = _opt_str(body.door_detail)

    if body.location is not None:
        lng_f, lat_f = float(body.location.lng), float(body.location.lat)
        lng, lat = lng_f, lat_f
        r = assign_region_for_coords(db, lng_f, lat_f, tenant_id=tid)
        rid = int(r.id) if r else None
        snap = amap.fetch_regeo_snapshot(lng_f, lat_f)
        pca_ln = snap.pca_prefix_line if snap else None
        if not pca_ln and snap:
            pca_ln = _format_pca_compact(snap.province, snap.city, snap.district) or None
        map_eff = _normalize_map_location_text_with_regeo_hints(
            map_text=map_raw,
            new_pca_ln=pca_ln,
            previous_pca_compact=None,
        )
    else:
        line = full_address_line(map_raw, door_eff)
        lng, lat, rid = _geocode_bundle(db, line, tenant_id=tid)
        map_eff = map_raw

    if effective_default:
        _clear_defaults(db, member_id, except_id=None)

    row = MemberAddress(
        member_id=member_id,
        contact_name=body.contact_name,
        contact_phone=body.contact_phone,
        delivery_region_id=rid,
        map_location_text=map_eff,
        door_detail=door_eff,
        remarks=body.remarks,
        lng=lng,
        lat=lat,
        is_default=effective_default,
    )
    db.add(row)
    db.flush()
    record_member_operation(
        db,
        member_id=member_id,
        operation_type=OP_ADDRESS_CREATE,
        summary=f"新增配送地址：{full_address_line(map_eff, door_eff) or '(空)'}"
        + ("（默认）" if effective_default else ""),
        before=None,
        after={
            "address_id": int(row.id),
            "contact_name": row.contact_name,
            "contact_phone": row.contact_phone,
            "map_location_text": map_eff,
            "door_detail": door_eff,
            "is_default": bool(effective_default),
        },
        ip_address=ip_address,
    )
    db.commit()
    db.refresh(row)
    nm = delivery_region_name_map(db, {int(row.delivery_region_id)} if row.delivery_region_id else set())
    return _to_out(row, nm)


def update_address(
    db: Session,
    member_id: int,
    address_id: int,
    body: MemberAddressUpdateIn,
    *,
    ip_address: str | None = None,
    source: str = "miniprogram",
    operator: str | None = None,
) -> MemberAddressOut:
    row = db.get(MemberAddress, address_id)
    if not row or row.member_id != member_id:
        raise HTTPException(status_code=404, detail="地址不存在")
    mem = db.get(Member, member_id)
    if mem and source == "miniprogram":
        guard_member_self_service_during_sf_fulfillment(db, mem)
    tid = int(mem.tenant_id) if mem and mem.tenant_id is not None else None

    # 采集变更前快照，供操作日志 before/after 对比
    prev = {
        "contact_name": row.contact_name,
        "contact_phone": row.contact_phone,
        "map_location_text": row.map_location_text,
        "door_detail": row.door_detail,
        "remarks": row.remarks,
        "is_default": bool(row.is_default),
        "full_address": full_address_line(row.map_location_text, row.door_detail),
    }

    coords_prev = _row_coords(row)
    prev_lng, prev_lat = (coords_prev[0], coords_prev[1]) if coords_prev else (None, None)
    old_pca_compact: str | None = None
    if prev_lng is not None and prev_lat is not None:
        osnap = amap.fetch_regeo_snapshot(prev_lng, prev_lat)
        if osnap:
            old_pca_compact = (
                osnap.pca_prefix_line or _format_pca_compact(osnap.province, osnap.city, osnap.district) or None
            )

    patch = body.model_dump(exclude_unset=True)
    is_default_new = patch.pop("is_default", None)
    location_patch = patch.pop("location", None)

    for k, v in patch.items():
        setattr(row, k, v)
    if "map_location_text" in patch:
        row.map_location_text = _opt_str(row.map_location_text)
    if "door_detail" in patch:
        row.door_detail = _opt_str(row.door_detail)

    if location_patch is not None:
        lng_f = float(location_patch["lng"])
        lat_f = float(location_patch["lat"])
        row.lng, row.lat = lng_f, lat_f
        r = assign_region_for_coords(db, lng_f, lat_f, tenant_id=tid)
        row.delivery_region_id = int(r.id) if r else None
    elif "map_location_text" in patch or "door_detail" in patch:
        line = full_address_line(row.map_location_text, row.door_detail)
        lng, lat, rid = _geocode_bundle(db, line, tenant_id=tid)
        row.lng, row.lat, row.delivery_region_id = lng, lat, rid

    lnglat = _row_coords(row)
    addr_touched = (
        location_patch is not None or "map_location_text" in patch or "door_detail" in patch
    )

    snap = amap.fetch_regeo_snapshot(lnglat[0], lnglat[1]) if lnglat else None

    if lnglat is not None and addr_touched:
        pca_ln = snap.pca_prefix_line if snap else None
        if not pca_ln and snap:
            pca_ln = _format_pca_compact(snap.province, snap.city, snap.district) or None
        row.map_location_text = _normalize_map_location_text_with_regeo_hints(
            map_text=row.map_location_text,
            new_pca_ln=pca_ln,
            previous_pca_compact=old_pca_compact,
        )

    if is_default_new is True:
        _clear_defaults(db, member_id, except_id=row.id)
        row.is_default = True
    elif is_default_new is False:
        row.is_default = False
        _assign_default_if_none(db, member_id)

    db.flush()
    after = {
        "address_id": int(row.id),
        "contact_name": row.contact_name,
        "contact_phone": row.contact_phone,
        "map_location_text": row.map_location_text,
        "door_detail": row.door_detail,
        "remarks": row.remarks,
        "is_default": bool(row.is_default),
        "full_address": full_address_line(row.map_location_text, row.door_detail),
    }
    # 仅在 before/after 真正发生差异时记一次日志，避免无意义空操作
    changed_keys = [k for k in after if prev.get(k) != after.get(k) and k != "address_id"]
    if changed_keys:
        only_set_default = changed_keys == ["is_default"] and after["is_default"] is True and not prev["is_default"]
        op_type = OP_ADDRESS_SET_DEFAULT if only_set_default else OP_ADDRESS_UPDATE
        if only_set_default:
            summary = f"设为默认配送地址：{after['full_address'] or '(空)'}"
        elif prev["full_address"] != after["full_address"]:
            summary = f"修改配送地址：{prev['full_address'] or '(空)'} → {after['full_address'] or '(空)'}"
        else:
            summary = f"修改配送地址信息：{after['full_address'] or '(空)'}"
        record_member_operation(
            db,
            member_id=member_id,
            operation_type=op_type,
            summary=summary,
            before={"address_id": int(row.id), **{k: prev[k] for k in changed_keys if k in prev}},
            after={k: after[k] for k in ["address_id", *changed_keys]},
            ip_address=ip_address,
            operator=operator,
            source=source,
        )

    db.commit()
    db.refresh(row)
    nm = delivery_region_name_map(db, {int(row.delivery_region_id)} if row.delivery_region_id else set())
    return _to_out(row, nm)


def delete_address(db: Session, member_id: int, address_id: int, *, ip_address: str | None = None) -> None:
    row = db.get(MemberAddress, address_id)
    if not row or row.member_id != member_id:
        raise HTTPException(status_code=404, detail="地址不存在")
    mem = db.get(Member, member_id)
    if mem:
        guard_member_self_service_during_sf_fulfillment(db, mem)
    was_default = bool(row.is_default)
    before = {
        "address_id": int(row.id),
        "contact_name": row.contact_name,
        "contact_phone": row.contact_phone,
        "map_location_text": row.map_location_text,
        "door_detail": row.door_detail,
        "is_default": was_default,
        "full_address": full_address_line(row.map_location_text, row.door_detail),
    }
    db.delete(row)
    db.flush()
    if was_default:
        _assign_default_if_none(db, member_id)
    record_member_operation(
        db,
        member_id=member_id,
        operation_type=OP_ADDRESS_DELETE,
        summary=f"删除配送地址：{before['full_address'] or '(空)'}" + ("（原默认）" if was_default else ""),
        before=before,
        after=None,
        ip_address=ip_address,
    )
    db.commit()
