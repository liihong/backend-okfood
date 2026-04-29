"""
顺丰同城推单：与配送大表、单点餐同合并为停靠点，预览 14+ 列模板，提交 `createorder`。

签名为 ``json + && + dev_id + && + appKey`` 再 MD5→Hex→Base64（与常见 openic Java 样例一致）。
"""

from __future__ import annotations

import hashlib
import math
import re
import time
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.timeutil import today_shanghai
from app.models.delivery_region import DeliveryRegion
from app.models.member import Member
from app.models.member_address import MemberAddress
from app.models.menu_dish import MenuDish
from app.models.sf_same_city_push import SfSameCityPush
from app.models.single_meal_order import SingleMealOrder
from app.services.courier_service import eligible_members_for_delivery
from app.services.delivery_sheet_service import (
    _filter_members_by_phone_hint,
    _member_line_remarks,
    _resolve_delivery_line,
    build_delivery_sheet,
)
from app.services.member_address_service import delivery_region_name_map, routing_area_label
from app.services.member_service import effective_daily_meal_units
from app.services.sf_open import sign as sf_sign_mod
from app.services.sf_open.client import SfOpenApiError, SfOpenClient
from app.services.store_config_service import get_store_config
from app.schemas.admin import (
    SfSameCityPreviewOut,
    SfSameCityPreviewRow,
    SfSameCityPushIn,
    SfSameCityPushItemResult,
    SfSameCityPushOut,
    SfSameCityRowBase,
)

_SH = ZoneInfo("Asia/Shanghai")


def _sf_push_request_snapshot(
    preview_row: dict[str, Any],
    pld: dict[str, Any],
    *,
    gset: Any,
) -> dict[str, Any]:
    """落库：预览行 + 实际发往顺丰的报文（与签名同源 canonical JSON）。"""
    canon = sf_sign_mod._canonical_json(pld)
    return {
        "preview_row": preview_row,
        "shop_id": str(gset.SF_OPEN_SHOP_ID or "").strip(),
        "dev_id": int(gset.SF_OPEN_DEV_ID),
        "product_type": int(gset.SF_DEFAULT_PRODUCT_TYPE or 1),
        "vehicle_type_code": int(gset.SF_VEHICLE_TYPE_CODE or 1),
        "sf_create_order": pld,
        "sf_canonical_json": canon,
    }


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
) -> dict[str, _Agg]:
    """大表所有到家停靠点 + 单次餐合并。"""
    sheet = build_delivery_sheet(db, delivery_date=d, area=area_key, phone=phone_key)
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
    db: Session, a: _Agg, d: date, default_by_id: dict[int, MemberAddress], m_by_id: dict[int, Member]
) -> SfSameCityPreviewRow:
    s = get_settings()
    p_phone = (s.SF_PICKUP_PHONE or "").strip()
    sub = sum(
        int(x.get("units") or 0) for x in a.sub_lines if not x.get("is_delivered")
    )
    sq = sum(int(x.get("qty") or 0) for x in a.singles)
    total = max(1, sub + sq)
    wkg = max(0.1, float(s.SF_KG_PER_MEAL_UNIT) * float(total))

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

    # 与会员地址表一致：收货大地址=地图选点文案；门牌=楼栋/门牌（无则回退整段详细地址）
    if maddr:
        recv_addr = (maddr.map_location_text or "").strip()
        recv_build = (maddr.door_detail or "").strip()
        if not recv_build:
            recv_build = (maddr.detail_address or "").strip()
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

    pushed = _has_success(db, d, a.stop_id)
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
        product_category=(s.SF_PRODUCT_CATEGORY_LABEL or "餐品").strip(),
        weight_kg=round(wkg, 2),
        push_immediately=True,
        expect_delivery_at=expect_at_default,
        remark=rmk_s,
        is_direct=False,
        vehicle_type=(s.SF_DEFAULT_VEHICLE_TYPE or "小轿车").strip(),
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


