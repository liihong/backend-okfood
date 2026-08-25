"""
将租户 3 导入会员的默认地址统一为「河南省许昌市禹州市」前缀，
并用高德（city=禹州市）补/校正经纬度；有坐标时再逆地理核对是否落在禹州。
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.balance_log import BalanceLog
from app.models.member import Member
from app.services.member.member_address_service import get_default_address
from app.services.shared import amap
from app.services.shared.region_assignment import assign_region_for_coords

TENANT_ID = 3
PCA = "河南省许昌市禹州市"
CITY = "禹州市"
# 禹州大致范围，用于发现被编到许昌市区等地的坐标
YU_LNG = (113.28, 113.68)
YU_LAT = (33.98, 34.32)
STORE_LNG = 113.485717
STORE_LAT = 34.149193
OPERATOR = "tenant3_xlsx_import"

_PCA_PREFIXES = (
    "河南省许昌市禹州市",
    "河南省禹州市",
    "许昌市禹州市",
    "河南省许昌市",
    "禹州市",
    "许昌市",
)


def _strip_pca(text: str) -> str:
    t = re.sub(r"[\r\n]+", " ", (text or "").strip())
    t = re.sub(r"\s+", " ", t)
    changed = True
    while t and changed:
        changed = False
        for pref in _PCA_PREFIXES:
            if t.startswith(pref):
                t = t[len(pref) :].lstrip(" ，,")
                changed = True
                break
    return t.strip()


def _in_yuzhou(lng: float | None, lat: float | None) -> bool:
    if lng is None or lat is None:
        return False
    return YU_LNG[0] <= float(lng) <= YU_LNG[1] and YU_LAT[0] <= float(lat) <= YU_LAT[1]


def _pca_from_regeo(lng: float, lat: float) -> str:
    snap = amap.fetch_regeo_snapshot(lng, lat)
    line = (snap.pca_prefix_line or "").strip() if snap else ""
    if "禹州" in line:
        return line
    return PCA


def _compose(pca: str, core: str) -> str:
    core = (core or "").strip()
    if not core:
        return pca[:500]
    if core.startswith(pca):
        return core[:500]
    return f"{pca} {core}".strip()[:500]


def _imported_member_ids(db) -> list[int]:
    ids = db.scalars(
        select(BalanceLog.member_id).where(BalanceLog.operator == OPERATOR).distinct()
    ).all()
    return [int(x) for x in ids if x is not None]


def backfill(db, *, geocode: bool, sleep_s: float) -> dict[str, int]:
    """回填导入会员默认地址的省市区前缀与坐标。"""
    stats = {
        "total": 0,
        "prefixed": 0,
        "geocoded": 0,
        "reused_coords": 0,
        "used_store": 0,
        "no_coords": 0,
        "skipped_ok": 0,
        "missing_addr": 0,
    }
    geo_cache: dict[str, tuple[float, float] | None] = {}
    for mid in _imported_member_ids(db):
        member = db.get(Member, mid)
        if member is None or member.deleted_at is not None or int(member.tenant_id) != TENANT_ID:
            continue
        addr = get_default_address(db, mid)
        if addr is None:
            stats["missing_addr"] += 1
            continue
        stats["total"] += 1
        raw = (addr.map_location_text or "").strip()
        core = _strip_pca(raw)
        if not core and addr.door_detail:
            core = _strip_pca(addr.door_detail)
        pickup = bool(member.store_pickup) or core in ("自提", "自取")

        lng = float(addr.lng) if addr.lng is not None else None
        lat = float(addr.lat) if addr.lat is not None else None
        already_ok = raw.startswith(PCA) and _in_yuzhou(lng, lat)
        if already_ok:
            stats["skipped_ok"] += 1
            continue

        new_lng, new_lat = lng, lat
        if pickup and (new_lng is None or not _in_yuzhou(new_lng, new_lat)):
            new_lng, new_lat = STORE_LNG, STORE_LAT
            stats["used_store"] += 1
        elif geocode and (new_lng is None or not _in_yuzhou(new_lng, new_lat)):
            query = core if core else PCA
            if PCA not in query:
                query = f"{PCA}{query}"
            if query not in geo_cache:
                geo_cache[query] = amap.geocode_address(query, city=CITY)
                time.sleep(sleep_s)
            coords = geo_cache[query]
            if coords:
                new_lng, new_lat = coords[0], coords[1]
                stats["geocoded"] += 1
            else:
                stats["no_coords"] += 1
        elif _in_yuzhou(new_lng, new_lat):
            stats["reused_coords"] += 1

        pca = PCA
        if new_lng is not None and new_lat is not None and geocode:
            pca = _pca_from_regeo(new_lng, new_lat)
            time.sleep(sleep_s)

        addr.map_location_text = _compose(pca, core if core else ("自提" if pickup else ""))
        if new_lng is not None and new_lat is not None:
            addr.lng = new_lng
            addr.lat = new_lat
            region = assign_region_for_coords(db, new_lng, new_lat, tenant_id=TENANT_ID)
            addr.delivery_region_id = int(region.id) if region else None
        stats["prefixed"] += 1

    db.commit()
    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description="回填租户3导入地址的禹州省市区与坐标")
    parser.add_argument("--no-geocode", action="store_true", help="只改文案前缀，不请求高德")
    parser.add_argument("--sleep", type=float, default=0.12, help="高德请求间隔秒")
    args = parser.parse_args()
    db = SessionLocal()
    try:
        stats = backfill(db, geocode=not args.no_geocode, sleep_s=max(0.0, args.sleep))
        print(
            "完成："
            f"导入地址 {stats['total']}，"
            f"已规范 {stats['prefixed']}，"
            f"原本合格跳过 {stats['skipped_ok']}，"
            f"新编码 {stats['geocoded']}，"
            f"沿用原坐标 {stats['reused_coords']}，"
            f"自提用门店点 {stats['used_store']}，"
            f"仍无坐标 {stats['no_coords']}，"
            f"无地址行 {stats['missing_addr']}"
        )
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
