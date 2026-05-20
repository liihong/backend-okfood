"""
顺丰同城推单：与配送大表、单点餐同合并为停靠点，预览 14+ 列模板，提交 `createorder`。

签名为 ``json + && + dev_id + && + appKey`` 再 MD5→Hex→Base64（与常见 openic Java 样例一致）。
"""

from __future__ import annotations

import hashlib
import logging
import math
import re
import time
import uuid
from copy import copy
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import and_, or_, select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.timeutil import beijing_now_naive, today_shanghai
from app.models.delivery_region import DeliveryRegion
from app.models.member import Member
from app.models.member_address import MemberAddress
from app.models.menu_dish import MenuDish
from app.models.sf_same_city_push import SfSameCityPush
from app.models.single_meal_order import SingleMealOrder
from app.models.store import Store
from app.services.courier_service import eligible_members_for_delivery
from app.services.delivery_sheet_service import (
    _filter_members_by_phone_hint,
    _member_line_remarks,
    _resolve_delivery_line,
    build_delivery_sheet,
)
from app.services.member_address_service import delivery_region_name_map, full_address_line, routing_area_label
from app.services.member_service import effective_daily_meal_units
from app.services.store_config_service import get_store_config
from app.services.sf_open import sign as sf_sign_mod
from app.services.sf_open.client import SfOpenApiError, SfOpenClient
from app.services.tenant_integration_service import merged_sf_integration_namespace
from app.schemas.admin import (
    SfSameCityPreviewOut,
    SfSameCityPreviewRow,
    SfSameCityPushIn,
    SfSameCityPushItemResult,
    SfSameCityPushOut,
    SfSameCityRowBase,
)

logger = logging.getLogger(__name__)

_SH = ZoneInfo("Asia/Shanghai")

# 与 sf_same_city_pushes.push_kind、履约回调分支一致
_SF_PUSH_KIND_SINGLE_MEAL_RETAIL = "single_meal_retail"


def _sf_push_request_snapshot(
    preview_row: dict[str, Any],
    pld: dict[str, Any],
    *,
    gset: Any,
    fulfillment_member_ids: list[int] | None = None,
    fulfillment_single_meal_order_ids: list[int] | None = None,
) -> dict[str, Any]:
    """落库：预览行 + 实际发往顺丰的报文（与签名同源 canonical JSON）。"""
    canon = sf_sign_mod._canonical_json(pld)
    snap: dict[str, Any] = {
        "preview_row": preview_row,
        "shop_id": str(gset.SF_OPEN_SHOP_ID or "").strip(),
        "dev_id": int(gset.SF_OPEN_DEV_ID),
        "product_type": int(gset.SF_DEFAULT_PRODUCT_TYPE or 1),
        "vehicle_type_code": int(gset.SF_VEHICLE_TYPE_CODE or 1),
        "sf_create_order": pld,
        "sf_canonical_json": canon,
    }
    mids = [int(x) for x in (fulfillment_member_ids or []) if x is not None]
    oids = [int(x) for x in (fulfillment_single_meal_order_ids or []) if x is not None]
    if mids:
        snap["fulfillment_member_ids"] = mids
    if oids:
        snap["fulfillment_single_meal_order_ids"] = oids
    return snap


def _sf_receive_city_name(row: SfSameCityRowBase, env_city: str) -> str:
    """
    顺丰 ``receive.city_name`` 一般使用地级市标准名（如「新乡市」）。
    传入「河南省新乡市」等带省前缀的写法，线上常返回「获取城市信息失败」。
    """
    texts: list[str | None] = [
        row.map_location_text,
        row.recv_address,
        getattr(row, "address_line", None),
    ]
    for raw in texts:
        s = (raw or "").strip()
        if not s:
            continue
        for muni in ("北京市", "上海市", "天津市", "重庆市"):
            if muni in s[:16]:
                return muni[:32]
        rm = re.search(r"(?:省|自治区)([\u4e00-\u9fff]{1,12}市)", s)
        if rm:
            return rm.group(1)[:32]
        rm = re.match(r"^([\u4e00-\u9fff]{2,12}市)", s)
        if rm:
            return rm.group(1)[:32]
    base = (env_city or "").strip()
    if base:
        rm = re.match(r"^.+省([\u4e00-\u9fff]{1,12}市)$", base)
        if rm:
            return rm.group(1)[:32]
        return base[:32]
    return "新乡市"


def _stop_key(d: date, group_area: str, address_line: str) -> str:
    return hashlib.sha256(f"{d.isoformat()}|{group_area}|{address_line}".encode()).hexdigest()[:32]


def _address_line_without_sheet_area(stop_area: str, address_line: str) -> str:
    """配送大表 address_line 为「片区 + 空格 + 详细」；顺丰预览/快照仅要详细段，不要片区前缀。"""
    line = (address_line or "").strip()
    ar = (stop_area or "").strip()
    if ar and line.startswith(f"{ar} "):
        return line[len(ar) + 1 :].strip()
    if ar and line.startswith(ar):
        return line[len(ar) :].strip()
    return line


def _to_unix(dtx: datetime | None) -> int:
    if dtx is None:
        return int(time.time())
    if dtx.tzinfo is None:
        dtx = dtx.replace(tzinfo=_SH)
    return int(dtx.timestamp())


def _second_day_noon_unix_shanghai(base_day: date) -> int:
    """业务日「次日」中午 12:00（上海）；用于顺丰 ``expect_pickup_time`` / ``shop_expect_time`` 等秒级时间戳。"""
    nd = base_day + timedelta(days=1)
    return int(datetime(nd.year, nd.month, nd.day, 12, 0, 0, tzinfo=_SH).timestamp())


def _load_default_address(
    db: Session, member_id: int, default_by_id: dict[int, MemberAddress]
) -> MemberAddress | None:
    a = default_by_id.get(member_id)
    if a is not None:
        return a
    a = db.scalar(
        select(MemberAddress)
        .where(
            and_(MemberAddress.member_id == member_id, MemberAddress.is_default.is_(True)),
        )
        .limit(1)
    )
    if a is not None:
        return a
    return db.scalar(
        select(MemberAddress)
        .where(MemberAddress.member_id == member_id)
        .order_by(MemberAddress.id.asc())
        .limit(1)
    )


