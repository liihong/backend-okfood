#!/usr/bin/env python3
"""只读巡检：会员配送状态不变量（不修改数据库）。"""

from __future__ import annotations

import argparse
import sys

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.member import Member
from app.services.member.member_lifecycle_service import member_needs_setup_alert, resolve_member_lifecycle


def main() -> int:
    parser = argparse.ArgumentParser(description="检查会员配送状态不变量（只读）")
    parser.add_argument("--store-id", type=int, default=None, help="限定门店")
    parser.add_argument("--limit", type=int, default=500, help="最多输出条数")
    args = parser.parse_args()

    issues: list[str] = []
    with SessionLocal() as db:
        stmt = select(Member).where(Member.deleted_at.is_(None))
        if args.store_id is not None:
            stmt = stmt.where(Member.store_id == int(args.store_id))
        members = db.scalars(stmt).all()
        for m in members:
            lifecycle = resolve_member_lifecycle(db, m)
            if lifecycle.setup_alert and lifecycle.code == "delivering":
                issues.append(
                    f"member_id={m.id} phone={m.phone} setup_alert=true 但 lifecycle=delivering"
                )
            if member_needs_setup_alert(db, m) and not lifecycle.setup_alert:
                issues.append(
                    f"member_id={m.id} phone={m.phone} 缺履约信息但未标 setup_alert"
                )
            if bool(m.delivery_deferred) and lifecycle.code == "delivering":
                issues.append(
                    f"member_id={m.id} phone={m.phone} delivery_deferred=true 但 lifecycle=delivering"
                )

    for line in issues[: max(1, int(args.limit))]:
        print(line)
    print(f"checked={len(members)} issues={len(issues)}")
    return 1 if issues else 0


if __name__ == "__main__":
    sys.exit(main())
