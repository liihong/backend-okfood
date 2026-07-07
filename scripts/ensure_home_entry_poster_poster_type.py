"""为 home_entry_poster 补齐 poster_type 列并删除误建的 menu_page_poster 表。可重复执行。"""
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
    t = "home_entry_poster"
    with engine.begin() as conn:
        if not _table_exists(conn, t):
            print(f"跳过：表 {t} 不存在")
            return

        if not _column_exists(conn, t, "poster_type"):
            conn.execute(
                text(
                    f"""
                    ALTER TABLE `{t}`
                    ADD COLUMN `poster_type` VARCHAR(32) NOT NULL DEFAULT 'entry'
                    COMMENT '海报场景：entry=进入小程序 menu=菜单页'
                    AFTER `store_id`
                    """
                )
            )
            print("已添加 poster_type")
        else:
            print("poster_type 已存在，跳过")

        conn.execute(
            text(
                f"""
                UPDATE `{t}` SET `poster_type` = 'entry'
                WHERE `poster_type` = '' OR `poster_type` IS NULL
                """
            )
        )

        if not _index_exists(conn, t, "uk_home_entry_poster_store_type"):
            conn.execute(
                text(
                    f"""
                    ALTER TABLE `{t}`
                    ADD UNIQUE KEY `uk_home_entry_poster_store_type` (`store_id`, `poster_type`)
                    """
                )
            )
            print("已添加唯一索引 uk_home_entry_poster_store_type")
        else:
            print("唯一索引 uk_home_entry_poster_store_type 已存在，跳过")

        if _index_exists(conn, t, "uk_home_entry_poster_store"):
            conn.execute(text(f"ALTER TABLE `{t}` DROP INDEX `uk_home_entry_poster_store`"))
            print("已删除旧唯一索引 uk_home_entry_poster_store")

        if _table_exists(conn, "menu_page_poster"):
            conn.execute(text("DROP TABLE `menu_page_poster`"))
            print("已删除误建表 menu_page_poster")


if __name__ == "__main__":
    main()