def _single_order_rows(
    db: Session, d: date
) -> list[tuple[SingleMealOrder, Member, MemberAddress, MenuDish]]:
    q = (
        select(SingleMealOrder, Member, MemberAddress, MenuDish)
        .join(Member, SingleMealOrder.member_id == Member.id)
        .join(MemberAddress, SingleMealOrder.member_address_id == MemberAddress.id)
        .join(MenuDish, SingleMealOrder.dish_id == MenuDish.id)
        .where(
            and_(
                SingleMealOrder.delivery_date == d,
                SingleMealOrder.pay_status == "已支付",
                SingleMealOrder.fulfillment_status == "pending",
                SingleMealOrder.store_pickup.is_(False),
            )
        )
    )
    return list(db.execute(q).all())


@dataclass
class _Agg:
    stop_id: str
    group_area: str
    address_line: str
    sub_lines: list[dict] = field(default_factory=list)
    # {id, label, qty, member_name, member_phone}
    singles: list[dict] = field(default_factory=list)


def _build_aggs(
    db: Session,
    d: date,
    area_key: str | None,
    phone_key: str | None,
    members: list[Member],
    default_by_id: dict[int, MemberAddress],
    *,
    store_id: int,
) -> dict[str, _Agg]:
    """大表所有到家停靠点 + 单次餐合并。"""
    sheet = build_delivery_sheet(
        db, delivery_date=d, area=area_key, phone=phone_key, store_id=int(store_id)
    )
    aggs: dict[str, _Agg] = {}
    m_by_id = {int(m.id): m for m in members}

    for g in sheet.groups:
        if g.area == "门店自提":
            continue
        for st in g.stops:
            line_full = (st.address_line or "").strip()
            if not line_full:
                continue
            line = _address_line_without_sheet_area(st.area, line_full)
            sk = _stop_key(d, g.area, line_full)
            a = _Agg(stop_id=sk, group_area=g.area, address_line=line, sub_lines=[])
            for m in st.members:
                u = 0
                is_del = bool(m.is_delivered)
                if not is_del and m.member_id in m_by_id:
                    u = int(effective_daily_meal_units(m_by_id[m.member_id]))
                a.sub_lines.append(
                    {
                        "member_id": m.member_id,
                        "name": m.name,
                        "phone": m.phone,
                        "units": u,
                        "is_delivered": is_del,
                        "remarks": m.remarks,
                    }
                )
            aggs[sk] = a

    for o, mem, aaddr, dsh in _single_order_rows(db, d):
        nm = delivery_region_name_map(
            db, {int(aaddr.delivery_region_id)} if aaddr.delivery_region_id else set()
        )
        ra = (o.routing_area or "").strip() or routing_area_label(aaddr, nm)
        if area_key and (ra or "").strip() != area_key.strip():
            continue
        rline = _resolve_delivery_line(aaddr, nm)
        line_full = (rline.address_line or "").strip()
        if not line_full:
            continue
        line = (rline.detail or "").strip() or _address_line_without_sheet_area(ra, line_full)
        sk = _stop_key(d, ra, line_full)
        if sk not in aggs:
            aggs[sk] = _Agg(stop_id=sk, group_area=ra, address_line=line, sub_lines=[])
        qty = max(1, int(o.quantity or 1))
        label = f"{(dsh.name or '').strip() or '单点'}x{qty}"
        aggs[sk].singles.append(
            {
                "id": int(o.id),
                "label": label,
                "qty": qty,
                "member_name": (mem.name or "").strip() or "会员",
                "member_phone": (mem.phone or "").strip(),
            }
        )

    out: dict[str, _Agg] = {}
    for sk, a in aggs.items():
        sub = sum(
            int(x.get("units") or 0) for x in a.sub_lines if not x.get("is_delivered")
        )
        sq = sum(int(s.get("qty") or 0) for s in a.singles)
        if sub + sq > 0:
            out[sk] = a
    return out


def _agg_to_row(
    db: Session,
    a: _Agg,
    d: date,
    default_by_id: dict[int, MemberAddress],
    m_by_id: dict[int, Member],
    gset: Any,
    success_member_map: dict[str, set[int]],
) -> SfSameCityPreviewRow:
    p_phone = (gset.SF_PICKUP_PHONE or "").strip()
    sub = sum(
        int(x.get("units") or 0) for x in a.sub_lines if not x.get("is_delivered")
    )
    sq = sum(int(x.get("qty") or 0) for x in a.singles)
    total = max(1, sub + sq)
    wkg = max(0.1, float(gset.SF_KG_PER_MEAL_UNIT) * float(total))

    maddr: MemberAddress | None = None
    for x in a.sub_lines:
        if not x.get("is_delivered") and int(x.get("units") or 0) > 0:
            maddr = _load_default_address(db, int(x["member_id"]), default_by_id)
            break
    if maddr is None and a.sub_lines:
        maddr = _load_default_address(db, int(a.sub_lines[0]["member_id"]), default_by_id)
    if maddr is None and a.singles:
        o = db.get(SingleMealOrder, a.singles[0]["id"])
        if o and o.member_address_id:
            maddr = db.get(MemberAddress, o.member_address_id)

    # 与会员地址表一致：收货大地址=地图选点文案；门牌=楼栋/门牌；仅一段时并入 recv_address
    if maddr:
        recv_addr = (maddr.map_location_text or "").strip()
        recv_build = (maddr.door_detail or "").strip()
        if not recv_addr:
            recv_addr = full_address_line(maddr.map_location_text, maddr.door_detail)
            recv_build = ""
    else:
        recv_addr = ""
        recv_build = ""
    if not recv_addr:
        recv_addr = (a.address_line or "").strip() or (a.group_area or "").strip()
    expect_at_default = datetime(d.year, d.month, d.day, 12, 0, 0)

    names: list[str] = []
    tels: list[str] = []
    for x in a.sub_lines:
        if not x.get("is_delivered") and int(x.get("units") or 0) > 0:
            if (x.get("name") or "").strip():
                names.append(x["name"].strip())
            if (x.get("phone") or "").strip():
                tels.append(x["phone"].strip())
    for sng in a.singles:
        names.append(sng.get("member_name", ""))
        tels.append(sng.get("member_phone", ""))
    names = [n for n in names if n]
    tels = [t for t in tels if t]
    rname = "、".join(dict.fromkeys(names)) if names else ((maddr.contact_name if maddr else "") or "收件人")
    rphone = tels[0] if tels else ((maddr.contact_phone if maddr else "") or "")

    rmk: list[str] = []
    for x in a.sub_lines:
        mem = m_by_id.get(int(x["member_id"]))
        if mem:
            ad = _load_default_address(db, int(x["member_id"]), default_by_id)
            t = _member_line_remarks(mem, ad)
            if t:
                rmk.append(t)
    for sng in a.singles:
        rmk.append(sng.get("label", ""))
    rmk_s = "；".join([x for x in rmk if x]) or None

    recv_lng_f: float | None = None
    recv_lat_f: float | None = None
    if maddr and maddr.lng is not None and maddr.lat is not None:
        try:
            lg = float(maddr.lng)
            lt = float(maddr.lat)
            if math.isfinite(lg) and math.isfinite(lt):
                recv_lng_f, recv_lat_f = lg, lt
        except (TypeError, ValueError):
            pass

    mids_ship = _member_ids_receiving_on_agg(db, a)
    dup_member_elsewhere = _member_overlap_with_other_success_stops(
        mids_ship, a.stop_id, success_member_map
    )
    pushed = _has_success(db, d, a.stop_id) or dup_member_elsewhere
    return SfSameCityPreviewRow(
        stop_id=a.stop_id,
        group_area=a.group_area,
        address_line=a.address_line,
        pickup_phone=p_phone or "（请在 .env 配置 SF_PICKUP_PHONE）",
        map_location_text=recv_addr,
        door_detail=recv_build,
        recv_address=recv_addr,
        recv_building=recv_build,
        recv_lng=recv_lng_f,
        recv_lat=recv_lat_f,
        recv_name=rname[:100],
        recv_phone=(rphone or "—")[:20],
        product_category=(gset.SF_PRODUCT_CATEGORY_LABEL or "餐品").strip(),
        weight_kg=round(wkg, 2),
        push_immediately=False,
        expect_delivery_at=expect_at_default,
        remark=rmk_s,
        is_direct=False,
        vehicle_type=(gset.SF_DEFAULT_VEHICLE_TYPE or "小轿车").strip(),
        is_insured=False,
        goods_value_yuan=None,
        subscription_pending_units=int(sub),
        single_meal_count=int(sq),
        selected=True,
        already_pushed=pushed,
    )


