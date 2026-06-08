-- 小程序首页 Banner 广告位
-- migration_040_home_banners.sql

CREATE TABLE IF NOT EXISTS `home_banner` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `store_id` BIGINT UNSIGNED NOT NULL,
  `title` VARCHAR(128) NULL DEFAULT NULL COMMENT '管理端备注，小程序不展示',
  `image_url` TEXT NOT NULL COMMENT 'Banner 图片 URL',
  `link_type` VARCHAR(32) NOT NULL DEFAULT 'none' COMMENT 'none/dish/tab/webview/member_card',
  `link_target` VARCHAR(512) NULL DEFAULT NULL COMMENT 'dish_id / tab pagePath / 外链 URL / 卡包模版 id',
  `sort_order` INT NOT NULL DEFAULT 0,
  `is_active` TINYINT(1) NOT NULL DEFAULT 1,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_home_banner_store_active_sort` (`store_id`, `is_active`, `sort_order`),
  CONSTRAINT `fk_home_banner_store` FOREIGN KEY (`store_id`) REFERENCES `stores` (`id`) ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='小程序首页 Banner';
