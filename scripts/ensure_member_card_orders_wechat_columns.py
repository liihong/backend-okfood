"""
补齐 member_card_orders 的微信支付相关列与唯一索引（与 sql/migrations/20260422_member_card_orders_wechat.sql 一致）。

旧库未跑该迁移时，访问开卡工单列表会报：Unknown column 'out_trade_no'。
可重复执行，已存在则跳过。
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
    t = "member_card_orders"
    with engine.begin() as conn:
        if not _table_exists(conn, t):
            print(f"跳过：表 {t} 不存在")
            return
        if not _column_exists(conn, t, "out_trade_no"):
            conn.execute(
                text(
                    f"""
                ALTER TABLE `{t}`
                ADD COLUMN `out_trade_no` VARCHAR(32) NULL DEFAULT NULL
                COMMENT '微信 JSAPI 商户订单号（小程序自助开卡）' AFTER `applied_to_member`
                """
                )
            )
            print("已添加 out_trade_no")
        else:
            print("out_trade_no 已存在，跳过")
        if not _column_exists(conn, t, "wx_transaction_id"):
            conn.execute(
                text(
                    f"""
                ALTER TABLE `{t}`
                ADD COLUMN `wx_transaction_id` VARCHAR(32) NULL DEFAULT NULL
                COMMENT '微信支付订单号' AFTER `out_trade_no`
                """
                )
            )
            print("已添加 wx_transaction_id")
        else:
            print("wx_transaction_id 已存在，跳过")
        if not _index_exists(conn, t, "uk_member_card_orders_out_trade_no"):
            conn.execute(
                text(
                    f"""
                ALTER TABLE `{t}` ADD UNIQUE KEY `uk_member_card_orders_out_trade_no` (`out_trade_no`)
                """
                )
            )
            print("已添加唯一索引 uk_member_card_orders_out_trade_no")
        else:
            print("唯一索引已存在，跳过")
    print("完成。")


if __name__ == "__main__":
    main()