def _has_success(db: Session, d: date, stop_id: str) -> bool:
    r = db.scalar(
        select(SfSameCityPush.id)
        .where(
            and_(
                SfSameCityPush.delivery_date == d,
                SfSameCityPush.stop_id == stop_id,
                SfSameCityPush.error_code == 0,
            )
        )
        .limit(1)
    )
    return r is not None


def _sf_push_row_cancelled_predicate() -> Any:
    """与监控页一致：商户 cancel 或顺丰回调已为取消类终态。"""
    return or_(
        SfSameCityPush.merchant_cancel_requested_at.isnot(None),
        SfSameCityPush.sf_callback_order_status.in_((2, 22)),
    )


def _member_ids_receiving_on_agg(db: Session, agg: _Agg) -> set[int]:
    """
    本会话停靠点上「实际占顺丰运力」的会员：订阅待送份数>0 + 单点餐（与履约口径一致）。
    用于同一配送日同一会员仅能一次成功创单。
    """
    out: set[int] = set()
    for x in agg.sub_lines:
        if x.get("is_delivered"):
            continue
        if int(x.get("units") or 0) <= 0:
            continue
        out.add(int(x["member_id"]))
    for sng in agg.singles:
        try:
            oid = int(sng["id"])
        except (KeyError, TypeError, ValueError):
            continue
        o = db.get(SingleMealOrder, oid)
        if o is not None and o.member_id is not None:
            out.add(int(o.member_id))
    return out


def _successful_sf_stop_ids(db: Session, *, store_id: int, d: date) -> list[str]:
    rows = db.scalars(
        select(SfSameCityPush.stop_id)
        .where(
            and_(
                SfSameCityPush.store_id == int(store_id),
                SfSameCityPush.delivery_date == d,
                SfSameCityPush.error_code == 0,
                ~_sf_push_row_cancelled_predicate(),
            )
        )
        .distinct()
    ).all()
    return [str(x) for x in rows]


def _success_stop_member_map(
    db: Session, *, store_id: int, d: date, ags_hint: dict[str, _Agg]
) -> dict[str, set[int]]:
    """已成功创单的每个 stop_id → 当时停靠点上收件会员 id 集合（用于跨停靠点去重）。"""
    m: dict[str, set[int]] = {}
    for sid_stop in _successful_sf_stop_ids(db, store_id=store_id, d=d):
        agg = ags_hint.get(sid_stop) or load_agg_for_stop_id(db, d, sid_stop, store_id=store_id)
        if agg is None:
            continue
        m[sid_stop] = _member_ids_receiving_on_agg(db, agg)
    return m


def _member_overlap_with_other_success_stops(
    mids: set[int], current_stop_id: str, success_member_map: dict[str, set[int]]
) -> bool:
    if not mids:
        return False
    for ost, omids in success_member_map.items():
        if ost == current_stop_id:
            continue
        if mids & omids:
            return True
    return False


@contextmanager
def _sf_push_serial_lock(db: Session, *, store_id: int, d: date):
    """
    同一门店 + 配送业务日串行化推单，避免并发请求同时越过「会员未推」校验造成双单。
    MySQL 使用 GET_LOCK；SQLite 等跳过。
    """
    bind = db.get_bind()
    if getattr(bind.dialect, "name", "") != "mysql":
        yield
        return
    key = f"okf_sfpush_{store_id}_{d.isoformat()}"[:64]
    rc = db.execute(text("SELECT GET_LOCK(:k, 30)"), {"k": key}).scalar()
    if rc != 1:
        raise ValueError("顺丰推单排队超时，请稍后重试")
    try:
        yield
    finally:
        db.execute(text("SELECT RELEASE_LOCK(:k)"), {"k": key})


def aggs_for_delivery_date(db: Session, d: date, *, store_id: int | None = None) -> dict[str, _Agg]:
    """当日全部停靠点聚合（与同业务日顺丰预览/履约同源）。"""
    sid = int(store_id) if store_id is not None else int(get_settings().DEFAULT_STORE_ID)
    members, default_by_id = eligible_members_for_delivery(
        db, delivery_date=d, delivery_region_id=None, store_id=sid
    )
    mlist = list(members)
    return _build_aggs(db, d, None, None, mlist, default_by_id, store_id=sid)


