-- 菜单重构：菜品库 menu_dish + 按日排期 menu_schedule（菜品与日期解耦）
-- 约束：每个自然日最多一道菜；同一菜品在同一自然月内最多排期一天（一个月不重样）
-- 执行前请备份。
-- 适用：从仍包含 daily_menu 的旧库升级。若已用新版 schema.sql 初始化（无 daily_menu），请勿执行本文件，避免1146。

SET NAMES utf8mb4;

CREATE TABLE IF NOT EXISTS `menu_dish` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `name` VARCHAR(200) NOT NULL COMMENT '菜品名称',
  `description` VARCHAR(1000) NULL,
  `image_url` VARCHAR(500) NULL,
  `is_enabled` TINYINT(1) NOT NULL DEFAULT 1 COMMENT '是否启用（停用后仍保留历史排期展示，新品排期建议只用启用菜品）',
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_menu_dish_enabled` (`is_enabled`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='菜品库';

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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='每日排期（指向菜品库）';

-- 自旧表迁移（若仍存在 daily_menu）
SET @__md_before := IFNULL((SELECT MAX(`id`) FROM `menu_dish`), 0);

INSERT INTO `menu_dish` (`name`, `description`, `image_url`, `is_enabled`)
SELECT `dish_name`, `description`, `image_url`, 1
FROM `daily_menu`
ORDER BY `menu_date`;

INSERT INTO `menu_schedule` (`menu_date`, `dish_id`)
SELECT odm.`menu_date`, omd.`id`
FROM (
  SELECT `menu_date`, ROW_NUMBER() OVER (ORDER BY `menu_date`) AS `rn`
  FROM `daily_menu`
) AS odm
JOIN (
  SELECT `id`, ROW_NUMBER() OVER (ORDER BY `id`) AS `rn`
  FROM `menu_dish`
  WHERE `id` > @__md_before
) AS omd ON odm.`rn` = omd.`rn`;

DROP TABLE IF EXISTS `daily_menu`;
