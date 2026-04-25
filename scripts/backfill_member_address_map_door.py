"""
根据现有 `detail_address` 启发式拆分到 `map_location_text` 与 `door_detail`。

小程序地图保存时格式多为：「省市区/道路/POI 等」+ 空格 +「栋单元门牌」；部分历史数据为
「小区名-6号楼2单元…」等。本脚本不修改 `detail_address`，仅补全两列 NULL/空 的记录。

默认只处理两新字段仍为空/NULL 的行；`--all` 对全部有 detail 的行重算并覆盖两列
（仍会跳过 detail_address 为空的行）。

用法（项目根目录、已配置 .env）：

  python scripts/backfill_member_address_map_door.py
  python scripts/backfill_member_address_map_door.py --dry-run
  python scripts/backfill_member_address_map_door.py --all
  python scripts/backfill_member_address_map_door.py --commit-every 100
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import and_, inspect, or_, select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal, engine
from app.models.member_address import MemberAddress


# 门牌/房间内层等特征：右段需命中才与左段切开（避免把路名+小区误拆）
_DOOR_RE = re.compile(
    r"(?:"
    r"\d+\s*栋|栋\s*[\d一二三四五六七八九十]+|"
    r"\d+\s*单元|单元\s*[\d一二三四五六七八九十]+|"
    r"\d+\s*号楼|号楼|"
    r"[#＃]?\d+\s*层|层\s*[\d#]|"
    r"室|厅|户|"
    r"门牌|单元门|"
    r"放前台|放大厅|放门口|"
    r"\d+-\d+-\d+"
    r")",
    re.UNICODE,
)

# 过短、不像门牌
_FAKE_DOOR = re.compile(r"^.{0,2}$")


def _looks_like_door_segment(part: str) -> bool:
    p = (part or "").strip()
    if len(p) < 2 or len(p) > 200:
        return False
    if _FAKE_DOOR.match(p) and not re.search(r"\d{3,}", p):
        return False
    if _DOOR_RE.search(p):
        return True
    # 纯 3–5 位房号（依附在“单元/楼/号”后时已由上匹配；仅房号时）
    if 2 <= len(p) <= 8 and re.fullmatch(r"[\d一二三四五六七八九十\-#]+", p):
        return bool(re.search(r"\d{3,5}", p))
    return False


def _split_by_last_space(s: str) -> tuple[str | None, str | None]:
    p = s.strip()
    if " " not in p and "\u3000" not in p:
        return None, None
    segs = re.split(r"[\s\u3000]+", p)
    if len(segs) < 2:
        return None, None
    for k in range(len(segs) - 1, 0, -1):
        left = " ".join(segs[:k]).strip()
        right = " ".join(segs[k:]).strip()
        if len(left) < 2:
            continue
        if _looks_like_door_segment(right):
            return left, right
    return None, None


def _split_by_hyphen(s: str) -> tuple[str | None, str | None]:
    p = s.strip()
    for sep in ("-", "－", "—"):
        if sep not in p:
            continue
        i = p.rfind(sep)
        left, right = p[:i].strip(), p[i + 1 :].strip()
        if len(left) < 2 or len(right) < 2:
            continue
        if _looks_like_door_segment(right):
            return left, right
    return None, None


def split_detail_to_map_door(detail: str) -> tuple[str, str | None]:
    """
    从单条详细地址拆出 (map_location_text, door_detail)；无法拆时整段作 map、door 为 None。
    """
    s = (detail or "").strip()
    if not s:
        return "", None
    a, b = _split_by_last_space(s)
    if a is not None and b is not None:
        return a, b
    a, b = _split_by_hyphen(s)
    if a is not None and b is not None:
        return a, b
    return s, None


def _table_has_column(session: Session, table: str, column: str) -> bool:
    try:
        insp = inspect(session.bind) if session.bind is not None else inspect(engine)
        if not insp.has_table(table):
            return False
        return any(c["name"] == column for c in insp.get_columns(table))
    except Exception:
        return False


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="从 detail_address 回填 map_location_text / door_detail")
    p.add_argument(
        "--all",
        action="store_true",
        help="重算并覆盖两列（仍不修改 detail_address）；默认只填两列均为空",
    )
    p.add_argument("--dry-run", action="store_true", help="只打印，不写库")
    p.add_argument(
        "--commit-every",
        type=int,
        default=200,
        metavar="N",
        help="每 N 条提交，默认 200",
    )
    return p.parse_args()


def main() -> int:
    args = _parse_args()
    with SessionLocal() as session:
        if not _table_has_column(session, "member_addresses", "map_location_text"):
            print("错误：表 member_addresses 无 map_location_text，请先执行迁移。")
            return 1

        stmt = select(MemberAddress).where(
            MemberAddress.detail_address.isnot(None),
            MemberAddress.detail_address != "",
        )
        if not args.all:
            stmt = stmt.where(
                and_(
                    or_(
                        MemberAddress.map_location_text.is_(None),
                        MemberAddress.map_location_text == "",
                    ),
                    or_(
                        MemberAddress.door_detail.is_(None),
                        MemberAddress.door_detail == "",
                    ),
                )
            )

        rows = list(session.scalars(stmt).all())
        n = len(rows)
        if n == 0:
            print("无待处理记录。")
            return 0
        print(f"待处理 {n} 条（dry_run={args.dry_run}）")
        since_commit = 0
        changed = 0
        for i, row in enumerate(rows, 1):
            d = (row.detail_address or "").strip()
            if not d:
                continue
            new_m, new_d = split_detail_to_map_door(d)

            if args.dry_run and i <= 20:
                print(
                    f"  id={row.id} map={new_m!r} door={new_d!r} "
                    f"(detail={d[:64]!r}{'...' if len(d) > 64 else ''})"
                )
            if args.dry_run and i == 21 and n > 20:
                print(f"  ... 其余 {n - 20} 条省略")

            if not args.dry_run:
                row.map_location_text = new_m
                row.door_detail = new_d
                session.add(row)
                changed += 1
                since_commit += 1
                if since_commit >= args.commit_every:
                    session.commit()
                    since_commit = 0
                    print(f"  已提交至 id≈{row.id}")

        if not args.dry_run:
            if since_commit:
                session.commit()
            print(f"完成：已更新 {changed} 条。")
        else:
            print(f"dry-run：本将更新 {n} 条。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
