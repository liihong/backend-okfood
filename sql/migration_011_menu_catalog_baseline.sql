-- 菜品相关表一次性补齐（适用于当前库尚无 menu_dish 等表的情况）
-- 依赖：无；仅新建表与种子分类。可重复执行（CREATE IF NOT EXISTS）。
-- 执行：mysql ...你的库 < migration_011_menu_catalog_baseline.sql

SET NAMES utf8mb4;

CREATE TABLE IF NOT EXISTS `product_category` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `code` VARCHAR(32) NOT NULL COMMENT '业务编码，如 weekly',
  `name` VARCHAR(64) NOT NULL COMMENT '展示名',
  `sort_order` INT NOT NULL DEFAULT 0,
  `is_active` TINYINT(1) NOT NULL DEFAULT 1,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_product_category_code` (`code`),
  KEY `idx_product_category_active_sort` (`is_active`, `sort_order`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='商品分类';

INSERT INTO `product_category` (`code`, `name`, `sort_order`, `is_active`)
VALUES ('weekly', '每周餐品', 0, 1)
ON DUPLICATE KEY UPDATE `id` = `id`;

CREATE TABLE IF NOT EXISTS `menu_dish` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `name` VARCHAR(200) NOT NULL COMMENT '菜品名称',
  `description` VARCHAR(1000) NULL,
  `image_url` TEXT NULL,
  `is_enabled` TINYINT(1) NOT NULL DEFAULT 1 COMMENT '是否启用',
  `category_id` BIGINT UNSIGNED NULL COMMENT '所属分类（商品库）',
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_menu_dish_enabled` (`is_enabled`),
  KEY `idx_menu_dish_category` (`category_id`),
  CONSTRAINT `fk_menu_dish_category` FOREIGN KEY (`category_id`) REFERENCES `product_category` (`id`)
    ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='菜品/商品库';

CREATE TABLE IF NOT EXISTS `weekly_menu_slot` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `week_start` DATE NOT NULL COMMENT '当周周一',
  `slot` TINYINT NOT NULL COMMENT '1=周一 … 7=周日',
  `dish_id` BIGINT UNSIGNED NOT NULL,
  `service_date` DATE AS (DATE_ADD(`week_start`, INTERVAL (`slot` - 1) DAY)) STORED,
  `service_ym` CHAR(7) AS (DATE_FORMAT(`service_date`, '%Y-%m')) STORED,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_weekly_slot_week_day` (`week_start`, `slot`),
  UNIQUE KEY `uk_weekly_dish_month` (`dish_id`, `service_ym`),
  KEY `idx_weekly_menu_week` (`week_start`),
  KEY `idx_weekly_menu_dish` (`dish_id`),
  CONSTRAINT `fk_weekly_menu_dish` FOREIGN KEY (`dish_id`) REFERENCES `menu_dish` (`id`)
    ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT `chk_weekly_slot_range` CHECK (`slot` BETWEEN 1 AND 7)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='每周餐品槽位';

CREATE TABLE IF NOT EXISTS `menu_schedule` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `menu_date` DATE NOT NULL COMMENT '配送/供餐业务日',
  `dish_id` BIGINT UNSIGNED NOT NULL,
  `schedule_ym` CHAR(7) AS (DATE_FORMAT(`menu_date`, '%Y-%m')) STORED COMMENT '自然月，用于同月菜品去重',
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_menu_schedule_date` (`menu_date`),
  UNIQUE KEY `uk_schedule_dish_month` (`dish_id`, `schedule_ym`),
  KEY `idx_menu_schedule_dish` (`dish_id`),
  CONSTRAINT `fk_menu_schedule_dish` FOREIGN KEY (`dish_id`) REFERENCES `menu_dish` (`id`)
    ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='每日排期';
