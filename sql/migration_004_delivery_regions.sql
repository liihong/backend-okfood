-- 配送区域表 + 区域-配送员关联；members.area 改为可变字符串
-- MySQL 8.0+，在业务低峰执行；执行前请备份。

SET NAMES utf8mb4;

CREATE TABLE IF NOT EXISTS `delivery_regions` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `name` VARCHAR(64) NOT NULL COMMENT '与 members.area 展示一致',
  `code` VARCHAR(32) NULL COMMENT '可选业务编码',
  `polygon_json` JSON NOT NULL COMMENT '多边形外环 GCJ-02',
  `priority` INT NOT NULL DEFAULT 0 COMMENT '重叠时越小越优先',
  `is_active` TINYINT(1) NOT NULL DEFAULT 1,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_delivery_regions_active_priority` (`is_active`, `priority`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='配送区域（可 CRUD）';

CREATE TABLE IF NOT EXISTS `delivery_region_couriers` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `region_id` BIGINT UNSIGNED NOT NULL,
  `courier_id` VARCHAR(50) NOT NULL,
  `is_primary` TINYINT(1) NOT NULL DEFAULT 0 COMMENT '该区域主责/默认配送员，每区最多一名',
  `sort_order` INT NOT NULL DEFAULT 0,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_region_courier` (`region_id`, `courier_id`),
  KEY `idx_drc_region` (`region_id`),
  KEY `idx_drc_courier` (`courier_id`),
  CONSTRAINT `fk_drc_region` FOREIGN KEY (`region_id`) REFERENCES `delivery_regions` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_drc_courier` FOREIGN KEY (`courier_id`) REFERENCES `couriers` (`courier_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='配送区域与配送员绑定';

ALTER TABLE `members` MODIFY COLUMN `area` VARCHAR(64) NOT NULL COMMENT '配送区域名，对应 delivery_regions.name 或 未分配';
