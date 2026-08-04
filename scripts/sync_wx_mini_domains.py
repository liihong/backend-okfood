#!/usr/bin/env python3
"""为已代授权租户同步小程序服务器域名（modify_domain）。

用法（项目根目录）：
  python scripts/sync_wx_mini_domains.py --tenant-id 3
  python scripts/sync_wx_mini_domains.py --appid wx6131d6d74a3edc6f
  python scripts/sync_wx_mini_domains.py --tenant-id 3 --action add --verify-only
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.tenant_integration_settings import TenantIntegrationSettings
from app.services.shared.wx_open_code_service import (
    get_effective_domains_for_tenant,
    sync_server_domains_for_tenant,
)


def _resolve_tenant_id(db, *, tenant_id: int | None, appid: str | None) -> int:
    if tenant_id is not None:
        return int(tenant_id)
    aid = (appid or "").strip()
    if not aid:
        raise SystemExit("请指定 --tenant-id 或 --appid")
    row = db.execute(
        select(TenantIntegrationSettings).where(TenantIntegrationSettings.wx_mini_appid == aid)
    ).scalar_one_or_none()
    if row is None:
        raise SystemExit(f"未找到 appid={aid} 对应租户")
    return int(row.tenant_id)


def main() -> None:
    parser = argparse.ArgumentParser(description="同步小程序服务器域名到已授权账号")
    parser.add_argument("--tenant-id", type=int, default=None)
    parser.add_argument("--appid", type=str, default=None)
    parser.add_argument("--action", type=str, default="add", help="add / set / get")
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="仅调用 get_effective_domain，不执行 modify_domain",
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        tid = _resolve_tenant_id(db, tenant_id=args.tenant_id, appid=args.appid)
        if args.verify_only:
            result = get_effective_domains_for_tenant(db, tid)
            print(json.dumps({"tenant_id": tid, "effective_domain": result}, ensure_ascii=False, indent=2))
            return
        result = sync_server_domains_for_tenant(db, tid, action=args.action)
        print(json.dumps({"tenant_id": tid, **result}, ensure_ascii=False, indent=2))
    finally:
        db.close()


if __name__ == "__main__":
    main()
