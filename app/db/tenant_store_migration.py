"""
启动时执行：一租户多门店 DDL + 数据回填（MySQL / MariaDB）。

SQLite 方言下跳过（开发机若以 SQLite 跑 ORM 将无法得到完整约束，请以 MySQL 为准）。
"""

from __future__ import annotations

import logging

from sqlalchemy import inspect, text

from app.db.session import engine

logger = logging.getLogger(__name__)


def _mysql_index_exists(conn, table: str, name: str) -> bool:
    r = conn.execute(
        text(
            "SELECT 1 FROM information_schema.statistics "
            "WHERE table_schema = DATABASE() AND table_name = :t AND index_name = :n LIMIT 1"
        ),
        {"t": table, "n": name},
    )
    return r.scalar() is not None


def _mysql_column_exists(conn, table: str, col: str) -> bool:
    r = conn.execute(
        text(
            "SELECT 1 FROM information_schema.COLUMNS "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :t AND COLUMN_NAME = :c LIMIT 1"
        ),
        {"t": table, "c": col},
    )
    return r.scalar() is not None


def _add_column_mysql(conn, table: str, ddl: str) -> None:
    """若列已存在则跳过（通过 SHOW COLUMNS 前已在外层判断）。"""
    conn.execute(text(f"ALTER TABLE `{table}` {ddl}"))


