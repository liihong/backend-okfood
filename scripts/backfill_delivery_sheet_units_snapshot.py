#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从历史顺丰大表推单回填 delivery_sheet_push_units_snapshots，并重新冻结当日生效份数。

用法（在 backend 目录）：
  python scripts/backfill_delivery_sheet_units_snapshot.py --date 2026-06-11
  python scripts/backfill_delivery_sheet_units_snapshot.py --date 2026-06-11 --apply
  python scripts/backfill_delivery_sheet_units_snapshot.py --date 2026-06-11 --apply --no-align-members
  python scripts/backfill_delivery_sheet_units_snapshot.py --date 2026-06-11 --apply --patch-frozen-only

默认 dry-run，仅打印统计；加 --apply 才写库。
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

# 保证可从 scripts/ 直接运行
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.session import SessionLocal
from app.services.delivery_sheet_service import build_delivery_sheet
from app.services.delivery_sheet_push_snapshot_service import (
    patch_frozen_member_ids_on_units_snapshot_if_missing,
)
from app.services.delivery_sheet_units_backfill_service import (
    backfill_and_refreeze_delivery_sheet_units,
    build_member_meal_units_from_sf_pushes,
)


def _parse_date(s: str) -> date:
    return date.fromisoformat(s.strip()[:10])


def main() -> int:
    parser = argparse.ArgumentParser(description="回填配送大表份数快照并重新冻结当日份数")
    parser.add_argument("--date", required=True, help="业务日 YYYY-MM-DD，如 2026-06-11")
    parser.add_argument("--store-id", type=int, default=1, help="门店 id，默认 1")
    parser.add_argument("--apply", action="store_true", help="写库（默认仅预览）")
    parser.add_argument(
        "--no-align-members",
        action="store_true",
        help="仅写快照，不回退 members.daily_meal_units",
    )
    parser.add_argument(
        "--patch-frozen-only",
        action="store_true",
        help="仅补齐快照 JSON 中的 frozen 会员 id 元数据（快，不改份数）",
    )
    args = parser.parse_args()

    d = _parse_date(args.date)
    sid = int(args.store_id)
    dry_run = not args.apply

    db = SessionLocal()
    try:
        if dry_run:
            units, stats = build_member_meal_units_from_sf_pushes(db, store_id=sid, delivery_date=d)
            sheet_before = build_delivery_sheet(db, delivery_date=d, store_id=sid)
            meals_before = (
                sheet_before.home_pending_meal_total + sheet_before.home_delivered_meal_total
            )
            print("=== DRY-RUN 预览 ===")
            print(json.dumps({"member_count": len(units), "meal_units_total": sum(units.values()), **stats}, ensure_ascii=False))
            print(f"当前大表到家份数: {meals_before}")
            print("加 --apply 执行写库")
            return 0

        if args.patch_frozen_only:
            patched = patch_frozen_member_ids_on_units_snapshot_if_missing(
                db, store_id=sid, delivery_date=d
            )
            db.commit()
            print(f"=== frozen 元数据补齐: {'已写入' if patched else '无需变更或快照不存在'} ===")
        else:
            report = backfill_and_refreeze_delivery_sheet_units(
                db,
                store_id=sid,
                delivery_date=d,
                overwrite_snapshot=True,
                align_member_daily_units=not args.no_align_members,
                dry_run=False,
            )
            print("=== 回填完成 ===")
            print(json.dumps(report.__dict__, ensure_ascii=False, default=str))
        sheet_after = build_delivery_sheet(db, delivery_date=d, store_id=sid)
        meals_after = sheet_after.home_pending_meal_total + sheet_after.home_delivered_meal_total
        print(f"回填后大表到家份数: {meals_after}")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