def load_agg_for_stop_id(
    db: Session, d: date, stop_id: str, *, store_id: int | None = None
) -> _Agg | None:
    """
    按业务日与停靠点 id（与顺丰预览/推单同源）解析聚合行；不加片区/手机筛选，
    与「全量大表 + 单次点餐到家」口径一致。
    """
    return aggs_for_delivery_date(db, d, store_id=store_id).get(stop_id)


def preview_sf_same_city(
    db: Session,
    *,
    delivery_date: date | None = None,
    area: str | None = None,
    phone: str | None = None,
    store_id: int | None = None,
) -> SfSameCityPreviewOut:
    sid = int(store_id) if store_id is not None else int(get_settings().DEFAULT_STORE_ID)
    st = db.get(Store, sid)
    if not st or not st.is_active:
        raise HTTPException(status_code=404, detail="门店不存在或已停用")
    tid = int(st.tenant_id)
    d = delivery_date or today_shanghai()
    akey = (area or "").strip() or None
    pkey = (phone or "").strip() or None
    reg_id = None
    if akey:
        rid = db.scalar(
            select(DeliveryRegion.id).where(
                DeliveryRegion.name == akey,
                DeliveryRegion.tenant_id == tid,
            )
        )
        if rid is not None:
            reg_id = int(rid)
    members, default_by_id = eligible_members_for_delivery(
        db, delivery_date=d, delivery_region_id=reg_id, store_id=sid
    )
    mlist = list(members)
    if pkey:
        mlist = _filter_members_by_phone_hint(mlist, pkey)
    m_by_id = {int(m.id): m for m in mlist}

    ags = _build_aggs(db, d, akey, pkey, mlist, default_by_id, store_id=sid)
    success_member_map = _success_stop_member_map(db, store_id=sid, d=d, ags_hint=ags)
    gset = merged_sf_integration_namespace(db, tid)
    rows: list[SfSameCityPreviewRow] = [
        _agg_to_row(db, ag, d, default_by_id, m_by_id, gset, success_member_map)
        for ag in sorted(ags.values(), key=lambda x: (x.group_area, x.address_line))
    ]
    return SfSameCityPreviewOut(
        delivery_date=d.isoformat(),
        rows=rows,
        sf_configured=bool(
            gset.SF_OPEN_DEV_ID and gset.SF_OPEN_SHOP_ID and (gset.SF_OPEN_SECRET or "").strip()
        ),
    )


def _create_order_payload(
    row: SfSameCityRowBase,
    *,
    shop_order_id: str,
    gset: Any,
    store: Any,
    now_ts: int,
    delivery_date: date,
) -> dict[str, Any]:
    n_meals = max(1, int(row.subscription_pending_units) + int(row.single_meal_count))
    w_gram = int(float(row.weight_kg) * 1000)
    total_fen = n_meals * 100
    is_appoint = 0 if row.push_immediately else 1
    expect_ts = 0
    if is_appoint and row.expect_delivery_at is not None:
        expect_ts = _to_unix(row.expect_delivery_at)
    is_insu = 1 if row.is_insured else 0
    decl = None
    if is_insu and row.goods_value_yuan is not None:
        decl = int(Decimal(str(row.goods_value_yuan)) * 100)
    # 备注：仅体现当次停靠点份数（如「2份餐」）；可选拼接管理端备注，不传车型/类别文案
    meal_note = f"{int(n_meals)}份餐"
    rmk0 = (row.remark or "").strip()
    rmk_final = f"{meal_note} {rmk0}".strip() if rmk0 else meal_note

    # 无会员坐标时的回退中心点（河南省新乡市，GCJ-02 约值，与默认 SF_CITY_NAME 一致）
    recv_lng, recv_lat = 113.883991, 35.303257
    if row.recv_lng is not None and row.recv_lat is not None:
        try:
            lg = float(row.recv_lng)
            lt = float(row.recv_lat)
            if math.isfinite(lg) and math.isfinite(lt):
                recv_lng, recv_lat = lg, lt
        except (TypeError, ValueError):
            pass
    s_lng = float(store.store_lng) if store and store.store_lng is not None else 113.883991
    s_lat = float(store.store_lat) if store and store.store_lat is not None else 35.303257

    def _coord_str(v: float) -> str:
        return f"{float(v):.6f}"

    p_phone = (gset.SF_PICKUP_PHONE or "").strip()
    p_addr = (gset.SF_PICKUP_ADDRESS or "").strip() or f"{(getattr(store, 'store_name', None) or '门店')}"

    line_map = (row.map_location_text or row.recv_address or "").strip()
    line_door = (row.door_detail or row.recv_building or "").strip()
    rec_full = f"{line_map} {line_door}".strip() or (line_map or "")[:200]

    body: dict[str, Any] = {
        "dev_id": int(gset.SF_OPEN_DEV_ID),
        "shop_id": str(gset.SF_OPEN_SHOP_ID or "").strip(),
        "shop_type": int(gset.SF_OPEN_SHOP_TYPE or 1),
        "shop_order_id": str(shop_order_id)[:64],
        "order_source": str((gset.SF_ORDER_SOURCE or "OKFOOD")[:12]),
        "order_time": int(now_ts),
        "is_appoint": is_appoint,
        "is_insured": is_insu,
        "rider_pick_method": 1,
        "return_flag": 7,
        "lbs_type": 2,
        "pay_type": 1,
        "push_time": int(now_ts),
        "version": int(gset.SF_API_VERSION or 17),
        "vehicle_type": int(gset.SF_VEHICLE_TYPE_CODE or 1),
        "order_sequence": str(shop_order_id)[-6:],
        "remark": rmk_final[:500],
    }
    if is_appoint and expect_ts:
        body["appoint_type"] = 1
        body["expect_time"] = int(expect_ts)
        # 用户期望上门时间 / 商家期望送达（骑士端展示、非考核字段）：业务日次日 12:00，秒级时间戳
        second_noon = _second_day_noon_unix_shanghai(delivery_date)
        body["shop_expect_time"] = str(int(second_noon))
    if decl is not None:
        body["declared_value"] = int(decl)
    body["is_person_direct"] = 1 if row.is_direct else 0
    body["receive"] = {
        "user_name": (row.recv_name or "收件人")[:64],
        "user_phone": (row.recv_phone or "")[:20],
        "user_lng": _coord_str(recv_lng),
        "user_lat": _coord_str(recv_lat),
        "user_address": rec_full[:1024],
        "city_name": _sf_receive_city_name(row, (gset.SF_CITY_NAME or "").strip()),
    }
    body["shop"] = {
        "shop_name": (getattr(store, "store_name", None) or "门店")[:128],
        "shop_phone": p_phone[:20],
        "shop_address": p_addr[:200],
        "shop_lng": _coord_str(s_lng),
        "shop_lat": _coord_str(s_lat),
    }
    body["order_detail"] = {
        "total_price": int(total_fen),
        "product_type": int(gset.SF_DEFAULT_PRODUCT_TYPE or 1),
        "weight_gram": int(w_gram),
        "product_num": int(n_meals),
        "product_type_num": 1,
        "user_money": int(total_fen),
        "shop_money": 0,
        "product_detail": [
            {
                "product_name": f"{(row.product_category or '餐品')[:80]} {n_meals}份"[:200],
                "product_num": int(n_meals),
            }
        ],
    }
    return body


