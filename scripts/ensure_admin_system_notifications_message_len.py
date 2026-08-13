"""
加长 admin_system_notifications.message，避免顺丰推单失败明细（姓名/手机号/原因）被截断。

可重复执行：列已是 VARCHAR(2000) 或更长则跳过。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text

from app.db.session import engine


def main() -> None:
    t = "admin_system_notifications"
    with engine.begin() as conn:
        exists = conn.execute(
            text(
                """
                SELECT COUNT(*) FROM information_schema.TABLES
                WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :t
                """
            ),
            {"t": t},
        ).scalar()
        if not int(exists or 0):
            print(f"跳过：表 {t} 不存在")
            return
        row = conn.execute(
            text(
                """
                SELECT CHARACTER_MAXIMUM_LENGTH, DATA_TYPE
                FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :t AND COLUMN_NAME = 'message'
                """
            ),
            {"t": t},
        ).mappings().first()
        if not row:
            print("跳过：无 message 列")
            return
        dtype = str(row["DATA_TYPE"] or "").lower()
        maxlen = row["CHARACTER_MAXIMUM_LENGTH"]
        if dtype in ("text", "mediumtext", "longtext"):
            print("message 已是 TEXT，跳过")
            return
        if maxlen is not None and int(maxlen) >= 2000:
            print(f"message 长度已是 {maxlen}，跳过")
            return
        conn.execute(
            text(
                f"""
                ALTER TABLE `{t}`
                MODIFY COLUMN `message` VARCHAR(2000) NOT NULL
                COMMENT '系统消息正文（含推单失败明细）'
                """
            )
        )
        print("已将 message 加长为 VARCHAR(2000)")


if __name__ == "__main__":
    main()
