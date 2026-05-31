-- 小程序营销：优惠券券种 + 用户持券；购卡/单次零售订单扩展优惠字段
-- migration_032_marketing_member_coupons.sql

CREATE TABLE IF NOT EXISTS `marketing_coupon_templates` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `tenant_id` INT NOT NULL,
  `store_id` BIGINT UNSIGNED NOT NULL,
  `name` VARCHAR(128) NOT NULL COMMENT '券名称',
  `coupon_type` VARCHAR(16) NOT NULL DEFAULT 'cash' COMMENT 'MVP: cash 代金券',
  `discount_yuan` DECIMAL(12, 2) NOT NULL COMMENT '减免金额',
  `min_order_yuan` DECIMAL(12, 2) NOT NULL DEFAULT 0.00 COMMENT '最低订单原价门槛',
  `biz_type` VARCHAR(32) NOT NULL COMMENT 'all/member_card/single_meal/store_retail',
  `scope_level` VARCHAR(32) NOT NULL DEFAULT 'all',
  `scope_target_id` BIGINT UNSIGNED NULL DEFAULT NULL,
  `validity_mode` VARCHAR(32) NOT NULL COMMENT 'fixed_range/days_after_grant',
  `valid_from` DATETIME NULL DEFAULT NULL,
  `valid_until` DATETIME NULL DEFAULT NULL,
  `valid_days_after_grant` INT NULL DEFAULT NULL,
  `usage_instructions` TEXT NULL,
  `sort_order` INT NOT NULL DEFAULT 0,
  `is_active` TINYINT(1) NOT NULL DEFAULT 1,
  `max_grants` INT NULL DEFAULT NULL COMMENT '可发放总上限，NULL 不限',
  `grants_issued` INT NOT NULL DEFAULT 0,
  `created_by` VARCHAR(64) NOT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_mct_tenant_store` (`tenant_id`, `store_id`),
  KEY `idx_mct_biz_active` (`store_id`, `biz_type`, `is_active`),
  CONSTRAINT `fk_mct_tenant` FOREIGN KEY (`tenant_id`) REFERENCES `tenants` (`id`) ON UPDATE CASCADE,
  CONSTRAINT `fk_mct_store` FOREIGN KEY (`store_id`) REFERENCES `stores` (`id`) ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='营销优惠券券种模板';

CREATE TABLE IF NOT EXISTS `member_coupons` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `template_id` BIGINT UNSIGNED NOT NULL,
  `member_id` BIGINT UNSIGNED NOT NULL,
  `tenant_id` INT NOT NULL,
  `store_id` BIGINT UNSIGNED NOT NULL,
  `discount_yuan` DECIMAL(12, 2) NOT NULL,
  `min_order_yuan` DECIMAL(12, 2) NOT NULL DEFAULT 0.00,
  `biz_type` VARCHAR(32) NOT NULL,
  `scope_level` VARCHAR(32) NOT NULL DEFAULT 'all',
  `scope_target_id` BIGINT UNSIGNED NULL DEFAULT NULL,
  `status` VARCHAR(16) NOT NULL DEFAULT 'available',
  `expires_at` DATETIME NULL DEFAULT NULL,
  `locked_order_biz` VARCHAR(32) NULL DEFAULT NULL,
  `locked_order_id` BIGINT UNSIGNED NULL DEFAULT NULL,
  `issued_by` VARCHAR(64) NOT NULL,
  `issued_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `used_at` DATETIME NULL DEFAULT NULL,
  `revoked_at` DATETIME NULL DEFAULT NULL,
  `remark` VARCHAR(500) NULL DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `idx_mc_member_status` (`member_id`, `status`),
  KEY `idx_mc_store_status` (`store_id`, `status`),
  KEY `idx_mc_locked_order` (`locked_order_biz`, `locked_order_id`),
  KEY `idx_mc_expires` (`expires_at`),
  CONSTRAINT `fk_mc_template` FOREIGN KEY (`template_id`) REFERENCES `marketing_coupon_templates` (`id`) ON UPDATE CASCADE,
  CONSTRAINT `fk_mc_member` FOREIGN KEY (`member_id`) REFERENCES `members` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_mc_tenant` FOREIGN KEY (`tenant_id`) REFERENCES `tenants` (`id`) ON UPDATE CASCADE,
  CONSTRAINT `fk_mc_store` FOREIGN KEY (`store_id`) REFERENCES `stores` (`id`) ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户持券实例';

ALTER TABLE `member_card_orders`
  ADD COLUMN `original_amount_yuan` DECIMAL(12, 2) NULL DEFAULT NULL COMMENT '购卡标价原价' AFTER `amount_yuan`,
  ADD COLUMN `coupon_discount_yuan` DECIMAL(12, 2) NULL DEFAULT NULL COMMENT '优惠券抵扣' AFTER `original_amount_yuan`,
  ADD COLUMN `member_coupon_id` BIGINT UNSIGNED NULL DEFAULT NULL COMMENT '使用的用户券' AFTER `coupon_discount_yuan`,
  ADD KEY `idx_mco_member_coupon` (`member_coupon_id`),
  ADD CONSTRAINT `fk_mco_member_coupon` FOREIGN KEY (`member_coupon_id`) REFERENCES `member_coupons` (`id`) ON DELETE SET NULL ON UPDATE CASCADE;

ALTER TABLE `single_meal_orders`
  ADD COLUMN `original_amount_yuan` DECIMAL(12, 2) NULL DEFAULT NULL COMMENT '单次零售原价' AFTER `amount_yuan`,
  ADD COLUMN `coupon_discount_yuan` DECIMAL(12, 2) NULL DEFAULT NULL COMMENT '优惠券抵扣' AFTER `original_amount_yuan`,
  ADD COLUMN `member_coupon_id` BIGINT UNSIGNED NULL DEFAULT NULL COMMENT '使用的用户券' AFTER `coupon_discount_yuan`,
  ADD KEY `idx_smo_member_coupon` (`member_coupon_id`),
  ADD CONSTRAINT `fk_smo_member_coupon` FOREIGN KEY (`member_coupon_id`) REFERENCES `member_coupons` (`id`) ON DELETE SET NULL ON UPDATE CASCADE;