def push_sf_same_city(db: Session, body: SfSameCityPushIn, *, store_id: int | None = None) -> SfSameCityPushOut:
    base = get_settings()
    d = body.delivery_date
    sid = int(store_id) if store_id is not None else int(base.DEFAULT_STORE_ID)
    st_row = db.get(Store, sid)
    if not st_row:
        raise ValueError("门店不存在")
    tid = int(st_row.tenant_id)
    gset = merged_sf_integration_namespace(db, tid)
    if not gset.SF_OPEN_DEV_ID or not (gset.SF_OPEN_SHOP_ID or "").strip() or not (gset.SF_OPEN_SECRET or "").strip():
        raise ValueError("请先在租户对接配置或 .env 配置 SF_OPEN_DEV_ID、SF_OPEN_SHOP_ID、SF_OPEN_SECRET")
    if not (gset.SF_PICKUP_PHONE or "").strip() or not (gset.SF_PICKUP_ADDRESS or "").strip():
        raise ValueError("请配置租户对接或 .env 中的顺丰取件电话与取件地址。")
    store = get_store_config(db, store_id=sid)
    out: list[SfSameCityPushItemResult] = []
    now_ts = int(time.time())
    httpc = SfOpenClient()
    with _sf_push_serial_lock(db, store_id=sid, d=d):
        ags_hint = aggs_for_delivery_date(db, d, store_id=sid)
        success_member_map = _success_stop_member_map(
            db, store_id=sid, d=d, ags_hint=ags_hint
        )
        for item in body.rows:
            if not item.selected:
                out.append(
                    SfSameCityPushItemResult(
                        stop_id=item.stop_id, ok=True, message="已跳过（未勾选）", sf_order_id=None
                    )
                )
                continue
            if _has_success(db, d, item.stop_id):
                out.append(
                    SfSameCityPushItemResult(
                        stop_id=item.stop_id,
                        ok=False,
                        message="本停靠点本日已推单成功。",
                        sf_order_id=None,
                    )
                )
                continue
            agg_cur = load_agg_for_stop_id(db, d, item.stop_id, store_id=sid)
            if agg_cur is not None:
                mids_try = _member_ids_receiving_on_agg(db, agg_cur)
                if _member_overlap_with_other_success_stops(
                    mids_try, item.stop_id, success_member_map
                ):
                    out.append(
                        SfSameCityPushItemResult(
                            stop_id=item.stop_id,
                            ok=False,
                            message="本配送日内有会员已在其他停靠点成功推单，不能重复创单。",
                            sf_order_id=None,
                        )
                    )
                    continue
            if item.is_insured and item.goods_value_yuan is None:
                out.append(
                    SfSameCityPushItemResult(
                        stop_id=item.stop_id,
                        ok=False,
                        message="保价时须填写货值(元)。",
                        sf_order_id=None,
                    )
                )
                continue
            if not item.push_immediately and item.expect_delivery_at is None:
                out.append(
                    SfSameCityPushItemResult(
                        stop_id=item.stop_id,
                        ok=False,
                        message="非立即推单时须选择期望送达时间。",
                        sf_order_id=None,
                    )
                )
                continue
            if not item.push_immediately and item.expect_delivery_at is not None:
                edt = item.expect_delivery_at
                if edt.tzinfo is None:
                    edt = edt.replace(tzinfo=_SH)
                else:
                    edt = edt.astimezone(_SH)
                t_today = today_shanghai()
                if d < t_today and edt.date() < t_today:
                    out.append(
                        SfSameCityPushItemResult(
                            stop_id=item.stop_id,
                            ok=False,
                            message="所选业务日已早于今日（上海），期望送达日期须为今日或之后。",
                            sf_order_id=None,
                        )
                    )
                    continue
                if edt.timestamp() < time.time():
                    out.append(
                        SfSameCityPushItemResult(
                            stop_id=item.stop_id,
                            ok=False,
                            message="期望送达须晚于当前时间（上海）；请调整预约时间或使用立即推单。",
                            sf_order_id=None,
                        )
                    )
                    continue
            soid = f"OKF{d:%Y%m%d}{item.stop_id[:12]}{uuid.uuid4().hex[:8]}"
            if len(soid) > 64:
                soid = soid[:64]
            snap_preview: dict[str, Any] = item.model_dump(mode="json")
            snap_db: dict[str, Any] = snap_preview
            try:
                pld = _create_order_payload(
                    item,
                    shop_order_id=soid,
                    gset=gset,
                    store=store,
                    now_ts=now_ts,
                    delivery_date=d,
                )
                ff_mids: list[int] = []
                ff_oids: list[int] = []
                if agg_cur is not None:
                    for sl in agg_cur.sub_lines:
                        if sl.get("is_delivered"):
                            continue
                        if int(sl.get("units") or 0) <= 0:
                            continue
                        try:
                            ff_mids.append(int(sl["member_id"]))
                        except (KeyError, TypeError, ValueError):
                            pass
                    for sng in agg_cur.singles:
                        try:
                            ff_oids.append(int(sng["id"]))
                        except (KeyError, TypeError, ValueError):
                            pass
                snap_db = _sf_push_request_snapshot(
                    snap_preview,
                    pld,
                    gset=gset,
                    fulfillment_member_ids=ff_mids,
                    fulfillment_single_meal_order_ids=ff_oids,
                )
                res = httpc.create_order(
                    pld,
                    dev_id=int(gset.SF_OPEN_DEV_ID),
                    app_key=(gset.SF_OPEN_SECRET or "").strip(),
                )
                r = res.get("result")
                sfo, sfb = None, None
                if isinstance(r, dict):
                    sfo, sfb = r.get("sf_order_id"), r.get("sf_bill_id")
                row = SfSameCityPush(
                    store_id=sid,
                    delivery_date=d,
                    stop_id=item.stop_id,
                    shop_order_id=soid,
                    sf_order_id=str(sfo) if sfo is not None else None,
                    sf_bill_id=str(sfb) if sfb is not None else None,
                    error_code=0,
                    error_msg="",
                    request_snapshot=snap_db,
                    response_json=res if isinstance(res, dict) else None,
                )
                db.add(row)
                db.commit()
                agg_after = load_agg_for_stop_id(db, d, item.stop_id, store_id=sid)
                if agg_after is not None:
                    success_member_map[item.stop_id] = _member_ids_receiving_on_agg(db, agg_after)
                out.append(
                    SfSameCityPushItemResult(
                        stop_id=item.stop_id,
                        ok=True,
                        message="已提交顺丰",
                        sf_order_id=str(sfo) if sfo is not None else None,
                    )
                )
            except SfOpenApiError as e:
                db.rollback()
                _persist_fail(
                    db,
                    d,
                    item.stop_id,
                    soid,
                    snap_db,
                    int(e.error_code) if e.error_code is not None else -1,
                    str(e)[:1000],
                    store_id=sid,
                )
                out.append(
                    SfSameCityPushItemResult(
                        stop_id=item.stop_id, ok=False, message=str(e), sf_order_id=None
                    )
                )
            except Exception as e:
                db.rollback()
                _persist_fail(db, d, item.stop_id, soid, snap_db, -2, str(e)[:1000], store_id=sid)
                out.append(
                    SfSameCityPushItemResult(
                        stop_id=item.stop_id,
                        ok=False,
                        message=f"推单异常: {e!s}",
                        sf_order_id=None,
                    )
                )
    return SfSameCityPushOut(results=out)


