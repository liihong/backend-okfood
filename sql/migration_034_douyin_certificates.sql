-- 抖音团购验券：门店 POI 配置 + 商品映射 + 核销流水
-- migration_034_douyin_certificates.sql

ALTER TABLE `stores`
  ADD COLUMN `douyin_poi_id` VARCHAR(64) NULL DEFAULT NULL COMMENT '抖音来客核销门店 POI ID' AFTER `wechat_pay_ssl_key_path`,
  ADD COLUMN `douyin_account_id` VARCHAR(64) NULL DEFAULT NULL COMMENT '抖音核销商户根账户 ID（云连锁可选）' AFTER `douyin_poi_id`;

CREATE TABLE IF NOT EXISTS `douyin_product_mappings` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `tenant_id` INT NOT NULL,
  `store_id` BIGINT UNSIGNED NOT NULL,
  `display_name` VARCHAR(128) NOT NULL COMMENT '后台展示名称',
  `douyin_product_id` VARCHAR(64) NULL DEFAULT NULL COMMENT '抖音 product_id',
  `douyin_sku_id` VARCHAR(64) NULL DEFAULT NULL COMMENT '抖音 sku_id',
  `douyin_product_out_id` VARCHAR(64) NULL DEFAULT NULL COMMENT '抖音 product_out_id / third_sku_id',
  `grant_type` VARCHAR(32) NOT NULL COMMENT 'week_card/month_card/membership_template/coupon_template',
  `target_id` BIGINT UNSIGNED NULL DEFAULT NULL COMMENT '卡包模板 ID 或优惠券券种 ID',
  `is_active` TINYINT(1) NOT NULL DEFAULT 1,
  `created_by` VARCHAR(64) NOT NULL DEFAULT '',
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_dpm_store_active` (`store_id`, `is_active`),
  KEY `idx_dpm_product_id` (`store_id`, `douyin_product_id`),
  KEY `idx_dpm_sku_id` (`store_id`, `douyin_sku_id`),
  CONSTRAINT `fk_dpm_tenant` FOREIGN KEY (`tenant_id`) REFERENCES `tenants` (`id`) ON UPDATE CASCADE,
  CONSTRAINT `fk_dpm_store` FOREIGN KEY (`store_id`) REFERENCES `stores` (`id`) ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='抖音团购商品与本地权益映射';

CREATE TABLE IF NOT EXISTS `douyin_certificate_redemptions` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `tenant_id` INT NOT NULL,
  `store_id` BIGINT UNSIGNED NOT NULL,
  `member_id` BIGINT UNSIGNED NOT NULL,
  `code_masked` VARCHAR(32) NULL DEFAULT NULL COMMENT '券码脱敏展示',
  `douyin_order_id` VARCHAR(64) NULL DEFAULT NULL,
  `certificate_id` VARCHAR(64) NOT NULL COMMENT '抖音侧券唯一标识，防重复兑换',
  `douyin_product_id` VARCHAR(64) NULL DEFAULT NULL,
  `douyin_sku_id` VARCHAR(64) NULL DEFAULT NULL,
  `douyin_product_title` VARCHAR(256) NULL DEFAULT NULL,
  `mapping_id` BIGINT UNSIGNED NULL DEFAULT NULL,
  `grant_type` VARCHAR(32) NULL DEFAULT NULL,
  `grant_target_id` BIGINT UNSIGNED NULL DEFAULT NULL,
  `grant_result_kind` VARCHAR(32) NULL DEFAULT NULL COMMENT 'member_card_order/member_coupon',
  `grant_result_id` BIGINT UNSIGNED NULL DEFAULT NULL,
  `status` VARCHAR(16) NOT NULL DEFAULT 'success' COMMENT 'success/failed/grant_failed',
  `error_msg` VARCHAR(512) NULL DEFAULT NULL,
  `verify_token` VARCHAR(64) NULL DEFAULT NULL,
  `amount_yuan` DECIMAL(12, 2) NULL DEFAULT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_dcr_certificate_id` (`certificate_id`),
  KEY `idx_dcr_store_created` (`store_id`, `created_at`),
  KEY `idx_dcr_member` (`member_id`, `created_at`),
  CONSTRAINT `fk_dcr_tenant` FOREIGN KEY (`tenant_id`) REFERENCES `tenants` (`id`) ON UPDATE CASCADE,
  CONSTRAINT `fk_dcr_store` FOREIGN KEY (`store_id`) REFERENCES `stores` (`id`) ON UPDATE CASCADE,
  CONSTRAINT `fk_dcr_member` FOREIGN KEY (`member_id`) REFERENCES `members` (`id`) ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='抖音券核销兑换流水';
