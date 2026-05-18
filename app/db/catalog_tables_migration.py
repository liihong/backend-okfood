"""启动 DDL：会员卡模版与普通商品 SKU 表（仅 MySQL）。"""

from __future__ import annotations

import logging

from sqlalchemy import inspect, text

from app.db.session import engine

logger = logging.getLogger(__name__)


def _mysql_column_exists(conn, table: str, col: str) -> bool:
    r = conn.execute(
        text(
            "SELECT 1 FROM information_schema.COLUMNS "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :t AND COLUMN_NAME = :c LIMIT 1"
        ),
        {"t": table, "c": col},
    )
    return r.scalar() is not None


def _create_membership_table_new(conn) -> None:
    conn.execute(
        text(
            """
CREATE TABLE IF NOT EXISTS `membership_card_templates` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `tenant_id` INT UNSIGNED NOT NULL,
  `store_id` BIGINT UNSIGNED NOT NULL,
  `period_kind` VARCHAR(16) NULL DEFAULT NULL COMMENT '可选weekly|monthly，仅占位兼容',
  `kind_label` VARCHAR(64) NOT NULL COMMENT '种类：手动填写（周卡/季卡/午晚餐卡等）',
  `name` VARCHAR(128) NOT NULL,
  `meals_grant` INT NOT NULL COMMENT '单笔购买入账餐次（占位，未接线支付入账）',
  `remark` TEXT NULL DEFAULT NULL,
  `sort_order` INT NOT NULL DEFAULT 0,
  `is_active` TINYINT(1) NOT NULL DEFAULT 1,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_mct_store` (`store_id`),
  KEY `idx_mct_tenant` (`tenant_id`),
  CONSTRAINT `fk_mct_tenant` FOREIGN KEY (`tenant_id`) REFERENCES `tenants` (`id`) ON UPDATE CASCADE,
  CONSTRAINT `fk_mct_store` FOREIGN KEY (`store_id`) REFERENCES `stores` (`id`) ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='会员卡模版(后台)';
            """.strip()
        )
    )


def _upgrade_membership_templates_add_kind_label(conn) -> None:
    if not _mysql_column_exists(conn, "membership_card_templates", "kind_label"):
        conn.execute(
            text(
                """
ALTER TABLE `membership_card_templates`
  ADD COLUMN `kind_label` VARCHAR(64) NULL DEFAULT NULL AFTER `period_kind`
                """.strip()
            )
        )
        conn.execute(
            text(
                """
UPDATE `membership_card_templates` SET `kind_label` =
  CASE COALESCE(`period_kind`, '')
    WHEN 'weekly' THEN '周卡'
    WHEN 'monthly' THEN '月卡'
    ELSE COALESCE(NULLIF(`period_kind`, ''), '会员卡')
  END
WHERE `kind_label` IS NULL OR `kind_label` = ''
                """.strip()
            )
        )
        conn.execute(
            text(
                """
ALTER TABLE `membership_card_templates`
  MODIFY COLUMN `kind_label` VARCHAR(64) NOT NULL,
  MODIFY COLUMN `period_kind` VARCHAR(16) NULL DEFAULT NULL
                """.strip()
            )
        )
        logger.info("补库: membership_card_templates 已增加 kind_label 并放宽 period_kind")


def ensure_catalog_admin_tables() -> None:
    dname = engine.dialect.name
    if dname not in ("mysql", "mariadb"):
        logger.info(
            "补库: 跳过会员卡模版/零售商品表（当前方言 %s）；生产使用 MySQL 时需在库中补齐相应表结构",
            dname,
        )
        return

    try:
        insp = inspect(engine)
    except Exception as e:
        logger.warning("补库: inspect 失败: %s", e)
        return

    try:
        with engine.begin() as conn:
            has_mct = insp.has_table("membership_card_templates")
            has_cat = insp.has_table("store_retail_categories")

            if not has_mct:
                _create_membership_table_new(conn)
            elif not _mysql_column_exists(conn, "membership_card_templates", "kind_label"):
                _upgrade_membership_templates_add_kind_label(conn)

            if not has_cat:
                conn.execute(
                    text(
                        """
CREATE TABLE IF NOT EXISTS `store_retail_categories` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `store_id` BIGINT UNSIGNED NOT NULL,
  `name` VARCHAR(128) NOT NULL,
  `sort_order` INT NOT NULL DEFAULT 0,
  `is_active` TINYINT(1) NOT NULL DEFAULT 1,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_store_retail_cat_store_name` (`store_id`,`name`),
  KEY `idx_src_store` (`store_id`),
  CONSTRAINT `fk_src_store` FOREIGN KEY (`store_id`) REFERENCES `stores` (`id`) ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='门店零售商品分类';
                        """.strip()
                    )
                )
                conn.execute(
                    text(
                        """
CREATE TABLE IF NOT EXISTS `store_retail_products` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `store_id` BIGINT UNSIGNED NOT NULL,
  `category_id` BIGINT UNSIGNED NULL DEFAULT NULL,
  `sku_code` VARCHAR(64) NULL DEFAULT NULL,
  `title` VARCHAR(256) NOT NULL,
  `subtitle` VARCHAR(512) NULL DEFAULT NULL,
  `description` TEXT NULL DEFAULT NULL,
  `unit_price_yuan` DECIMAL(12,2) NOT NULL DEFAULT 0.00,
  `list_price_yuan` DECIMAL(12,2) NULL DEFAULT NULL,
  `cover_image_url` VARCHAR(512) NULL DEFAULT NULL,
  `sort_order` INT NOT NULL DEFAULT 0,
  `is_on_shelf` TINYINT(1) NOT NULL DEFAULT 0,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_srp_store` (`store_id`),
  KEY `idx_srp_category` (`category_id`),
  CONSTRAINT `fk_srp_store` FOREIGN KEY (`store_id`) REFERENCES `stores` (`id`) ON UPDATE CASCADE,
  CONSTRAINT `fk_srp_cat` FOREIGN KEY (`category_id`) REFERENCES `store_retail_categories` (`id`) ON UPDATE CASCADE ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='门店零售 SKU';
                        """.strip()
                    )
                )

        logger.info("补库: 会员卡模版/零售商品表已就绪")
    except Exception as e:
        logger.exception("补库: 会员卡/零售商品表迁移失败: %s", e)