def apply_tenant_store_multitenancy() -> None:
    dname = engine.dialect.name
    if dname not in ("mysql", "mariadb"):
        logger.info(
            "补库: 跳过租户/门店迁移（当前方言 %s）；生产请使用 MySQL 并执行 sql/migrations/20260516_tenant_store_multitenancy.sql",
            dname,
        )
        return

    try:
        insp = inspect(engine)
    except Exception as e:
        logger.warning("补库: inspect 失败: %s", e)
        return

    # 已全部迁移：归档表已带 store_id 主键列（最后一步）
    try:
        if insp.has_table("admin_dashboard_biz_day_snapshots"):
            dash_cols = {c["name"].lower() for c in insp.get_columns("admin_dashboard_biz_day_snapshots")}
            if "store_id" in dash_cols:
                logger.info("补库: 租户门店迁移已存在，跳过")
                return
    except Exception as e:
        logger.warning("补库: 检查归档表列失败: %s", e)
        return

    try:
        with engine.begin() as conn:
            # 1) tenants / stores
            conn.execute(
                text(
                    """
CREATE TABLE IF NOT EXISTS `tenants` (
  `id` INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `name` VARCHAR(128) NOT NULL COMMENT '租户名称',
  `is_active` TINYINT(1) NOT NULL DEFAULT 1,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='租户'
                    """.strip()
                )
            )
            conn.execute(
                text(
                    """
CREATE TABLE IF NOT EXISTS `stores` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `tenant_id` INT UNSIGNED NOT NULL,
  `name` VARCHAR(128) NOT NULL COMMENT '门店名称',
  `store_logo_url` VARCHAR(512) NULL DEFAULT NULL,
  `store_lng` DECIMAL(11,8) NULL DEFAULT NULL,
  `store_lat` DECIMAL(11,8) NULL DEFAULT NULL,
  `leave_deadline_time` TIME NOT NULL DEFAULT '21:00:00',
  `courier_delivery_base_yuan` DECIMAL(12,2) NOT NULL DEFAULT 4.00,
  `courier_delivery_extra_per_unit_yuan` DECIMAL(12,2) NOT NULL DEFAULT 1.00,
  `member_card_week_price_yuan` DECIMAL(12,2) NOT NULL DEFAULT 168.00,
  `member_card_month_price_yuan` DECIMAL(12,2) NOT NULL DEFAULT 669.00,
  `member_card_week_list_price_yuan` DECIMAL(12,2) NULL DEFAULT NULL,
  `member_card_month_list_price_yuan` DECIMAL(12,2) NULL DEFAULT NULL,
  `is_active` TINYINT(1) NOT NULL DEFAULT 1,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_stores_tenant` (`tenant_id`),
  CONSTRAINT `fk_stores_tenant` FOREIGN KEY (`tenant_id`) REFERENCES `tenants` (`id`) ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='门店'
                    """.strip()
                )
            )

            conn.execute(text("INSERT INTO `tenants` (`id`, `name`) VALUES (1, '默认租户') ON DUPLICATE KEY UPDATE `name`=`name`"))

            # 门店 1：优先从 app_settings 拷贝展示名与配置
            conn.execute(
                text(
                    """
INSERT INTO `stores` (
  `id`, `tenant_id`, `name`, `store_logo_url`, `store_lng`, `store_lat`,
  `leave_deadline_time`, `courier_delivery_base_yuan`, `courier_delivery_extra_per_unit_yuan`,
  `member_card_week_price_yuan`, `member_card_month_price_yuan`,
  `member_card_week_list_price_yuan`, `member_card_month_list_price_yuan`, `is_active`
)
SELECT
  1, 1,
  COALESCE(NULLIF(TRIM(`store_name`), ''), '默认门店'),
  `store_logo_url`, `store_lng`, `store_lat`,
  `leave_deadline_time`, `courier_delivery_base_yuan`, `courier_delivery_extra_per_unit_yuan`,
  `member_card_week_price_yuan`, `member_card_month_price_yuan`,
  NULL, NULL, 1
FROM `app_settings` WHERE `id` = 1
ON DUPLICATE KEY UPDATE `name` = VALUES(`name`)
                    """.strip()
                )
            )
            # 无 app_settings 行时保证仍有店
            conn.execute(
                text(
                    """
INSERT IGNORE INTO `stores` (`id`, `tenant_id`, `name`, `leave_deadline_time`, `is_active`)
VALUES (1, 1, '默认门店', '21:00:00', 1)
                    """.strip()
                )
            )

            # 2) members
            if insp.has_table("members"):
                if not _mysql_column_exists(conn, "members", "tenant_id"):
                    _add_column_mysql(
                        conn,
                        "members",
                        "ADD COLUMN `tenant_id` INT UNSIGNED NOT NULL DEFAULT 1 COMMENT '租户' AFTER `id`, "
                        "ADD COLUMN `store_id` BIGINT UNSIGNED NOT NULL DEFAULT 1 COMMENT '门店' AFTER `tenant_id`",
                    )
                if _mysql_index_exists(conn, "members", "uk_members_phone"):
                    conn.execute(text("ALTER TABLE `members` DROP INDEX `uk_members_phone`"))
                if _mysql_index_exists(conn, "members", "uk_members_wx_mini_openid"):
                    conn.execute(text("ALTER TABLE `members` DROP INDEX `uk_members_wx_mini_openid`"))
                if not _mysql_index_exists(conn, "members", "uk_members_store_phone"):
                    conn.execute(
                        text(
                            "ALTER TABLE `members` ADD UNIQUE KEY `uk_members_store_phone` (`store_id`, `phone`), "
                            "ADD UNIQUE KEY `uk_members_store_wx_mini_openid` (`store_id`, `wx_mini_openid`), "
                            "ADD KEY `idx_members_tenant` (`tenant_id`), "
                            "ADD CONSTRAINT `fk_members_tenant` FOREIGN KEY (`tenant_id`) REFERENCES `tenants` (`id`) ON UPDATE CASCADE, "
                            "ADD CONSTRAINT `fk_members_store` FOREIGN KEY (`store_id`) REFERENCES `stores` (`id`) ON UPDATE CASCADE"
                        )
                    )

            # 3) 目录与菜单
            if insp.has_table("product_category") and not _mysql_column_exists(conn, "product_category", "store_id"):
                _add_column_mysql(
                    conn,
                    "product_category",
                    "ADD COLUMN `store_id` BIGINT UNSIGNED NOT NULL DEFAULT 1 AFTER `id`",
                )
            if insp.has_table("product_category"):
                if _mysql_index_exists(conn, "product_category", "uk_product_category_code"):
                    conn.execute(text("ALTER TABLE `product_category` DROP INDEX `uk_product_category_code`"))
                if not _mysql_index_exists(conn, "product_category", "uk_product_category_store_code"):
                    conn.execute(
                        text(
                            "ALTER TABLE `product_category` ADD UNIQUE KEY `uk_product_category_store_code` (`store_id`, `code`), "
                            "ADD KEY `idx_product_category_store` (`store_id`), "
                            "ADD CONSTRAINT `fk_product_category_store` FOREIGN KEY (`store_id`) REFERENCES `stores` (`id`) ON UPDATE CASCADE"
                        )
                    )

            if insp.has_table("menu_dish") and not _mysql_column_exists(conn, "menu_dish", "store_id"):
                _add_column_mysql(conn, "menu_dish", "ADD COLUMN `store_id` BIGINT UNSIGNED NOT NULL DEFAULT 1 AFTER `id`")
            if insp.has_table("menu_dish") and not _mysql_index_exists(conn, "menu_dish", "idx_menu_dish_store"):
                conn.execute(
                    text(
                        "ALTER TABLE `menu_dish` ADD KEY `idx_menu_dish_store` (`store_id`), "
                        "ADD CONSTRAINT `fk_menu_dish_store` FOREIGN KEY (`store_id`) REFERENCES `stores` (`id`) ON UPDATE CASCADE"
                    )
                )

            if insp.has_table("menu_schedule") and not _mysql_column_exists(conn, "menu_schedule", "store_id"):
                _add_column_mysql(conn, "menu_schedule", "ADD COLUMN `store_id` BIGINT UNSIGNED NOT NULL DEFAULT 1 AFTER `id`")
            if insp.has_table("menu_schedule"):
                if _mysql_index_exists(conn, "menu_schedule", "uk_menu_schedule_date"):
                    conn.execute(text("ALTER TABLE `menu_schedule` DROP INDEX `uk_menu_schedule_date`"))
                if not _mysql_index_exists(conn, "menu_schedule", "uk_menu_schedule_store_date"):
                    conn.execute(
                        text(
                            "ALTER TABLE `menu_schedule` ADD UNIQUE KEY `uk_menu_schedule_store_date` (`store_id`, `menu_date`), "
                            "ADD KEY `idx_menu_schedule_store` (`store_id`), "
                            "ADD CONSTRAINT `fk_menu_schedule_store` FOREIGN KEY (`store_id`) REFERENCES `stores` (`id`) ON UPDATE CASCADE"
                        )
                    )

            if insp.has_table("weekly_menu_slot") and not _mysql_column_exists(conn, "weekly_menu_slot", "store_id"):
                _add_column_mysql(conn, "weekly_menu_slot", "ADD COLUMN `store_id` BIGINT UNSIGNED NOT NULL DEFAULT 1 AFTER `id`")
            if insp.has_table("weekly_menu_slot"):
                if _mysql_index_exists(conn, "weekly_menu_slot", "uk_weekly_slot_week_day"):
                    conn.execute(text("ALTER TABLE `weekly_menu_slot` DROP INDEX `uk_weekly_slot_week_day`"))
                if not _mysql_index_exists(conn, "weekly_menu_slot", "uk_weekly_slot_store_week_slot"):
                    conn.execute(
                        text(
                            "ALTER TABLE `weekly_menu_slot` ADD UNIQUE KEY `uk_weekly_slot_store_week_slot` (`store_id`, `week_start`, `slot`), "
                            "ADD KEY `idx_weekly_menu_store` (`store_id`), "
                            "ADD CONSTRAINT `fk_weekly_menu_slot_store` FOREIGN KEY (`store_id`) REFERENCES `stores` (`id`) ON UPDATE CASCADE"
                        )
                    )

            # 4) 骑手 / 片区 / 管理员
            if insp.has_table("couriers") and not _mysql_column_exists(conn, "couriers", "tenant_id"):
                _add_column_mysql(conn, "couriers", "ADD COLUMN `tenant_id` INT UNSIGNED NOT NULL DEFAULT 1 AFTER `courier_id`")
            if insp.has_table("couriers") and not _mysql_index_exists(conn, "couriers", "idx_couriers_tenant"):
                conn.execute(
                    text(
                        "ALTER TABLE `couriers` ADD KEY `idx_couriers_tenant` (`tenant_id`), "
                        "ADD CONSTRAINT `fk_couriers_tenant` FOREIGN KEY (`tenant_id`) REFERENCES `tenants` (`id`) ON UPDATE CASCADE"
                    )
                )

            if insp.has_table("delivery_regions") and not _mysql_column_exists(conn, "delivery_regions", "tenant_id"):
                _add_column_mysql(conn, "delivery_regions", "ADD COLUMN `tenant_id` INT UNSIGNED NOT NULL DEFAULT 1 AFTER `id`")
            if insp.has_table("delivery_regions") and not _mysql_index_exists(conn, "delivery_regions", "idx_delivery_regions_tenant"):
                conn.execute(
                    text(
                        "ALTER TABLE `delivery_regions` ADD KEY `idx_delivery_regions_tenant` (`tenant_id`), "
                        "ADD CONSTRAINT `fk_delivery_regions_tenant` FOREIGN KEY (`tenant_id`) REFERENCES `tenants` (`id`) ON UPDATE CASCADE"
                    )
                )

            if insp.has_table("admin_users") and not _mysql_column_exists(conn, "admin_users", "tenant_id"):
                _add_column_mysql(conn, "admin_users", "ADD COLUMN `tenant_id` INT UNSIGNED NOT NULL DEFAULT 1 AFTER `id`")
            if insp.has_table("admin_users") and not _mysql_index_exists(conn, "admin_users", "idx_admin_users_tenant"):
                conn.execute(
                    text(
                        "ALTER TABLE `admin_users` ADD KEY `idx_admin_users_tenant` (`tenant_id`), "
                        "ADD CONSTRAINT `fk_admin_users_tenant` FOREIGN KEY (`tenant_id`) REFERENCES `tenants` (`id`) ON UPDATE CASCADE"
                    )
                )

            # 5) 订单
            if insp.has_table("single_meal_orders") and not _mysql_column_exists(conn, "single_meal_orders", "tenant_id"):
                _add_column_mysql(
                    conn,
                    "single_meal_orders",
                    "ADD COLUMN `tenant_id` INT UNSIGNED NOT NULL DEFAULT 1 AFTER `id`, "
                    "ADD COLUMN `store_id` BIGINT UNSIGNED NOT NULL DEFAULT 1 AFTER `tenant_id`",
                )
            if insp.has_table("single_meal_orders"):
                if _mysql_index_exists(conn, "single_meal_orders", "uk_smo_out_trade_no"):
                    conn.execute(text("ALTER TABLE `single_meal_orders` DROP INDEX `uk_smo_out_trade_no`"))
                if not _mysql_index_exists(conn, "single_meal_orders", "uk_smo_store_out_trade_no"):
                    conn.execute(
                        text(
                            "ALTER TABLE `single_meal_orders` ADD UNIQUE KEY `uk_smo_store_out_trade_no` (`store_id`, `out_trade_no`), "
                            "ADD KEY `idx_smo_tenant` (`tenant_id`), "
                            "ADD KEY `idx_smo_store` (`store_id`), "
                            "ADD CONSTRAINT `fk_smo_tenant` FOREIGN KEY (`tenant_id`) REFERENCES `tenants` (`id`) ON UPDATE CASCADE, "
                            "ADD CONSTRAINT `fk_smo_store` FOREIGN KEY (`store_id`) REFERENCES `stores` (`id`) ON UPDATE CASCADE"
                        )
                    )

            if insp.has_table("member_card_orders") and not _mysql_column_exists(conn, "member_card_orders", "tenant_id"):
                _add_column_mysql(
                    conn,
                    "member_card_orders",
                    "ADD COLUMN `tenant_id` INT UNSIGNED NOT NULL DEFAULT 1 AFTER `id`, "
                    "ADD COLUMN `store_id` BIGINT UNSIGNED NOT NULL DEFAULT 1 AFTER `tenant_id`",
                )
            if insp.has_table("member_card_orders"):
                if _mysql_index_exists(conn, "member_card_orders", "uk_member_card_orders_out_trade_no"):
                    conn.execute(text("ALTER TABLE `member_card_orders` DROP INDEX `uk_member_card_orders_out_trade_no`"))
                if not _mysql_index_exists(conn, "member_card_orders", "uk_mco_store_out_trade_no"):
                    conn.execute(
                        text(
                            "ALTER TABLE `member_card_orders` ADD UNIQUE KEY `uk_mco_store_out_trade_no` (`store_id`, `out_trade_no`), "
                            "ADD KEY `idx_mco_tenant` (`tenant_id`), "
                            "ADD KEY `idx_mco_store` (`store_id`), "
                            "ADD CONSTRAINT `fk_mco_tenant` FOREIGN KEY (`tenant_id`) REFERENCES `tenants` (`id`) ON UPDATE CASCADE, "
                            "ADD CONSTRAINT `fk_mco_store` FOREIGN KEY (`store_id`) REFERENCES `stores` (`id`) ON UPDATE CASCADE"
                        )
                    )

            # 6) dashboard 快照：复合主键
            if insp.has_table("admin_dashboard_biz_day_snapshots") and not _mysql_column_exists(
                conn, "admin_dashboard_biz_day_snapshots", "store_id"
            ):
                _add_column_mysql(
                    conn,
                    "admin_dashboard_biz_day_snapshots",
                    "ADD COLUMN `store_id` BIGINT UNSIGNED NOT NULL DEFAULT 1 FIRST",
                )
                conn.execute(text("ALTER TABLE `admin_dashboard_biz_day_snapshots` DROP PRIMARY KEY"))
                conn.execute(
                    text(
                        "ALTER TABLE `admin_dashboard_biz_day_snapshots` "
                        "ADD PRIMARY KEY (`store_id`, `business_anchor_date`), "
                        "ADD CONSTRAINT `fk_admin_dash_snap_store` FOREIGN KEY (`store_id`) REFERENCES `stores` (`id`) ON UPDATE CASCADE"
                    )
                )

        logger.info("补库: 租户/门店多租户迁移已完成")
    except Exception as e:
        logger.exception("补库: 租户/门店迁移失败，请手动执行 sql/migrations/20260516_tenant_store_multitenancy.sql: %s", e)


