"""
创建 admin_system_notifications 表（管理端系统消息：购卡待审批、顺丰推单摘要等）。

旧库未建该表时，小程序购卡支付成功写入通知会失败，后台铃铛无消息。
可重复执行，表已存在则跳过。
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


def main() -> None:
    t = "admin_system_notifications"
    ddl = f"""
    CREATE TABLE IF NOT EXISTS `{t}` (
      `id` BIGINT NOT NULL AUTO_INCREMENT,
      `store_id` BIGINT NOT NULL,
      `kind` VARCHAR(50) NOT NULL,
      `business_date` DATE NOT NULL,
      `title` VARCHAR(200) NOT NULL,
      `message` VARCHAR(500) NOT NULL,
      `total_count` INT NOT NULL DEFAULT 0,
      `success_count` INT NOT NULL DEFAULT 0,
      `failed_count` INT NOT NULL DEFAULT 0,
      `skip_reason` VARCHAR(200) NULL DEFAULT NULL,
      `acknowledged_at` DATETIME NULL DEFAULT NULL,
      `acknowledged_by` VARCHAR(100) NULL DEFAULT NULL,
      `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
      PRIMARY KEY (`id`),
      KEY `ix_admin_system_notifications_store_id` (`store_id`),
      KEY `ix_admin_system_notifications_kind` (`kind`),
      KEY `ix_admin_system_notifications_created_at` (`created_at`),
      CONSTRAINT `fk_admin_system_notifications_store`
        FOREIGN KEY (`store_id`) REFERENCES `stores` (`id`) ON UPDATE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
      COMMENT='管理端系统消息（待审批购卡、顺丰推单摘要等）'
    """
    with engine.begin() as conn:
        if _table_exists(conn, t):
            print(f"表 {t} 已存在，跳过")
            return
        conn.execute(text(ddl))
        print(f"已创建表 {t}")


if __name__ == "__main__":
    main()
