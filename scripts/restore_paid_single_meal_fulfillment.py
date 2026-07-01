"""
恢复「已支付但履约仍为 cancelled」的单次零售订单（超时自动取消后补同步支付的场景）。

用法（项目根目录）：

  # 预览 2026-06-01 供餐日需恢复的订单
  python scripts/restore_paid_single_meal_fulfillment.py --delivery-date 2026-06-01 --dry-run

  # 正式恢复
  python scripts/restore_paid_single_meal_fulfillment.py --delivery-date 2026-06-01

  # 仅指定订单
  python scripts/restore_paid_single_meal_fulfillment.py --delivery-date 2026-06-01 --order-ids 145,146,148
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.member_address import MemberAddress
from app.models.single_meal_order import SingleMealOrder
from app.services.order.single_meal_order_service import primary_courier_for_region_id


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="恢复已支付单次零售订单的履约状态（cancelled → pending）")
    p.add_argument("--delivery-date", required=True, metavar="YYYY-MM-DD")
    p.add_argument("--store-id", type=int, default=1)
    p.add_argument("--order-ids", default="", help="逗号分隔，如 145,146")
    p.add_argument("--dry-run", action="store_true")
    return p.parse_args()


def _parse_order_ids(raw: str) -> set[int] | None:
    s = (raw or "").strip()
    if not s:
        return None
    return {int(x.strip()) for x in s.split(",") if x.strip()}


def main() -> None:
    args = _parse_args()
    delivery_day = date.fromisoformat(args.delivery_date.strip())
    store_id = int(args.store_id)
    order_ids = _parse_order_ids(args.order_ids)

    db = SessionLocal()
    try:
        filters = [
            SingleMealOrder.store_id == store_id,
            SingleMealOrder.delivery_date == delivery_day,
            SingleMealOrder.pay_status == "已支付",
            SingleMealOrder.fulfillment_status == "cancelled",
        ]
        if order_ids is not None:
            filters.append(SingleMealOrder.id.in_(sorted(order_ids)))

        rows = list(
            db.scalars(
                select(SingleMealOrder).where(*filters).order_by(SingleMealOrder.id.asc())
            ).all()
        )
        if not rows:
            print("[restore] 无「已支付 + cancelled」订单，结束。")
            return

        print(f"[restore] 待恢复 {len(rows)} 笔：")
        for r in rows:
            mode = "自提" if bool(getattr(r, "store_pickup", False)) else "配送"
            print(f"  id={int(r.id)}  out={r.out_trade_no}  {mode}")

        if args.dry_run:
            print("[restore] --dry-run 未写库。")
            return

        n = 0
        for r in rows:
            r.fulfillment_status = "pending"
            if bool(getattr(r, "store_pickup", False)):
                r.courier_id = None
            else:
                pay_addr = (
                    db.get(MemberAddress, int(r.member_address_id))
                    if r.member_address_id is not None
                    else None
                )
                r.courier_id = primary_courier_for_region_id(
                    db,
                    int(pay_addr.delivery_region_id)
                    if pay_addr and pay_addr.delivery_region_id
                    else None,
                )
            db.add(r)
            n += 1
            print(f"  ✓ #{int(r.id)} → pending")
        db.commit()
        print(f"[restore] 完成，已恢复 {n} 笔。")
    finally:
        db.close()


if __name__ == "__main__":
    main()