def ensure_member_card_list_price_columns() -> None:
    """补齐 ``stores`` / ``app_settings`` 会员卡划线价列（新老库兼容）。"""
    try:
        insp = inspect(engine)
    except Exception as e:
        logger.warning("补库: inspect 失败(list_price): %s", e)
        return
    dname = engine.dialect.name
    if dname not in ("mysql", "mariadb", "sqlite"):
        logger.info("补库: 跳过会员卡划线价列（方言 %s）", dname)
        return

    try:
        with engine.begin() as conn:
            if dname in ("mysql", "mariadb"):
                if insp.has_table("stores"):
                    if not _mysql_column_exists(conn, "stores", "member_card_week_list_price_yuan"):
                        _add_column_mysql(
                            conn,
                            "stores",
                            "ADD COLUMN `member_card_week_list_price_yuan` DECIMAL(12,2) NULL DEFAULT NULL "
                            "AFTER `member_card_month_price_yuan`",
                        )
                    if not _mysql_column_exists(conn, "stores", "member_card_month_list_price_yuan"):
                        _add_column_mysql(
                            conn,
                            "stores",
                            "ADD COLUMN `member_card_month_list_price_yuan` DECIMAL(12,2) NULL DEFAULT NULL "
                            "AFTER `member_card_week_list_price_yuan`",
                        )
                if insp.has_table("app_settings"):
                    if not _mysql_column_exists(conn, "app_settings", "member_card_week_list_price_yuan"):
                        _add_column_mysql(
                            conn,
                            "app_settings",
                            "ADD COLUMN `member_card_week_list_price_yuan` DECIMAL(12,2) NULL DEFAULT NULL "
                            "AFTER `member_card_month_price_yuan`",
                        )
                    if not _mysql_column_exists(conn, "app_settings", "member_card_month_list_price_yuan"):
                        _add_column_mysql(
                            conn,
                            "app_settings",
                            "ADD COLUMN `member_card_month_list_price_yuan` DECIMAL(12,2) NULL DEFAULT NULL "
                            "AFTER `member_card_week_list_price_yuan`",
                        )
            elif dname == "sqlite":
                stmts = [
                    "ALTER TABLE stores ADD COLUMN member_card_week_list_price_yuan DECIMAL(12,2)",
                    "ALTER TABLE stores ADD COLUMN member_card_month_list_price_yuan DECIMAL(12,2)",
                    "ALTER TABLE app_settings ADD COLUMN member_card_week_list_price_yuan DECIMAL(12,2)",
                    "ALTER TABLE app_settings ADD COLUMN member_card_month_list_price_yuan DECIMAL(12,2)",
                ]
                for sql in stmts:
                    try:
                        conn.execute(text(sql))
                    except Exception:
                        pass

        logger.info("补库: 会员卡划线价列检查已完成")
    except Exception as e:
        logger.warning("补库: 会员卡划线价列补齐失败（可稍后手动 ALTER）: %s", e)