def _persist_fail(
    db: Session,
    d: date,
    stop_id: str,
    shop_order_id: str,
    snap: dict,
    err_code: int,
    err_msg: str,
    *,
    store_id: int,
    push_kind: str = "delivery_sheet",
) -> None:
    row = SfSameCityPush(
        store_id=int(store_id),
        delivery_date=d,
        stop_id=stop_id,
        push_kind=(push_kind or "delivery_sheet").strip() or "delivery_sheet",
        shop_order_id=shop_order_id,
        error_code=err_code,
        error_msg=err_msg,
        request_snapshot=snap,
        response_json=None,
    )
    db.add(row)
    db.commit()


def cancel_sf_same_city_push(
    db: Session,
    *,
    push_id: int,
    cancel_reason: str | None = None,
) -> dict[str, Any]:
    """
    调用顺丰开放平台 ``POST …/cancelorder?sign=``，同步返回顺丰 JSON。

    同城开放平台约定示例字段（与三方封装一致）：``order_id`` + ``order_type``
    （``1``=顺丰订单号，``2``=商家订单号）、可选 ``cancel_code`` / ``cancel_reason``。
    """
    row = db.get(SfSameCityPush, push_id)
    if row is None:
        raise HTTPException(status_code=404, detail="推单记录不存在")
    st_row = db.get(Store, int(row.store_id)) if row.store_id else None
    tid = int(st_row.tenant_id) if st_row else int(get_settings().DEFAULT_TENANT_ID)
    gset = merged_sf_integration_namespace(db, tid)
    if not gset.SF_OPEN_DEV_ID or not (gset.SF_OPEN_SHOP_ID or "").strip() or not (
        gset.SF_OPEN_SECRET or ""
    ).strip():
        raise HTTPException(status_code=400, detail="请先在租户对接或 .env 配置 SF_OPEN_DEV_ID、SF_OPEN_SHOP_ID、SF_OPEN_SECRET")
    try:
        ec_int = int(row.error_code) if row.error_code is not None else None
    except (TypeError, ValueError):
        ec_int = None
    has_sf_id = bool((row.sf_order_id or "").strip())
    create_ok = ec_int == 0
    # 仅「明确创单成功」或「已有顺丰单号」才允许调顺丰 cancel（后者兼容异常/历史数据）
    if not create_ok and not has_sf_id:
        em = (row.error_msg or "").strip()
        bits = [
            "本条推单在系统中标记为「未成功创单」（error_code≠0），且未保存顺丰订单号，无法在顺丰侧取消。"
            " 常见原因：请求顺丰 createorder 时被拒绝或超时落库失败。"
        ]
        if row.error_code is not None:
            bits.append(f"落地 error_code={row.error_code}。")
        if em:
            bits.append(em[:300])
        raise HTTPException(status_code=400, detail=" ".join(bits))
    st = row.sf_callback_order_status
    if st is not None and int(st) in (2, 17, 22, 31):
        raise HTTPException(status_code=400, detail="当前顺丰回调状态已为取消、完结或取消中，如需核对请以顺丰控制台为准")
    sfo = (row.sf_order_id or "").strip()
    shop_oid = (row.shop_order_id or "").strip()
    if not sfo and not shop_oid:
        raise HTTPException(status_code=400, detail="缺少顺丰单号与商家订单号")
    reason = (cancel_reason or "").strip() or "商家发起取消"
    now_ts = int(time.time())
    dev_id = int(gset.SF_OPEN_DEV_ID)
    body: dict[str, Any] = {
        "cancel_code": 313,
        "cancel_reason": reason[:200],
        "dev_id": dev_id,
        "push_time": now_ts,
    }
    if sfo:
        body["order_id"] = sfo
        body["order_type"] = 1
    else:
        body["order_id"] = shop_oid[:64]
        body["order_type"] = 2
        body["shop_id"] = str(gset.SF_OPEN_SHOP_ID or "").strip()
        body["shop_type"] = int(gset.SF_OPEN_SHOP_TYPE or 1)
    httpc = SfOpenClient()
    try:
        res = httpc.cancel_order(
            body, dev_id=dev_id, app_key=(gset.SF_OPEN_SECRET or "").strip()
        )
    except SfOpenApiError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    row.sf_callback_order_status = 31
    row.merchant_cancel_requested_at = beijing_now_naive()
    row.last_callback_at = beijing_now_naive()
    row.last_callback_kind = "merchant_cancel"
    db.commit()

    if isinstance(res, dict):
        return {"message": "顺丰已受理取消", "sf_response": res}
    return {"message": "顺丰已受理取消", "sf_response": None}


