-- 礼品券（跟餐履约，非代金券）：活动 + 会员资格账本
-- 与 members.remarks、营销优惠券 member_coupons 均无关联

CREATE TABLE IF NOT EXISTS `gift_coupon_campaigns` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `tenant_id` INT NOT NULL,
  `store_id` BIGINT UNSIGNED NOT NULL,
  `name` VARCHAR(128) NOT NULL COMMENT '内部名称，如 2026年8月开卡礼品券',
  `sheet_label` VARCHAR(64) NOT NULL COMMENT '厨房标签上的礼品名',
  `status` VARCHAR(16) NOT NULL DEFAULT 'draft' COMMENT 'draft/active/closed',
  `plan_kinds` JSON NOT NULL COMMENT '["month"] / ["quarter"] / 两者；看工单模版种类，不用 plan_type',
  `credited_from` DATE NOT NULL COMMENT '入账日闭区间起（上海）',
  `credited_to` DATE NOT NULL COMMENT '入账日闭区间止（上海）',
  `exclude_membership_refunded` TINYINT(1) NOT NULL DEFAULT 1,
  `match_mode` VARCHAR(32) NOT NULL DEFAULT 'any_in_range' COMMENT '区间内任意一次入账即入围',
  `created_by` VARCHAR(64) NOT NULL,
  `granted_at` DATETIME NULL DEFAULT NULL,
  `closed_at` DATETIME NULL DEFAULT NULL,
  `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_gcc_store_status` (`store_id`, `status`),
  CONSTRAINT `fk_gcc_tenant` FOREIGN KEY (`tenant_id`) REFERENCES `tenants` (`id`) ON UPDATE CASCADE,
  CONSTRAINT `fk_gcc_store` FOREIGN KEY (`store_id`) REFERENCES `stores` (`id`) ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='礼品券活动';

CREATE TABLE IF NOT EXISTS `gift_coupon_entitlements` (
  `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `campaign_id` BIGINT UNSIGNED NOT NULL,
  `member_id` BIGINT UNSIGNED NOT NULL,
  `tenant_id` INT NOT NULL,
  `store_id` BIGINT UNSIGNED NOT NULL,
  `status` VARCHAR(16) NOT NULL DEFAULT 'granted' COMMENT 'granted/redeemed/revoked',
  `grant_source` VARCHAR(16) NOT NULL DEFAULT 'rule' COMMENT 'rule=圈人规则 / manual=手工',
  `granted_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `granted_by` VARCHAR(64) NOT NULL,
  `redeemed_at` DATETIME NULL DEFAULT NULL,
  `redeemed_delivery_date` DATE NULL DEFAULT NULL,
  `redeemed_by` VARCHAR(64) NULL DEFAULT NULL,
  `redeemed_sheet_view` VARCHAR(32) NULL DEFAULT NULL,
  `revoked_at` DATETIME NULL DEFAULT NULL,
  `revoked_by` VARCHAR(64) NULL DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_gce_campaign_member` (`campaign_id`, `member_id`),
  KEY `idx_gce_store_status` (`store_id`, `status`),
  KEY `idx_gce_member` (`member_id`),
  KEY `idx_gce_redeemed_date` (`store_id`, `redeemed_delivery_date`),
  CONSTRAINT `fk_gce_campaign` FOREIGN KEY (`campaign_id`) REFERENCES `gift_coupon_campaigns` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_gce_member` FOREIGN KEY (`member_id`) REFERENCES `members` (`id`) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT `fk_gce_tenant` FOREIGN KEY (`tenant_id`) REFERENCES `tenants` (`id`) ON UPDATE CASCADE,
  CONSTRAINT `fk_gce_store` FOREIGN KEY (`store_id`) REFERENCES `stores` (`id`) ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='礼品券会员资格';
