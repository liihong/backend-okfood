-- 会员卡模版 & 门店零售商品
-- 「种类」为 kind_label 手填；period_kind 可空占位（weekly/monthly）。

CREATE TABLE IF NOT EXISTS `membership_card_templates` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `tenant_id` INT UNSIGNED NOT NULL,
  `store_id` BIGINT UNSIGNED NOT NULL,
  `period_kind` VARCHAR(16) NULL DEFAULT NULL COMMENT '可选 weekly|monthly',
  `kind_label` VARCHAR(64) NOT NULL COMMENT '种类手填：周卡/季卡/午晚餐卡等',
  `name` VARCHAR(128) NOT NULL,
  `meals_grant` INT NOT NULL,
  `remark` TEXT NULL,
  `sort_order` INT NOT NULL DEFAULT 0,
  `is_active` TINYINT(1) NOT NULL DEFAULT 1,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_mct_store` (`store_id`),
  KEY `idx_mct_tenant` (`tenant_id`),
  CONSTRAINT `fk_mct_tenant` FOREIGN KEY (`tenant_id`) REFERENCES `tenants` (`id`) ON UPDATE CASCADE,
  CONSTRAINT `fk_mct_store` FOREIGN KEY (`store_id`) REFERENCES `stores` (`id`) ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 若已有旧表（仅有 period_kind、无 kind_label），执行：
-- ALTER TABLE `membership_card_templates` ADD COLUMN `kind_label` VARCHAR(64) NULL AFTER `period_kind`;
-- UPDATE `membership_card_templates` SET `kind_label` = CASE COALESCE(`period_kind`,'') WHEN 'weekly' THEN '周卡' WHEN 'monthly' THEN '月卡' ELSE COALESCE(NULLIF(`period_kind`,''),'会员卡') END WHERE `kind_label` IS NULL OR `kind_label` = '';
-- ALTER TABLE `membership_card_templates` MODIFY `kind_label` VARCHAR(64) NOT NULL, MODIFY `period_kind` VARCHAR(16) NULL;

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
  CONSTRAINT `fk_src_store` FOREIGN KEY (`store_id`) REFERENCES `stores` (`id`) ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `store_retail_products` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `store_id` BIGINT UNSIGNED NOT NULL,
  `category_id` BIGINT UNSIGNED NULL,
  `sku_code` VARCHAR(64) NULL,
  `title` VARCHAR(256) NOT NULL,
  `subtitle` VARCHAR(512) NULL,
  `description` TEXT NULL,
  `unit_price_yuan` DECIMAL(12,2) NOT NULL DEFAULT 0.00,
  `list_price_yuan` DECIMAL(12,2) NULL,
  `cover_image_url` VARCHAR(512) NULL,
  `sort_order` INT NOT NULL DEFAULT 0,
  `is_on_shelf` TINYINT(1) NOT NULL DEFAULT 0,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_srp_store` (`store_id`),
  KEY `idx_srp_category` (`category_id`),
  CONSTRAINT `fk_srp_store` FOREIGN KEY (`store_id`) REFERENCES `stores` (`id`) ON UPDATE CASCADE,
  CONSTRAINT `fk_srp_cat` FOREIGN KEY (`category_id`) REFERENCES `store_retail_categories` (`id`) ON UPDATE CASCADE ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
