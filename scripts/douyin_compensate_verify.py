#!/usr/bin/env python3
"""
补偿核销：本地已发奖 success，但抖音侧仍为「未核销」时，补调 prepare + verify。

典型场景：pay_channel 迁移前发奖失败并撤销核销，用户重试时旧代码跳过 verify 仅本地发奖。

用法（在项目根目录、已配置 .env）：
  .venv/bin/python scripts/douyin_compensate_verify.py --order-id 121349085360194
  .venv/bin/python scripts/douyin_compensate_verify.py --redemption-id 10
  .venv/bin/python scripts/douyin_compensate_verify.py --order-id 121349085360194 --dry-run
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import select

from app.db.session import SessionLocal
from app.integrations.douyin_life import certificate_prepare, certificate_verify
from app.models.douyin.certificate_redemption import DouyinCertificateRedemption
from app.models.enums import DouyinRedemptionStatus
from app.models.member import Member
from app.services.douyin.certificate_service import _extract_verify_id
from app.services.douyin.config_service import get_douyin_access_token, get_douyin_store_config


def _load_row(db, *, order_id: str | None, redemption_id: int | None) -> DouyinCertificateRedemption:
    if redemption_id is not None:
        row = db.get(DouyinCertificateRedemption, int(redemption_id))
    elif order_id:
        row = db.scalar(
            select(DouyinCertificateRedemption)
            .where(DouyinCertificateRedemption.douyin_order_id == order_id.strip())
            .order_by(DouyinCertificateRedemption.id.desc())
            .limit(1)
        )
    else:
        raise SystemExit("请指定 --order-id 或 --redemption-id")

    if row is None:
        raise SystemExit("未找到核销流水")
    return row


def main() -> None:
    parser = argparse.ArgumentParser(description="补偿调用抖音验券核销")
    parser.add_argument("--order-id", help="抖音订单号 douyin_order_id")
    parser.add_argument("--redemption-id", type=int, help="本地流水 ID")
    parser.add_argument("--code", help="券码明文（未传则从管理端/用户处获取后填入）")
    parser.add_argument("--dry-run", action="store_true", help="仅打印将执行的操作，不调抖音")
    args = parser.parse_args()

    code = (args.code or "").strip()
    if not code:
        raise SystemExit("必须提供 --code（券码明文），prepare 接口需要")

    db = SessionLocal()
    try:
        row = _load_row(db, order_id=args.order_id, redemption_id=args.redemption_id)
        member = db.get(Member, int(row.member_id))
        if not member:
            raise SystemExit(f"会员不存在 member_id={row.member_id}")

        print(
            f"流水 id={row.id} status={row.status} order={row.douyin_order_id} "
            f"cert={row.certificate_id} verify_id={row.douyin_verify_id} "
            f"grant={row.grant_result_kind}:{row.grant_result_id}"
        )

        if row.status != DouyinRedemptionStatus.SUCCESS.value:
            print("警告：流水状态不是 success，请确认是否仍需补偿核销")

        store_cfg = get_douyin_store_config(db, int(member.store_id))
        access_token = get_douyin_access_token(db, int(member.tenant_id))

        if args.dry_run:
            print(
                f"[dry-run] 将调用 prepare(code={code[:4]}***) + verify "
                f"poi={store_cfg.poi_id}"
            )
            return

        prepared = certificate_prepare(
            access_token=access_token,
            code=code,
            poi_id=store_cfg.poi_id,
            account_id=store_cfg.account_id,
        )
        cert = prepared.certificates[0]
        verify_data = certificate_verify(
            access_token=access_token,
            verify_token=prepared.verify_token,
            poi_id=store_cfg.poi_id,
            encrypted_codes=[cert.encrypted_code],
            order_id=prepared.order_id,
        )
        new_verify_id = _extract_verify_id(verify_data)
        row.douyin_verify_id = new_verify_id or row.douyin_verify_id
        row.verify_token = prepared.verify_token
        if prepared.order_id:
            row.douyin_order_id = prepared.order_id
        db.add(row)
        db.commit()
        print(f"补偿核销成功 verify_id={new_verify_id}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
