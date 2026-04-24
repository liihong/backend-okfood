#!/usr/bin/env python3
"""
从配送名单 CSV 生成 members + member_addresses 的 INSERT SQL。
地理编码：高德 v3/geocode/geo（GCJ-02），与 app/services/amap.py 一致。

用法（在项目根目录 backend/ 下）:
  set AMAP_KEY=你的Web服务Key
  python scripts/csv_members_to_sql.py "tests/4.20-4.25配送数据 - 4月25日周六.csv" -o sql/generated_members_from_csv.sql

依赖环境变量:
  AMAP_KEY — 未配置时 lng/lat 输出为 NULL，仍生成 SQL。

说明:
  - 同一规范化手机号 → 一条 members；可对应多条 member_addresses。
  - 手机号相同且配送地址（规范化后）相同 → 合并为一条地址，累加 daily_meal_units（并写入 members.daily_meal_units 为各地址合并后的合计，上限 50）。
  - 无有效手机号时：按「姓名（规范化）」归并为同一会员，并分配占位号 17000020001 起（不同姓名 = 不同会员）。
  - 「先不送的」区块：delivery_deferred=1 且 is_active=0。
  - 套餐列「自提」或地址为纯「自提/店内自取」类：该地址视为 store_pickup；会员级 store_pickup=1 仅当所有地址均为自提类。
  - Excel 日期序列（如 46131）会尝试转为日期。
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from io import StringIO
from pathlib import Path

# 保证可加载 app.core.config（读取 .env 中的 AMAP_KEY）
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

try:
    from app.core.config import settings
except ImportError:
    settings = None  # type: ignore

import httpx


def _sql_str(s: str) -> str:
    return "'" + s.replace("\\", "\\\\").replace("'", "''") + "'"


def _sql_decimal8(x: float) -> str:
    d = Decimal(str(round(x, 8)))
    return format(d, "f")


def _normalize_phone(raw: str) -> str | None:
    if raw is None:
        return None
    t = raw.strip().replace(" ", "").replace("-", "")
    if not t or t in ("无", "暂无", "—", "-"):
        return None
    if re.fullmatch(r"1\d{10}", t):
        return t
    if re.fullmatch(r"\d{10}", t):
        return t
    if re.fullmatch(r"\d{11,12}", t):
        return t[:11] if len(t) >= 11 else t
    return None


def _normalize_name(name: str) -> str:
    return re.sub(r"\s+", " ", (name or "").strip())


def _normalize_detail_address(addr: str) -> str:
    s = (addr or "").strip().replace("\r\n", "\n").replace("\r", "\n")
    s = re.sub(r"\s+", " ", s.replace("\n", " "))
    return s.strip()


def _parse_int(raw: str) -> int | None:
    if raw is None:
        return None
    t = str(raw).strip()
    if not t:
        return None
    try:
        return int(float(t))
    except ValueError:
        return None


def _parse_start_date(raw: str) -> datetime | None:
    if raw is None:
        return None
    t = str(raw).strip()
    if not t:
        return None
    for fmt in ("%Y/%m/%d", "%Y-%m-%d"):
        try:
            return datetime.strptime(t, fmt)
        except ValueError:
            continue
    try:
        n = float(t)
        if 30000 <= n <= 60000:
            base = datetime(1899, 12, 30)
            return base + timedelta(days=int(n))
    except ValueError:
        pass
    return None


def _merge_remarks(*parts: str) -> str:
    out: list[str] = []
    for p in parts:
        if not p:
            continue
        s = str(p).strip()
        if not s:
            continue
        s = re.sub(r"\s+", " ", s.replace("\n", " ").replace("\r", " "))
        if s not in out:
            out.append(s)
    return " | ".join(out)


def _plan_type(raw: str) -> str | None:
    if not raw:
        return None
    t = str(raw).strip()
    if t in ("周卡", "月卡", "次卡"):
        return t
    if t == "自提":
        return None
    return None


def _infer_plan_type_fallback(total: int | None, used: int | None, balance: int | None) -> str:
    if total is not None and total >= 20:
        return "月卡"
    return "周卡"


def _daily_meal_units_from_text(*texts: str) -> int:
    for tx in texts:
        if not tx:
            continue
        m = re.search(r"送\s*(\d+)\s*份", tx)
        if m:
            n = int(m.group(1))
            if 1 <= n <= 50:
                return n
    return 1


def _is_store_pickup_address(addr: str, plan_col: str) -> bool:
    a = (addr or "").strip()
    p = (plan_col or "").strip()
    if p == "自提":
        return True
    if a in ("自提", "店内自取", "门店自取"):
        return True
    if "店内自取" in a and len(a) <= 20:
        return True
    return False


def _geocode(amap_key: str, address: str) -> tuple[float, float] | None:
    line = address.strip().replace("\n", " ").replace("\r", " ")
    if not line:
        return None
    if "新乡" not in line and "河南" not in line:
        line = "河南省新乡市" + line
    if not amap_key.strip():
        return None
    try:
        with httpx.Client(timeout=15.0) as client:
            r = client.get(
                "https://restapi.amap.com/v3/geocode/geo",
                params={"address": line, "key": amap_key.strip()},
            )
            r.raise_for_status()
            data = r.json()
    except Exception:
        return None
    if str(data.get("status")) != "1":
        return None
    geos = data.get("geocodes") or []
    if not geos:
        return None
    loc = (geos[0] or {}).get("location") or ""
    parts = str(loc).split(",")
    if len(parts) != 2:
        return None
    try:
        return float(parts[0]), float(parts[1])
    except ValueError:
        return None


@dataclass
class MemberRow:
    name: str
    phone_raw: str
    detail_address: str
    plan_type: str
    balance: int
    meal_quota_total: int
    daily_meal_units: int
    delivery_start: datetime | None
    remarks: str
    delivery_deferred: bool
    store_pickup: bool
    geocode_query: str
    source_line: int = 0


@dataclass
class MergedAddress:
    """同一会员下、规范化地址相同的多行合并结果。"""
    detail_display: str
    addr_norm: str
    daily_meal_units: int
    remarks: str
    store_pickup: bool
    contact_names: list[str] = field(default_factory=list)
    min_source_line: int = 0


@dataclass
class AggregatedMember:
    phone: str
    name: str
    member_remarks: str
    balance: int
    daily_meal_units: int
    meal_quota_total: int
    plan_type: str | None
    is_active: int
    delivery_start: datetime | None
    delivery_deferred: int
    store_pickup: int
    created_at: datetime
    addresses: list[MergedAddress] = field(default_factory=list)


def _read_csv_text(path: Path) -> str:
    data = path.read_bytes()
    for enc in ("utf-8-sig", "utf-8", "gbk", "cp936"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def _iter_csv_rows(path: Path):
    text = _read_csv_text(path)
    reader = csv.DictReader(StringIO(text))
    for i, row in enumerate(reader, start=2):
        yield i, row


def _should_skip_row(row: dict[str, str]) -> tuple[bool, bool | None]:
    seq = (row.get("序号") or "").strip()
    name = (row.get("名称") or "").strip()
    phone_raw = (row.get("电话") or "").strip()
    addr = (row.get("地址") or "").strip()
    plan = (row.get("套餐") or "").strip()

    if seq == "先不送的" or name == "先不送的" or seq.startswith("先不送"):
        return True, True
    if name.startswith("方向：") or name.startswith("方向:"):
        return True, False
    if "次数已更新" in (row.get("套餐") or "") + (row.get("备注") or ""):
        return True, None
    if not name and not phone_raw and not addr and not plan:
        return True, None

    if not name or not addr or not plan:
        return True, None

    if _normalize_phone(phone_raw) is None and phone_raw not in ("无", "") and not re.search(r"\d", phone_raw):
        return True, None

    return False, None


def collect_member_rows(path: Path) -> list[MemberRow]:
    rows: list[MemberRow] = []
    in_deferred = False
    for line_no, row in _iter_csv_rows(path):
        skip, def_new = _should_skip_row(row)
        if def_new is not None:
            in_deferred = def_new
        if skip:
            continue

        name = (row.get("名称") or "").strip()
        phone_raw = (row.get("电话") or "").strip()
        addr = (row.get("地址") or "").strip()
        note1 = (row.get("特殊备注") or "").strip()
        plan_col = (row.get("套餐") or "").strip()
        total = _parse_int(row.get("套餐总次数") or "")
        used = _parse_int(row.get("已用次数") or "")
        balance = _parse_int(row.get("剩余次数") or "")
        renew = (row.get("续卡时间") or "").strip()
        note2 = (row.get("备注") or "").strip()

        if balance is None:
            balance = 0
        if total is None:
            total = 0

        pt = _plan_type(plan_col)
        if pt is None:
            pt = _infer_plan_type_fallback(total, used, balance)

        start = _parse_start_date(row.get("开始日期") or "")
        daily = _daily_meal_units_from_text(note1, note2, addr)
        store_pu = _is_store_pickup_address(addr, plan_col)
        remarks = _merge_remarks(note1, renew, note2)

        geo_q = addr.strip().replace("\n", " ").replace("\r", " ")
        rows.append(
            MemberRow(
                name=name,
                phone_raw=phone_raw,
                detail_address=addr,
                plan_type=pt,
                balance=balance,
                meal_quota_total=total,
                daily_meal_units=daily,
                delivery_start=start,
                remarks=remarks,
                delivery_deferred=in_deferred,
                store_pickup=store_pu,
                geocode_query=geo_q,
                source_line=line_no,
            )
        )
    return rows


def _member_bucket_key(r: MemberRow) -> tuple[str, str]:
    """(kind, key)：kind 为 'p' 表示真实手机，'n' 表示无手机按姓名归并。"""
    p = _normalize_phone(r.phone_raw)
    if p is not None:
        return ("p", p)
    return ("n", _normalize_name(r.name))


def _assign_placeholder_phones(
    groups: dict[tuple[str, str], list[MemberRow]],
) -> dict[tuple[str, str], str]:
    """为 kind=='n' 的分组分配占位手机号。"""
    out: dict[tuple[str, str], str] = {}
    synth = 17000020001
    for key in sorted(groups.keys(), key=lambda k: (k[0], k[1])):
        kind, _ = key
        if kind == "n":
            out[key] = str(synth)
            synth += 1
    return out


def aggregate_members(raw_rows: list[MemberRow]) -> list[AggregatedMember]:
    groups: dict[tuple[str, str], list[MemberRow]] = {}
    for r in raw_rows:
        k = _member_bucket_key(r)
        groups.setdefault(k, []).append(r)

    placeholders = _assign_placeholder_phones(groups)
    result: list[AggregatedMember] = []

    for key in sorted(groups.keys(), key=lambda k: (k[0], k[1])):
        kind, _ident = key
        rows = groups[key]
        rows.sort(key=lambda x: x.source_line)

        if kind == "p":
            phone = _ident
        else:
            phone = placeholders[key]

        # 会员级：balance / meal_quota 取 max，避免同一人在多行重复填剩余次数被加总
        balance = max(r.balance for r in rows)
        meal_quota_total = max(r.meal_quota_total for r in rows)
        plan_type = rows[0].plan_type
        deferred = 1 if any(r.delivery_deferred for r in rows) else 0
        is_active = 0 if deferred else 1

        starts = [r.delivery_start for r in rows if r.delivery_start is not None]
        delivery_start = min(starts) if starts else None
        created = delivery_start or datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

        name_primary = _normalize_name(rows[0].name)
        all_names = []
        for r in rows:
            nn = _normalize_name(r.name)
            if nn and nn not in all_names:
                all_names.append(nn)
        display_name = name_primary
        extra_names = [n for n in all_names if n != display_name]
        member_remarks_parts: list[str] = [r.remarks for r in rows if r.remarks]
        if extra_names:
            member_remarks_parts.append("【表格别名】" + " | ".join(extra_names))
        member_remarks = _merge_remarks(*member_remarks_parts)
        if kind == "n":
            member_remarks = _merge_remarks(member_remarks, "【导入生成占位手机号】原表电话无效或为空")

        # 按规范化地址合并
        addr_map: dict[str, MergedAddress] = {}
        for r in rows:
            an = _normalize_detail_address(r.detail_address)
            if not an:
                continue
            disp = r.detail_address.strip().replace("\r\n", "\n").replace("\r", "\n")
            disp_one = re.sub(r"\s+", " ", disp.replace("\n", " ")).strip()
            cn = _normalize_name(r.name)
            if an not in addr_map:
                addr_map[an] = MergedAddress(
                    detail_display=disp_one,
                    addr_norm=an,
                    daily_meal_units=r.daily_meal_units,
                    remarks=r.remarks,
                    store_pickup=r.store_pickup,
                    contact_names=[cn] if cn else [],
                    min_source_line=r.source_line,
                )
            else:
                m = addr_map[an]
                m.daily_meal_units += r.daily_meal_units
                m.remarks = _merge_remarks(m.remarks, r.remarks)
                m.store_pickup = m.store_pickup or r.store_pickup
                m.min_source_line = min(m.min_source_line, r.source_line)
                if cn and cn not in m.contact_names:
                    m.contact_names.append(cn)
                if len(disp_one) > len(m.detail_display):
                    m.detail_display = disp_one

        for m in addr_map.values():
            m.daily_meal_units = min(50, max(1, m.daily_meal_units))

        addresses = sorted(addr_map.values(), key=lambda a: (a.min_source_line, a.addr_norm))
        total_units = sum(a.daily_meal_units for a in addresses)
        total_units = min(50, max(1, total_units))

        member_store_pickup = 1 if addresses and all(a.store_pickup for a in addresses) else 0

        result.append(
            AggregatedMember(
                phone=phone,
                name=display_name,
                member_remarks=member_remarks,
                balance=balance,
                daily_meal_units=total_units,
                meal_quota_total=meal_quota_total,
                plan_type=plan_type,
                is_active=is_active,
                delivery_start=delivery_start,
                delivery_deferred=deferred,
                store_pickup=member_store_pickup,
                created_at=created,
                addresses=addresses,
            )
        )

    return result


def emit_sql(
    members: list[AggregatedMember],
    amap_key: str,
    sleep_s: float,
    fh,
) -> list[str]:
    failures: list[str] = []
    fh.write(
        """-- 由 scripts/csv_members_to_sql.py 生成；执行前请确认是否清空 members / member_addresses
