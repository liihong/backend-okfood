-- 商品分类 + 每周槽位排期（week_start=当周周一 + slot 1..7 对应周一至周日）
-- 「本周/下周」仅由查询时的 week_start 决定，日历翻周后原「下周」数据自然成为「本周」，无需定时任务拷贝。
-- service_ym + uk_weekly_dish_month：同一自然月内同一菜品仅占用一天（与 menu_schedule 口径一致）。

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
ON DUPLICATE KEY UPDATE `name` = VALUES(`name`);

ALTER TABLE `menu_dish`
  ADD COLUMN `category_id` BIGINT UNSIGNED NULL COMMENT '所属分类（商品库货架）' AFTER `is_enabled`,
  ADD KEY `idx_menu_dish_category` (`category_id`),
  ADD CONSTRAINT `fk_menu_dish_category` FOREIGN KEY (`category_id`) REFERENCES `product_category` (`id`)
    ON DELETE SET NULL ON UPDATE CASCADE;

CREATE TABLE IF NOT EXISTS `weekly_menu_slot` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `week_start` DATE NOT NULL COMMENT '当周周一（上海日历周）',
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='每周餐品槽位（预告=维护未来 week_start）';

-- 从按日排期灌入周槽位（便于过渡；若已存在同周同槽则跳过冲突行可手工处理）
INSERT IGNORE INTO `weekly_menu_slot` (`week_start`, `slot`, `dish_id`)
SELECT
  DATE_SUB(`menu_date`, INTERVAL WEEKDAY(`menu_date`) DAY) AS `week_start`,
  WEEKDAY(`menu_date`) + 1 AS `slot`,
  `dish_id`
FROM `menu_schedule`;
