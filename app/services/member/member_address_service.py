import math

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.constants import ADDRESS_USAGE_MEAL, ADDRESS_USAGE_RETAIL, UNASSIGNED_DELIVERY_AREA
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
# 小程序/管理端保存地址时若仍无有效坐标，拒绝落库，避免顺丰推单缺经纬度
_MISSING_COORDS_DETAIL = "无法确定收货坐标，请使用地图选点后再保存"
# 中国大陆及港澳台常见 GCJ-02 范围；用于拦截 0,0 等选点失败脏数据
_LNG_MIN, _LNG_MAX = 73.0, 136.0
_LAT_MIN, _LAT_MAX = 3.0, 54.0


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


def _validate_map_coords(lng: float, lat: float) -> tuple[float, float]:
    """校验地图选点坐标：须为有限值且落在国内常见范围内。"""
    try:
        lng_f, lat_f = float(lng), float(lat)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=_MISSING_COORDS_DETAIL) from exc
    if not math.isfinite(lng_f) or not math.isfinite(lat_f):
        raise HTTPException(status_code=400, detail=_MISSING_COORDS_DETAIL)
    if not (_LNG_MIN <= lng_f <= _LNG_MAX and _LAT_MIN <= lat_f <= _LAT_MAX):
        raise HTTPException(status_code=400, detail="经纬度超出有效范围，请重新地图选点")
    return lng_f, lat_f


def _require_row_coords(row: MemberAddress) -> None:
    """地址文案或选点变更后必须仍有有效坐标，禁止静默写成空经纬度。"""
    if _row_coords(row) is None:
        raise HTTPException(status_code=400, detail=_MISSING_COORDS_DETAIL)


def parse_address_usage(raw: str | None) -> str:
    """地址用途：仅 meal / retail；其它值回落为会员送餐。"""
    s = (raw or "").strip().lower()
    if s == ADDRESS_USAGE_RETAIL:
        return ADDRESS_USAGE_RETAIL
    return ADDRESS_USAGE_MEAL


def default_address_pick_subquery():
    """每人一条会员送餐默认地址：不含果蔬汁/月饼商城地址；多条 is_default 取 id 最大者。"""
    return (
        select(
            MemberAddress.member_id.label("mid"),
            func.max(MemberAddress.id).label("addr_id"),
        )
        .where(
            MemberAddress.is_default.is_(True),
            MemberAddress.address_usage == ADDRESS_USAGE_MEAL,
        )
        .group_by(MemberAddress.member_id)
    ).subquery("daf")


def get_default_address(
    db: Session, member_id: int, *, usage: str = ADDRESS_USAGE_MEAL
) -> MemberAddress | None:
    u = parse_address_usage(usage)
    return db.scalars(
        select(MemberAddress).where(
            MemberAddress.member_id == member_id,
            MemberAddress.is_default.is_(True),
            MemberAddress.address_usage == u,
        )
    ).first()


def load_default_address_map(db: Session, member_ids: list[int]) -> dict[int, MemberAddress | None]:
    """按会员 id 批量取会员送餐默认地址；无默认地址时值为 None。"""
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
            MemberAddress.address_usage == ADDRESS_USAGE_MEAL,
        )
        .group_by(MemberAddress.member_id)
    ).subquery("daf_page")
    rows = db.scalars(
        select(MemberAddress).join(pick, MemberAddress.id == pick.c.addr_id)
    ).all()
    by_mid: dict[int, MemberAddress] = {int(r.member_id): r for r in rows}
    return {mid: by_mid.get(mid) for mid in uniq}


