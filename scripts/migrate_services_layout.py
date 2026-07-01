#!/usr/bin/env python3
"""一次性迁移 app/services 目录结构：admin / client / delivery / member / order / shared。"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVICES = ROOT / "app" / "services"

# 顶层 service 文件 -> 目标子目录（meal_period / dinner / douyin / marketing / sf_open 保持不动）
FILE_MOVES: dict[str, str] = {
    # admin — 管理后台专用
    "admin_service.py": "admin",
    "admin_delivery_fulfillment_service.py": "admin",
    "admin_system_notification_service.py": "admin",
    "catalog_admin_service.py": "admin",
    "courier_admin_service.py": "admin",
    "day_stock_service.py": "admin",
    "delivery_region_map_overview_service.py": "admin",
    "finance_received_service.py": "admin",
    "member_delivery_deduction_service.py": "admin",
    "member_meal_compensation_service.py": "admin",
    "member_membership_refund_service.py": "admin",
    "menu_day_stock_service.py": "admin",
    "pickup_verification_service.py": "admin",
    "sf_same_city_monitor_xlsx.py": "admin",
    "store_kitchen_plan_service.py": "admin",
    "store_retail_order_admin_service.py": "admin",
    # client — 小程序 / 用户端专用
    "delivery_region_consult_service.py": "client",
    "home_banner_service.py": "client",
    "home_entry_poster_service.py": "client",
    "member_card_pay_service.py": "client",
    "single_meal_balance_pay_service.py": "client",
    "store_retail_order_service.py": "client",
    # delivery — 配送域（admin + 内部 + 骑手）
    "courier_service.py": "delivery",
    "courier_store_scope.py": "delivery",
    "courier_task_sorting.py": "delivery",
    "delivery_day_lock_service.py": "delivery",
    "delivery_sheet_meal_units_service.py": "delivery",
    "delivery_sheet_push_snapshot_service.py": "delivery",
    "delivery_sheet_service.py": "delivery",
    "delivery_sheet_units_backfill_service.py": "delivery",
    "sf_callback_service.py": "delivery",
    "sf_order_fulfillment_service.py": "delivery",
    "sf_same_city_service.py": "delivery",
    "sf_open_notify_payload.py": "delivery",
    # member — 会员域（admin + client 共用）
    "leave.py": "member",
    "member_address_service.py": "member",
    "member_card_order_service.py": "member",
    "member_daily_meal_units_service.py": "member",
    "member_operation_log_service.py": "member",
    "member_renew_subscribe_service.py": "member",
    "member_service.py": "member",
    # order — 订单域
    "single_meal_order_service.py": "order",
    # shared — 基础设施 / 跨域共用
    "amap.py": "shared",
    "delivery_region_service.py": "shared",
    "geo.py": "shared",
    "oss_upload_service.py": "shared",
    "platform_tenant_service.py": "shared",
    "region_assignment.py": "shared",
    "region_geo.py": "shared",
    "store_config_service.py": "shared",
    "tenant_integration_service.py": "shared",
    "upload_service.py": "shared",
    "wechat_pay_notify_dispatch.py": "shared",
}


def _build_import_replacements() -> list[tuple[str, str]]:
    """旧 import 路径 -> 新 import 路径（按路径长度降序，避免前缀误替换）。"""
    pairs: list[tuple[str, str]] = []
    for filename, subdir in FILE_MOVES.items():
        mod = filename.removesuffix(".py")
        pairs.append((f"app.services.{mod}", f"app.services.{subdir}.{mod}"))
    pairs.sort(key=lambda x: len(x[0]), reverse=True)
    return pairs


IMPORT_REPLACEMENTS = _build_import_replacements()


def _ensure_pkg_init(subdir: str) -> None:
    pkg = SERVICES / subdir
    pkg.mkdir(parents=True, exist_ok=True)
    init = pkg / "__init__.py"
    if not init.exists():
        init.write_text(f'"""app.services.{subdir} 模块包。"""\n', encoding="utf-8")


def move_files() -> None:
    for subdir in set(FILE_MOVES.values()):
        _ensure_pkg_init(subdir)
    for filename, subdir in FILE_MOVES.items():
        src = SERVICES / filename
        dst = SERVICES / subdir / filename
        if not src.exists():
            if dst.exists():
                print(f"skip (already moved): {filename}")
                continue
            print(f"WARN missing: {src}", file=sys.stderr)
            continue
        if dst.exists():
            print(f"WARN dst exists: {dst}", file=sys.stderr)
            continue
        try:
            subprocess.run(["git", "mv", str(src), str(dst)], cwd=ROOT, check=True)
        except subprocess.CalledProcessError:
            shutil.move(str(src), str(dst))
        print(f"moved: {filename} -> {subdir}/")


def _replace_imports_in_text(text: str) -> str:
    # from app.services import amap -> from app.services.shared import amap
    text = re.sub(
        r"\bfrom app\.services import amap\b",
        "from app.services.shared import amap",
        text,
    )
    for old, new in IMPORT_REPLACEMENTS:
        text = text.replace(old, new)
    return text


def update_imports_in_tree(base: Path) -> int:
    count = 0
    for path in base.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix != ".py":
            continue
        if path.name == "migrate_services_layout.py":
            continue
        original = path.read_text(encoding="utf-8")
        updated = _replace_imports_in_text(original)
        if updated != original:
            path.write_text(updated, encoding="utf-8")
            count += 1
            print(f"updated imports: {path.relative_to(ROOT)}")
    return count


def write_root_init() -> None:
    init = SERVICES / "__init__.py"
    init.write_text(
        '''"""业务服务层 — 按端与域划分。

目录结构
--------
admin/      管理后台专用（dashboard、库存、财务、补偿等）
client/     小程序 / 用户端专用（首页、支付、零售单等）
delivery/   配送域（配送单、顺丰、骑手任务）
member/     会员域（资料、地址、请假、续费，admin + client 共用）
order/      订单域（单餐订单等）
shared/     基础设施（地图、门店配置、上传、租户集成）
meal_period/  餐段业务规则（午/晚分离）
dinner/       晚餐配送专项
douyin/       抖音对接
marketing/    营销 / 优惠券
sf_open/      顺丰开放平台 SDK
"""
''',
        encoding="utf-8",
    )


def main() -> None:
    move_files()
    write_root_init()
    n = update_imports_in_tree(ROOT)
    print(f"\nDone. Updated {n} files.")


if __name__ == "__main__":
    main()
