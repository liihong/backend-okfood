-- 开菜单：食材出成率与菜品单份毛菜用量。不改 menu_dish / weekly_menu_slot。
-- 启动时 schema_patches.ensure_prep_menu_schema 会幂等建表。

CREATE TABLE IF NOT EXISTS `prep_ingredient` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `store_id` BIGINT UNSIGNED NOT NULL,
  `name` VARCHAR(64) NOT NULL COMMENT '食材名称，同一门店唯一',
  `unit` VARCHAR(16) NOT NULL COMMENT 'g=克；piece=个',
  `yield_rate` DECIMAL(6, 4) NOT NULL DEFAULT 1.0000 COMMENT '净菜/毛菜，大于 0 且不超过 1；按个计固定为 1',
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_prep_ingredient_store_name` (`store_id`, `name`),
  KEY `idx_prep_ingredient_store` (`store_id`),
  CONSTRAINT `fk_prep_ingredient_store` FOREIGN KEY (`store_id`) REFERENCES `stores` (`id`) ON UPDATE CASCADE,
  CONSTRAINT `chk_prep_ingredient_unit` CHECK (`unit` IN ('g', 'piece')),
  CONSTRAINT `chk_prep_ingredient_yield` CHECK (`yield_rate` > 0 AND `yield_rate` <= 1)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='开菜单食材与出成率';

CREATE TABLE IF NOT EXISTS `dish_prep_sop_line` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `store_id` BIGINT UNSIGNED NOT NULL,
  `dish_id` BIGINT UNSIGNED NOT NULL,
  `ingredient_id` BIGINT UNSIGNED NOT NULL,
  `gross_qty_per_portion` DECIMAL(12, 3) NOT NULL COMMENT '单份毛菜：克或个数',
  `sort_order` INT NOT NULL DEFAULT 0,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_dish_prep_sop_dish_ingredient` (`dish_id`, `ingredient_id`),
  KEY `idx_dish_prep_sop_store_dish` (`store_id`, `dish_id`),
  KEY `idx_dish_prep_sop_ingredient` (`ingredient_id`),
  CONSTRAINT `fk_dish_prep_sop_store` FOREIGN KEY (`store_id`) REFERENCES `stores` (`id`) ON UPDATE CASCADE,
  CONSTRAINT `fk_dish_prep_sop_dish` FOREIGN KEY (`dish_id`) REFERENCES `menu_dish` (`id`) ON UPDATE CASCADE,
  CONSTRAINT `fk_dish_prep_sop_ingredient` FOREIGN KEY (`ingredient_id`) REFERENCES `prep_ingredient` (`id`) ON UPDATE CASCADE,
  CONSTRAINT `chk_dish_prep_sop_qty` CHECK (`gross_qty_per_portion` > 0)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='菜品配菜单份毛菜';