def delivery_region_name_map(
    db: Session, ids: set[int], *, tenant_id: int | None = None
) -> dict[int, str]:
    """片区 id→名称；传入 ``tenant_id`` 时只映射本租户片区，避免跨租户片区名泄漏。"""
    if not ids:
        return {}
    stmt = select(DeliveryRegion.id, DeliveryRegion.name).where(DeliveryRegion.id.in_(ids))
    if tenant_id is not None:
        stmt = stmt.where(DeliveryRegion.tenant_id == int(tenant_id))
    rows = db.execute(stmt).all()
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
    _clear_defaults(db, member_id, except_id=None, usage=ADDRESS_USAGE_MEAL)
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
            address_usage=ADDRESS_USAGE_MEAL,
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
    _clear_defaults(db, member_id, except_id=None, usage=ADDRESS_USAGE_MEAL)
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
            address_usage=ADDRESS_USAGE_MEAL,
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
    _clear_defaults(db, member_id, except_id=None, usage=ADDRESS_USAGE_MEAL)
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
            address_usage=ADDRESS_USAGE_MEAL,
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
        usage=parse_address_usage(getattr(row, "address_usage", None)),
        created_at=row.created_at.isoformat() if row.created_at else "",
        updated_at=row.updated_at.isoformat() if row.updated_at else "",
    )


def _ensure_member_exists(db: Session, member_id: int) -> None:
    m = db.get(Member, member_id)
    if not m or m.deleted_at is not None:
        raise HTTPException(status_code=404, detail="用户不存在")


def _clear_defaults(
    db: Session, member_id: int, except_id: int | None = None, *, usage: str = ADDRESS_USAGE_MEAL
) -> None:
    u = parse_address_usage(usage)
    stmt = select(MemberAddress).where(
        MemberAddress.member_id == member_id,
        MemberAddress.is_default.is_(True),
        MemberAddress.address_usage == u,
    )
    if except_id is not None:
        stmt = stmt.where(MemberAddress.id != except_id)
    for row in db.scalars(stmt).all():
        row.is_default = False