SET NAMES utf8mb4;

"""
    )
    for m in members:
        pt_sql = "NULL" if m.plan_type is None else _sql_str(m.plan_type)
        ds_sql = "NULL" if m.delivery_start is None else _sql_str(m.delivery_start.strftime("%Y-%m-%d"))
        created_sql = _sql_str(m.created_at.strftime("%Y-%m-%d %H:%M:%S"))
        rem_m = _sql_str(m.member_remarks)

        fh.write(
            f"""INSERT INTO `members` (
  `phone`, `name`, `wechat_name`, `remarks`, `balance`, `daily_meal_units`, `meal_quota_total`,
  `plan_type`, `is_active`, `is_leaved_tomorrow`, `delivery_start_date`, `delivery_deferred`, `store_pickup`, `created_at`
) VALUES (
  {_sql_str(m.phone)}, {_sql_str(m.name)}, {_sql_str(m.name)}, {rem_m},
  {m.balance}, {m.daily_meal_units}, {m.meal_quota_total},
  {pt_sql}, {m.is_active}, 0, {ds_sql}, {m.delivery_deferred}, {m.store_pickup}, {created_sql}
);
SET @__member_id = LAST_INSERT_ID();

"""
        )

        for i, addr in enumerate(m.addresses):
            cname = " | ".join(addr.contact_names) if addr.contact_names else m.name
            det = _sql_str(addr.detail_display)
            rem_a = _sql_str(addr.remarks)
            is_def = 1 if i == 0 else 0

            skip_geo = addr.store_pickup and addr.detail_display.strip() in ("自提", "店内自取", "门店自取")
            coords = None if skip_geo else _geocode(amap_key, addr.detail_display)
            if coords is None and amap_key.strip() and not skip_geo:
                failures.append(f"{m.phone} {cname} {addr.detail_display[:40]}...")
            lng_sql = "NULL"
            lat_sql = "NULL"
            if coords:
                lng_sql = _sql_decimal8(coords[0])
                lat_sql = _sql_decimal8(coords[1])
            if sleep_s > 0 and amap_key.strip():
                time.sleep(sleep_s)

            fh.write(
                f"""INSERT INTO `member_addresses` (
  `member_id`, `contact_name`, `contact_phone`, `delivery_region_id`, `detail_address`, `remarks`, `lng`, `lat`, `is_default`, `created_at`, `updated_at`
) VALUES (
  @__member_id, {_sql_str(cname)}, {_sql_str(m.phone)}, NULL, {det}, {rem_a}, {lng_sql}, {lat_sql}, {is_def}, {created_sql}, {created_sql}
);

