-- 包装耗材库存。不改菜单、会员、餐品日库存表。
-- 启动时 app.db.packaging_schema.ensure_packaging_schema 会幂等建表。

CREATE TABLE IF NOT EXISTS `packaging_sku` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `store_id` BIGINT UNSIGNED NOT NULL,
  `name` VARCHAR(64) NOT NULL,
  `usage_note` VARCHAR(64) NULL COMMENT '用途，如沙拉、料汁',
  `supplier_name` VARCHAR(64) NULL,
  `unit` VARCHAR(16) NOT NULL DEFAULT '个',
  `safety_stock` INT NULL COMMENT '最低库存；空表示不发采购提醒',
  `bag_flag` INT NULL COMMENT '1=每餐固定扣一只的打包袋；普通品为空',
  `is_active` TINYINT(1) NOT NULL DEFAULT 1,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_packaging_sku_store_name` (`store_id`, `name`),
  UNIQUE KEY `uk_packaging_sku_store_bag` (`store_id`, `bag_flag`),
  KEY `idx_packaging_sku_store` (`store_id`),
  CONSTRAINT `fk_packaging_sku_store` FOREIGN KEY (`store_id`) REFERENCES `stores` (`id`) ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='包装耗材档案';

CREATE TABLE IF NOT EXISTS `packaging_stock` (
  `sku_id` BIGINT UNSIGNED NOT NULL,
  `store_id` BIGINT UNSIGNED NOT NULL,
  `qty` INT NOT NULL DEFAULT 0,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`sku_id`),
  KEY `idx_packaging_stock_store` (`store_id`),
  CONSTRAINT `fk_packaging_stock_sku` FOREIGN KEY (`sku_id`) REFERENCES `packaging_sku` (`id`) ON UPDATE CASCADE ON DELETE CASCADE,
  CONSTRAINT `fk_packaging_stock_store` FOREIGN KEY (`store_id`) REFERENCES `stores` (`id`) ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='包装耗材结存';

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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='包装耗材流水';

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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='菜品默认用盒';

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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='本周槽位用盒';

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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='每份标配';

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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='包装扣库运行记录';