def auto_push_sf_next_business_day_for_store(db: Session, *, store_id: int) -> SfSameCityPushOut | None:
    """
    夜间定时任务：向顺丰推送「次日」上海业务日、当前仍待推的停靠点（与手动推单同一套预览/合并逻辑）。
    门店须启用 ``sf_nightly_auto_push_enabled`` 且处于营业状态。
    """
    st = db.get(Store, int(store_id))
    if st is None or not st.is_active:
        return None
    if not bool(getattr(st, "sf_nightly_auto_push_enabled", False)):
        return None
    d = today_shanghai() + timedelta(days=1)
    preview = preview_sf_same_city(db, delivery_date=d, store_id=int(store_id))
    if not preview.sf_configured:
        logger.info("顺丰夜间自动推单跳过（未配置顺丰） store_id=%s", store_id)
        return None
    rows = [r for r in preview.rows if r.selected and not r.already_pushed]
    if not rows:
        logger.info("顺丰夜间自动推单跳过（无待推停靠点） store_id=%s date=%s", store_id, d)
        return None
    body = SfSameCityPushIn(delivery_date=d, rows=rows)
    return push_sf_same_city(db, body, store_id=int(store_id))


def run_sf_nightly_auto_push_for_all_stores(db: Session) -> None:
    """启用夜间推单的全部门店依次执行 ``auto_push_sf_next_business_day_for_store``。"""
    ids = list(
        db.scalars(
            select(Store.id).where(
                Store.is_active.is_(True),
                Store.sf_nightly_auto_push_enabled.is_(True),
            )
        ).all()
    )
    for sid in ids:
        sid_int = int(sid)
        try:
            auto_push_sf_next_business_day_for_store(db, store_id=sid_int)
        except HTTPException as e:
            logger.warning(
                "顺丰夜间自动推单跳过 store_id=%s detail=%s",
                sid_int,
                e.detail,
            )
        except ValueError as e:
            logger.warning("顺丰夜间自动推单跳过 store_id=%s err=%s", sid_int, e)
        except Exception:
            logger.exception("顺丰夜间自动推单失败 store_id=%s", sid_int)


def retry_sf_same_city_push_by_id(db: Session, *, push_id: int) -> SfSameCityPushItemResult:
    """监控页：对创单失败记录按当前大表数据重试单停靠点推单。"""
    row = db.get(SfSameCityPush, push_id)
    if row is None:
        raise HTTPException(status_code=404, detail="推单记录不存在")
    try:
        ec_int = int(row.error_code) if row.error_code is not None else -1
    except (TypeError, ValueError):
        ec_int = -1
    if ec_int == 0:
        raise HTTPException(status_code=400, detail="创单已成功，无需重试")
    sid = int(row.store_id)
    d = row.delivery_date
    if d is None:
        raise HTTPException(status_code=400, detail="记录缺少业务日")
    preview = preview_sf_same_city(db, delivery_date=d, store_id=sid)
    prow: SfSameCityPreviewRow | None = None
    for r in preview.rows:
        if r.stop_id == row.stop_id:
            prow = r
            break
    if prow is None:
        raise HTTPException(
            status_code=400,
            detail="当前业务日已无此停靠点待配送数据，请在配送大表核对或改用手动推单",
        )
    if prow.already_pushed:
        raise HTTPException(
            status_code=400,
            detail="该停靠点本日不可再推（本停靠点已成功创单，或同配送日内同一会员已在其他停靠点成功推单）。",
        )
    body = SfSameCityPushIn(delivery_date=d, rows=[prow])
    out = push_sf_same_city(db, body, store_id=sid)
    if not out.results:
        raise HTTPException(status_code=500, detail="重试无返回结果")
    return out.results[0]