"""
            )

    return failures


def main() -> int:
    ap = argparse.ArgumentParser(description="CSV 配送名单 -> members SQL + 高德经纬度")
    ap.add_argument("csv_path", type=Path, help="CSV 文件路径")
    ap.add_argument("-o", "--output", type=Path, default=Path("sql/generated_members_from_csv.sql"))
    ap.add_argument("--sleep", type=float, default=0.12, help="两次地理编码请求间隔（秒）")
    ap.add_argument("--no-geocode", action="store_true", help="不请求高德，lng/lat 一律 NULL")
    args = ap.parse_args()

    csv_path = args.csv_path if args.csv_path.is_absolute() else _BACKEND_ROOT / args.csv_path
    if not csv_path.is_file():
        print(f"文件不存在: {csv_path}", file=sys.stderr)
        return 1

    raw = collect_member_rows(csv_path)
    members = aggregate_members(raw)

    amap_key = ""
    if not args.no_geocode and settings is not None:
        amap_key = (settings.AMAP_KEY or "").strip()
    elif not args.no_geocode:
        import os

        amap_key = (os.environ.get("AMAP_KEY") or "").strip()

    out_path = args.output if args.output.is_absolute() else _BACKEND_ROOT / args.output
    out_path.parent.mkdir(parents=True, exist_ok=True)

    fail_path = out_path.with_suffix(".geocode_failed.txt")

    with out_path.open("w", encoding="utf-8") as fh:
        fails = emit_sql(members, "" if args.no_geocode else amap_key, args.sleep, fh)

    if fails:
        fail_path.write_text("\n".join(fails), encoding="utf-8")
        print(f"地理编码失败 {len(fails)} 条，见 {fail_path}", file=sys.stderr)
    else:
        if fail_path.is_file():
            fail_path.unlink()

    n_addr = sum(len(m.addresses) for m in members)
    print(f"已写入 {len(members)} 名会员、{n_addr} 条地址 -> {out_path}")
    if not args.no_geocode and not amap_key.strip():
        print("提示: 未配置 AMAP_KEY，坐标均为 NULL。可在 backend/.env 中配置或在命令前设置环境变量。", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
