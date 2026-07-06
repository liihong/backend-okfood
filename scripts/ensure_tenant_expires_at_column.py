"""
为 tenants 表补齐 expires_at 列（按年订阅到期日）。

旧库未跑 migration_050 时，平台租户接口读写会失败。
可重复执行，列已存在则跳过。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text

from app.db.session import engine


def _table_exists(conn, table: str) -> bool:
    r = conn.execute(
        text(
            """
            SELECT COUNT(*) FROM information_schema.TABLES
            WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :t
            """
        ),
        {"t": table},
    )
    return int(r.scalar() or 0) > 0


def _column_exists(conn, table: str, column: str) -> bool:
    r = conn.execute(
        text(
            """
            SELECT COUNT(*) FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :t AND COLUMN_NAME = :c
            """
        ),
        {"t": table, "c": column},
    )
    return int(r.scalar() or 0) > 0


def _index_exists(conn, table: str, name: str) -> bool:
    r = conn.execute(
        text(
            """
            SELECT COUNT(*) FROM information_schema.STATISTICS
            WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :t AND INDEX_NAME = :n
            """
        ),
        {"t": table, "n": name},
    )
    return int(r.scalar() or 0) > 0


def main() -> None:
    t = "tenants"
    with engine.begin() as conn:
        if not _table_exists(conn, t):
            print(f"跳过：表 {t} 不存在")
            return
        if not _column_exists(conn, t, "expires_at"):
            conn.execute(
                text(
                    f"""
                ALTER TABLE `{t}`
                ADD COLUMN `expires_at` DATE NULL DEFAULT NULL
                COMMENT '按年订阅到期日（含当日仍有效）' AFTER `is_active`
                """
                )
            )
            print("已添加 expires_at")
        else:
            print("expires_at 已存在，跳过")
        if not _index_exists(conn, t, "ix_tenants_expires_at"):
            conn.execute(
                text(f"ALTER TABLE `{t}` ADD KEY `ix_tenants_expires_at` (`expires_at`)")
            )
            print("已添加索引 ix_tenants_expires_at")
        else:
            print("索引 ix_tenants_expires_at 已存在，跳过")


if __name__ == "__main__":
    main()
