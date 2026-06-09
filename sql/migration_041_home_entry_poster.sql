-- 小程序进入首页弹窗海报（每门店一条）
-- migration_041_home_entry_poster.sql

CREATE TABLE IF NOT EXISTS `home_entry_poster` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `store_id` BIGINT UNSIGNED NOT NULL,
  `image_url` TEXT NOT NULL COMMENT '海报图片 URL',
  `is_active` TINYINT(1) NOT NULL DEFAULT 0 COMMENT '是否启用',
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_home_entry_poster_store` (`store_id`),
  CONSTRAINT `fk_home_entry_poster_store` FOREIGN KEY (`store_id`) REFERENCES `stores` (`id`) ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='小程序进入弹窗海报';
