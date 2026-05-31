"""
按供餐日批量同步单次零售订单微信支付状态（向微信 orderquery 查单，与异步回调同路径入账）。

适用场景：用户已扣款但库内仍显示「未支付」（异步通知未达、IP 白名单等）。

用法（项目根目录，已配置 .env 数据库与微信支付密钥）：

  # 同步 2026-06-01 供餐日、门店 1 下所有「未支付」订单
  python scripts/sync_single_meal_wechat_pay_by_delivery_date.py --delivery-date 2026-06-01

  # 仅预览待处理订单，不调微信
  python scripts/sync_single_meal_wechat_pay_by_delivery_date.py --delivery-date 2026-06-01 --dry-run

  # 含履约已取消的未支付单（极少数：超时取消前已付款）
  python scripts/sync_single_meal_wechat_pay_by_delivery_date.py --delivery-date 2026-06-01 --include-cancelled

  # 指定订单 id（逗号分隔，仍须满足供餐日/门店筛选）
  python scripts/sync_single_meal_wechat_pay_by_delivery_date.py --delivery-date 2026-06-01 --order-ids 154,155
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.single_meal_order import SingleMealOrder
from app.services.single_meal_order_service import sync_single_meal_order_from_wechat_query


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="按供餐日批量同步单次零售微信支付状态（微信查单 → 本地入账）"
    )
    p.add_argument(
        "--delivery-date",
        required=True,
        metavar="YYYY-MM-DD",
        help="供餐日，如 2026-06-01",
    )
    p.add_argument(
        "--store-id",
        type=int,
        default=1,
        help="门店 id，默认 1",
    )
    p.add_argument(
        "--include-cancelled",
        action="store_true",
        help="包含履约 status=cancelled 的未支付单（默认跳过，减少无效查单）",
    )
    p.add_argument(
        "--order-ids",
        type=str,
        default="",
        help="仅处理指定订单 id，逗号分隔，如 154,155",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="只列出待查单订单，不调用微信、不写库",
    )
    p.add_argument(
        "--sleep-ms",
        type=int,
        default=200,
        metavar="MS",
        help="每笔查单间隔毫秒，避免微信限频，默认 200",
    )
    return p.parse_args()


def _parse_delivery_date(raw: str) -> date:
    s = (raw or "").strip()
    try:
        return date.fromisoformat(s)
    except ValueError as e:
        raise SystemExit(f"无效 --delivery-date: {raw!r}，请用 YYYY-MM-DD") from e


def _parse_order_ids(raw: str) -> set[int] | None:
    s = (raw or "").strip()
    if not s:
        return None
    out: set[int] = set()
    for part in s.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            oid = int(part)
        except ValueError as e:
            raise SystemExit(f"无效 --order-ids 片段: {part!r}") from e
        if oid < 1:
            raise SystemExit(f"无效 order id: {oid}")
        out.add(oid)
    return out or None


def _load_candidates(
    db,
    *,
    delivery_day: date,
    store_id: int,
    include_cancelled: bool,
    order_ids: set[int] | None,
) -> list[SingleMealOrder]:
    filters = [
        SingleMealOrder.store_id == int(store_id),
        SingleMealOrder.delivery_date == delivery_day,
        SingleMealOrder.pay_status == "未支付",
    ]
    if not include_cancelled:
        filters.append(SingleMealOrder.fulfillment_status != "cancelled")
    if order_ids is not None:
        filters.append(SingleMealOrder.id.in_(sorted(order_ids)))

    rows = db.scalars(
        select(SingleMealOrder)
        .where(*filters)
        .order_by(SingleMealOrder.id.asc())
    ).all()
    return list(rows)


def main() -> None:
    args = _parse_args()
    delivery_day = _parse_delivery_date(args.delivery_date)
    order_ids = _parse_order_ids(args.order_ids)
    store_id = int(args.store_id)
    sleep_ms = max(0, int(args.sleep_ms))

    started = datetime.now()
    print(
        f"[sync] 供餐日={delivery_day.isoformat()} store_id={store_id} "
        f"include_cancelled={args.include_cancelled} dry_run={args.dry_run}"
    )

    db = SessionLocal()
    try:
        rows = _load_candidates(
            db,
            delivery_day=delivery_day,
            store_id=store_id,
            include_cancelled=args.include_cancelled,
            order_ids=order_ids,
        )
        if not rows:
            print("[sync] 无符合条件的「未支付」订单，结束。")
            return

        print(f"[sync] 待处理 {len(rows)} 笔：")
        for r in rows:
            print(
                f"  id={int(r.id):>4}  out={r.out_trade_no or '—':<12}  "
                f"fulfill={r.fulfillment_status or '—':<12}  amt={r.amount_yuan}"
            )

        if args.dry_run:
            print("[sync] --dry-run 未调用微信，结束。")
            return

        import time

        ok_paid = 0
        already = 0
        skipped = 0
        failed: list[tuple[int, str]] = []

        for i, row in enumerate(rows):
            oid = int(row.id)
            mid = int(row.member_id)
            if i > 0 and sleep_ms > 0:
                time.sleep(sleep_ms / 1000.0)

            try:
                ok, reason = sync_single_meal_order_from_wechat_query(db, mid, oid)
            except Exception as e:
                db.rollback()
                failed.append((oid, str(e)[:200]))
                print(f"  ✗ #{oid} 异常: {e}")
                continue

            if ok:
                if reason in ("already_synced", "already_paid"):
                    already += 1
                    print(f"  ✓ #{oid} 已是已支付 ({reason})")
                else:
                    ok_paid += 1
                    warn = ""
                    db.refresh(row)
                    if (row.fulfillment_status or "").strip().lower() == "cancelled":
                        warn = " ⚠ 履约仍为 cancelled，请在订单管理核对是否需恢复"
                    print(f"  ✓ #{oid} 已同步为已支付 ({reason}){warn}")
            else:
                if reason in ("not_paid", "wechat_order_not_found", "PAY_USERPAYING"):
                    skipped += 1
                    print(f"  - #{oid} 微信侧未支付 ({reason})")
                else:
                    failed.append((oid, reason))
                    print(f"  ✗ #{oid} 失败: {reason}")

        elapsed = (datetime.now() - started).total_seconds()
        print(
            f"\n[sync] 完成：新入账 {ok_paid}，已是已支付 {already}，"
            f"微信未付/无单 {skipped}，失败 {len(failed)}，耗时 {elapsed:.1f}s"
        )
        if failed:
            print("[sync] 失败明细：")
            for oid, reason in failed:
                print(f"  #{oid}: {reason}")
            sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
