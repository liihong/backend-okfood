"""包装耗材建表。只建新表，不改已有业务表。"""

from __future__ import annotations

import logging

from sqlalchemy import Engine, inspect, text

logger = logging.getLogger(__name__)

# 与 sql/migration_packaging.sql 保持同一套表。SQLite 用于本地测试，不建外键以免启动顺序绑死旧表。
_MYSQL_STATEMENTS: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS `packaging_sku` (
      `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
      `store_id` BIGINT UNSIGNED NOT NULL,
      `name` VARCHAR(64) NOT NULL,
      `usage_note` VARCHAR(64) NULL,
      `supplier_name` VARCHAR(64) NULL,
      `unit` VARCHAR(16) NOT NULL DEFAULT '个',
      `safety_stock` INT NULL,
      `bag_flag` INT NULL,
      `is_active` TINYINT(1) NOT NULL DEFAULT 1,
      `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
      `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
      PRIMARY KEY (`id`),
      UNIQUE KEY `uk_packaging_sku_store_name` (`store_id`, `name`),
      UNIQUE KEY `uk_packaging_sku_store_bag` (`store_id`, `bag_flag`),
      KEY `idx_packaging_sku_store` (`store_id`),
      CONSTRAINT `fk_packaging_sku_store` FOREIGN KEY (`store_id`) REFERENCES `stores` (`id`) ON UPDATE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS `packaging_stock` (
      `sku_id` BIGINT UNSIGNED NOT NULL,
      `store_id` BIGINT UNSIGNED NOT NULL,
      `qty` INT NOT NULL DEFAULT 0,
      `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
      PRIMARY KEY (`sku_id`),
      KEY `idx_packaging_stock_store` (`store_id`),
      CONSTRAINT `fk_packaging_stock_sku` FOREIGN KEY (`sku_id`) REFERENCES `packaging_sku` (`id`) ON UPDATE CASCADE ON DELETE CASCADE,
      CONSTRAINT `fk_packaging_stock_store` FOREIGN KEY (`store_id`) REFERENCES `stores` (`id`) ON UPDATE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS `packaging_stock_txn` (
      `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
      `store_id` BIGINT UNSIGNED NOT NULL,
      `sku_id` BIGINT UNSIGNED NOT NULL,
      `txn_type` VARCHAR(32) NOT NULL,
      `qty_delta` INT NOT NULL,
      `qty_after` INT NOT NULL,
      `biz_date` DATE NOT NULL,
      `meal_period` VARCHAR(16) NULL,
      `operator` VARCHAR(100) NOT NULL DEFAULT '',
      `remark` VARCHAR(200) NULL,
      `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
      PRIMARY KEY (`id`),
      KEY `idx_packaging_txn_store_date` (`store_id`, `biz_date`),
      KEY `idx_packaging_txn_sku` (`sku_id`),
      CONSTRAINT `fk_packaging_txn_store` FOREIGN KEY (`store_id`) REFERENCES `stores` (`id`) ON UPDATE CASCADE,
      CONSTRAINT `fk_packaging_txn_sku` FOREIGN KEY (`sku_id`) REFERENCES `packaging_sku` (`id`) ON UPDATE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS `packaging_dish_line` (
      `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
      `store_id` BIGINT UNSIGNED NOT NULL,
      `dish_id` BIGINT UNSIGNED NOT NULL,
      `sku_id` BIGINT UNSIGNED NOT NULL,
      `qty_per_portion` INT NOT NULL,
      `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
      `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
      PRIMARY KEY (`id`),
      UNIQUE KEY `uk_packaging_dish_line` (`dish_id`, `sku_id`),
      KEY `idx_packaging_dish_line_store` (`store_id`),
      CONSTRAINT `fk_packaging_dish_line_store` FOREIGN KEY (`store_id`) REFERENCES `stores` (`id`) ON UPDATE CASCADE,
      CONSTRAINT `fk_packaging_dish_line_dish` FOREIGN KEY (`dish_id`) REFERENCES `menu_dish` (`id`) ON UPDATE CASCADE ON DELETE CASCADE,
      CONSTRAINT `fk_packaging_dish_line_sku` FOREIGN KEY (`sku_id`) REFERENCES `packaging_sku` (`id`) ON UPDATE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS `packaging_slot_line` (
      `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
      `store_id` BIGINT UNSIGNED NOT NULL,
      `slot_id` BIGINT UNSIGNED NOT NULL,
      `sku_id` BIGINT UNSIGNED NOT NULL,
      `qty_per_portion` INT NOT NULL,
      `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
      `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
      PRIMARY KEY (`id`),
      UNIQUE KEY `uk_packaging_slot_line` (`slot_id`, `sku_id`),
      KEY `idx_packaging_slot_line_store` (`store_id`),
      CONSTRAINT `fk_packaging_slot_line_store` FOREIGN KEY (`store_id`) REFERENCES `stores` (`id`) ON UPDATE CASCADE,
      CONSTRAINT `fk_packaging_slot_line_slot` FOREIGN KEY (`slot_id`) REFERENCES `weekly_menu_slot` (`id`) ON UPDATE CASCADE ON DELETE CASCADE,
      CONSTRAINT `fk_packaging_slot_line_sku` FOREIGN KEY (`sku_id`) REFERENCES `packaging_sku` (`id`) ON UPDATE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS `packaging_standard_line` (
      `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
      `store_id` BIGINT UNSIGNED NOT NULL,
      `sku_id` BIGINT UNSIGNED NOT NULL,
      `qty_per_portion` INT NOT NULL,
      `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
      `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
      PRIMARY KEY (`id`),
      UNIQUE KEY `uk_packaging_standard_store_sku` (`store_id`, `sku_id`),
      CONSTRAINT `fk_packaging_standard_store` FOREIGN KEY (`store_id`) REFERENCES `stores` (`id`) ON UPDATE CASCADE,
      CONSTRAINT `fk_packaging_standard_sku` FOREIGN KEY (`sku_id`) REFERENCES `packaging_sku` (`id`) ON UPDATE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    """
    CREATE TABLE IF NOT EXISTS `packaging_consume_run` (
      `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
      `store_id` BIGINT UNSIGNED NOT NULL,
      `biz_date` DATE NOT NULL,
      `meal_period` VARCHAR(16) NOT NULL,
      `portions` INT NOT NULL DEFAULT 0,
      `portion_source` VARCHAR(16) NOT NULL,
      `note` VARCHAR(500) NULL,
      `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
      PRIMARY KEY (`id`),
      UNIQUE KEY `uk_packaging_consume_run` (`store_id`, `biz_date`, `meal_period`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
)


def ensure_packaging_schema(engine: Engine) -> None:
    """表已存在则跳过。失败由启动流程捕获，不影响原有接口。"""
    dialect = engine.dialect.name
    if dialect == "sqlite":
        _ensure_sqlite(engine)
        return
    insp = inspect(engine)
    existing = set(insp.get_table_names())
    with engine.begin() as conn:
        for statement in _MYSQL_STATEMENTS:
            table_name = _table_name(statement)
            if table_name in existing:
                continue
            conn.execute(text(statement))
            existing.add(table_name)
    logger.info("已检查包装耗材表")


def _table_name(statement: str) -> str:
    marker = "CREATE TABLE IF NOT EXISTS `"
    start = statement.find(marker)
    if start < 0:
        return ""
    start += len(marker)
    end = statement.find("`", start)
    return statement[start:end]


def _ensure_sqlite(engine: Engine) -> None:
    """测试库使用。不建外键，避免和旧表的创建顺序缠在一起。"""
    statements = (
        """
        CREATE TABLE IF NOT EXISTS packaging_sku (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          store_id BIGINT NOT NULL,
          name VARCHAR(64) NOT NULL,
          usage_note VARCHAR(64),
          supplier_name VARCHAR(64),
          unit VARCHAR(16) NOT NULL DEFAULT '个',
          safety_stock INT,
          bag_flag INT,
          is_active BOOLEAN NOT NULL DEFAULT 1,
          created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
          UNIQUE (store_id, name),
          UNIQUE (store_id, bag_flag)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS packaging_stock (
          sku_id INTEGER PRIMARY KEY,
          store_id BIGINT NOT NULL,
          qty INT NOT NULL DEFAULT 0,
          updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS packaging_stock_txn (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          store_id BIGINT NOT NULL,
          sku_id BIGINT NOT NULL,
          txn_type VARCHAR(32) NOT NULL,
          qty_delta INT NOT NULL,
          qty_after INT NOT NULL,
          biz_date DATE NOT NULL,
          meal_period VARCHAR(16),
          operator VARCHAR(100) NOT NULL DEFAULT '',
          remark VARCHAR(200),
          created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS packaging_dish_line (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          store_id BIGINT NOT NULL,
          dish_id BIGINT NOT NULL,
          sku_id BIGINT NOT NULL,
          qty_per_portion INT NOT NULL,
          created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
          UNIQUE (dish_id, sku_id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS packaging_slot_line (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          store_id BIGINT NOT NULL,
          slot_id BIGINT NOT NULL,
          sku_id BIGINT NOT NULL,
          qty_per_portion INT NOT NULL,
          created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
          UNIQUE (slot_id, sku_id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS packaging_standard_line (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          store_id BIGINT NOT NULL,
          sku_id BIGINT NOT NULL,
          qty_per_portion INT NOT NULL,
          created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
          updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
          UNIQUE (store_id, sku_id)
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS packaging_consume_run (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          store_id BIGINT NOT NULL,
          biz_date DATE NOT NULL,
          meal_period VARCHAR(16) NOT NULL,
          portions INT NOT NULL DEFAULT 0,
          portion_source VARCHAR(16) NOT NULL,
          note VARCHAR(500),
          created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
          UNIQUE (store_id, biz_date, meal_period)
        )
        """,
    )
    with engine.begin() as conn:
        for statement in statements:
            conn.execute(text(statement))