def _assign_default_if_none(
    db: Session, member_id: int, *, usage: str = ADDRESS_USAGE_MEAL
) -> None:
    u = parse_address_usage(usage)
    has_default = db.scalar(
        select(func.count()).select_from(MemberAddress).where(
            MemberAddress.member_id == member_id,
            MemberAddress.is_default.is_(True),
            MemberAddress.address_usage == u,
        )
    )
    if has_default:
        return
    last = db.scalars(
        select(MemberAddress)
        .where(MemberAddress.member_id == member_id, MemberAddress.address_usage == u)
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


def list_addresses(
    db: Session, member_id: int, *, usage: str | None = ADDRESS_USAGE_MEAL
) -> list[MemberAddressOut]:
    _ensure_member_exists(db, member_id)
    stmt = select(MemberAddress).where(MemberAddress.member_id == member_id)
    if usage is not None:
        stmt = stmt.where(MemberAddress.address_usage == parse_address_usage(usage))
    rows = db.scalars(stmt.order_by(MemberAddress.is_default.desc(), MemberAddress.id.desc())).all()
    ids = {int(r.delivery_region_id) for r in rows if r.delivery_region_id is not None}
    nm = delivery_region_name_map(db, ids)
    return [_to_out(r, nm) for r in rows]


def create_address(
    db: Session,
    member_id: int,
    body: MemberAddressCreateIn,
    *,
    ip_address: str | None = None,
    source: str = "miniprogram",
) -> MemberAddressOut:
    _ensure_member_exists(db, member_id)
    mem = db.get(Member, member_id)
    usage = parse_address_usage(getattr(body, "usage", None))
    # 管理端代建不受顺丰履约中自助改址限制；商城地址与会员送餐履约无关
    if mem and source == "miniprogram" and usage == ADDRESS_USAGE_MEAL:
        guard_member_self_service_during_sf_fulfillment(db, mem)
    tid = int(mem.tenant_id) if mem and mem.tenant_id is not None else None
    count = (
        db.scalar(
            select(func.count())
            .select_from(MemberAddress)
            .where(MemberAddress.member_id == member_id, MemberAddress.address_usage == usage)
        )
        or 0
    )
    if count >= _MAX_ADDRESSES_PER_MEMBER:
        raise HTTPException(status_code=400, detail=f"每位会员最多保存 {_MAX_ADDRESSES_PER_MEMBER} 条地址")

    effective_default = True if count == 0 else body.is_default

    map_raw = _opt_str(body.map_location_text)
    door_eff = _opt_str(body.door_detail)

    # 小程序建档必须以地图选点坐标入库；无坐标时禁止走「纯文案地理编码失败仍保存」
    if body.location is None and source == "miniprogram":
        raise HTTPException(status_code=400, detail=_MISSING_COORDS_DETAIL)

    if body.location is not None:
        lng_f, lat_f = _validate_map_coords(body.location.lng, body.location.lat)
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
        if lng is None or lat is None:
            raise HTTPException(status_code=400, detail=_MISSING_COORDS_DETAIL)
        lng, lat = _validate_map_coords(lng, lat)

    if effective_default:
        _clear_defaults(db, member_id, except_id=None, usage=usage)

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
        address_usage=usage,
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
            "usage": usage,
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
    row_usage = parse_address_usage(getattr(row, "address_usage", None))
    if mem and source == "miniprogram" and row_usage == ADDRESS_USAGE_MEAL:
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
        lng_f, lat_f = _validate_map_coords(location_patch["lng"], location_patch["lat"])
        row.lng, row.lat = lng_f, lat_f
        r = assign_region_for_coords(db, lng_f, lat_f, tenant_id=tid)
        row.delivery_region_id = int(r.id) if r else None
    elif "map_location_text" in patch or "door_detail" in patch:
        # 改门牌/主文案不得覆盖已有坐标。地理编码失败曾把 lng/lat 写成 NULL。
        if _row_coords(row) is None:
            line = full_address_line(row.map_location_text, row.door_detail)
            lng, lat, rid = _geocode_bundle(db, line, tenant_id=tid)
            if lng is not None and lat is not None:
                lng, lat = _validate_map_coords(lng, lat)
                row.lng, row.lat, row.delivery_region_id = lng, lat, rid

    lnglat = _row_coords(row)
    addr_touched = (
        location_patch is not None or "map_location_text" in patch or "door_detail" in patch
    )
    if addr_touched:
        _require_row_coords(row)

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
        _clear_defaults(db, member_id, except_id=row.id, usage=row_usage)
        row.is_default = True
    elif is_default_new is False:
        row.is_default = False
        _assign_default_if_none(db, member_id, usage=row_usage)

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
    row_usage = parse_address_usage(getattr(row, "address_usage", None))
    if mem and row_usage == ADDRESS_USAGE_MEAL:
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
        _assign_default_if_none(db, member_id, usage=row_usage)
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


def _norm_addr_text(v: str | None) -> str:
    return (v or "").strip()


def _find_matching_retail_address(db: Session, src: MemberAddress) -> MemberAddress | None:
    """按联系人+电话+主文案+门牌匹配已有商城地址，避免回填重复复制。"""
    rows = db.scalars(
        select(MemberAddress).where(
            MemberAddress.member_id == int(src.member_id),
            MemberAddress.address_usage == ADDRESS_USAGE_RETAIL,
        )
    ).all()
    for r in rows:
        if (
            _norm_addr_text(r.contact_name) == _norm_addr_text(src.contact_name)
            and _norm_addr_text(r.contact_phone) == _norm_addr_text(src.contact_phone)
            and _norm_addr_text(r.map_location_text) == _norm_addr_text(src.map_location_text)
            and _norm_addr_text(r.door_detail) == _norm_addr_text(src.door_detail)
        ):
            return r
    return None


def _clone_as_retail_address(db: Session, src: MemberAddress) -> MemberAddress:
    """将会员送餐地址复制为商城地址，不改写源记录。"""
    retail_count = (
        db.scalar(
            select(func.count())
            .select_from(MemberAddress)
            .where(
                MemberAddress.member_id == int(src.member_id),
                MemberAddress.address_usage == ADDRESS_USAGE_RETAIL,
            )
        )
        or 0
    )
    is_default = retail_count == 0
    if is_default:
        _clear_defaults(db, int(src.member_id), except_id=None, usage=ADDRESS_USAGE_RETAIL)
    clone = MemberAddress(
        member_id=int(src.member_id),
        contact_name=src.contact_name,
        contact_phone=src.contact_phone,
        delivery_region_id=src.delivery_region_id,
        map_location_text=src.map_location_text,
        door_detail=src.door_detail,
        remarks=src.remarks,
        lng=src.lng,
        lat=src.lat,
        is_default=is_default,
        address_usage=ADDRESS_USAGE_RETAIL,
    )
    db.add(clone)
    db.flush()
    return clone


def ensure_retail_address(db: Session, addr: MemberAddress) -> MemberAddress:
    """
    商城订单只绑定零售地址。
    若传入的是会员送餐地址，则复制一条零售地址（已有相同内容则复用），源地址保持不变。
    """
    if parse_address_usage(getattr(addr, "address_usage", None)) == ADDRESS_USAGE_RETAIL:
        return addr
    existing = _find_matching_retail_address(db, addr)
    if existing is not None:
        return existing
    return _clone_as_retail_address(db, addr)


def backfill_retail_address_separation(db: Session) -> None:
    """
    存量数据：
    1) 从未开卡且无餐次余额的用户，地址改为零售用途；
    2) 商城订单若仍绑着餐次地址，复制后改绑，避免改送餐地址带动果蔬汁/月饼单。
    """
    from sqlalchemy import exists, or_, update

    from app.models.enums import MealPeriod
    from app.models.member_card_order import MemberCardOrder
    from app.models.member_meal_period_state import MemberMealPeriodState
    from app.models.store_retail_order import StoreRetailOrder

    has_applied_card = exists(
        select(1)
        .select_from(MemberCardOrder)
        .where(
            MemberCardOrder.member_id == Member.id,
            MemberCardOrder.applied_to_member.is_(True),
        )
    )
    has_dinner_quota = exists(
        select(1)
        .select_from(MemberMealPeriodState)
        .where(
            MemberMealPeriodState.member_id == Member.id,
            MemberMealPeriodState.meal_period == MealPeriod.DINNER.value,
            or_(
                MemberMealPeriodState.balance > 0,
                func.coalesce(MemberMealPeriodState.meal_quota_total, 0) > 0,
            ),
        )
    )
    juice_only = select(Member.id).where(
        ~has_applied_card,
        func.coalesce(Member.balance, 0) == 0,
        func.coalesce(Member.meal_quota_total, 0) == 0,
        ~has_dinner_quota,
    )
    db.execute(
        update(MemberAddress)
        .where(
            MemberAddress.address_usage == ADDRESS_USAGE_MEAL,
            MemberAddress.member_id.in_(juice_only),
        )
        .values(address_usage=ADDRESS_USAGE_RETAIL)
    )

    order_addr_ids = [
        int(x)
        for x in db.scalars(
            select(StoreRetailOrder.member_address_id)
            .join(MemberAddress, MemberAddress.id == StoreRetailOrder.member_address_id)
            .where(
                StoreRetailOrder.member_address_id.isnot(None),
                MemberAddress.address_usage == ADDRESS_USAGE_MEAL,
            )
            .distinct()
        ).all()
        if x is not None
    ]
    seen: set[int] = set()
    for aid in order_addr_ids:
        if aid in seen:
            continue
        seen.add(aid)
        src = db.get(MemberAddress, aid)
        if src is None:
            continue
        retail = ensure_retail_address(db, src)
        if int(retail.id) == aid:
            continue
        db.execute(
            update(StoreRetailOrder)
            .where(StoreRetailOrder.member_address_id == aid)
            .values(member_address_id=int(retail.id))
        )
    db.commit()
