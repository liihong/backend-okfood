"""
片区重新划分后，按会员默认地址坐标重新匹配最新 delivery_regions 多边形，
仅更新 member_addresses.delivery_region_id，不修改 lng/lat、地址文案及会员其它字段。

与 scripts/assign_member_address_regions.py 的区别：
- 本脚本只处理「默认配送地址」（决定会员列表/配送大表展示的所属片区）
- 只写 delivery_region_id，绝不改动坐标与其它地址列
- 默认全量重算（含已有片区的会员）

用法（项目根目录，已配置 .env 数据库；无坐标时需 --geocode-fallback 且配置 AMAP_KEY）：

  python scripts/reassign_member_delivery_regions.py --dry-run
  python scripts/reassign_member_delivery_regions.py
  python scripts/reassign_member_delivery_regions.py --geocode-fallback
  python scripts/reassign_member_delivery_regions.py --output-sql sql/reassign_member_regions.sql
  python scripts/reassign_member_delivery_regions.py --store-id 1
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.core.timeutil import beijing_now_naive
from app.db.session import SessionLocal
from app.models.member import Member
from app.models.member_address import MemberAddress
from app.services.member.member_address_service import (
    default_address_pick_subquery,
    delivery_region_name_map,
    full_address_line,
)
from app.services.shared import amap
from app.services.shared.region_assignment import assign_region_for_coords


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="按最新片区多边形，仅重算会员默认地址的 delivery_region_id（不改其它字段）"
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="不写入数据库，仅打印将发生的片区变更",
    )
    p.add_argument(
        "--geocode-fallback",
        action="store_true",
        help="无 lng/lat 时尝试高德地理编码后划区；仍只写 delivery_region_id，不写坐标",
    )
    p.add_argument(
        "--store-id",
        type=int,
        default=None,
        metavar="ID",
        help="仅处理指定门店下的会员",
    )
    p.add_argument(
        "--commit-every",
        type=int,
        default=200,
        metavar="N",
        help="每 N 条提交一次，默认 200",
    )
    p.add_argument(
        "--output-sql",
        type=str,
        default=None,
        metavar="FILE",
        help="生成仅含 delivery_region_id 的 UPDATE SQL 文件（UTF-8）",
    )
    p.add_argument(
        "--no-commit",
        action="store_true",
        help="不提交事务（回滚），配合 --output-sql 审阅后手工执行",
    )
    return p.parse_args()


def _resolve_new_region_id(
    db,
    *,
    addr: MemberAddress,
    tenant_id: int,
    geocode_fallback: bool,
) -> int | None:
    """根据已有坐标或（可选）地理编码，计算应写入的 delivery_region_id。"""
    if addr.lng is not None and addr.lat is not None:
        region = assign_region_for_coords(db, float(addr.lng), float(addr.lat), tenant_id=tenant_id)
        return int(region.id) if region else None

    if not geocode_fallback:
        return None

    line = full_address_line(addr.map_location_text, addr.door_detail)
    coords = amap.geocode_address(line) if line.strip() else None
    if not coords:
        return None
    lng_f, lat_f = float(coords[0]), float(coords[1])
    region = assign_region_for_coords(db, lng_f, lat_f, tenant_id=tenant_id)
    return int(region.id) if region else None


def _format_region_sql(*, row_id: int, member_id: int, delivery_region_id: int | None, updated_at_sql: str) -> str:
    rid = "NULL" if delivery_region_id is None else str(int(delivery_region_id))
    return (
        f"UPDATE `member_addresses` SET `delivery_region_id` = {rid}, "
        f"`updated_at` = {updated_at_sql!r} WHERE `id` = {int(row_id)};  "
        f"-- member_id={int(member_id)}\n"
    )


def _load_default_addresses(db, *, store_id: int | None) -> list[tuple[Member, MemberAddress]]:
    """加载未删除会员的默认配送地址（每人一条，多条 is_default 时取 id 最大）。"""
    pick = default_address_pick_subquery()
    stmt = (
        select(Member, MemberAddress)
        .join(pick, Member.id == pick.c.mid)
        .join(MemberAddress, MemberAddress.id == pick.c.addr_id)
        .where(Member.deleted_at.is_(None))
        .order_by(Member.id.asc())
    )
    if store_id is not None:
        stmt = stmt.where(Member.store_id == int(store_id))
    return list(db.execute(stmt).all())


def main() -> None:
    args = _parse_args()
    if args.no_commit and not args.output_sql:
        print("已忽略无意义的 --no-commit（请同时指定 --output-sql）。")
        args.no_commit = False

    db = SessionLocal()
    try:
        pairs = _load_default_addresses(db, store_id=args.store_id)
        if not pairs:
            print("没有需要处理的会员默认地址。")
            return

        name_cache: dict[int, str] = {}

        def region_name(rid: int | None) -> str:
            if rid is None:
                return "（未分配）"
            if rid not in name_cache:
                nm = delivery_region_name_map(db, {int(rid)})
                name_cache[rid] = nm.get(int(rid), f"id={rid}")
            return name_cache[rid]

        changed = 0
        skipped_no_coords = 0
        unchanged = 0
        sql_chunks: list[str] = []

        for i, (member, addr) in enumerate(pairs, 1):
            old_rid = int(addr.delivery_region_id) if addr.delivery_region_id is not None else None
            has_coords = addr.lng is not None and addr.lat is not None

            if not has_coords and not args.geocode_fallback:
                skipped_no_coords += 1
                continue

            new_rid = _resolve_new_region_id(
                db,
                addr=addr,
                tenant_id=int(member.tenant_id),
                geocode_fallback=bool(args.geocode_fallback),
            )

            if new_rid == old_rid:
                unchanged += 1
                continue

            changed += 1
            if args.dry_run:
                detail = full_address_line(addr.map_location_text, addr.door_detail)[:50]
                print(
                    f"member_id={member.id} addr_id={addr.id} "
                    f"{region_name(old_rid)} -> {region_name(new_rid)}  detail={detail!r}"
                )
                continue

            # 仅更新 delivery_region_id，不触碰 lng/lat 与其它列
            addr.delivery_region_id = new_rid

            if args.output_sql:
                db.flush()
                u = addr.updated_at
                if u is not None:
                    u_naive = u.replace(tzinfo=None) if getattr(u, "tzinfo", None) else u
                    updated_at_sql = u_naive.strftime("%Y-%m-%d %H:%M:%S")
                else:
                    updated_at_sql = beijing_now_naive().strftime("%Y-%m-%d %H:%M:%S")
                sql_chunks.append(
                    _format_region_sql(
                        row_id=int(addr.id),
                        member_id=int(member.id),
                        delivery_region_id=new_rid,
                        updated_at_sql=updated_at_sql,
                    )
                )

            if args.commit_every and i % args.commit_every == 0 and not args.no_commit and not args.dry_run:
                db.commit()

        if args.dry_run:
            print(
                f"[dry-run] 共 {len(pairs)} 名会员默认地址；"
                f"将变更: {changed}；不变: {unchanged}；"
                f"无坐标且未启用 --geocode-fallback 跳过: {skipped_no_coords}"
            )
            return

        if args.no_commit:
            db.rollback()
        else:
            db.commit()

        if args.output_sql:
            out_path = Path(args.output_sql)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            gen_at = beijing_now_naive().strftime("%Y-%m-%d %H:%M:%S")
            header = (
                "-- 由 scripts/reassign_member_delivery_regions.py 生成\n"
                f"-- 生成时间(北京时间) {gen_at}\n"
                "-- 仅更新 delivery_region_id\n"
                "SET NAMES utf8mb4;\n\n"
            )
            body = "".join(sql_chunks) if sql_chunks else "-- （无列变更，划区结果与处理前一致。）\n"
            out_path.write_text(header + body, encoding="utf-8")
            print(f"已写入 SQL: {out_path.resolve()}，共 {len(sql_chunks)} 条 UPDATE。")

        if args.no_commit:
            print("已回滚，数据库未修改。")

        print(
            f"处理 {len(pairs)} 名会员默认地址；"
            f"delivery_region_id 有变更: {changed}；不变: {unchanged}；"
            f"无坐标跳过: {skipped_no_coords}"
        )
        if skipped_no_coords:
            print("提示: 对无坐标地址加 --geocode-fallback 可尝试按地址文本划区（仍不写坐标）。")
    finally:
        db.close()


if __name__ == "__main__":
    main()
