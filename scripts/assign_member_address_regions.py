"""
为 member_addresses 按坐标匹配 delivery_regions 多边形，写回 delivery_region_id。

与后台「恢复自动划区」相同：有 lng/lat 则做点在多边形内匹配；无坐标则按详细地址
高德地理编码后再匹配（需配置 AMAP_KEY）。

默认只处理 delivery_region_id 为空的记录；--all 可全量重算。
指定 --output-sql 时，在写库后（与之一致）生成可回放的 UPDATE 语句；可用 --no-commit 只生成
SQL 不落库，便于在别的环境或审阅后手工执行。

用法（在项目根目录、已配置 .env 数据库与可选高德 Key）：

  python scripts/assign_member_address_regions.py
  python scripts/assign_member_address_regions.py --output-sql sql/member_address_region_updates.sql
  python scripts/assign_member_address_regions.py --output-sql sql/updates.sql --no-commit
  python scripts/assign_member_address_regions.py --dry-run
  python scripts/assign_member_address_regions.py --all
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.member_address import MemberAddress
from app.services.member_address_service import apply_auto_area_from_coords_or_geocode, delivery_region_name_map
from app.services.region_assignment import assign_region_for_coords


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="为会员地址自动分配配送片区（delivery_region_id）")
    p.add_argument(
        "--all",
        action="store_true",
        help="重算所有地址；默认仅处理 delivery_region_id 为 NULL 的地址",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="不写入数据库。仅对已有坐标的行模拟匹配；无坐标的行会提示将走地理编码",
    )
    p.add_argument(
        "--commit-every",
        type=int,
        default=200,
        metavar="N",
        help="每 N 条提交一次，默认 200；结束时再提交余数",
    )
    p.add_argument(
        "--output-sql",
        type=str,
        default=None,
        metavar="FILE",
        help="将本批地址的落库内容写成 UPDATE member_addresses 的 SQL 文件（UTF-8）",
    )
    p.add_argument(
        "--no-commit",
        action="store_true",
        help="不提交事务（回滚），仅当需配合 --output-sql 在本地试算/审阅时使用",
    )
    return p.parse_args()


def _fnum(v: object | None) -> float | None:
    if v is None:
        return None
    return float(v)


def _num_equal(a: float | None, b: float | None) -> bool:
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    return abs(a - b) < 1e-9


def _format_update_sql(
    *,
    row_id: int,
    member_id: int,
    delivery_region_id: int | None,
    lng: float | None,
    lat: float | None,
    updated_at_sql: str,
) -> str:
    rid = "NULL" if delivery_region_id is None else str(int(delivery_region_id))
    lng_s = "NULL" if lng is None else f"{lng:.8f}"
    lat_s = "NULL" if lat is None else f"{lat:.8f}"
    return (
        f"UPDATE `member_addresses` SET `delivery_region_id` = {rid}, `lng` = {lng_s}, `lat` = {lat_s}, "
        f"`updated_at` = {updated_at_sql!r} WHERE `id` = {int(row_id)};  "
        f"-- member_id={int(member_id)}\n"
    )


def _build_sql_file_header(*, no_commit: bool) -> str:
    gen_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    lines = [
        "-- 由 scripts/assign_member_address_regions.py 生成",
        f"-- 生成时间(UTC) {gen_at}",
    ]
    if no_commit:
        lines.append("-- 本文件由 --no-commit 试算生成，数据库未落库，请在目标库核对后执行。")
    lines.extend(["SET NAMES utf8mb4;", ""])
    return "\n".join(lines)


def main() -> None:
    args = _parse_args()
    if args.no_commit and not args.output_sql:
        print("已忽略无意义的 --no-commit（请同时指定 --output-sql）。")
        args.no_commit = False

    db = SessionLocal()
    try:
        stmt = select(MemberAddress)
        if not args.all:
            stmt = stmt.where(MemberAddress.delivery_region_id.is_(None))
        rows = list(db.scalars(stmt).all())
        if not rows:
            print("没有需要处理的地址行。")
            return

        if args.dry_run:
            if args.output_sql:
                print("[提示] --dry-run 与 --output-sql 互斥，已跳过写 SQL 文件。去掉 --dry-run 可生成 UPDATE。")
            _dry_run(db, rows)
            return

        changed_region = 0
        sql_chunks: list[str] = []

        for i, row in enumerate(rows, 1):
            old_rid = int(row.delivery_region_id) if row.delivery_region_id is not None else None
            old_lng = _fnum(row.lng)
            old_lat = _fnum(row.lat)

            apply_auto_area_from_coords_or_geocode(db, row)
            if args.output_sql:
                db.flush()
                u = row.updated_at
                if u is not None:
                    u_naive = u.replace(tzinfo=None) if getattr(u, "tzinfo", None) else u
                    updated_at_sql = u_naive.strftime("%Y-%m-%d %H:%M:%S")
                else:
                    updated_at_sql = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
            else:
                updated_at_sql = ""

            new_rid = int(row.delivery_region_id) if row.delivery_region_id is not None else None
            new_lng = _fnum(row.lng)
            new_lat = _fnum(row.lat)

            if new_rid != old_rid:
                changed_region += 1
            if args.output_sql and (
                new_rid != old_rid or not _num_equal(new_lng, old_lng) or not _num_equal(new_lat, old_lat)
            ):
                sql_chunks.append(
                    _format_update_sql(
                        row_id=int(row.id),
                        member_id=int(row.member_id),
                        delivery_region_id=new_rid,
                        lng=new_lng,
                        lat=new_lat,
                        updated_at_sql=updated_at_sql,
                    )
                )

            if args.commit_every and i % args.commit_every == 0 and not args.no_commit:
                db.commit()

        if args.no_commit:
            db.rollback()
        else:
            db.commit()

        if args.output_sql:
            out_path = Path(args.output_sql)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            text = _build_sql_file_header(no_commit=bool(args.no_commit)) + "\n".join(sql_chunks)
            if not sql_chunks:
                text += "-- （无列变更，未生成任何 UPDATE 行；划区结果与处理前一致。）\n"
            out_path.write_text(text, encoding="utf-8")
            print(f"已写入 SQL: {out_path.resolve()}，共 {len(sql_chunks)} 条 UPDATE。")

        # 统计未分配（--no-commit 时 ORM 已回滚，用内存中 row 的最后一次 apply 结果）
        null_ids = [r for r in rows if r.delivery_region_id is None]
        if args.no_commit:
            print("已回滚，数据库未修改。")
        print(f"处理 {len(rows)} 条，其中 delivery_region_id 有变更: {changed_region} 条。")
        print(f"仍为 NULL（未落入任一启用区域多边形或地理编码失败）: {len(null_ids)} 条")
        if null_ids and len(null_ids) <= 30:
            for r in null_ids:
                detail = (r.detail_address or "")[:60]
                print(f"  id={r.id} member_id={r.member_id} detail={detail!r} lng={r.lng} lat={r.lat}")
    finally:
        db.close()


def _dry_run(db, rows: list[MemberAddress]) -> None:
    would_change = 0
    need_geocode = 0
    name_cache: dict[int, str] = {}

    def name_for(rid: int | None) -> str:
        if rid is None:
            return "（空）"
        if rid not in name_cache:
            nm = delivery_region_name_map(db, {int(rid)})
            name_cache[rid] = nm.get(int(rid), f"id={rid}")
        return name_cache[rid]

    for row in rows:
        if row.lng is None or row.lat is None:
            need_geocode += 1
            continue
        r = assign_region_for_coords(db, float(row.lng), float(row.lat))
        new_id = int(r.id) if r else None
        old_id = int(row.delivery_region_id) if row.delivery_region_id is not None else None
        if new_id != old_id:
            would_change += 1
            print(
                f"id={row.id} member_id={row.member_id} "
                f"{name_for(old_id)} -> {name_for(new_id) if new_id is not None else '（空/未分配）'}"
            )

    print(
        f"[dry-run] 共 {len(rows)} 条；有坐标可模拟: {len(rows) - need_geocode}；"
        f"将发生变更: {would_change}；无坐标、完整运行将尝试地理编码: {need_geocode}"
    )

    if need_geocode:
        print("提示: 去掉 --dry-run 后将对无坐标行调用高德地理编码（需 AMAP_KEY）。")


if __name__ == "__main__":
    main()