def load_agg_for_stop_id(db: Session, d: date, stop_id: str) -> _Agg | None:
    """
    按业务日与停靠点 id（与顺丰预览/推单同源）解析聚合行；不加片区/手机筛选，
    与「全量大表 + 单次点餐到家」口径一致。
    """
    members, default_by_id = eligible_members_for_delivery(db, delivery_date=d, delivery_region_id=None)
    mlist = list(members)
    ags = _build_aggs(db, d, None, None, mlist, default_by_id)
    return ags.get(stop_id)


def preview_sf_same_city(
    db: Session,
    *,
    delivery_date: date | None = None,
    area: str | None = None,
    phone: str | None = None,
) -> SfSameCityPreviewOut:
    d = delivery_date or today_shanghai()
    akey = (area or "").strip() or None
    pkey = (phone or "").strip() or None
    reg_id = None
    if akey:
        rid = db.scalar(select(DeliveryRegion.id).where(DeliveryRegion.name == akey))
        if rid is not None:
            reg_id = int(rid)
    members, default_by_id = eligible_members_for_delivery(
        db, delivery_date=d, delivery_region_id=reg_id
    )
    mlist = list(members)
    if pkey:
        mlist = _filter_members_by_phone_hint(mlist, pkey)
    m_by_id = {int(m.id): m for m in mlist}

    ags = _build_aggs(db, d, akey, pkey, mlist, default_by_id)
    gset = get_settings()
    rows: list[SfSameCityPreviewRow] = [
        _agg_to_row(db, ag, d, default_by_id, m_by_id)
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


def push_sf_same_city(db: Session, body: SfSameCityPushIn) -> SfSameCityPushOut:
    gset = get_settings()
    if not gset.SF_OPEN_DEV_ID or not (gset.SF_OPEN_SHOP_ID or "").strip() or not (gset.SF_OPEN_SECRET or "").strip():
        raise ValueError("请先在 .env 配置 SF_OPEN_DEV_ID、SF_OPEN_SHOP_ID、SF_OPEN_SECRET")
    if not (gset.SF_PICKUP_PHONE or "").strip() or not (gset.SF_PICKUP_ADDRESS or "").strip():
        raise ValueError("请配置 .env 中 SF_PICKUP_PHONE 与 SF_PICKUP_ADDRESS。")
    d = body.delivery_date
    store = get_store_config(db)
    out: list[SfSameCityPushItemResult] = []
    now_ts = int(time.time())
    httpc = SfOpenClient()
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
                    stop_id=item.stop_id, ok=False, message="本停靠点本日已推单成功。", sf_order_id=None
                )
            )
            continue
        if item.is_insured and item.goods_value_yuan is None:
            out.append(
                SfSameCityPushItemResult(
                    stop_id=item.stop_id, ok=False, message="保价时须填写货值(元)。", sf_order_id=None
                )
            )
            continue
        if not item.push_immediately and item.expect_delivery_at is None:
            out.append(
                SfSameCityPushItemResult(
                    stop_id=item.stop_id, ok=False, message="非立即推单时须选择期望送达时间。", sf_order_id=None
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
                item, shop_order_id=soid, gset=gset, store=store, now_ts=now_ts
            )
            snap_db = _sf_push_request_snapshot(snap_preview, pld, gset=gset)
            res = httpc.create_order(
                pld, dev_id=int(gset.SF_OPEN_DEV_ID), app_key=(gset.SF_OPEN_SECRET or "").strip()
            )
            r = res.get("result")
            sfo, sfb = None, None
            if isinstance(r, dict):
                sfo, sfb = r.get("sf_order_id"), r.get("sf_bill_id")
            row = SfSameCityPush(
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
            )
            out.append(
                SfSameCityPushItemResult(stop_id=item.stop_id, ok=False, message=str(e), sf_order_id=None)
            )
        except Exception as e:
            db.rollback()
            _persist_fail(db, d, item.stop_id, soid, snap_db, -2, str(e)[:1000])
            out.append(
                SfSameCityPushItemResult(
                    stop_id=item.stop_id, ok=False, message=f"推单异常: {e!s}", sf_order_id=None
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
) -> None:
    row = SfSameCityPush(
        delivery_date=d,
        stop_id=stop_id,
        shop_order_id=shop_order_id,
        error_code=err_code,
        error_msg=err_msg,
        request_snapshot=snap,
        response_json=None,
    )
    db.add(row)
    db.commit()