def push_single_meal_retail_to_sf(db: Session, *, order_id: int, store_id: int) -> SfSameCityPushItemResult:
    """
    订单管理：单次点餐直推顺丰 ``createorder``。

    使用门店上单独配置的 ``sf_retail_push_shop_id``（及可选 shop_type），
    与租户对接里用于智能配送大表推单的顺丰店铺编号互不干扰；dev_id/secret/取件信息仍走租户合并配置。
    """
    order = db.get(SingleMealOrder, int(order_id))
    if order is None or int(order.store_id) != int(store_id):
        raise ValueError("订单不存在或不属于当前门店")
    if (order.pay_status or "").strip() != "已支付":
        raise ValueError("仅已支付订单可推送顺丰")
    if bool(order.store_pickup):
        raise ValueError("门店自提订单无需发顺丰到家，可使用「门店自配送」指派配送员")
    if not order.member_address_id:
        raise ValueError("订单无收货地址，无法推顺丰")

    if (order.fulfillment_status or "").strip() != "pending":
        raise ValueError("仅「待发货」订单可推送顺丰（已在配送中或已完成的订单请勿重复操作）")

    st_row = db.get(Store, int(store_id))
    if not st_row:
        raise ValueError("门店不存在")
    retail_shop = (getattr(st_row, "sf_retail_push_shop_id", None) or "").strip()
    if not retail_shop:
        raise ValueError(
            "请先在「门店设置」填写「零售推顺丰店铺ID」（与智能配送大表使用的顺丰店铺编号区分）"
        )

    tid = int(st_row.tenant_id)
    gset = merged_sf_integration_namespace(db, tid)
    if not gset.SF_OPEN_DEV_ID or not (gset.SF_OPEN_SECRET or "").strip():
        raise ValueError("请先在租户对接或环境变量配置顺丰开发者 dev_id 与 secret")
    if not (gset.SF_PICKUP_PHONE or "").strip() or not (gset.SF_PICKUP_ADDRESS or "").strip():
        raise ValueError("请配置顺丰取件电话与取件地址（租户对接或 .env）")

    gset = copy(gset)
    gset.SF_OPEN_SHOP_ID = retail_shop
    if getattr(st_row, "sf_retail_push_shop_type", None) is not None:
        gset.SF_OPEN_SHOP_TYPE = int(st_row.sf_retail_push_shop_type)

    addr = db.get(MemberAddress, int(order.member_address_id))
    if not addr:
        raise ValueError("收货地址不存在")

    dish = db.get(MenuDish, int(order.dish_id))
    dish_name = ((dish.name or "餐品").strip() if dish else None) or "餐品"

    base = get_settings()
    kg_unit = float(getattr(base, "SF_KG_PER_MEAL_UNIT", None) or 0.5)
    weight_kg = max(0.01, kg_unit * max(1, int(order.quantity or 1)))

    recv_lng = float(addr.lng) if addr.lng is not None else None
    recv_lat = float(addr.lat) if addr.lat is not None else None

    nm_map = delivery_region_name_map(
        db, {int(addr.delivery_region_id)} if addr.delivery_region_id else set()
    )
    ar_lbl = routing_area_label(addr, nm_map)

    recv_phone = (addr.contact_phone or "").strip()
    recv_name = (addr.contact_name or "").strip()

    stop_id = f"retail-smo-{order.id}"
    d = order.delivery_date
    if d is None:
        raise ValueError("订单缺少供餐日")

    if _has_success(db, d, stop_id):
        raise ValueError("该订单在供餐日已成功创建顺丰单，请勿重复推送（可在顺丰订单监控核对）")

    row_sfc = SfSameCityRowBase(
        stop_id=stop_id,
        pickup_phone=(gset.SF_PICKUP_PHONE or "")[:20],
        map_location_text=(addr.map_location_text or "").strip(),
        door_detail=(addr.door_detail or "").strip(),
        recv_address=(addr.map_location_text or "").strip(),
        recv_building=(addr.door_detail or "").strip(),
        recv_name=recv_name or "收件人",
        recv_phone=recv_phone,
        recv_lng=recv_lng,
        recv_lat=recv_lat,
        product_category=dish_name[:80],
        weight_kg=weight_kg,
        push_immediately=True,
        expect_delivery_at=None,
        remark=f"单次点餐 #{order.id} {ar_lbl}".strip()[:2000],
        is_direct=False,
        vehicle_type=(gset.SF_DEFAULT_VEHICLE_TYPE or "小轿车").strip(),
        is_insured=False,
        goods_value_yuan=None,
        subscription_pending_units=0,
        single_meal_count=max(1, int(order.quantity or 1)),
    )

    store_cfg = get_store_config(db, store_id=int(store_id))

    class _StoreWrap:
        __slots__ = ("store_name", "store_lng", "store_lat")

        def __init__(self, name: str | None, lng: float | None, lat: float | None):
            self.store_name = name
            self.store_lng = lng
            self.store_lat = lat

    store = _StoreWrap(store_cfg.store_name, store_cfg.store_lng, store_cfg.store_lat)

    now_ts = int(time.time())
    soid = f"OKFSMO{order.id}{uuid.uuid4().hex[:10]}"
    if len(soid) > 64:
        soid = soid[:64]

    snap_preview: dict[str, Any] = row_sfc.model_dump(mode="json")
    snap_db: dict[str, Any] = snap_preview
    httpc = SfOpenClient()

    with _sf_push_serial_lock(db, store_id=int(store_id), d=d):
        if _has_success(db, d, stop_id):
            raise ValueError("该订单在供餐日已成功创建顺丰单，请勿重复推送")

        pld: dict[str, Any] | None = None
        try:
            pld = _create_order_payload(
                row_sfc,
                shop_order_id=soid,
                gset=gset,
                store=store,
                now_ts=now_ts,
                delivery_date=d,
            )
            snap_db = _sf_push_request_snapshot(
                snap_preview,
                pld,
                gset=gset,
                fulfillment_single_meal_order_ids=[int(order.id)],
            )
            res = httpc.create_order(
                pld,
                dev_id=int(gset.SF_OPEN_DEV_ID),
                app_key=(gset.SF_OPEN_SECRET or "").strip(),
            )
            r = res.get("result")
            sfo, sfb = None, None
            if isinstance(r, dict):
                sfo, sfb = r.get("sf_order_id"), r.get("sf_bill_id")
            row_db = SfSameCityPush(
                store_id=int(store_id),
                delivery_date=d,
                stop_id=stop_id,
                push_kind=_SF_PUSH_KIND_SINGLE_MEAL_RETAIL,
                shop_order_id=soid,
                sf_order_id=str(sfo) if sfo is not None else None,
                sf_bill_id=str(sfb) if sfb is not None else None,
                error_code=0,
                error_msg="",
                request_snapshot=snap_db,
                response_json=res if isinstance(res, dict) else None,
            )
            order.fulfillment_status = "accepted"
            db.add(row_db)
            db.add(order)
            db.commit()
            return SfSameCityPushItemResult(
                stop_id=stop_id,
                ok=True,
                message="已提交顺丰（单次零售，独立顺丰店铺）",
                sf_order_id=str(sfo) if sfo is not None else None,
            )
        except SfOpenApiError as e:
            db.rollback()
            snap_fail = (
                _sf_push_request_snapshot(snap_preview, pld, gset=gset)
                if pld is not None
                else snap_preview
            )
            _persist_fail(
                db,
                d,
                stop_id,
                soid,
                snap_fail,
                int(e.error_code) if e.error_code is not None else -1,
                str(e)[:1000],
                store_id=int(store_id),
                push_kind=_SF_PUSH_KIND_SINGLE_MEAL_RETAIL,
            )
            raise ValueError(str(e)) from e
        except Exception as e:
            db.rollback()
            snap_fail = (
                _sf_push_request_snapshot(snap_preview, pld, gset=gset)
                if pld is not None
                else snap_preview
            )
            _persist_fail(
                db, d, stop_id, soid, snap_fail, -2, str(e)[:1000], store_id=int(store_id),
                push_kind=_SF_PUSH_KIND_SINGLE_MEAL_RETAIL,
            )
            raise ValueError(f"推单异常: {e!s}") from e
